import json
import logging
import os
import traceback
from datetime import datetime
from pathlib import Path

import pandas as pd
import tomli
from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException, Security
from fastapi.security.api_key import APIKeyHeader
from openai import AzureOpenAI
from sqlalchemy import create_engine, delete, select
from sqlalchemy.orm import Session, sessionmaker

from discharge_docs.database.models import (
    ApiEncounter,
    ApiGeneratedDoc,
    ApiRequest,
    Base,
)
from discharge_docs.processing.deduce_text import apply_deduce
from discharge_docs.processing.processing import (
    get_patient_file,
    process_data_metavision_dp,
)
from discharge_docs.prompts.prompt import (
    load_prompts,
    load_template_prompt,
)
from discharge_docs.prompts.prompt_builder import PromptBuilder

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
load_dotenv()

with open(Path(__file__).parents[3] / "pyproject.toml", "rb") as f:
    config = tomli.load(f)
API_VERSION = config["project"]["version"]

DB_USER = os.getenv("DB_USER", "")
DB_PASSWD = os.getenv("DB_PASSWD", "")
DB_HOST = os.getenv("DB_HOST", "")
DB_PORT = os.getenv("DB_PORT", 1433)
DB_DATABASE = os.getenv("DB_DATABASE", "")

if DB_USER == "":
    logger.warning("Using debug SQLite database...")
    SQLALCHEMY_DATABASE_URL = "sqlite:///./sql_app.db"
    execution_options = {"schema_translate_map": {"discharge_aiva": None}}
else:
    SQLALCHEMY_DATABASE_URL = (
        rf"mssql+pymssql://{DB_USER}:{DB_PASSWD}@{DB_HOST}:{DB_PORT}/{DB_DATABASE}"
    )
    execution_options = None

engine = create_engine(SQLALCHEMY_DATABASE_URL, execution_options=execution_options)
Base.metadata.create_all(engine)
SessionLocal = sessionmaker(bind=engine)

api_key_header = APIKeyHeader(name="X-API-KEY", auto_error=False)

app = FastAPI()

TEMPERATURE = 0.2
deployment_name = "aiva-gpt"

client = AzureOpenAI(
    api_version="2024-02-01",
    api_key=os.getenv("AZURE_OPENAI_KEY", ""),
    azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT", ""),
)

with open(Path(__file__).parent / "deployment_config.toml", "rb") as f:
    deployment_config_dict = tomli.load(f)


def get_db():
    try:
        db = SessionLocal()
        yield db
        db.close()
    except Exception as e:
        print(e)


def check_api_key(api_key_header: str = Security(api_key_header)) -> str:
    if api_key_header == os.getenv("X_API_KEY", ""):
        return api_key_header
    else:
        raise HTTPException(403, "Unauthorized, Api Key not valid")


@app.post("/process-and-generate-discharge-docs")
async def process_and_generate_discharge_docs(
    data: list[dict],
    db: Session = Depends(get_db),
    api_key: str = Depends(check_api_key),
) -> dict:
    """For every encounter update the discharge documentation with the latest
    information.

    Parameters
    ----------
    daily_updates : list[dict]
        raw export of patient data in json-format,
        needs at least the following fields:
          TODO ADD FIELDS
    """
    try:
        start_time = datetime.now()

        data_df = pd.DataFrame.from_records(data)

        processed_data = process_data_metavision_dp(data_df, nifi=True)

        processed_data = apply_deduce(processed_data, "value")

        api_request = ApiRequest(
            timestamp=start_time,
            endpoint="/update-discharge-docs",
            api_version=API_VERSION,
        )

        prompt_builder = PromptBuilder(
            temperature=deployment_config_dict["TEMPERATURE"],
            deployment_name=deployment_config_dict["deployment_name"],
            client=client,
        )
        user_prompt, system_prompt = load_prompts()

        for enc_id in processed_data["enc_id"].unique():
            patient_file_string, patient_df = get_patient_file(processed_data, enc_id)
            department = patient_df["department"].values[0]
            template_prompt = load_template_prompt(department)

            token_length = prompt_builder.get_token_length(
                patient_file_string, system_prompt, user_prompt, template_prompt
            )

            logger.info(
                f"Generating discharge doc for encounter {enc_id} "
                f"and department {department}..."
            )

            discharge_letter = prompt_builder.generate_discharge_doc(
                patient_file=patient_file_string,
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                template_prompt=template_prompt,
            )

            discharge_letter.insert(
                0,
                {
                    "Categorie": "Datum gegenereerd",
                    "Beloop tijdens opname": "Deze brief is gegenereerd door AI op: "
                    + str(datetime.now().strftime("%Y-%m-%d %H:%M")),
                },
            )

            api_encounter = db.execute(
                select(ApiEncounter).where(ApiEncounter.encounter_hix_id == str(enc_id))
            ).scalar_one_or_none()

            if not api_encounter:
                api_encounter = ApiEncounter(
                    encounter_hix_id=str(enc_id),
                    patient_number=str(patient_df["patient_number"].values[0]),
                    department=department,
                )
            else:
                pass

            api_discharge_letter = ApiGeneratedDoc(
                discharge_letter=json.dumps(discharge_letter),
                input_token_length=token_length,
            )
            api_encounter.generated_doc_relation.append(api_discharge_letter)
            api_request.encounter_relation.append(api_encounter)

        end_time = datetime.now()
        runtime = (end_time - start_time).total_seconds()
        api_request.runtime = runtime
        api_request.response_code = 200
        db.merge(api_request)
        db.commit()

    except Exception as e:
        tb = traceback.format_exc()
        logger.error(f"Error in update_discharge_docs: {e}\n{tb}")
        raise HTTPException(500, "Internal Server Error") from e
    return {"message": "Success"}


@app.post("/remove_old_discharge_docs")
async def remove_old_discharge_docs(
    max_date: datetime,
    db: Session = Depends(get_db),
    api_key: str = Depends(check_api_key),
) -> dict:
    """Remove all discharge documentation generated before the given date.

    Parameters
    ----------
    max_date : datetime
        The maximum date for which discharge documentation should be kept.
        Example format: YYYY-MM-DDT00:00:00
    """
    start_time = datetime.now()
    api_request = ApiRequest(
        timestamp=datetime.now(),
        endpoint="/remove_old_discharge_docs",
        api_version=API_VERSION,
    )

    # Get IDs of all ApiDischargeDocs that are older than max_date
    encounter_id_subquery = (
        select(ApiEncounter.id)
        .join(ApiRequest)
        .where(ApiRequest.timestamp < max_date)
        .scalar_subquery()
    )

    # Delete all ApiDischargeDocs that are older than max_date
    rows_deleted = db.execute(
        delete(ApiGeneratedDoc).where(
            ApiGeneratedDoc.encounter_id.in_(encounter_id_subquery)
        )
    )
    logger.warning(f"Deleted {rows_deleted.rowcount} rows from ApiGeneratedDoc")

    api_request.response_code = 200
    api_request.runtime = (datetime.now() - start_time).total_seconds()
    db.add(api_request)
    db.commit()

    return {"message": "Success"}


@app.get("/")
async def root():
    return {"message": "Hello World"}
