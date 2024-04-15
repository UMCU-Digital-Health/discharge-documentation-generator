"""
This module contains the PromptBuilder class for generating prompts for the GPT model.
"""

import json
import logging
import re

import pandas as pd
import tiktoken
from openai import AzureOpenAI

from discharge_docs.processing.processing import get_patient_file

logger = logging.getLogger(__name__)


class PromptBuilder:
    def __init__(
        self,
        temperature: float,
        deployment_name: str,
        client: AzureOpenAI,
        token_encoding: str = "cl100k_base",
        max_context_length: int = 16384,
    ):
        self.temperature = temperature
        self.deployment_name = deployment_name
        self.client = client
        self.token_encoding = token_encoding
        self.max_context_length = max_context_length

    def get_token_length(
        self,
        patient_file: str,
        system_prompt: str,
        user_prompt: str,
        template_prompt: str,
        addition_prompt: str | None = None,
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
        addition_prompt : str | None, optional
            additional prompt for the GPT model, by default None

        Returns
        -------
        int
            The number of tokens in the prompt
        """
        total_prompt = patient_file + template_prompt + user_prompt + system_prompt
        if addition_prompt is not None:
            total_prompt += addition_prompt
        encoding = tiktoken.get_encoding(self.token_encoding)
        token_length = len(encoding.encode(total_prompt))
        return token_length

    def generate_discharge_doc(
        self,
        patient_file: str,
        system_prompt: str,
        user_prompt: str,
        template_prompt: str,
        addition_prompt: str | None = None,
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
        addition_prompt : str, optional
            Additional prompt for the GPT model, by default None.

        Returns
        -------
        dict
            The generated discharge documentation as a dictionary.
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
        if addition_prompt is not None:
            messages.append(
                {
                    "role": "user",
                    "content": addition_prompt,
                }
            )

        token_length = self.get_token_length(
            patient_file=patient_file,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            template_prompt=template_prompt,
            addition_prompt=addition_prompt,
        )
        if token_length > self.max_context_length:
            logger.error(f"Token length {token_length} exceeds maximum context length")
        logger.info("Sending request to GPT model...")
        response = self.client.chat.completions.create(
            model=self.deployment_name,
            messages=messages,
            temperature=self.temperature,
        )
        logger.info("Parsing response to JSON...")
        reply = json.loads(
            re.sub(
                "```(json)?",
                "",
                response.model_dump()["choices"][0]["message"]["content"],
            )
        )
        return reply

    def iterative_simulation(
        self,
        patient_data: pd.DataFrame,
        system_prompt: str,
        user_prompt: str,
        template_prompt: str,
        addition_prompt: str | None = None,
    ) -> list[dict]:
        """Generate discharge letters iteratively.

        This method generates discharge letters iteratively based on the provided
        patient data and prompts. It iterates over the unique dates in the patient data
        and generates a discharge letter for each date.

        Parameters
        ----------
        patient_data : pd.DataFrame
            DataFrame containing patient data.
        system_prompt : str
            System prompt for the GPT model.
        user_prompt : str
            User prompt for the GPT model.
        template_prompt : str
            Template prompt for the GPT model.
        addition_prompt : str, optional
            Additional prompt for the GPT model, by default None.

        Returns
        -------
        list[dict]
            List of discharge letters generated for each date in the patient data.
        """
        temp_discharge_letter = None
        discharge_letters = []
        logger.info("Running in iterative mode...")

        for i, date in enumerate(patient_data["date"].sort_values().unique()):
            logger.info(f"{i}: Processing date {date}")
            patient_file_string, _ = get_patient_file(
                patient_data[patient_data["date"] == date]
            )

            patient_file_string_new = (
                f"\n\n# 1. Huidige ontslagbrief\n{temp_discharge_letter}"
                f"\n\n# 2. Huidige dagstatus\n{patient_file_string}"
            )

            discharge_letter = self.generate_discharge_doc(
                patient_file=patient_file_string_new,
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                template_prompt=template_prompt,
                addition_prompt=addition_prompt,
            )
            discharge_letters.append(discharge_letter)
            temp_discharge_letter = discharge_letter
        return discharge_letters
