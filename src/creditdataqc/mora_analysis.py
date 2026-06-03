"""
Análisis de morosidad v2 - Dataset unificado por cliente.

Este script crea un dataset completamente nuevo con una fila por cliente,
incluyendo información de morosidad actual, histórica y facturas.
"""

import pandas as pd
from pathlib import Path
from typing import Optional

from creditdataqc.config._config import AppConfig
from creditdataqc._log import get_logger
from creditdataqc._conn_manager import get_connection

logger = get_logger(__name__)

conn_snowflake = get_connection(AppConfig.snowflake, AppConfig.run.env, prefer_snowpark=False)

PROJECT_ROOT = Path(__file__).parents[2]
DATA_OUTPUT_DIR = PROJECT_ROOT / "output"

# Mapeo de códigos CNAE-2009 a sectores descriptivos
CNAE_SECTOR_MAP = {
    '01': 'Agricultura', '02': 'Silvicultura', '03': 'Pesca',
    '05': 'Mineria_carbon', '06': 'Extraccion_petroleo', '07': 'Mineria_metalica',
    '08': 'Otras_extractivas', '09': 'Servicios_mineria',
    '10': 'Alimentacion', '11': 'Bebidas', '12': 'Tabaco',
    '13': 'Textil', '14': 'Confeccion', '15': 'Cuero_calzado',
    '16': 'Madera', '17': 'Papel', '18': 'Artes_graficas',
    '19': 'Coquerias_refino', '20': 'Quimica', '21': 'Farmaceutica',
    '22': 'Caucho_plasticos', '23': 'Productos_minerales', '24': 'Metalurgia',
    '25': 'Productos_metalicos', '26': 'Electronica', '27': 'Material_electrico',
    '28': 'Maquinaria', '29': 'Vehiculos', '30': 'Otro_transporte',
    '31': 'Muebles', '32': 'Otras_manufacturas', '33': 'Reparacion_maquinaria',
    '35': 'Energia_electrica', '36': 'Agua', '37': 'Saneamiento',
    '38': 'Gestion_residuos', '39': 'Descontaminacion',
    '41': 'Construccion_edificios', '42': 'Ingenieria_civil', '43': 'Actividades_construccion',
    '45': 'Venta_vehiculos', '46': 'Comercio_mayorista', '47': 'Comercio_minorista',
    '49': 'Transporte_terrestre', '50': 'Transporte_maritimo', '51': 'Transporte_aereo',
    '52': 'Almacenamiento', '53': 'Actividades_postales',
    '55': 'Alojamiento', '56': 'Hosteleria',
    '58': 'Edicion', '59': 'Cine_video', '60': 'Radio_television',
    '61': 'Telecomunicaciones', '62': 'Programacion_informatica', '63': 'Servicios_informacion',
    '64': 'Servicios_financieros', '65': 'Seguros', '66': 'Auxiliares_financieros',
    '68': 'Inmobiliarias',
    '69': 'Juridicas_contables', '70': 'Sedes_centrales', '71': 'Servicios_tecnicos',
    '72': 'Investigacion', '73': 'Publicidad', '74': 'Otras_profesionales',
    '75': 'Veterinarias',
    '77': 'Alquiler', '78': 'Empleo', '79': 'Agencias_viajes',
    '80': 'Seguridad', '81': 'Servicios_edificios', '82': 'Actividades_administrativas',
    '84': 'Administracion_publica', '85': 'Educacion', '86': 'Sanitarias',
    '87': 'Asistencia_residencial', '88': 'Servicios_sociales',
    '90': 'Creacion_artistico', '91': 'Bibliotecas_museos', '92': 'Juegos_azar',
    '93': 'Deportivas', '94': 'Asociativas', '95': 'Reparacion_ordenadores',
    '96': 'Otros_servicios_personales', '97': 'Hogares_empleados', '99': 'Organizaciones_extraterritoriales'
}

