import json
import logging
import os
from datetime import datetime
from pathlib import Path

import pandas as pd
import tiktoken
import tomli
from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException, Security
from fastapi.security.api_key import APIKeyHeader
from openai import AzureOpenAI
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from discharge_docs.database.models import (
    ApiEncounter,
    ApiGeneratedDoc,
    ApiRequest,
    Base,
)
from discharge_docs.processing.processing import get_patient_file
from discharge_docs.prompts.prompt import (
    load_prompts,
    load_template_prompt,
)
from discharge_docs.prompts.prompt_builder import PromptBuilder

logger = logging.getLogger(__name__)
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


@app.post("/update-discharge-docs")
async def update_discharge_docs(
    daily_updates: list[dict],
    db: Session = Depends(get_db),
    api_key: str = Depends(check_api_key),
) -> dict:
    """For every encounter update the discharge documentation with the latest
    information.

    Parameters
    ----------
    daily_updates : list[dict]
        daily updates on patients in json-format,
        needs at least the following fields:
          end_id, department, date, value and description
    """
    start_time = datetime.now()
    daily_updates_df = pd.DataFrame.from_records(daily_updates)
    daily_updates_df["date"] = pd.to_datetime(daily_updates_df["date"])

    api_request = ApiRequest(
        timestamp=start_time,
        endpoint="/update-discharge-docs",
        api_version=API_VERSION,
    )

    prompt_builder = PromptBuilder(
        temperature=TEMPERATURE, deployment_name=deployment_name, client=client
    )

    user_prompt, system_prompt = load_prompts()

    for enc_id in daily_updates_df["enc_id"].unique():
        patient_file_string, patient_df = get_patient_file(daily_updates_df, enc_id)
        department = patient_df["department"].values[0]
        template_prompt = load_template_prompt(department)

        # Calculate token length, TODO add this to promptbuilder class
        encoding = tiktoken.get_encoding("cl100k_base")
        token_length = len(
            encoding.encode(
                patient_file_string + template_prompt + user_prompt + system_prompt
            )
        )

        discharge_letter = prompt_builder.generate_discharge_doc(
            patient_file=patient_file_string,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            template_prompt=template_prompt,
            addition_prompt=None,
        )

        api_encounter = ApiEncounter(
            encounter_hix_id=str(enc_id),
            department=department,
            input_token_length=token_length,
        )
        api_discharge_letter = ApiGeneratedDoc(
            discharge_letter=json.dumps(discharge_letter)
        )
        api_encounter.generated_doc_relation = api_discharge_letter
        api_request.encounter_relation.append(api_encounter)

    end_time = datetime.now()
    runtime = (end_time - start_time).total_seconds()
    api_request.runtime = runtime
    api_request.response_code = 200
    db.add(api_request)
    db.commit()
    return {"message": "Success"}


@app.get("/")
async def root():
    return {"message": "Hello World"}
