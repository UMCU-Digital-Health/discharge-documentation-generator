import os
from pathlib import Path

import tomli
from pydantic import BaseModel

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


config = load_config(CONFIG_PATH)

TEMPERATURE = config.temperature
DEPLOYMENT_NAME_ACC = config.deployment_name_acc
DEPLOYMENT_NAME_PROD = config.deployment_name_prod
DEPLOYMENT_NAME_BULK = config.deployment_name_bulk
DEPLOYMENT_NAME_ENV = config.deployment_name_env