# Diccionario de normalización de provincias
PROVINCIA_NORMALIZADA = {
    # España - normalización de variantes
    'ALAVA': 'Álava',
    'ÁLAVA': 'Álava',
    'ALBACETE': 'Albacete',
    'ALICANTE': 'Alicante',
    'ALICANTE/ALACANT': 'Alicante',
    'ALACANT': 'Alicante',
    'ALMERIA': 'Almería',
    'ALMERÍA': 'Almería',
    'ASTURIAS': 'Asturias',
    'AVILA': 'Ávila',
    'ÁVILA': 'Ávila',
    'BADAJOZ': 'Badajoz',
    'BALEARES': 'Baleares',
    'BARCELONA': 'Barcelona',
    'BIZKAIA': 'Vizcaya',
    'BURGOS': 'Burgos',
    'CACERES': 'Cáceres',
    'CÁCERES': 'Cáceres',
    'CADIZ': 'Cádiz',
    'CÁDIZ': 'Cádiz',
    'CANTABRIA': 'Cantabria',
    'CASTELLON': 'Castellón',
    'CASTELLÓN': 'Castellón',
    'CIUDAD REAL': 'Ciudad Real',
    'CORDOBA': 'Córdoba',
    'CÓRDOBA': 'Córdoba',
    'A CORUÑA': 'A Coruña',
    'LA CORUÑA': 'A Coruña',
    'CORUÑA': 'A Coruña',
    'CORUÑA, A': 'A Coruña',
    'CUENCA': 'Cuenca',
    'GIRONA': 'Gerona',
    'GIRONA (GERONA)': 'Gerona',
    'GERONA': 'Gerona',
    'GRANADA': 'Granada',
    'GUADALAJARA': 'Guadalajara',
    'GIPUZKOA': 'Guipúzcoa',
    'GUIPUZCOA': 'Guipúzcoa',
    'GUIPÚZCOA': 'Guipúzcoa',
    'HUELVA': 'Huelva',
    'HUESCA': 'Huesca',
    'JAEN': 'Jaén',
    'JAÉN': 'Jaén',
    'LEON': 'León',
    'LEÓN': 'León',
    'LLEIDA': 'Lérida',
    'LERIDA': 'Lérida',
    'LÉRIDA': 'Lérida',
    'LA RIOJA': 'La Rioja',
    'LUGO': 'Lugo',
    'MADRID': 'Madrid',
    'MALAGA': 'Málaga',
    'MÁLAGA': 'Málaga',
    'MURCIA': 'Murcia',
    'NAVARRA': 'Navarra',
    'OURENSE': 'Ourense',
    'OURENSE (ORENSE)': 'Ourense',
    'ORENSE': 'Ourense',
    'PALENCIA': 'Palencia',
    'LAS PALMAS': 'Las Palmas',
    'PALMAS DE GRAN CANARIA, LAS': 'Las Palmas',
    'PALMAS, LAS': 'Las Palmas',
    'PONTEVEDRA': 'Pontevedra',
    'SALAMANCA': 'Salamanca',
    'SANTA CRUZ DE TENERIFE': 'Santa Cruz de Tenerife',
    'SEGOVIA': 'Segovia',
    'SEVILLA': 'Sevilla',
    'SORIA': 'Soria',
    'TARRAGONA': 'Tarragona',
    'TERUEL': 'Teruel',
    'TOLEDO': 'Toledo',
    'VALENCIA': 'Valencia',
    'VALLADOLID': 'Valladolid',
    'ZAMORA': 'Zamora',
    'ZARAGOZA': 'Zaragoza',
    'CEUTA': 'Ceuta',
    'MELILLA': 'Melilla',
    'STA. CRUZ TENERIFE': 'Santa Cruz de Tenerife',
    'STA CRUZ DE TENERIFE': 'Santa Cruz de Tenerife',
    'TENERIFE': 'Santa Cruz de Tenerife',
    'S.C. TENERIFE': 'Santa Cruz de Tenerife',
    'SANTA CRUZ TENERIFE': 'Santa Cruz de Tenerife',
    'S.C. DE TENERIFE': 'Santa Cruz de Tenerife',
    'FUERTEVENTURA': 'Las Palmas',
    'LAS PALMAS DE GRAN CANARIA': 'Las Palmas',
    'SAN SEBASTIAN': 'Guipúzcoa',
    'DONOSTIA': 'Guipúzcoa',
    'P. ASTURIAS': 'Asturias',
    'PRINCIPADO DE ASTURIAS': 'Asturias',
    'VIZCAYA': 'Vizcaya',
    'VIZCAIA': 'Vizcaya',

    # Portugal - distritos principales
    'AVEIRO': 'Aveiro',
    'BEJA': 'Beja',
    'BRAGA': 'Braga',
    'BRAGANÇA': 'Bragança',
    'BRAGANCA': 'Bragança',
    'CASTELO BRANCO': 'Castelo Branco',
    'COIMBRA': 'Coimbra',
    'ÉVORA': 'Évora',
    'EVORA': 'Évora',
    'FARO': 'Faro',
    'GUARDA': 'Guarda',
    'LEIRIA': 'Leiria',
    'LISBOA': 'Lisboa',
    'PORTALEGRE': 'Portalegre',
    'PORTO': 'Porto',
    'SANTARÉM': 'Santarém',
    'SANTAREM': 'Santarém',
    'SETÚBAL': 'Setúbal',
    'SETUBAL': 'Setúbal',
    'VIANA DO CASTELO': 'Viana do Castelo',
    'VILA REAL': 'Vila Real',
    'VISEU': 'Viseu',
}

# Provincias de Portugal (para corregir país)
# Incluye variaciones con/sin tildes, con/sin espacios, y abreviaciones
PROVINCIAS_PORTUGAL = {
    # Distritos de Portugal continental
    'AVEIRO', 'BEJA', 'BRAGA', 'BRAGANÇA', 'BRAGANCA', 'BRAGAN?A',
    'CASTELO BRANCO', 'COIMBRA', 'ÉVORA', 'EVORA',
    'FARO', 'GUARDA', 'LEIRIA', 'LISBOA', 'LISBON', 'PORTALEGRE',
    'PORTO', 'OPORTO', 'SANTARÉM', 'SANTAREM', 'SETÚBAL', 'SETUBAL',
    'VIANA DO CASTELO', 'VILA REAL', 'VISEU',
    # Regiones autónomas
    'AÇORES', 'ACORES', 'AZORES', 'MADEIRA',
    # Variaciones adicionales observadas
    'VILA DO CONDE', 'MATOSINHOS', 'GONDOMAR', 'MAIA',
    'PÓVOA DE VARZIM', 'VALONGO', 'PAREDES', 'PENAFIEL',
    'SANTO TIRSO', 'TROFA', 'AMARANTE', 'FELGUEIRAS',
    'LOUSADA', 'PACOS DE FERREIRA', 'PAÇOS DE FERREIRA',
    'MARCO DE CANAVESES', 'PÓVOA DO VARZIM', 'PÓVOA DE VARZIM',
    # Verificar si contiene alguna de estas palabras
}


