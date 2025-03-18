import logging
import os

from dotenv import load_dotenv
from openai import AzureOpenAI

load_dotenv()

logger = logging.getLogger(__name__)


def initialise_azure_connection() -> AzureOpenAI:
    """Initialises the connection to the Azure OpenAI API using the environment
    variables

    This function reads the environment variables for the Azure OpenAI API and
    initialises the connection to the Azure OpenAI API. If the environment
    variables are not set, it raises a ValueError.

    Returns
    -------
    AzureOpenAI
        client object to interact with the Azure OpenAI API

    Raises
    ------
    ValueError
        If any of the environment variables for the Azure OpenAI API are not set
    """
    api_version = os.getenv("AZURE_OPENAI_API_VERSION")
    api_key = os.getenv("AZURE_OPENAI_KEY")
    azure_endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
    if not api_version or not api_key or not azure_endpoint:
        logger.error(
            "Missing environment variables for Azure OpenAI API. "
            "Please set AZURE_OPENAI_API_VERSION, AZURE_OPENAI_KEY and "
            "AZURE_OPENAI_ENDPOINT."
        )

    client = AzureOpenAI(
        api_version=str(api_version),
        api_key=str(api_key),
        azure_endpoint=str(azure_endpoint),
    )
    return client
