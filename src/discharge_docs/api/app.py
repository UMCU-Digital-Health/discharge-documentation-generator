import os

import pandas as pd
from dotenv import load_dotenv
from fastapi import FastAPI
from openai import AzureOpenAI

from discharge_docs.processing.processing import get_patient_file
from discharge_docs.prompts.prompt import (
    load_prompts,
    load_template_prompt,
)
from discharge_docs.prompts.prompt_builder import PromptBuilder

load_dotenv()

app = FastAPI()

TEMPERATURE = 0.2
deployment_name = "aiva-gpt"

client = AzureOpenAI(
    api_version="2024-02-01",
    api_key=os.getenv("AZURE_OPENAI_KEY"),
    azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT", ""),
)


@app.post("/update-discharge-docs")
async def update_discharge_docs(daily_updates: list[dict]) -> dict:
    """For every encounter update the discharge documentation with the latest
    information.

    Parameters
    ----------
    daily_updates : list[dict]
        daily updates on patients in json-format
    """
    daily_updates_df = pd.DataFrame.from_records(daily_updates)
    daily_updates_df["time"] = pd.to_datetime(daily_updates_df["time"])

    prompt_builder = PromptBuilder(
        temperature=TEMPERATURE, deployment_name=deployment_name, client=client
    )

    user_prompt, system_prompt = load_prompts(iterative=True)
    enc_dict = {}

    for enc_id in daily_updates_df["enc_id"].unique():
        enc_string, encounter_df = get_patient_file(daily_updates_df, enc_id)
        department = encounter_df["department"].values[0]
        template_prompt = load_template_prompt(department)

        prev_discharge_letter = ""  # TODO: get previous discharge letter

        encounter_string_new = (
            f"\n\n# 1. Huidige ontslagbrief\n{prev_discharge_letter}"
            f"\n\n# 2. Huidige dagstatus\n{enc_string}"
        )

        discharge_letter = prompt_builder.generate_discharge_doc(
            patient_file=encounter_string_new,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            template_prompt=template_prompt,
            addition_prompt=None,
        )

        enc_dict[enc_id] = discharge_letter
    return enc_dict


@app.get("/")
async def root():
    return {"message": "Hello World"}
