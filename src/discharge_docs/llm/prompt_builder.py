"""
This module contains the PromptBuilder class for generating prompts for the GPT model.
"""

import json
import logging

import tiktoken
from openai import AzureOpenAI

logger = logging.getLogger(__name__)


class ContextLengthError(Exception):
    """Exception raised when the token length exceeds the maximum context length."""

    def __init__(self) -> None:
        self.type = "LengthError"
        self.dutch_message = (
            "De omvang van het patientendossier is te groot geworden voor het AI model."
            " Daardoor kan er geen ontslagbrief worden gegenereerd."
            " Schrijf de ontslagbrief op de oude manier."
        )
        super().__init__("Token length exceeds maximum context length")


class JSONError(Exception):
    """Exception raised when there is an error converting the response to JSON."""

    def __init__(self) -> None:
        self.type = "JSONError"
        self.dutch_message = (
            "Er is een fout opgetreden bij het genereren van de ontslagbrief met AI."
            " Schrijf de ontslagbrief op de oude manier."
        )
        super().__init__("Error converting response to JSON")


class GeneralError(Exception):
    """Exception raised when there is a general error generating the discharge docs."""

    def __init__(self) -> None:
        self.type = "GeneralError"
        self.dutch_message = (
            "Er is een fout opgetreden bij het genereren van de ontslagbrief met AI."
            " Schrijf de ontslagbrief op de oude manier."
        )
        super().__init__("Error generating discharge docs")


class PromptBuilder:
    def __init__(
        self,
        temperature: float,
        deployment_name: str,
        client: AzureOpenAI,
        token_encoding: str = "cl100k_base",
    ):
        self.temperature = temperature
        self.deployment_name = deployment_name
        self.client = client
        self.token_encoding = token_encoding
        self.max_context_length = self.determine_context_length(deployment_name)

    def determine_context_length(self, deployment_name):
        context_length_by_deployment = {
            "aiva-gpt": 16384,
            "aiva-gpt4": 120000,
            "aiva-gpt4-new": 120000,
        }
        if deployment_name in context_length_by_deployment:
            return context_length_by_deployment[deployment_name]
        else:
            raise ValueError(f"Unknown deployment name: {deployment_name}")

    def get_token_length(
        self,
        patient_file: str,
        system_prompt: str,
        user_prompt: str,
        template_prompt: str,
    ) -> int:
        """Get the token length of the input for the GPT model.

        Parameters
        ----------
        patient_file : str
            the patient file as a string
        system_prompt : str
            the system prompt for the GPT model
        user_prompt : str
            the user prompt for the GPT model
        template_prompt : str
            the template prompt for the GPT model

        Returns
        -------
        int
            The number of tokens in the prompt
        """
        total_prompt = patient_file + template_prompt + user_prompt + system_prompt
        encoding = tiktoken.get_encoding(self.token_encoding)
        token_length = len(encoding.encode(total_prompt))
        return token_length

    def generate_discharge_doc(
        self,
        patient_file: str,
        system_prompt: str,
        user_prompt: str,
        template_prompt: str,
    ) -> dict:
        """
        Generate discharge documentation using GPT model.

        Parameters
        ----------
        patient_file : str
            The path to the patient file.
        system_prompt : str
            The system prompt for the GPT model.
        user_prompt : str
            The user prompt for the GPT model.
        template_prompt : str
            The template prompt for the GPT model.

        Returns
        -------
        dict
            The generated discharge documentation as a dictionary.

        Raises
        ------
        ContextLengthError
            If the token length exceeds the maximum context length.
        JSONError
            If there is an error converting the response to JSON.
        GeneralError
            If there is a general error generating the discharge documentation.
        """
        messages = [
            {
                "role": "system",
                "content": system_prompt,
            },
            {
                "role": "user",
                "content": user_prompt,
            },
            {
                "role": "user",
                "content": template_prompt,
            },
            {"role": "user", "content": patient_file},
        ]

        token_length = self.get_token_length(
            patient_file=patient_file,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            template_prompt=template_prompt,
        )
        if token_length > self.max_context_length:
            logger.error(f"Token length {token_length} exceeds maximum context length")
            raise ContextLengthError()

        logger.info("Sending request to GPT model...")
        try:
            response = self.client.chat.completions.create(
                model=self.deployment_name,
                messages=messages,  # type: ignore
                temperature=self.temperature,
                response_format={"type": "json_object"},
            )
            if response.choices[0].message.content is None:
                raise Exception("Empty response from GPT model")
        except Exception as e:
            logger.error(f"Error generating discharge documentation: {e}")
            raise GeneralError() from e

        try:
            reply = json.loads(response.choices[0].message.content)
        except Exception as e:
            logger.error(f"Error converting to JSON: {e}")
            raise JSONError() from e
        return reply
