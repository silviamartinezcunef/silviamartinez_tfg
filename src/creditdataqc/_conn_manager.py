import io
import sys
import importlib
import sqlalchemy as sqla
import snowflake.connector as snowconn
import snowflake.snowpark as snowpark
import paramiko
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.backends import default_backend
from pathlib import Path
from azure.identity import DefaultAzureCredential
from azure.keyvault.secrets import SecretClient
from omegaconf import OmegaConf
from sqlalchemy.pool import QueuePool
from typing import Union, TYPE_CHECKING
from functools import lru_cache

# MongoDB import opcional (solo si está instalado)
try:
    from pymongo import MongoClient
    MONGODB_AVAILABLE = True
except ImportError:
    MongoClient = None
    MONGODB_AVAILABLE = False

from creditdataqc._log import get_logger

if TYPE_CHECKING:
    Connection = Union[
        sqla.engine.Connection,
        snowconn.SnowflakeConnection,
        snowpark.Session,
        paramiko.SFTPClient,
        MongoClient,
        "Pyadomd",
    ]
else:
    Connection = Union[
        sqla.engine.Connection,
        snowconn.SnowflakeConnection,
        snowpark.Session,
        paramiko.SFTPClient,
        "Pyadomd",
    ]

logger = get_logger(__name__)

KEYVAULT_URL = {
    "prod": "https://kv-quant-risk-0-prod.vault.azure.net/",
    "test": "https://kv-quant-risk-0-test.vault.azure.net/",
    "dev": "https://kv-quant-risk-0-dev.vault.azure.net/"
}

# Global connection cache
CONNECTION_CACHE = {}

# Get Azure Credential
# Sequentially attempts multiple authentication methods in this order:
# - Environment variables (EnvironmentCredential),
# - Managed Identity (for Azure VMs, App Services, etc.),
# - Shared Token Cache (for tools like Visual Studio),
# - Azure CLI (AzureCliCredential),
# - Interactive browser login (if enabled)
CREDENTIAL = DefaultAzureCredential(
    exclude_interactive_browser_credential=False,
    additionally_allowed_tenants=["8619c67c-945a-48ae-8e77-35b1b71c9b98"],
    # allow Key Vault’s tenants explicitly for interactive browser login
)

# Common local install folders for ADOMD.NET (the last segment is the provider
# version: 110 → SQL 2012, 120 → SQL 2014, … 160 → latest)
_DEFAULT_ADOMD_DIRS = [
    # 64-bit installs
    r"C:\Program Files\Microsoft.NET\ADOMD.NET\160",
    r"C:\Program Files\Microsoft.NET\ADOMD.NET\150",
    r"C:\Program Files\Microsoft.NET\ADOMD.NET\140",
    r"C:\Program Files\Microsoft.NET\ADOMD.NET\130",
    r"C:\Program Files\Microsoft.NET\ADOMD.NET\120",
    r"C:\Program Files\Microsoft.NET\ADOMD.NET\110",

    # 32-bit installs (Program Files (x86))
    r"C:\Program Files (x86)\Microsoft.NET\ADOMD.NET\160",
    r"C:\Program Files (x86)\Microsoft.NET\ADOMD.NET\150",
    r"C:\Program Files (x86)\Microsoft.NET\ADOMD.NET\140",
    r"C:\Program Files (x86)\Microsoft.NET\ADOMD.NET\130",
    r"C:\Program Files (x86)\Microsoft.NET\ADOMD.NET\120",
    r"C:\Program Files (x86)\Microsoft.NET\ADOMD.NET\110",
]

