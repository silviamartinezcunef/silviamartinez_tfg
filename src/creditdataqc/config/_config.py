"""
This module contains the configuration logic for the package.
It is responsible for locating and loading the configuration files,  parsing command line arguments,
 and building the AppConfig: A DictConfig object that contains the configuration settings for the package.
"""
from datetime import datetime, date, timedelta
from pandas.tseries.offsets import Day, BDay
from pathlib import Path
import argparse
from hydra import initialize, compose
from omegaconf import OmegaConf, DictConfig
from dataclasses import dataclass
from typing import List, Type, Optional, Union

# Define custom resolvers (check if already registered to avoid errors on re-import)
if not OmegaConf.has_resolver("bday_before"):
    OmegaConf.register_new_resolver(
        "bday_before",
        lambda days, start_date="", fmt="%Y-%m-%d":
            ((date.today() if not start_date else datetime.strptime(start_date, fmt).date()) - BDay(int(days))).strftime(fmt)
    )
if not OmegaConf.has_resolver("day_before"):
    OmegaConf.register_new_resolver(
        "day_before",
        lambda days, start_date="", fmt="%Y-%m-%d":
            ((date.today() if not start_date else datetime.strptime(start_date, fmt).date()) - Day(int(days))).strftime(fmt)
    )

'''##################### Accepted Command Line Arguments #####################'''

def parse_cli_args() -> DictConfig:
    parser = argparse.ArgumentParser(description='Description of your package')
    parser.add_argument('--run.env', choices=['prod', 'test', 'dev'],
                        help='Environment to run the script in, must be one of these values: prod, test, dev')

    # Use parse_known_args to avoid errors on unknown arguments (like Jupyter's -f)
    args, unknown = parser.parse_known_args()
    if unknown:
        print(f"Unknown arguments not defined in parse_cli_args(): {unknown}")

    # Create nested dictionary from dot-separated keys
    cli_dict = {}
    for k, v in vars(args).items():
        if v is not None:
            keys = k.split('.')
            d = cli_dict
            for key in keys[:-1]:
                if key not in d:
                    d[key] = {}
                d = d[key]
            d[keys[-1]] = v
    return OmegaConf.create(cli_dict)

'''##################### Build App Config #####################'''
def locate_and_load_config(config_dirs: List[str], config_files: List[str]) -> List[DictConfig]:
    """Load configurations from the specified directories and files."""
    configs = []
    for config_dir in config_dirs:
        for config_file in config_files:
            config_path = Path(config_dir) / config_file
            if config_path.is_file():
                configs.append(OmegaConf.load(config_path))
    return configs

def build_app_config(config_files: List[str] = ['config.yaml'],
                     app_config_base: Optional[Type[dataclass]] = None) -> DictConfig:
    """Function to locate, load the configuration files, and build the AppConfig.
        Creates candidate file paths where config files may be located, and proceeds to load them in the following order:

        1. If provided, the base configuration dataclass is loaded to impose structure
        2. "config" subpackage source directory - Where default config files for the package are stored
        3. .config directory at user's home directory - Where base config files are stored
        4. Current Working Directory - Where user may have placed config files for the specific run
        5. Command Line Arguments - If provided, they will override the configuration

        This sequence is ordered. If the same config setting is specified in multiple
        locations, the value at the last found location will prevail (i.e. command line args have the highest priority).
        """

    # Initialize base configuration if provided
    base_config = OmegaConf.structured(app_config_base) if app_config_base else OmegaConf.create()

    # Define the directories to search for configuration files
    source_dirs = [
        str(Path(__file__).parent),  # Root of the installed package
        str(Path.home() / ".config"),  # Home directory config
        str(Path.cwd())  # Current working directory
    ]

    # Locate and load the config files in the specified directories
    file_confs = locate_and_load_config(source_dirs, config_files)

    # Initialize Hydra and compose the configuration
    with initialize(config_path=None, version_base=None):
        # Merge loaded files manually
        hydra_conf = OmegaConf.merge(*file_confs)

    # Parse CLI arguments and merge them
    cli_conf = parse_cli_args()

    # Merge the configurations in the order specified: base_config -> hydra_conf -> cli_conf
    app_conf = OmegaConf.merge(base_config, hydra_conf, cli_conf)

    # Add internal root path based on the package root and add CWD
    app_conf.internal_location.root = str(Path(__file__).parent.parent).replace("\\", "/")
    app_conf.run.cwd = str(Path.cwd()).replace("\\", "/")

    return app_conf

# Instance the AppConfig
AppConfig = build_app_config(app_config_base=None)
Path(AppConfig.output_path).mkdir(parents=True, exist_ok=True)