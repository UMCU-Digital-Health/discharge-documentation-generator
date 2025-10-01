import logging
import os
import sys
import tomllib
from pathlib import Path

from rich.logging import RichHandler

from discharge_docs.config_models import (
    AuthConfig,
    DepartmentConfig,
    LLMConfig,
)
from discharge_docs.llm.prompt import (
    load_department_examples,
    load_department_prompt,
    load_post_processing_prompt,
)

CONFIG_PATH = Path(__file__).parents[2] / "run" / "config" / "deployment_config.toml"
AUTH_CONFIG_PATH = Path(__file__).parents[2] / "run" / "config" / "auth.toml"
DEPARTMENT_CONFIG_PATH = (
    Path(__file__).parent / "llm" / "prompts" / "department_config.toml"
)


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
    env_name = os.getenv("LLM_ENVIRONMENT", "ACC").upper()
    if env_name not in ["ACC", "PROD", "BULK", "EVAL"]:
        raise ValueError(
            f"Invalid environment name: {env_name}. "
            "Must be one of 'ACC', 'PROD', 'BULK', or 'EVAL'."
        )
    with open(config_path, "rb") as f:
        deployment_config_dict = tomllib.load(f)
    deployment_name_env = deployment_config_dict[f"DEPLOYMENT_NAME_{env_name}"]
    return LLMConfig(**deployment_config_dict, DEPLOYMENT_NAME_ENV=deployment_name_env)


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


def load_department_config(
    config_path: Path = DEPARTMENT_CONFIG_PATH, fill_prompts: bool = True
) -> DepartmentConfig:
    """Load the department configuration from a TOML file.

    Parameters
    ----------
    config_path : Path, optional
        The path to the department configuration file, by default DEPARTMENT_CONFIG_PATH
    fill_prompts : bool, optional
        Whether to fill department prompts and examples, by default True

    Returns
    -------
    DepartmentConfig
        An instance of DepartmentConfig containing department settings.
        Use the instance like:
        returned = load_department_config()
        returned.department["IC"].department_prompt
    """
    with open(config_path, "rb") as f:
        data = tomllib.load(f)
    department_config = DepartmentConfig(**data)

    if fill_prompts:
        for dept in department_config.department.values():
            dept.department_prompt = load_department_prompt(dept.id)
            if dept.department_examples is not None:
                dept.department_examples = load_department_examples(dept.id)

            if dept.post_processing:
                dept.post_processing_prompt = load_post_processing_prompt(dept.id)
    return department_config


config = load_config(CONFIG_PATH)

TEMPERATURE = config.temperature
DEPLOYMENT_NAME_BULK = config.DEPLOYMENT_NAME_BULK
DEPLOYMENT_NAME_ENV = config.DEPLOYMENT_NAME_ENV