def _is_closed(conn: Connection) -> bool:
    """
    Check whether a given connection is closed.
    """
    # --- SQLAlchemy Connection ---
    if isinstance(conn, sqla.engine.Connection):
        return conn.closed

    # --- Snowflake Connection ---
    elif isinstance(conn, snowconn.SnowflakeConnection):
        # SnowflakeConnection has an is_closed() method:
        return conn.is_closed()

    # --- Snowpark Session ---
    # The Snowpark Session internally holds a SnowflakeConnection in `conn._conn`.
    elif isinstance(conn, snowpark.Session):
        # If conn._conn is None or the underlying Snowflake connection is closed, then it's "closed".
        if conn._conn is None:
            return True
        return conn._conn.is_closed()

    # --- Paramiko SFTP Connection ---
    elif isinstance(conn, paramiko.SFTPClient):
        # Paramiko doesn't have a direct "closed" flag. We try a small operation: listing a directory.
        try:
            conn.listdir(".")
        except (IOError, paramiko.SSHException):
            return True
        return False

    # --- MongoDB Connection ---
    elif isinstance(conn, MongoClient):
        # MongoClient doesn't have an explicit "closed" flag. We try a simple operation to check connectivity.
        try:
            conn.admin.command("ping")
        except Exception:
            return True
        return False

    # --- SSAS Connection ---
    elif isinstance(conn, Pyadomd):
        try:
            return str(conn.state) != "Open"
        except Exception:
            return True

    return True  # Default if we get an unexpected type.

def _load_private_key(pem_text: str, passphrase: str | None) -> bytes:
    """
    Convert an (encrypted) PEM string into DER bytes accepted by the Snowflake
    connector / Snowpark. The PEM text *must* include the ----BEGIN ... lines.
    """
    key_obj = serialization.load_pem_private_key(
        data=pem_text.encode(),
        password=passphrase.encode() if passphrase else None,
        backend=default_backend(),
    )
    return key_obj.private_bytes(
        encoding=serialization.Encoding.DER,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )

def get_azure_keyvault_secret(
    secret_name: str,
    env: str,
    parse_as: str | None = None,
):
    """
    A function to connect to an Azure Key Vault and get a secret with config structure

    :param str secret_name: The name of the Azure Key vault secret you want to get. Note that this secret should have json structure.
    :param str env: The environment that determines the Azure Key Vault URL to connect to. Accepted values are 'prod', 'test', 'dev'.
    :param str parse_as: Whether to parse the value of the secret in a specific way. Accepted values are (None - Returns raw values, 'config' - Assumes the secret is a serialized JSON string format, returns DictConfig)
    :return : Returns either the secret value, or, in case there's content_type, a tuple holding (secret, content_type), in the requested parsed format.
    """

    # Authenticate to Azure Key Vault
    logger.info("Authenticating to Azure Key Vault...")

    client = SecretClient(vault_url=KEYVAULT_URL[env], credential=CREDENTIAL)

    # Fetch the secret
    logger.info(f"Fetching secret {secret_name}...")
    secret = client.get_secret(secret_name)

    if parse_as == "config":
        # Assuming the secret is a serialized JSON string - Deserialize JSON using OmegaConf
        return {
            "secret": OmegaConf.create(secret.value),
            "content_type": OmegaConf.create(secret.properties.content_type) if secret.properties.content_type else None,
        }

    return {"secret": secret.value, "content_type": secret.properties.content_type}


def get_sqlalchemy_connection(credentials, **overrides) -> sqla.engine.Connection:
    """
    Generic function to build an SQLAlchemy connection given:
      - secret: A dict with keys that map directly to URL parameters (or 'query' sub-keys, etc.).
      - overrides: Additional keyword args to override or add to the final config.

    Returns an active Connection object from an Engine configured for pooling.
    """

    # Merge all configs so that user overrides can take highest precedence
    #    The order (lowest -> highest) is: credentials < overrides
    config = {**credentials, **overrides}

    # Pop out the standard URL fields
    dialect_driver = config.pop("dialect+driver", None)
    if not dialect_driver:
        raise ValueError("Missing 'dialect+driver' in the combined configuration.")

    username = config.pop("username", None)
    password = config.pop("password", None)
    host = config.pop("host", None)
    port = config.pop("port", None)
    database = config.pop("database", None)
    query = config.pop("query", None)

    # Build the URL
    connection_url = sqla.engine.URL.create(
        dialect_driver,
        username=username,
        password=password,
        host=host,
        port=port,
        database=database,
        query=query
    )
    # Create SQLAlchemy engine with SQLALchemy default QueuePool
    engine = sqla.create_engine(connection_url, poolclass=QueuePool)
    return engine.connect()

