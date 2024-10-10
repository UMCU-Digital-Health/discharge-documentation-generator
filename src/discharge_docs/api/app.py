import logging
import os
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd
import tomli
from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException
from fastapi.responses import PlainTextResponse
from fastapi.security.api_key import APIKeyHeader
from openai import AzureOpenAI
from pydantic import BaseModel
from sqlalchemy import create_engine, delete, desc, select
from sqlalchemy.orm import Session, sessionmaker

from discharge_docs.dashboard.helper import format_generated_doc
from discharge_docs.database.models import (
    ApiEncounter,
    ApiFeedback,
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

header_scheme = APIKeyHeader(name="X-API-KEY")


class PatientFile(BaseModel):
    enc_id: int
    pseudo_id: str
    subject_Patient_value: str
    period_start: str
    location_Location_value_original: str
    effectiveDateTime: str
    valueString: str
    code_display_original: str


app = FastAPI()

client = AzureOpenAI(
    api_version="2024-02-01",
    api_key=os.getenv("AZURE_OPENAI_KEY", ""),
    azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT", ""),
)

with open(Path(__file__).parent / "deployment_config.toml", "rb") as f:
    deployment_config_dict = tomli.load(f)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@app.post("/process-and-generate-discharge-docs")
async def process_and_generate_discharge_docs(
    data: list[PatientFile],
    db: Session = Depends(get_db),
    key: str = Depends(header_scheme),
) -> dict:
    """Process the data and generate discharge documentation.
    Save this to database.

    Parameters
    ----------
    data : list[PatientFile]
        json data containing the patient data
    db : Session, optional
        database, by default Depends(get_db)
    key : str, optional
        api_key for authorization, by default Depends(header_scheme)

    Returns
    -------
    dict
        message and last generated discharge letter in the for loop (only relevant when
         a single discharge letter is generated)

    Raises
    ------
    HTTPException
        403 error when the api_key is not authorized
    """
    if key != os.environ["X_API_KEY_generate"]:
        raise HTTPException(
            status_code=403, detail="You are not authorized to access this endpoint"
        )

    start_time = datetime.now()

    validated_data = [item.model_dump() for item in data]
    data_df = pd.DataFrame.from_records(validated_data)

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

        if discharge_letter[0]["Categorie"] in [
            "LengthError",
            "JSONError",
            "GeneralError",
        ]:
            success = discharge_letter[0]["Categorie"]
            discharge_letter = discharge_letter[0]["Beloop tijdens opname"]

        else:
            discharge_letter = format_generated_doc(
                discharge_letter, format_type="plain"
            )

            discharge_letter = (
                "Deze brief is door AI gegenereerd voor patient "
                + str(patient_df["patient_number"].values[0])
                + " op: "
                + str(start_time.strftime("%Y-%m-%d %H:%M"))
                + "\n\n"
                + discharge_letter
            )
            success = "Success"

        api_encounter = db.execute(
            select(ApiEncounter).where(ApiEncounter.encounter_hix_id == str(enc_id))
        ).scalar_one_or_none()

        if not api_encounter:
            api_encounter = ApiEncounter(
                encounter_hix_id=str(enc_id),
                patient_number=str(patient_df["patient_number"].values[0]),
                department=department,
            )

        api_discharge_letter = ApiGeneratedDoc(
            discharge_letter=discharge_letter,
            input_token_length=token_length,
            success=success,
            generation_date=start_time,
        )
        api_encounter.generated_doc_relation.append(api_discharge_letter)
        api_request.encounter_relation.append(api_encounter)

    end_time = datetime.now()
    runtime = (end_time - start_time).total_seconds()
    api_request.runtime = runtime
    api_request.response_code = 200
    api_request.logging_number = str(len(processed_data["enc_id"].unique()))
    db.merge(api_request)
    db.commit()
    return {
        "message": "Success",
        "discharge_letter": discharge_letter,
    }


@app.post("/remove_old_discharge_docs")
async def remove_old_discharge_docs(
    max_date: datetime,
    db: Session = Depends(get_db),
    key: str = Depends(header_scheme),
) -> dict:
    """Remove old discharge documents from the database. This removes all discharge
    letters before the specified date given that there is no newly generated document
    after the specified date. Meaning only non-active patients will have their discharge
    letters removed.

    Parameters
    ----------
    max_date : datetime
        The maximum date for which discharge documents should be removed.
        Example format: YYYY-MM-DDT00:00:00
    db : Session, optional
        The database session, by default Depends(get_db)
    key : str, optional
        The API key for authorization, by default Depends(header_scheme)

    Returns
    -------
    dict
        A dictionary indicating the success of the operation.

    Raises
    ------
    HTTPException
        Raises a 403 error when the API key is not authorized.
    """
    if key != os.environ["X_API_KEY_remove"]:
        raise HTTPException(
            status_code=403, detail="You are not authorized to access this endpoint"
        )
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
    api_request.logging_number = str(rows_deleted.rowcount)
    db.add(api_request)
    db.commit()

    return {"message": "Success"}


@app.get("/retrieve_discharge_doc/{enc_id}", response_class=PlainTextResponse)
async def retrieve_discharge_doc(
    enc_id: str,
    db: Session = Depends(get_db),
    key: str = Depends(header_scheme),
    max_days_old: int = 7,
) -> str:
    """Retrieve the discharge document for a specific patient.

    Returns the discharge document and some additional information as plain text

    Parameters
    ----------
    enc_id : str
        The encounter ID of the patient.
        This is NOT the patient number 7-digit patient number.
    db : Session, optional
        The database session, by default Depends(get_db)
    key : str, optional
        The API key for authorization, by default Depends(header_scheme)
    max_days_old : int, optional
        The maximum number of days old the discharge document can be, by default 7

    Returns
    -------
    str
        The discharge document for the patient in plain text.

    Raises
    ------
    HTTPException
        Raises a 403 error when the API key is not authorized.
    """
    if key != os.environ["X_API_KEY_retrieve"]:
        raise HTTPException(
            status_code=403, detail="You are not authorized to access this endpoint"
        )
    start_time = datetime.now()
    api_request = ApiRequest(
        timestamp=datetime.now(),
        endpoint="/retrieve_discharge_doc",
        api_version=API_VERSION,
    )
    # initialize the logging number
    api_request.logging_number = "0"

    # Fetch the last 7 discharge letters for the given encounter ID
    query = (
        select(
            ApiGeneratedDoc.discharge_letter,
            ApiGeneratedDoc.encounter_id,
            ApiGeneratedDoc.id,
            ApiGeneratedDoc.success,
            ApiGeneratedDoc.generation_date,
        )
        .join(ApiEncounter, ApiGeneratedDoc.encounter_id == ApiEncounter.id)
        .where(ApiEncounter.encounter_hix_id == enc_id)
        .where(
            ApiGeneratedDoc.generation_date
            >= (datetime.now().date() - timedelta(days=max_days_old))
        )
        .order_by(desc(ApiGeneratedDoc.id))
    )

    result = db.execute(query).fetchall()

    result_df = pd.DataFrame(
        result,
        columns=[
            "discharge_letter",
            "encounter_id",
            "id",
            "success",
            "generation_date",
        ],
    )
    if result_df.empty:
        discharge_letter = (
            "Er is geen ontslagbrief in de database gevonden voor deze patiënt. "
            "Als dit onverwachts is, neem dan contact op met de key-users op "
            "jouw afdeling en/of met de afdeling Digital Health via "
            "ai-support@umcutrecht.nl"
        )

    else:
        # Get the most recent letter regardless of success
        latest_letter = result_df.iloc[0]

        # filter for the successful letters
        successful_letters = result_df[result_df["success"] == "Success"]

        if successful_letters.empty:
            discharge_letter = (
                "Er is geen successvolle AI-gegeneratie van de ontslagbrief geweest in "
                "de afgelopen 7 dagen voor deze patiënt."
            )
            if latest_letter["success"] == "LengthError":
                discharge_letter += (
                    " Dit komt doordat het patientendossier te lang is geworden voor "
                    "het dossier."
                )

        else:
            # Get the most recent successful letter
            latest_successful_letter = successful_letters.iloc[0]
            discharge_letter = latest_successful_letter["discharge_letter"]

            # add note if letter older than today is retrieved
            if (
                latest_successful_letter["generation_date"].date()
                < datetime.now().date()
            ):
                discharge_letter = (
                    "NB Let erop dat deze brief niet afgelopen nacht is gegenereerd."
                    + "\n\n"
                    + discharge_letter
                )

            api_request.logging_number = (
                f"{latest_successful_letter['encounter_id']}_"
                f"{latest_successful_letter['id']}"
            )

    # manually filter out [LEEFTIJD-1]-jarige from discharge letter as end users don't
    # want to read the age placeholder in every letter
    discharge_letter = discharge_letter.replace(" [LEEFTIJD-1]-jarige", "")

    api_request.response_code = 200
    api_request.runtime = (datetime.now() - start_time).total_seconds()

    db.add(api_request)
    db.commit()

    return discharge_letter


@app.post("/save-feedback/{feedback}")
async def save_feedback(
    feedback: str,
    db: Session = Depends(get_db),
    key: str = Depends(header_scheme),
) -> dict:
    """Save the feedback provided by the user.

    Parameters
    ----------
    feedback : str
        The feedback provided by the user. This is of the form: enc_id_feedback
        The feedback is 'ja' or 'nee' indicating whether the user agrees with the
        question whether the discharge letter helped them.
    db : Session, optional
        The database session, by default Depends(get_db)
    key : str, optional
        The API key for authorization, by default Depends(header_scheme)

    Returns
    -------
    dict
        A dictionary indicating the success of the operation.

    Raises
    ------
    HTTPException
        Raises a 403 error when the API key is not authorized.
    """
    if key != os.environ["X_API_KEY_feedback"]:
        raise HTTPException(
            status_code=403, detail="You are not authorized to access this endpoint"
        )

    start_time = datetime.now()

    api_request = ApiRequest(
        timestamp=start_time,
        endpoint="/save-feedback",
        api_version=API_VERSION,
    )

    api_feedback = ApiFeedback(
        feedback=feedback.split("_")[1], encounter_hix_id=int(feedback.split("_")[0])
    )

    api_request.feedback_relation.append(api_feedback)

    end_time = datetime.now()
    runtime = (end_time - start_time).total_seconds()
    api_request.runtime = runtime
    api_request.response_code = 200
    api_request.logging_number = "1"
    db.merge(api_request)
    db.commit()
    return {"message": "Success"}


@app.get("/")
async def root():
    return {"message": "Hello World"}
