import logging
import os
import sys
from pathlib import Path

import tomli
from pydantic import BaseModel
from rich.logging import RichHandler

CONFIG_PATH = Path(__file__).parent / "llm" / "deployment_config.toml"


class LLMConfig(BaseModel):
    temperature: float
    deployment_name_acc: str
    deployment_name_prod: str
    deployment_name_bulk: str
    deployment_name_env: str


def load_config(config_path: Path = CONFIG_PATH) -> LLMConfig:
    with open(config_path, "rb") as f:
        deployment_config_dict = tomli.load(f)
    deployment_name_env = deployment_config_dict[
        f"deployment_name_{os.getenv('ENVIRONMENT', 'acc')}"
    ]
    return LLMConfig(**deployment_config_dict, deployment_name_env=deployment_name_env)


def setup_root_logger() -> None:
    """Setup the root logger for the project.
    This function sets up the root logger with a specific format and level.
    """
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    # Some packages have already initialized the root logger, so we need to remove
    # their handlers first.
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    # Posit does not support rich logging, so use a simple console handler
    if os.getenv("CONNECT_SERVER") is not None:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(
            logging.Formatter("%(levelname)s: [%(name)s] - %(message)s")
        )
    else:
        console_handler = RichHandler()
        console_handler.setFormatter(
            logging.Formatter(
                "%(message)s",
                datefmt="[%X]",
            )
        )
    root_logger.addHandler(console_handler)


config = load_config(CONFIG_PATH)

TEMPERATURE = config.temperature
DEPLOYMENT_NAME_ACC = config.deployment_name_acc
DEPLOYMENT_NAME_PROD = config.deployment_name_prod
DEPLOYMENT_NAME_BULK = config.deployment_name_bulk
DEPLOYMENT_NAME_ENV = config.deployment_name_env