def get_mongodb_connection(credentials, **overrides) -> MongoClient:
    """
    Builds a MongoDB connection using a generic configuration format.
    The configuration can include:
      - connection_string: A full MongoDB URI (if provided, used directly).
      - host, port, database, username, password: Connection components.
      - query: A string (e.g., "authSource=admin&replicaSet=rs0&tls=true")
    """
    config = {**credentials, **overrides}

    # Use connection_string if provided
    connection_string = config.pop("connection_string", None)
    if connection_string:
        return MongoClient(connection_string, **config)

    host = config.pop("host", None)
    if not host:
        raise ValueError("MongoDB configuration must include a 'host' key.")
    port = config.pop("port", 27017)
    database = config.pop("database", "")
    username = config.pop("username", None)
    password = config.pop("password", None)

    # Process query parameters
    query = config.pop("query", None)
    if query and isinstance(query, str):
        # Use the string directly
        query_string = f"?{query}"
    else:
        query_string = ""

    auth_part = f"{username}:{password}@" if username and password else ""
    database_part = f"/{database}" if database else ""
    connection_uri = f"mongodb://{auth_part}{host}:{port}{database_part}{query_string}"
    return MongoClient(connection_uri)

def get_sftp_connection(credentials, content_type) -> paramiko.SFTPClient:
    logger.info("Establishing SFTP connection...")
    # Check AuthType and establish connection accordingly
    if content_type.get("AuthType") == "password":
        # Password-based authentication
        transport = paramiko.Transport((credentials["host"], int(credentials.get("port", 22))))
        transport.connect(username=credentials["usr"], password=credentials["pwd"])
        return paramiko.SFTPClient.from_transport(transport)

    elif content_type.get("AuthType") == "ssh":
        # SSH key-based authentication
        private_key = paramiko.RSAKey(file_obj=io.StringIO(credentials["pkey"]))
        transport = paramiko.Transport((credentials["host"], int(credentials.get("port", 22))))
        transport.connect(username=credentials["usr"], pkey=private_key)
        return paramiko.SFTPClient.from_transport(transport)

    else:
        raise ValueError("Invalid AuthType for SFTP")

@lru_cache(maxsize=1)
def _load_pyadomd(dll_override: str | None = None):
    """
    Locate Microsoft.AnalysisServices.AdomdClient.dll, add its folder to
    sys.path (once), import pyadomd and return the Pyadomd class.
    """
    search_dirs: list[str] = []
    if dll_override:
        search_dirs.append(dll_override)
    search_dirs.extend(_DEFAULT_ADOMD_DIRS)

    for d in search_dirs:
        dll = Path(d) / "Microsoft.AnalysisServices.AdomdClient.dll"
        if dll.exists():
            sys.path.append(str(Path(d)))      # make pythonnet find the DLL
            break
    else:
        raise FileNotFoundError(
            "Microsoft.AnalysisServices.AdomdClient.dll not found.\n"
            "Install ADOMD.NET client or pass dll_path to get_connection()."
        )

    # --------------------------------------------------------------------------------
    # Expose the class at module level so other functions (e.g. _is_closed)
    # can use it in isinstance() without a NameError.
    # --------------------------------------------------------------------------------
    globals()["Pyadomd"] = importlib.import_module("pyadomd").Pyadomd


def get_ssas_connection(credentials, **overrides):
    """
    Build a connection to an SSAS cube using pyadomd.
    """
    dll_path = overrides.pop("dll_path", None)
    _load_pyadomd(dll_path)  # lazy import

    cfg = {**credentials, **overrides}
    conn_str = cfg.get("connection_string")
    if not conn_str:
        provider = cfg.get("provider", "MSOLAP")
        data_source = cfg["data_source"]
        catalog = cfg.get("catalog")
        if cfg.get("integrated_security", "").upper() in ("SSPI", "TRUE", "YES"):
            auth = "Integrated Security=SSPI;"
        elif "username" in cfg and "password" in cfg:
            auth = f"User ID={cfg['username']};Password={cfg['password']};"
        else:
            raise ValueError("SSAS credentials must contain auth info.")
        conn_str = (
            f"Provider={provider};Data Source={data_source};"
            f"Initial Catalog={catalog};{auth}"
        )

    try:
        conn = Pyadomd(conn_str)   # build the handle
        # Pyadomd keeps the connection closed until .open() / __enter__()
        if str(conn.state) != "Open":
            conn.open()
        return conn
    except Exception as exc:
        raise RuntimeError(f"Could not open SSAS connection: {exc}") from exc

