import json
import logging
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv
from openai import AzureOpenAI

from discharge_docs.config import DEPLOYMENT_NAME_BULK, TEMPERATURE
from discharge_docs.dashboard.helper import (
    get_data_from_patient_admission,
    get_template_prompt,
)
from discharge_docs.llm.prompt import (
    load_all_templates_prompts_into_dict,
    load_prompts,
)
from discharge_docs.llm.prompt_builder import (
    ContextLengthError,
    GeneralError,
    JSONError,
    PromptBuilder,
)
from discharge_docs.processing.processing import (
    get_patient_file,
)

logger = logging.getLogger(__name__)
load_dotenv()


def bulk_generate(
    data: pd.DataFrame,
    save_folder: Path,
    enc_ids_dict: dict,
    client: AzureOpenAI,
    skip_old_enc_ids: bool = False,
    old_bulk_letters: pd.DataFrame | None = None,
) -> None:
    """Bulk generate disharge documents for all encounters in the data.

    Parameters
    ----------
    data : pd.DataFrame
        Dataframe containing patient data
    save_folder : Path
        Path to save the generated documents
    enc_ids_dict : dict
        Dictionary containing encounter IDs
    client : AzureOpenAI
        OpenAI client object to interact with the API
    skip_old_enc_ids : bool
        Flag to skip encounters that already have a bulk generated letter
        NB make sure that old_bulk_letters is not None if this is set to True
    old_bulk_letters : pd.DataFrame
        Dataframe containing previously generated bulk letters
    """
    logger.info(f"Running with deployment name: {DEPLOYMENT_NAME_BULK}")

    all_enc_ids = [enc_id for enc_ids in enc_ids_dict.values() for enc_id in enc_ids]

    user_prompt, system_prompt = load_prompts()
    template_prompt_dict = load_all_templates_prompts_into_dict()

    if skip_old_enc_ids and old_bulk_letters is not None:
        enc_ids_to_skip = old_bulk_letters["enc_id"].unique()
        all_enc_ids = [
            enc_id for enc_id in all_enc_ids if enc_id not in enc_ids_to_skip
        ]
        logging.info(
            f"Skipping {len(enc_ids_to_skip)} encounters that already have a bulk "
            "generated letter"
        )
        bulk_generated_docs = old_bulk_letters
    else:
        bulk_generated_docs = pd.DataFrame(
            columns=["enc_id", "department", "generated_doc"]
        )

    logger.info(f"Bulk generating discharge letters for {len(all_enc_ids)} encounters")
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
        try:
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
                    "generated_doc": [json.dumps(discharge_letter)],
                }
            )
        except (ContextLengthError, JSONError, GeneralError) as e:
            new_row = pd.DataFrame(
                {
                    "enc_id": [patient_data["enc_id"].values[0]],
                    "department": [department],
                    "generated_doc": [
                        json.dumps(
                            {
                                "Geen Vooraf Gegenereerde Ontslagbrief Beschikbaar": (
                                    e.dutch_message
                                )
                            }
                        )
                    ],
                }
            )

        bulk_generated_docs = pd.concat(
            [bulk_generated_docs, new_row], ignore_index=True
        )

        bulk_generated_docs.to_parquet(
            Path(save_folder / "bulk_generated_docs_gpt.parquet")
        )