def normalizar_provincias(df: pd.DataFrame, provincia_col: str = 'provincia', pais_col: str = 'pais') -> pd.DataFrame:
    """
    Normaliza los nombres de provincias a formato estándar y corrige el país según la provincia.
    Primera letra mayúscula, con tildes en castellano.

    Args:
        df: DataFrame con columna de provincia y país
        provincia_col: Nombre de la columna con provincias
        pais_col: Nombre de la columna con país

    Returns:
        DataFrame con provincias normalizadas y país corregido
    """
    logger.info(f"Normalizando nombres de provincias y corrigiendo país...")

    if provincia_col not in df.columns:
        logger.warning(f"Columna '{provincia_col}' no encontrada.")
        return df

    # Convertir a mayúsculas para el mapeo
    df[provincia_col] = df[provincia_col].astype(str).str.strip().str.upper()

    # LIMPIEZA: Marcar como NULL provincias que son claramente inválidas
    # (países extranjeros, códigos postales, direcciones, etc.)
    PROVINCIAS_INVALIDAS = {
        'GERMANY', 'SWITZERLAND', 'SINGAPUR', 'SINGAPORE', 'LONDON', 'LONDRES',
        'LONDON-UNITED KINGDOM', 'AMSTERDAM', 'GINEBRA', 'GINEGRA', 'LUGANO',
        'TESINO', 'BAAR', 'BADEN -SUIZA', 'BUCELAS', 'PAU CEDEX',
        # Códigos postales y similares
        'BE10', 'CH033', 'PL91',
        # Direcciones
        'JUAN DE MARIANA 17 B',
        # Islas que deberían ser parte de provincias
        'FUERTEVENTURA',  # → Las Palmas
        # Variaciones incorrectas
        'LAS PALMAS DE GRAN CANARIA', 'SAN SEBASTIAN', 'SANTA CRUZ TENERIFE', 'S.C. DE TENERIFE'
    }

    mask_invalidas = df[provincia_col].isin(PROVINCIAS_INVALIDAS)
    n_invalidas = mask_invalidas.sum()
    if n_invalidas > 0:
        logger.warning(f"Encontradas {n_invalidas} provincias inválidas (países extranjeros, códigos, etc.). Se marcarán como NULL")
        df.loc[mask_invalidas, provincia_col] = None

    # CORRECCIÓN DE PAÍS: Si la provincia es de Portugal, corregir país a PRT
    if pais_col in df.columns:
        mask_portugal = df[provincia_col].isin(PROVINCIAS_PORTUGAL)
        df.loc[mask_portugal, pais_col] = 'PRT'
        n_corregidos = mask_portugal.sum()
        if n_corregidos > 0:
            logger.info(f"Corregidos {n_corregidos} registros de Portugal mal clasificados como ESP")

    # Aplicar mapeo de normalización
    df[provincia_col] = df[provincia_col].map(PROVINCIA_NORMALIZADA).fillna(df[provincia_col])

    # Para valores que no están en el diccionario, aplicar formato Title Case básico
    # (primera letra de cada palabra en mayúscula)
    mask_no_mapeado = ~df[provincia_col].isin(PROVINCIA_NORMALIZADA.values()) & df[provincia_col].notna()
    df.loc[mask_no_mapeado, provincia_col] = (
        df.loc[mask_no_mapeado, provincia_col].str.title()
    )

    n_provincias = df[provincia_col].nunique()
    logger.info(f"Provincias normalizadas: {n_provincias} provincias únicas")
    logger.info(f"Top 10 provincias:")
    logger.info(f"\n{df[provincia_col].value_counts().head(10)}")

    return df


def mapear_cnae_sector(df: pd.DataFrame, cnae_col: str = 'cnae') -> pd.DataFrame:
    """
    Reemplaza los códigos CNAE numéricos por sectores descriptivos.

    Args:
        df: DataFrame con columna de código CNAE
        cnae_col: Nombre de la columna con código CNAE

    Returns:
        DataFrame con códigos CNAE reemplazados por sectores
    """
    logger.info(f"Mapeando códigos CNAE a sectores...")

    if cnae_col not in df.columns:
        logger.warning(f"Columna '{cnae_col}' no encontrada. Se asignará 'Desconocido'")
        df[cnae_col] = 'Desconocido'
        return df

    # Convertir CNAE a string y extraer primeros 2 dígitos
    df['cnae_2dig'] = (
        df[cnae_col]
        .astype(str)
        .str.replace('.0', '', regex=False)
        .str.replace('nan', '', regex=False)
        .str.zfill(4)
        .str[:2]
    )

    # Mapear a sector descriptivo y reemplazar la columna cnae
    df[cnae_col] = df['cnae_2dig'].map(CNAE_SECTOR_MAP).fillna('Desconocido')

    # Eliminar columna temporal
    df = df.drop(columns=['cnae_2dig'])

    n_con_sector = df[cnae_col].ne('Desconocido').sum()
    logger.info(f"CNAE mapeado: {n_con_sector}/{len(df)} registros ({100*n_con_sector/len(df):.1f}%)")

    return df


