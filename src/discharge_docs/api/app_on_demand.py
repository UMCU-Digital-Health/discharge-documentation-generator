import json
import logging
import os
from datetime import datetime
from pathlib import Path

import pandas as pd
import tomli
from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException
from fastapi.security.api_key import APIKeyHeader
from sqlalchemy.orm import Session
from striprtf.striprtf import rtf_to_text

from discharge_docs.api.pydantic_models import (
    HixInput,
    HixOutput,
    LLMOutput,
)
from discharge_docs.config import DEPLOYMENT_NAME_ENV, TEMPERATURE
from discharge_docs.database.connection import get_connection_string, get_engine
from discharge_docs.database.models import (
    Base,
    Encounter,
    GeneratedDoc,
    Request,
    RequestGenerate,
)
from discharge_docs.llm.connection import initialise_azure_connection
from discharge_docs.llm.helper import format_generated_doc
from discharge_docs.llm.prompt import (
    load_prompts,
    load_template_prompt,
)
from discharge_docs.llm.prompt_builder import (
    ContextLengthError,
    GeneralError,
    JSONError,
    PromptBuilder,
)
from discharge_docs.processing.deduce_text import apply_deduce
from discharge_docs.processing.processing import (
    get_patient_file,
    process_data,
)

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
load_dotenv()

with open(Path(__file__).parents[3] / "pyproject.toml", "rb") as f:
    config = tomli.load(f)
API_VERSION = config["project"]["version"]

if not os.getenv("DB_USER"):
    logger.warning("Using debug SQLite database...")
    SQLALCHEMY_DATABASE_URL = "sqlite:///./sql_app.db"
    execution_options = {"schema_translate_map": {"discharge_aiva": None}}
else:
    SQLALCHEMY_DATABASE_URL = get_connection_string()
    execution_options = None

engine = get_engine(SQLALCHEMY_DATABASE_URL, execution_options)
Base.metadata.create_all(engine)

header_scheme = APIKeyHeader(name="API-KEY")


app = FastAPI()

client = initialise_azure_connection()

logger.info(f"Using deployment {DEPLOYMENT_NAME_ENV}")


def get_session():
    with Session(engine, autoflush=False) as session:
        yield session


@app.post("/process-hix-data")
async def process_hix_data(
    data: HixInput,
    db: Session = Depends(get_session),
    key: str = Depends(header_scheme),
) -> HixOutput:
    """Process the HIX data and return the processed data.

    This endpoint preocesses the HiX-data and pseudonomizes it using DEDUCE.
    It also transforms the data into a format that can be used by the
    generate-hix-discharge-docs endpoint.

    Parameters
    ----------
    data : HixPatientFile
        The HiX data to process.
    db : Session, optional
        The database session, by default Depends(get_db)
    key : str, optional
        The API key for authorization, by default Depends(header_scheme)

    Returns
    -------
    HixOutput
        The processed data, which can be send to the generate-hix-discharge-docs
        endpoint.
    """
    if key != os.environ["X_API_KEY_HIX"]:
        raise HTTPException(
            status_code=403, detail="You are not authorized to access this endpoint"
        )

    start_time = datetime.now()
    request_db = Request(
        timestamp=start_time,
        response_code=500,
        api_version=API_VERSION,
        endpoint="/proces_hix_data",
    )
    db.add(request_db)
    db.commit()

    validated_data = data.model_dump()
    data_df = pd.DataFrame.from_records(validated_data["ALLPARTS"]).rename(
        columns={
            "TEXT": "content",
            "NAAM": "description",
            "DATE": "date",
            "SPECIALISM": "department",
        },
    )
    data_df["content"] = data_df["content"].apply(rtf_to_text)
    processed_data = apply_deduce(data_df, "content")
    processed_data = processed_data[
        ["date", "department", "description", "content"]
    ].copy()
    processed_data.loc[:, "enc_id"] = "TEMP_ENC_ID"

    processed_data = process_data(processed_data)

    patient_file_string, patient_df = get_patient_file(processed_data)
    department = patient_df["department"].values[0]

    end_time = datetime.now()
    runtime = (end_time - start_time).total_seconds()
    request_db.runtime = runtime
    request_db.response_code = 200
    db.commit()

    return HixOutput(department=department, value=patient_file_string)


@app.post("/generate-hix-discharge-docs")
async def generate_hix_discharge_docs(
    data: HixOutput,
    db: Session = Depends(get_session),
    key: str = Depends(header_scheme),
) -> LLMOutput:
    """Generate discharge documentation for the given data using the GPT model.

    Parameters
    ----------
    data : HiXOutput
        The data to generate discharge documentation for.
    db : Session, optional
        The database session, by default Depends(get_db)
    key : str, optional
        The API key for authorization, by default Depends(header_scheme)

    Returns
    -------
    LLMOutput
        The generated discharge documentation.
    """
    if key != os.environ["X_API_KEY_HIX"]:
        raise HTTPException(
            status_code=403, detail="You are not authorized to access this endpoint"
        )

    start_time = datetime.now()
    request_db = Request(
        timestamp=start_time,
        response_code=500,
        api_version=API_VERSION,
        endpoint="/generate-hix-discharge-docs",
    )
    request_generate = RequestGenerate(request_relation=request_db)
    db.add(request_generate)
    db.commit()

    validated_data = data.model_dump()

    patient_file_string = validated_data["value"]
    department = validated_data["department"]

    template_prompt = load_template_prompt(department)

    prompt_builder = PromptBuilder(
        temperature=TEMPERATURE,
        deployment_name=DEPLOYMENT_NAME_ENV,
        client=client,
    )

    user_prompt, system_prompt = load_prompts()
    token_length = prompt_builder.get_token_length(
        patient_file_string, system_prompt, user_prompt, template_prompt
    )
    try:
        discharge_letter = prompt_builder.generate_discharge_doc(
            patient_file=patient_file_string,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            template_prompt=template_prompt,
        )
        discharge_letter_json = json.dumps(discharge_letter)
        discharge_letter = format_generated_doc(discharge_letter, format_type="plain")

        discharge_letter = (
            f"Deze brief is door AI gegenereerd op: "
            f"{start_time:%d-%m-%Y %H:%M}\n\n\n{discharge_letter}"
        )
        outcome = "Success"
    except (ContextLengthError, JSONError, GeneralError) as e:
        outcome = e.type
        discharge_letter = e.dutch_message

    encounter_db = Encounter(
        enc_id=None, patient_id=None, department=department, admissionDate=None
    )
    db.add(encounter_db)

    gendoc_db = GeneratedDoc(
        discharge_letter=discharge_letter_json,
        input_token_length=token_length,
        success_ind=outcome,
    )
    request_generate.generated_doc_relation.append(gendoc_db)
    encounter_db.gen_doc_relation.append(gendoc_db)
    db.add(gendoc_db)
    db.commit()

    end_time = datetime.now()
    runtime = (end_time - start_time).total_seconds()
    request_db.runtime = runtime
    request_db.response_code = 200
    db.commit()

    return LLMOutput(message=discharge_letter)


@app.get("/")
@app.post("/")
async def root():
    return {"message": "Hello World"}
