import json
import logging
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv
from openai import AzureOpenAI
from sqlalchemy import select
from sqlalchemy.orm import sessionmaker
from umcu_ai_utils.database_connection import get_engine

from discharge_docs.config import (
    DEPLOYMENT_NAME_BULK,
    TEMPERATURE,
    load_department_config,
)
from discharge_docs.config_models import DepartmentConfig
from discharge_docs.database.models import DashEncounter, PatientFile, StoredDoc
from discharge_docs.llm.helper import DischargeLetter, generate_single_doc
from discharge_docs.llm.prompt_builder import (
    PromptBuilder,
)
from discharge_docs.processing.processing import (
    get_patient_file,
)

logger = logging.getLogger(__name__)
load_dotenv()


def bulk_generate(
    data: pd.DataFrame,
    client: AzureOpenAI,
    department_config: DepartmentConfig,
    department_prompt: str | None = None,
    post_processing_prompt: str | None = None,
) -> pd.DataFrame:
    """Bulk generate discharge documents for all encounters in the provided dataframe.

    Parameters
    ----------
    data : pd.DataFrame
        Dataframe containing patient data
    client : AzureOpenAI
        OpenAI client object to interact with the API
    department_config : DepartmentConfig
        Configuration for different departments
    """
    logger.info(f"Running with deployment name: {DEPLOYMENT_NAME_BULK}")

    logger.info(
        f"Bulk generating discharge letters for {len(data['enc_id'].unique().tolist())}"
        " encounters"
    )
    development_admissions = data[
        ["enc_id", "department", "length_of_stay"]
    ].drop_duplicates()

    bulk_rows = []

    for _, row in development_admissions.iterrows():
        enc_id = row["enc_id"]
        department = row["department"]
        length_of_stay = row["length_of_stay"]
        logger.info(f"Generating discharge doc for enc id: {enc_id} from {department}")

        prompt_builder = PromptBuilder(
            temperature=TEMPERATURE,
            deployment_name=DEPLOYMENT_NAME_BULK,
            client=client,
        )

        patient_file_string, patient_data = get_patient_file(data, enc_id)

        if department_prompt is None and post_processing_prompt is None:
            discharge_letter = generate_single_doc(
                prompt_builder,
                patient_file_string,
                department,
                department_config,
                length_of_stay,
            )
        else:
            discharge_letter = generate_single_doc(
                prompt_builder,
                patient_file_string,
                department,
                department_config,
                length_of_stay,
                department_prompt=department_prompt,
                post_processing_prompt=post_processing_prompt,
            )

        bulk_rows.append(
            {
                "enc_id": patient_data["enc_id"].values[0],
                "department": department,
                "generated_doc": json.dumps(discharge_letter.generated_doc),
                "generation_time": discharge_letter.generation_time,
                "success_indicator": discharge_letter.success_indicator,
                "error_type": discharge_letter.error_type,
            }
        )

    # Build final DataFrame once
    bulk_generated_docs = pd.DataFrame(
        bulk_rows,
        columns=[
            "enc_id",
            "department",
            "generated_doc",
            "generation_time",
            "success_indicator",
            "error_type",
        ],
    )
    return bulk_generated_docs


def run_bulk_generation(
    client: AzureOpenAI,
    storage_location: str,
    selected_department: str | None = None,
    department_prompt: str | None = None,
    post_processing_prompt: str | None = None,
) -> None:
    """Run bulk generation of discharge letters for the selected_department.
    The data used for bulk generation is gathered from storage_location.

    Parameters
    ----------
    client : AzureOpenAI
        OpenAI client object to interact with the API
    storage_location : str
        Location of the data to be processed. "database" or "data/processed"
    selected_department : str | None, optional
        Department to filter encounters on when loading from database, by default None.
        When using data/processed, all departments in that data will be processed
        (which will only be one department).

    Raises
    ------
    ValueError
        If storage_location is "database" and selected_department is None.
    """
    processed_data_folder = Path(__file__).parents[3] / "data" / "processed"

    engine = get_engine(schema_name=DashEncounter.__table__.schema)
    session_factory = sessionmaker(bind=engine)

    if storage_location == "data/processed":
        bulk_encounters_data = pd.read_parquet(
            Path(processed_data_folder / "evaluation_data.parquet")
        )
    elif storage_location == "database":
        if not selected_department:
            raise ValueError(
                "selected_department must be provided when storage_location is "
                "'database'"
            )
        with session_factory() as session:
            bulk_encounters_query = session.execute(
                select(
                    DashEncounter.enc_id,
                    DashEncounter.department,
                    DashEncounter.length_of_stay,
                    PatientFile.description,
                    PatientFile.content,
                    PatientFile.date,
                )
                .join(PatientFile, PatientFile.encounter_id == DashEncounter.id)
                .where(DashEncounter.department == selected_department)
            )

            bulk_encounters_data = pd.DataFrame(
                bulk_encounters_query.fetchall(),
                columns=list(bulk_encounters_query.keys()),
            )

    department_config = load_department_config()

    if department_prompt is None or post_processing_prompt is None:
        bulk_generation_df = bulk_generate(
            bulk_encounters_data,
            client=client,
            department_config=department_config,
        )
    else:
        bulk_generation_df = bulk_generate(
            bulk_encounters_data,
            client=client,
            department_config=department_config,
            department_prompt=department_prompt,
            post_processing_prompt=post_processing_prompt,
        )
    logger.info("Bulk generation of letters complete")

    if storage_location == "data/processed":
        bulk_generation_df.to_parquet(
            Path(processed_data_folder / "bulk_generated_docs_gpt.parquet")
        )
        logger.info('Bulk generated documents saved to "data/processed" folder')

    if storage_location == "database":
        with session_factory() as session:
            for _, row in bulk_generation_df.iterrows():
                enc_id = row["enc_id"]
                encounter_db = session.execute(
                    select(DashEncounter).where(DashEncounter.enc_id == str(enc_id))
                ).scalar_one_or_none()

                if not encounter_db:
                    logger.warning(
                        f"Encounter {enc_id} not found in database, skipping."
                    )
                    continue
                generated_doc_json = json.loads(row["generated_doc"])

                generated_doc = DischargeLetter(
                    generated_doc=generated_doc_json,
                    generation_time=row["generation_time"],
                    success_indicator=row["success_indicator"],
                    error_type=row["error_type"],
                )
                stored_doc_db = StoredDoc(
                    timestamp=pd.Timestamp.now(),
                    discharge_letter=str(
                        generated_doc.format(
                            format_type="plain",
                            manual_filtering=False,
                            include_generation_time=True,
                        )
                    ),
                    doc_type="AI",
                )
                encounter_db.stored_doc_relation.append(stored_doc_db)
                session.add(stored_doc_db)

            session.commit()
        logger.info("Bulk generated letters loaded into development database")
