import logging
import os
import sys
import tomllib
from pathlib import Path

from pydantic import BaseModel, EmailStr
from rich.logging import RichHandler

CONFIG_PATH = Path(__file__).parents[2] / "run" / "config" / "deployment_config.toml"
AUTH_CONFIG_PATH = Path(__file__).parents[2] / "run" / "config" / "auth.toml"


class LLMConfig(BaseModel):
    """Configuration for the LLM deployments.

    Environments are:
    - acc: Acceptance environment for test pipeline
    - prod: Production environment for production pipeline
    - bulk: Bulk generation environment for bulk generating letters for evaluation
    - eval: Evaluation environment for evaluation dashboard
    - env: Environment variable to determine the current environment
    """

    temperature: float
    deployment_name_acc: str
    deployment_name_prod: str
    deployment_name_bulk: str
    deployment_name_eval: str
    deployment_name_env: str


class AuthUser(BaseModel):
    email: EmailStr
    groups: list[str]
    developer: bool = False


class AuthConfig(BaseModel):
    users: dict[str, AuthUser]


def load_config(config_path: Path = CONFIG_PATH) -> LLMConfig:
    """Load the LLM configuration from a TOML file.

    Parameters
    ----------
    config_path : Path, optional
        The path to the configuration file, by default CONFIG_PATH

    Returns
    -------
    LLMConfig
        An instance of LLMConfig containing the configuration parameters.
    """
    env_name = os.getenv("ENVIRONMENT", "acc").lower()
    if env_name not in ["acc", "prod", "bulk", "eval"]:
        raise ValueError(
            f"Invalid environment name: {env_name}. "
            "Must be one of 'acc', 'prod', 'bulk', or 'eval'."
        )
    with open(config_path, "rb") as f:
        deployment_config_dict = tomllib.load(f)
    deployment_name_env = deployment_config_dict[f"deployment_name_{env_name}"]
    return LLMConfig(**deployment_config_dict, deployment_name_env=deployment_name_env)


def load_auth_config(config_path: Path = AUTH_CONFIG_PATH) -> AuthConfig:
    """Load the authentication configuration from a TOML file.

    Parameters
    ----------
    config_path : Path, optional
        The path to the authentication configuration file, by default AUTH_CONFIG_PATH

    Returns
    -------
    AuthConfig
        An instance of AuthConfig containing the user authorization information.
    """
    with open(config_path, "rb") as f:
        auth_config_dict = tomllib.load(f)
    return AuthConfig(**auth_config_dict)


def get_current_version() -> str:
    """Get the current version of the project from the pyproject.toml file.

    Returns
    -------
    str
        The version of the project.
    """
    with open(Path(__file__).parents[2] / "pyproject.toml", "rb") as f:
        config = tomllib.load(f)
    return config["project"]["version"]


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
DEPLOYMENT_NAME_BULK = config.deployment_name_bulk
DEPLOYMENT_NAME_ENV = config.deployment_name_env
