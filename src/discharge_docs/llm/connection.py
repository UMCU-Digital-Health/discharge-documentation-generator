import os

from dotenv import load_dotenv
from openai import AzureOpenAI

load_dotenv()


def initialise_azure_connection() -> AzureOpenAI:
    """initialises the connection to the Azure OpenAI API using the environment
    variables

    Returns
    -------
    AzureOpenAI
        client object to interact with the Azure OpenAI API
    """
    client = AzureOpenAI(
        api_version=os.getenv("AZURE_OPENAI_API_VERSION", ""),
        api_key=os.getenv("AZURE_OPENAI_KEY", ""),
        azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT", ""),
    )
    return client