def get_sfdb_connection(credentials, prefer_snowpark: bool = True, **overrides) -> Connection:
    # ── 1. If the secret uses key-pair auth, transform the fields ─────────
    if "private_key" in credentials:
        pem            = credentials.pop("private_key")
        passphrase     = credentials.pop("private_key_passphrase", None)
        credentials["private_key"] = _load_private_key(pem, passphrase)

    # ── 2. Create the connection as before ───────────────────────────────
    if prefer_snowpark:
        return snowpark.Session.builder.configs({**credentials, **overrides}).create()
    else:
        return snowconn.connect(**{**credentials, **overrides})

def get_connection(
    secret_name: str,
    env: str,
    prefer_snowpark: bool =True,
    **overrides,
) -> Connection | None:
    """
    Retrieves a cached connection if available, otherwise connects to Azure Key Vault and gets the credentials associated with secret_name,
    then creates a new connection based on connection type and caches it. Any other additional parameter neccessary for the connection can be passed via **kwargs.

    :param str secret_name: The name of the Azure Key Vault secret storing the connection configuration attributes.
    :param str env: The environment that determines the Azure Key Vault URL to connect to. Accepted values are 'prod', 'test', 'dev'.
    :param overrides: Keyword additional parameters to pass when creating the connection objects of DBs and Snowflake to override or add.
    :return: Connection object of type sqla.engine.Connection, snowc.SnowflakeConnection or paramiko.SFTPClient
    """
    global CONNECTION_CACHE

    # Build a cache key that includes all relevant parameters to uniquely identify the connection
    cache_key = (
        secret_name,
        KEYVAULT_URL[env],
        prefer_snowpark,
        tuple(sorted(overrides.items())), # Ensures kwargs are stored in a hashable, consistent form.
    )

    # Check if we have a cached connection matching our full cache_key
    if cache_key in CONNECTION_CACHE:
        cached_conn = CONNECTION_CACHE[cache_key]
        if _is_closed(cached_conn):
            logger.info(
                f"Cached connection for '{secret_name}' with override parameters {overrides} is closed. Re-establishing..."
            )
            del CONNECTION_CACHE[cache_key]
        else:
            return cached_conn

    # Retrieve credentials from Azure Key Vault
    credentials, content_type = get_azure_keyvault_secret(
        secret_name,
        env,
        parse_as="config"
    ).values()

    # Create connection based on the ConnectionType
    if content_type["ConnectionType"] == "database":
        conn = get_sqlalchemy_connection(credentials, **overrides)
        logger.info("Established SQLAlchemy connection")

    elif content_type["ConnectionType"] == "snowflake":
        conn = get_sfdb_connection(credentials, prefer_snowpark, **overrides)
        logger.info("Established Snowflake connection")

    elif content_type["ConnectionType"] == "mongodb":
        conn = get_mongodb_connection(credentials, **overrides)
        logger.info("Established MongoDB connection")

    elif content_type["ConnectionType"] == "sftp":
        conn = get_sftp_connection(credentials, content_type)
        logger.info("Established SFTP connection.")

    elif content_type["ConnectionType"] == "ssas":
        conn = get_ssas_connection(credentials, **overrides)

    else:
        raise ValueError(f"Unsupported ConnectionType: {content_type['ConnectionType']}")

    # Store connection in cache with the full key
    CONNECTION_CACHE[cache_key] = conn
    return conn



if __name__ == "__main__":
    conn = get_connection('temq-arp-ssas-config-general', env='prod')
    print(_is_closed(conn))

    conn = get_connection('temq-ark-db-config-general', env='test')