def query_morosidad_dataset(conn_snowflake, reportdate: str,
                             umbral_dias: int = 60,
                             umbral_importe: float = 2000.0) -> pd.DataFrame:
    """
    Construye el dataset de morosidad con una fila por cliente.

    Columnas generadas:
    - cif_nif: Identificador fiscal del cliente
    - cnae: Tipo de empresa según CNAE (descripción del sector, ej: "Hostelería", "Agricultura")
    - provincia: Provincia del cliente (normalizada)
    - pais: País del cliente ('ESP' o 'PRT')
    - tipo: Tipo de cliente ('Persona' o 'Empresa')
    - fecha_creacion: Fecha de constitución de la empresa (NULL para personas físicas)
    - es_moroso: ¿Es moroso actualmente? (bool) - Tiene deuda vencida >60 días y >2000€
    - dias_mora_maximo: Días máximos de mora de todas las facturas del cliente
    - saldo_pendiente_total: Suma del saldo pendiente de TODAS las facturas del cliente
    - n_facturas_totales: Total de facturas del cliente
    - n_facturas_morosas: Número de facturas morosas (vencidas >60 días de clientes morosos)
    - proporcion_facturas_morosas: n_facturas_morosas / n_facturas_totales

    Args:
        conn_snowflake: Conexión a Snowflake
        reportdate: Fecha de reporte para calcular morosidad
        umbral_dias: Días mínimos de vencimiento (default: 60)
        umbral_importe: Deuda vencida total mínima del cliente para considerarse moroso (default: 2000)

    Returns:
        DataFrame con una fila por cliente (cif_nif único)
    """
    logger.info(f"Construyendo dataset de morosidad (reportdate={reportdate})")
    logger.info(f"Umbrales: {umbral_dias} días, {umbral_importe}€")

    query = f"""
    WITH
    -- 1. MAPEO CIF/NIF: Unificar códigos de cliente con priorización por país
    -- Prioridad: NAVISION_PT > BC_ESP > NAVISION_ESP (para evitar que Porto/Aveiro aparezcan como ESP)
    CLIENTES_TODAS_TABLAS AS (
        SELECT DISTINCT
            NO_ AS codigo_cliente,
            TRIM(UPPER(VAT_REGISTRATION_NO_)) AS cif_nif,
            COUNTY AS provincia,
            CITY AS ciudad,
            POST_CODE AS codigo_postal,
            NULL AS cnae_bc,
            -- Extraer país del prefijo VAT si es extranjero, sino usar tabla de origen
            CASE
                -- VAT extranjero: 2 letras + números (ej: CH498556, FR123456, DE789012)
                WHEN REGEXP_LIKE(TRIM(UPPER(VAT_REGISTRATION_NO_)), '^[A-Z]{2}[0-9]')
                THEN LEFT(TRIM(UPPER(VAT_REGISTRATION_NO_)), 2)
                -- Si no, es portugués (tabla NAVISION_PT)
                ELSE 'PRT'
            END AS pais,
            1 AS prioridad
        FROM NEURON_PRO.NAVISION_PT.CUSTOMER
        WHERE VAT_REGISTRATION_NO_ IS NOT NULL
          AND TRIM(VAT_REGISTRATION_NO_) != ''

        UNION ALL

        SELECT DISTINCT
            NO_ AS codigo_cliente,
            TRIM(UPPER(VAT_REGISTRATION_NO_)) AS cif_nif,
            COUNTY AS provincia,
            CITY AS ciudad,
            POST_CODE AS codigo_postal,
            ATT_CNAE AS cnae_bc,
            -- Extraer país del prefijo VAT si es extranjero, sino usar tabla de origen
            CASE
                -- VAT extranjero: 2 letras + números (ej: CH498556, FR123456, DE789012)
                WHEN REGEXP_LIKE(TRIM(UPPER(VAT_REGISTRATION_NO_)), '^[A-Z]{2}[0-9]')
                THEN LEFT(TRIM(UPPER(VAT_REGISTRATION_NO_)), 2)
                -- Si no, es español (tabla BC_ESP)
                ELSE 'ESP'
            END AS pais,
            2 AS prioridad
        FROM NEURON_PRO.BC_ESP.CUSTOMER
        WHERE VAT_REGISTRATION_NO_ IS NOT NULL
          AND TRIM(VAT_REGISTRATION_NO_) != ''

        UNION ALL

        SELECT DISTINCT
            NO_ AS codigo_cliente,
            TRIM(UPPER(VAT_REGISTRATION_NO_)) AS cif_nif,
            COUNTY AS provincia,
            CITY AS ciudad,
            POST_CODE AS codigo_postal,
            NULL AS cnae_bc,
            -- Extraer país del prefijo VAT si es extranjero, sino usar tabla de origen
            CASE
                -- VAT extranjero: 2 letras + números (ej: CH498556, FR123456, DE789012)
                WHEN REGEXP_LIKE(TRIM(UPPER(VAT_REGISTRATION_NO_)), '^[A-Z]{2}[0-9]')
                THEN LEFT(TRIM(UPPER(VAT_REGISTRATION_NO_)), 2)
                -- Si no, es español (tabla NAVISION_ESP)
                ELSE 'ESP'
            END AS pais,
            3 AS prioridad
        FROM NEURON_PRO.NAVISION_ESP.CUSTOMER
        WHERE VAT_REGISTRATION_NO_ IS NOT NULL
          AND TRIM(VAT_REGISTRATION_NO_) != ''
    ),

    -- Deduplicar por cif_nif, priorizando NAVISION_PT (prioridad 1)
    CLIENTES_MAESTRO AS (
        SELECT
            codigo_cliente,
            cif_nif,
            provincia,
            ciudad,
            codigo_postal,
            cnae_bc,
            pais
        FROM (
            SELECT *,
                   ROW_NUMBER() OVER (PARTITION BY cif_nif ORDER BY prioridad) AS rn
            FROM CLIENTES_TODAS_TABLAS
        )
        WHERE rn = 1
    ),

    -- 2. DATOS DE SALESFORCE: Obtener CNAE y fecha de constitución desde Salesforce/Falcon
    CLIENTES_SALESFORCE_RAW AS (
        SELECT
            TRIM(UPPER(A.FALCON_FLD_DOCUMENTNUMBER__C)) AS cif_nif,
            C.NAME AS cnae_salesforce,
            LEFT(A.FALCON_FLD_INCORPORATIONDATE__C, 10) AS fecha_constitucion_salesforce,
            ROW_NUMBER() OVER (
                PARTITION BY TRIM(UPPER(A.FALCON_FLD_DOCUMENTNUMBER__C))
                ORDER BY A.LASTMODIFIEDDATE DESC
            ) AS rn
        FROM NEURON_PRO.SALESFORCE_REP.ACCOUNT A
        LEFT JOIN NEURON_PRO.SALESFORCE_REP.FALCON_OBJ_CNAE__C C
            ON A.FALCON_FLD_CNAE__C = C.ID
        WHERE A.FALCON_FLD_DOCUMENTNUMBER__C IS NOT NULL
    ),

    CLIENTES_SALESFORCE AS (
        SELECT
            cif_nif,
            cnae_salesforce,
            fecha_constitucion_salesforce
        FROM CLIENTES_SALESFORCE_RAW
        WHERE rn = 1
    ),

    -- 3. DATOS DE RATING: Obtener CNAE, tipo y fecha de constitución
    CLIENTES_RATING_RAW AS (
        SELECT
            TRIM(UPPER(T_CLIENTE.CIF_NIF)) AS cif_nif,
            FIRST_VALUE(
                CASE
                    WHEN T_CLIENTE.TIPO_PERSONA = 'PERSON' THEN 'Persona'
                    WHEN T_CLIENTE.TIPO_PERSONA = 'CORPORATE' THEN 'Empresa'
                    ELSE NULL
                END
            ) OVER (
                PARTITION BY T_CLIENTE.CIF_NIF
                ORDER BY T_EVALUACION.FECHA_CREACION DESC
            ) AS tipo,
            FIRST_VALUE(T_EEFF.CODIGO_CNAE) OVER (
                PARTITION BY T_CLIENTE.CIF_NIF
                ORDER BY T_EVALUACION.FECHA_CREACION DESC
            ) AS cnae,
            FIRST_VALUE(T_EEFF.FECHA_CONSTITUCION) OVER (
                PARTITION BY T_CLIENTE.CIF_NIF
                ORDER BY T_EVALUACION.FECHA_CREACION DESC
            ) AS fecha_creacion,
            ROW_NUMBER() OVER (
                PARTITION BY T_CLIENTE.CIF_NIF
                ORDER BY T_EVALUACION.FECHA_CREACION DESC
            ) AS rn
        FROM NEURON_PRO.RATING.T_CLIENTE T_CLIENTE
        LEFT JOIN NEURON_PRO.RATING.T_RATING_REQUEST T_RATING_REQUEST
            ON T_CLIENTE.ID_CLIENTE = T_RATING_REQUEST.ID_CLIENTE
        LEFT JOIN NEURON_PRO.RATING.T_EVALUACION T_EVALUACION
            ON T_RATING_REQUEST.ID_EVALUACION = T_EVALUACION.ID_EVALUACION
        LEFT JOIN NEURON_PRO.RATING.T_REL_EVAL_EEFF T_REL
            ON T_EVALUACION.ID_EVALUACION = T_REL.ID_EVALUACION
        LEFT JOIN NEURON_PRO.RATING.T_EEFF T_EEFF
            ON T_REL.ID_EEFF = T_EEFF.ID_EEFF
        WHERE T_CLIENTE.CIF_NIF IS NOT NULL
    ),

    CLIENTES_RATING AS (
        SELECT
            cif_nif,
            tipo,
            cnae,
            fecha_creacion
        FROM CLIENTES_RATING_RAW
        WHERE rn = 1
    ),

    -- 3a. FACTURAS_TODAS_RAW: Todas las facturas de todas las fuentes (puede haber duplicados por migración)
    FACTURAS_TODAS_RAW AS (
        -- BC_ESP (España - actual)
        SELECT
            TRIM(UPPER(CUST.VAT_REGISTRATION_NO_)) AS cif_nif,
            CLE.CUSTOMER_NO_ AS codigo_cliente,
            CLE.DOCUMENT_NO_ AS numero_factura,
            LEFT(CLE.DUE_DATE, 10) AS fecha_vencimiento,
            LEFT(CLE.POSTING_DATE, 10) AS fecha_emision,
            CAST(CLE.REMAINING_AMOUNT__LCY_STATS_ AS DECIMAL(16,2)) AS saldo_pendiente,
            DATEDIFF(DAY, TO_DATE(LEFT(CLE.DUE_DATE, 10)), TO_DATE('{reportdate}')) AS dias_vencido,
            LEFT(CLE.POSTING_DATE, 7) AS mes_ano_emision,
            'BC_ESP' AS fuente
        FROM NEURON_PRO.BC_ESP.CUST_LEDGER_ENTRY CLE
        INNER JOIN NEURON_PRO.BC_ESP.CUSTOMER CUST ON CLE.CUSTOMER_NO_ = CUST.NO_
        WHERE CUST.VAT_REGISTRATION_NO_ IS NOT NULL
          AND TRIM(CUST.VAT_REGISTRATION_NO_) != ''

        UNION ALL

        -- NAVISION_PT (Portugal - histórico)
        SELECT
            TRIM(UPPER(CUST.VAT_REGISTRATION_NO_)) AS cif_nif,
            CLE.CUSTOMER_NO_ AS codigo_cliente,
            CLE.DOCUMENT_NO_ AS numero_factura,
            LEFT(CLE.DUE_DATE, 10) AS fecha_vencimiento,
            LEFT(CLE.POSTING_DATE, 10) AS fecha_emision,
            CAST(CLE.REMAINING_AMOUNT_LCY_STATS_ AS DECIMAL(16,2)) AS saldo_pendiente,
            DATEDIFF(DAY, TO_DATE(LEFT(CLE.DUE_DATE, 10)), TO_DATE('{reportdate}')) AS dias_vencido,
            LEFT(CLE.POSTING_DATE, 7) AS mes_ano_emision,
            'NAVISION_PT' AS fuente
        FROM NEURON_PRO.NAVISION_PT.CUST__LEDGER_ENTRY CLE
        INNER JOIN NEURON_PRO.NAVISION_PT.CUSTOMER CUST ON CLE.CUSTOMER_NO_ = CUST.NO_
        WHERE CUST.VAT_REGISTRATION_NO_ IS NOT NULL
          AND TRIM(CUST.VAT_REGISTRATION_NO_) != ''

        UNION ALL

        -- NAVISION_ESP (España - histórico)
        SELECT
            TRIM(UPPER(CUST.VAT_REGISTRATION_NO_)) AS cif_nif,
            CLE.CUSTOMER_NO_ AS codigo_cliente,
            CLE.DOCUMENT_NO_ AS numero_factura,
            LEFT(CLE.DUE_DATE, 10) AS fecha_vencimiento,
            LEFT(CLE.POSTING_DATE, 10) AS fecha_emision,
            CAST(CLE.REMAINING_AMOUNT_LCY_STATS_ AS DECIMAL(16,2)) AS saldo_pendiente,
            DATEDIFF(DAY, TO_DATE(LEFT(CLE.DUE_DATE, 10)), TO_DATE('{reportdate}')) AS dias_vencido,
            LEFT(CLE.POSTING_DATE, 7) AS mes_ano_emision,
            'NAVISION_ESP' AS fuente
        FROM NEURON_PRO.NAVISION_ESP.CUST__LEDGER_ENTRY CLE
        INNER JOIN NEURON_PRO.NAVISION_ESP.CUSTOMER CUST ON CLE.CUSTOMER_NO_ = CUST.NO_
        WHERE CUST.VAT_REGISTRATION_NO_ IS NOT NULL
          AND TRIM(CUST.VAT_REGISTRATION_NO_) != ''
    ),

    -- 3b. FACTURAS_TODAS: Deduplicar facturas que pueden existir en múltiples sistemas (prioridad: BC_ESP > NAVISION_PT > NAVISION_ESP)
    -- Deduplicación por (cif_nif, numero_factura, fecha_emision) para evitar eliminar facturas legítimas
    FACTURAS_TODAS AS (
        SELECT
            cif_nif,
            codigo_cliente,
            numero_factura,
            fecha_vencimiento,
            fecha_emision,
            saldo_pendiente,
            dias_vencido,
            mes_ano_emision
        FROM (
            SELECT *,
                   ROW_NUMBER() OVER (
                       PARTITION BY cif_nif, numero_factura, fecha_emision
                       ORDER BY
                           CASE fuente
                               WHEN 'BC_ESP' THEN 1
                               WHEN 'NAVISION_PT' THEN 2
                               WHEN 'NAVISION_ESP' THEN 3
                           END
                   ) AS rn
            FROM FACTURAS_TODAS_RAW
        )
        WHERE rn = 1
    ),

    -- 3c. FACTURAS: Solo facturas con saldo pendiente
    FACTURAS AS (
        SELECT *
        FROM FACTURAS_TODAS
        WHERE saldo_pendiente != 0
    ),

    -- 4. FACTURAS VENCIDAS: Facturas con días vencidos > umbral_dias y saldo positivo
    FACTURAS_VENCIDAS AS (
        SELECT
            cif_nif,
            numero_factura,
            fecha_vencimiento,
            saldo_pendiente,
            dias_vencido,
            mes_ano_emision
        FROM FACTURAS
        WHERE dias_vencido > {umbral_dias}
          AND saldo_pendiente > 0
    ),

    -- 5. FACTURAS MOROSAS CRITERIO 1: Al menos UNA factura >60d con saldo >2000€
    FACTURAS_MOROSAS_60D AS (
        SELECT
            cif_nif,
            numero_factura,
            fecha_vencimiento,
            saldo_pendiente,
            dias_vencido,
            mes_ano_emision
        FROM FACTURAS_VENCIDAS
        WHERE saldo_pendiente > {umbral_importe}
    ),

    -- 6. CLIENTES MOROSOS CRITERIO 1: Tienen al menos una factura que cumple criterio 1
    CLIENTES_MOROSOS AS (
        SELECT DISTINCT
            cif_nif
        FROM FACTURAS_MOROSAS_60D
    ),

    -- 6b. FACTURAS MOROSAS CRITERIO 2: Al menos UNA factura >90d con saldo >1€
    FACTURAS_MOROSAS_90D AS (
        SELECT
            cif_nif,
            numero_factura,
            fecha_vencimiento,
            saldo_pendiente,
            dias_vencido,
            mes_ano_emision
        FROM FACTURAS
        WHERE dias_vencido > 90
          AND saldo_pendiente > 1.0
    ),

    -- 6c. CLIENTES MOROSOS CRITERIO 2: Tienen al menos una factura que cumple criterio 2
    CLIENTES_MOROSOS_90D AS (
        SELECT DISTINCT
            cif_nif
        FROM FACTURAS_MOROSAS_90D
    ),

    -- 7. FACTURAS MOROSAS: Unión de facturas que cumplen criterio 1 O criterio 2
    FACTURAS_MOROSAS_ACTUAL AS (
        SELECT
            cif_nif,
            numero_factura,
            fecha_vencimiento,
            saldo_pendiente,
            dias_vencido,
            mes_ano_emision
        FROM FACTURAS_MOROSAS_60D
        UNION
        SELECT
            cif_nif,
            numero_factura,
            fecha_vencimiento,
            saldo_pendiente,
            dias_vencido,
            mes_ano_emision
        FROM FACTURAS_MOROSAS_90D
    ),

    -- 7b. AGREGACIONES DE FACTURAS POR CLIENTE (para evitar producto cartesiano en el GROUP BY final)
    FACTURAS_AGREGADAS AS (
        SELECT
            cif_nif,
            COUNT(DISTINCT numero_factura) AS n_facturas_totales
        FROM FACTURAS_TODAS
        GROUP BY cif_nif
    ),

    FACTURAS_PENDIENTES_AGREGADAS AS (
        SELECT
            cif_nif,
            SUM(saldo_pendiente) AS saldo_pendiente_total
        FROM FACTURAS
        GROUP BY cif_nif
    ),

    FACTURAS_VENCIDAS_AGREGADAS AS (
        SELECT
            cif_nif,
            COUNT(DISTINCT numero_factura) AS n_facturas_vencidas
        FROM FACTURAS
        GROUP BY cif_nif
    ),

    FACTURAS_MOROSAS_AGREGADAS AS (
        SELECT
            cif_nif,
            COUNT(DISTINCT numero_factura) AS n_facturas_morosas,
            MAX(dias_vencido) AS dias_mora_maximo
        FROM FACTURAS_MOROSAS_ACTUAL
        GROUP BY cif_nif
    ),

    -- 8. DATASET POR CLIENTE
    DATASET_FINAL AS (
        SELECT
            CM.cif_nif,
            -- CNAE solo para empresas (NULL si es persona)
            CASE
                -- Si Rating dice que es Empresa
                WHEN CR.tipo = 'Empresa' THEN COALESCE(CM.cnae_bc, CR.cnae, CSF.cnae_salesforce)
                -- Si Rating dice que es Persona
                WHEN CR.tipo = 'Persona' THEN NULL
                -- Si no hay dato en Rating, inferir por formato CIF/NIF
                WHEN REGEXP_LIKE(CM.cif_nif, '^[0-9]{8}[A-Z]$') THEN NULL -- DNI español
                WHEN REGEXP_LIKE(CM.cif_nif, '^[XYZ][0-9]{7}[A-Z]$') THEN NULL -- NIE español
                WHEN REGEXP_LIKE(CM.cif_nif, '^[0-9]{9}$') THEN NULL -- NIF portugués
                -- Si parece CIF de empresa, asignar CNAE
                WHEN REGEXP_LIKE(CM.cif_nif, '^[A-W][0-9]{8}$') THEN COALESCE(CM.cnae_bc, CR.cnae, CSF.cnae_salesforce)
                -- Por defecto NULL
                ELSE NULL
            END AS cnae,
            CM.provincia,
            CM.pais,
            -- Tipo con inferencia: si Rating no tiene datos, inferir por formato CIF/NIF
            CASE
                WHEN CR.tipo IS NOT NULL THEN CR.tipo
                -- DNI español: 8 dígitos + 1 letra (ej: 12345678A)
                WHEN REGEXP_LIKE(CM.cif_nif, '^[0-9]{8}[A-Z]$') THEN 'Persona'
                -- NIE español: letra + 7 dígitos + letra (ej: X1234567A)
                WHEN REGEXP_LIKE(CM.cif_nif, '^[XYZ][0-9]{7}[A-Z]$') THEN 'Persona'
                -- NIF portugués persona: 9 dígitos (ej: 123456789)
                WHEN REGEXP_LIKE(CM.cif_nif, '^[0-9]{9}$') THEN 'Persona'
                -- Por defecto: todo lo demás es Empresa
                ELSE 'Empresa'
            END AS tipo,
            -- Fecha de creación solo para empresas (NULL si es persona o tipo desconocido)
            CASE
                WHEN CR.tipo = 'Empresa' THEN COALESCE(CR.fecha_creacion, CSF.fecha_constitucion_salesforce)
                -- Si inferimos que es empresa por CIF, también usar fecha
                WHEN CR.tipo IS NULL AND REGEXP_LIKE(CM.cif_nif, '^[A-W][0-9]{8}$') THEN COALESCE(CR.fecha_creacion, CSF.fecha_constitucion_salesforce)
                ELSE NULL
            END AS fecha_creacion,

            -- Morosidad combinada: TRUE si cumple criterio 1 O criterio 2
            CASE
                WHEN CMO.cif_nif IS NOT NULL OR CMO90.cif_nif IS NOT NULL THEN TRUE
                ELSE FALSE
            END AS es_moroso,

            -- Criterio 1: >60d y >2000€
            CASE
                WHEN CMO.cif_nif IS NOT NULL THEN TRUE
                ELSE FALSE
            END AS es_moroso_60d,

            -- Criterio 2: >90d y >1€
            CASE
                WHEN CMO90.cif_nif IS NOT NULL THEN TRUE
                ELSE FALSE
            END AS es_moroso_90d,

            -- Métricas de facturas (pre-agregadas para evitar producto cartesiano)
            COALESCE(FMA_AGG.dias_mora_maximo, 0) AS dias_mora_maximo,
            COALESCE(FP_AGG.saldo_pendiente_total, 0) AS saldo_pendiente_total,
            COALESCE(FT_AGG.n_facturas_totales, 0) AS n_facturas_totales,
            COALESCE(FV_AGG.n_facturas_vencidas, 0) AS n_facturas_vencidas,
            COALESCE(FMA_AGG.n_facturas_morosas, 0) AS n_facturas_morosas,

            -- Proporción de facturas morosas
            CASE
                WHEN COALESCE(FT_AGG.n_facturas_totales, 0) > 0
                THEN CAST(COALESCE(FMA_AGG.n_facturas_morosas, 0) AS FLOAT) / FT_AGG.n_facturas_totales
                ELSE 0.0
            END AS proporcion_facturas_morosas

        FROM CLIENTES_MAESTRO CM
        LEFT JOIN CLIENTES_SALESFORCE CSF ON CM.cif_nif = CSF.cif_nif
        LEFT JOIN CLIENTES_RATING CR ON CM.cif_nif = CR.cif_nif
        LEFT JOIN FACTURAS_AGREGADAS FT_AGG ON CM.cif_nif = FT_AGG.cif_nif
        LEFT JOIN FACTURAS_PENDIENTES_AGREGADAS FP_AGG ON CM.cif_nif = FP_AGG.cif_nif
        LEFT JOIN FACTURAS_VENCIDAS_AGREGADAS FV_AGG ON CM.cif_nif = FV_AGG.cif_nif
        LEFT JOIN FACTURAS_MOROSAS_AGREGADAS FMA_AGG ON CM.cif_nif = FMA_AGG.cif_nif
        LEFT JOIN CLIENTES_MOROSOS CMO ON CM.cif_nif = CMO.cif_nif
        LEFT JOIN CLIENTES_MOROSOS_90D CMO90 ON CM.cif_nif = CMO90.cif_nif
    )

    SELECT
        cif_nif,
        cnae,
        provincia,
        pais,
        tipo,
        fecha_creacion,
        es_moroso,
        es_moroso_60d,
        es_moroso_90d,
        dias_mora_maximo,
        saldo_pendiente_total,
        n_facturas_totales,
        n_facturas_vencidas,
        n_facturas_morosas,
        proporcion_facturas_morosas
    FROM DATASET_FINAL
    ORDER BY es_moroso DESC, dias_mora_maximo DESC
    """

    logger.info("Ejecutando query en Snowflake...")
    df = pd.read_sql(query, conn_snowflake)

    # Normalizar nombres de columnas a minúsculas
    df.columns = df.columns.str.lower()

    # Normalizar nombres de provincias y corregir país
    df = normalizar_provincias(df, provincia_col='provincia', pais_col='pais')

    # Mapear CNAE a sector descriptivo
    df = mapear_cnae_sector(df, cnae_col='cnae')

    logger.info(f"Dataset generado: {len(df)} clientes")
    logger.info(f"  - Clientes morosos: {df['es_moroso'].sum()}")

    return df


