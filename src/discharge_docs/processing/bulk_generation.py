import logging
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv

from discharge_docs.config import DEPLOYMENT_NAME_BULK, TEMPERATURE
from discharge_docs.dashboard.helper import (
    get_data_from_patient_admission,
    get_template_prompt,
    load_enc_ids,
)
from discharge_docs.llm.connection import initialise_azure_connection
from discharge_docs.llm.prompt import (
    load_all_templates_prompts_into_dict,
    load_prompts,
)
from discharge_docs.llm.prompt_builder import PromptBuilder
from discharge_docs.processing.processing import (
    get_patient_file,
)

logger = logging.getLogger(__name__)
load_dotenv()


def bulk_generate(data: pd.DataFrame, save_folder: Path) -> None:
    logger.info(f"Running with deployment name: {DEPLOYMENT_NAME_BULK}")

    client = initialise_azure_connection()

    enc_ids_dict = load_enc_ids()
    all_enc_ids = [enc_id for enc_ids in enc_ids_dict.values() for enc_id in enc_ids]

    user_prompt, system_prompt = load_prompts()
    template_prompt_dict = load_all_templates_prompts_into_dict()

    bulk_generated_docs = pd.DataFrame(
        columns=["enc_id", "department", "generated_doc"]
    )

    for enc_id in all_enc_ids:
        template_prompt, department = get_template_prompt(
            enc_id, template_prompt_dict, enc_ids_dict
        )

        logger.info(f"Generating discharge letter for encounter ID: {enc_id}")
        patient_data = get_data_from_patient_admission(enc_id, data)

        prompt_builder = PromptBuilder(
            temperature=TEMPERATURE,
            deployment_name=DEPLOYMENT_NAME_BULK,
            client=client,
        )

        patient_file_string, _ = get_patient_file(patient_data)
        discharge_letter = prompt_builder.generate_discharge_doc(
            patient_file=patient_file_string,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            template_prompt=template_prompt,
        )

        new_row = pd.DataFrame(
            {
                "enc_id": [patient_data["enc_id"].values[0]],
                "department": [department],
                "generated_doc": [discharge_letter],
            }
        )
        bulk_generated_docs = pd.concat(
            [bulk_generated_docs, new_row], ignore_index=True
        )

        bulk_generated_docs.to_parquet(
            Path(save_folder / "bulk_generated_docs_gpt.parquet")
        )