def run_mora_analysis_v2(reportdate: Optional[str] = None,
                         umbral_dias: int = 60,
                         umbral_importe: float = 2000.0) -> pd.DataFrame:
    """
    Ejecuta el análisis de morosidad v2 y exporta el resultado.

    Args:
        reportdate: Fecha de reporte (default: hoy)
        umbral_dias: Días mínimos para considerar morosidad
        umbral_importe: Importe mínimo para considerar morosidad

    Returns:
        DataFrame con el dataset de morosidad
    """
    if reportdate is None:
        reportdate = pd.Timestamp.today().strftime('%Y-%m-%d')

    logger.info("=" * 80)
    logger.info("ANÁLISIS DE MOROSIDAD V2 - DATASET UNIFICADO")
    logger.info("=" * 80)

    DATA_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    df = query_morosidad_dataset(
        conn_snowflake,
        reportdate=reportdate,
        umbral_dias=umbral_dias,
        umbral_importe=umbral_importe
    )

    output_file = DATA_OUTPUT_DIR / f"morosidad_dataset_{reportdate}.xlsx"

    if output_file.exists():
        output_file.unlink()
        logger.info(f"Archivo anterior eliminado: {output_file}")

    logger.info(f"Exportando resultados a: {output_file}")

    # Exportar solo una hoja con todos los datos
    df.to_excel(output_file, sheet_name='dataset_morosidad', index=False, engine='openpyxl')

    logger.info("=" * 80)
    logger.info("RESUMEN DEL ANÁLISIS")
    logger.info("=" * 80)
    logger.info(f"Total de clientes: {len(df)}")
    logger.info(f"Clientes morosos actualmente: {df['es_moroso'].sum()}")
    logger.info(f"Promedio facturas por cliente: {df['n_facturas_totales'].mean():.2f}")
    logger.info(f"Exportado a: {output_file}")
    logger.info("=" * 80)

    return df


if __name__ == "__main__":
    import sys

    try:
        df = run_mora_analysis_v2(
            reportdate='2026-04-23',
            umbral_dias=60,
            umbral_importe=2000.0
        )
        print("\n[OK] Análisis completado exitosamente")
        print(f"[OK] Total clientes: {len(df)}")
        print(f"[OK] Clientes morosos: {df['es_moroso'].sum()}")
    except Exception as e:
        print(f"\n[ERROR] {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
