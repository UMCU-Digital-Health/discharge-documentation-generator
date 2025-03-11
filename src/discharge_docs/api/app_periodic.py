import logging
import os
from datetime import datetime
from pathlib import Path

import pandas as pd
import tomli
from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException
from fastapi.responses import PlainTextResponse
from fastapi.security.api_key import APIKeyHeader
from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session

from discharge_docs.api.pydantic_models import MetavisionPatientFile
from discharge_docs.config import DEPLOYMENT_NAME_ENV, TEMPERATURE
from discharge_docs.dashboard.helper import format_generated_doc
from discharge_docs.database.connection import get_connection_string, get_engine
from discharge_docs.database.models import (
    Base,
    Encounter,
    FeedbackDetails,
    GeneratedDoc,
    Request,
    RequestFeedback,
    RequestGenerate,
    RequestRetrieve,
)
from discharge_docs.llm.connection import initialise_azure_connection
from discharge_docs.llm.prompt import (
    load_prompts,
    load_template_prompt,
)
from discharge_docs.llm.prompt_builder import PromptBuilder
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

header_scheme = APIKeyHeader(name="X-API-KEY")

app = FastAPI()

client = initialise_azure_connection()

logger.info(f"Using deployment {DEPLOYMENT_NAME_ENV}")


def get_session():
    with Session(engine, autoflush=False) as session:
        yield session


@app.post("/process-and-generate-discharge-docs")
async def process_and_generate_discharge_docs(
    data: list[MetavisionPatientFile],
    db: Session = Depends(get_session),
    key: str = Depends(header_scheme),
) -> dict:
    """Process the data and generate discharge documentation.

    Receives all the patient data and processes it to generate discharge documentation.
    The discharge documentation is generated using the GPT model and saved
    in the database.

    Parameters
    ----------
    data : list[PatientFile]
        The patient data to process and generate discharge documentation for.
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
    logger.info("Processing and generating endpoint called")
    request_db = Request(
        timestamp=start_time,
        response_code=500,
        api_version=API_VERSION,
        endpoint="/process-and-generate-discharge-docs",
    )

    requestgenerate = RequestGenerate(request_relation=request_db)
    db.add(requestgenerate)
    db.commit()

    validated_data = [item.model_dump() for item in data]
    data_df = pd.DataFrame.from_records(validated_data)

    processed_data = process_data(data_df)

    processed_data = apply_deduce(processed_data, "content")

    prompt_builder = PromptBuilder(
        temperature=TEMPERATURE,
        deployment_name=DEPLOYMENT_NAME_ENV,
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
                f"Deze brief is door AI gegenereerd voor patientnummer: "
                f"{patient_df['patient_id'].values[0]} op: "
                f"{start_time:%d-%m-%Y %H:%M}\n\n\n{discharge_letter}"
            )
            success = "Success"

        encounter_db = db.execute(
            select(Encounter).where(Encounter.enc_id == str(enc_id))
        ).scalar_one_or_none()

        if not encounter_db:
            encounter_db = Encounter(
                enc_id=str(enc_id),
                patient_id=str(patient_df["patient_id"].values[0]),
                department=department,
                admissionDate=patient_df["admissionDate"]
                .values[0]
                .astype("datetime64[s]")
                .astype(datetime),
            )
            db.add(encounter_db)

        gendoc_db = GeneratedDoc(
            discharge_letter=discharge_letter,
            input_token_length=token_length,
            success_ind=success,
        )
        requestgenerate.generated_doc_relation.append(gendoc_db)
        encounter_db.gen_doc_relation.append(gendoc_db)
        db.add(gendoc_db)
        db.commit()

    end_time = datetime.now()
    runtime = (end_time - start_time).total_seconds()
    request_db.runtime = runtime
    request_db.response_code = 200
    db.commit()

    logger.info("Processing and generating endpoint finished")
    return {
        "message": "Success",
    }


@app.get("/retrieve-discharge_doc/{enc_id}", response_class=PlainTextResponse)
async def retrieve_discharge_doc(
    enc_id: str,
    db: Session = Depends(get_session),
    key: str = Depends(header_scheme),
) -> str:
    """Retrieve the discharge document for a specific patient.

    Returns the discharge document and some additional information as plain text from
    the application database.

    Parameters
    ----------
    enc_id : str
        The encounter ID of the patient.
        This is NOT the patient number 7-digit patient number.
    db : Session, optional
        The database session, by default Depends(get_db)
    key : str, optional
        The API key for authorization, by default Depends(header_scheme)

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
    request_db = Request(
        timestamp=start_time,
        response_code=500,
        api_version=API_VERSION,
        endpoint="/retrieve-discharge-doc",
    )

    requestretrieve = RequestRetrieve(
        request_enc_id=enc_id,
        request_relation=request_db,
    )
    db.add(requestretrieve)

    # Fetch the last 7 discharge letters for the given encounter ID
    query = (
        select(
            GeneratedDoc.discharge_letter,
            GeneratedDoc.id,
            GeneratedDoc.success_ind,
            Encounter.enc_id,
            Request.timestamp,
        )
        .join(Encounter, GeneratedDoc.encounter_id == Encounter.id)
        .join(RequestGenerate, GeneratedDoc.request_generate_id == RequestGenerate.id)
        .join(Request, RequestGenerate.request_id == Request.id)
        .where(Encounter.enc_id == str(enc_id))
        .order_by(desc(Request.timestamp))
    )

    result = db.execute(query).fetchall()

    result_df = pd.DataFrame(
        result,
        columns=[
            "discharge_letter",
            "generated_doc_id",
            "success_ind",
            "enc_id",
            "timestamp",
        ],
    )
    if result_df.empty:
        returned_message = (
            "Er is geen ontslagbrief in de database gevonden voor deze patiënt. "
            "Dit komt voor bij patiënten in hun eerste 24 uur van de opname. "
            "Indien de patient nog is opgenomen, zal morgen een AI-ontslagbrief worden "
            "gegenereerd \n\n"
            "Als dit toch onverwachts is, neem dan contact op met de key-users op "
            "jouw afdeling en/of met de afdeling Digital Health via "
            "ai-support@umcutrecht.nl"
        )
        requestretrieve.success_ind = False
    else:
        # filter for the successful letters
        most_recent_successful_letter = result_df[
            result_df["success_ind"] == "Success"
        ].iloc[0]
        requestretrieve.success_ind = True

        # add note if letter older than today is retrieved
        nr_days_old = (
            datetime.now().date() - most_recent_successful_letter["timestamp"].date()
        ).days
        message_parts = []

        if nr_days_old > 0:
            if nr_days_old > 7:
                message_parts.append(
                    "NB Let erop dat deze AI-brief meer dan een week geleden is "
                    f"gegenereerd, namelijk {nr_days_old} dagen geleden.\n"
                )
            else:
                message_parts.append(
                    "NB Let erop dat deze AI-brief niet afgelopen nacht is gegenereerd,"
                    f" maar {nr_days_old} dagen geleden.\n"
                )
            if result_df.iloc[0]["success_ind"] == "LengthError":
                message_parts.append(
                    "Dit komt doordat het patientendossier te lang is geworden voor het"
                    " AI model.\n\n"
                )
            else:
                message_parts.append("\n\n")

        message_parts.append(f"{most_recent_successful_letter['discharge_letter']}")
        returned_message = "".join(message_parts)

        requestretrieve.generated_doc_id = int(
            most_recent_successful_letter["generated_doc_id"]
        )
        requestretrieve.nr_days_old = nr_days_old

    # manually filter out [LEEFTIJD-1]-jarige from message as it is a DEDUCE-placeholder
    returned_message = returned_message.replace(" [LEEFTIJD-1]-jarige", "")
    # IC letters only have one heading (beloop) so filter it out, NICU has others
    returned_message = returned_message.replace("\n\nBeloop\n", "\n\n")

    end_time = datetime.now()
    runtime = (end_time - start_time).total_seconds()
    request_db.runtime = runtime
    request_db.response_code = 200
    db.commit()

    return returned_message


@app.post("/save-feedback/{feedback}", response_class=PlainTextResponse)
async def save_feedback(
    feedback: str,
    db: Session = Depends(get_session),
    key: str = Depends(header_scheme),
) -> str:
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
    logger.info("Save feedback endpoint called")

    request_db = Request(
        timestamp=start_time,
        response_code=500,
        api_version=API_VERSION,
        endpoint="/save-feedback",
    )
    requestfeedback = RequestFeedback(
        request_enc_id=feedback.split("_")[0], request_relation=request_db
    )
    db.add(requestfeedback)
    db.commit()

    feedback_details = FeedbackDetails(
        feedback_question="Heeft deze AI brief jou geholpen?",
        feedback_answer=feedback.split("_")[1],
    )
    requestfeedback.feedback_relation.append(feedback_details)
    db.add(feedback_details)

    end_time = datetime.now()
    runtime = (end_time - start_time).total_seconds()
    request_db.runtime = runtime
    request_db.response_code = 200
    db.commit()

    return "success"


@app.post("/remove-outdated-discharge-docs")
async def remove_outdated_discharge_docs(
    enc_ids: list[int],
    db: Session = Depends(get_session),
    key: str = Depends(header_scheme),
) -> dict:
    """Remove the outdated discharge letters for the given encounters.
    Outdated discharge letters are those which are replaced by a newer succesfully
    generated version of the discharge letter.
    This function is called periodically to remove outdated discharge letters.

    Parameters
    ----------
    enc_ids : list[int]
        The encounter IDs of the patients to remove the outdated discharge letters for.
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
    logger.info("Remove outdated discharge docs endpoint called")

    start_time = datetime.now()
    request_db = Request(
        timestamp=start_time,
        response_code=500,
        api_version=API_VERSION,
        endpoint="/remove-outdated-discharge-docs",
    )
    db.add(request_db)
    db.commit()

    # Get encounter records matching the provided enc_ids
    encounters = (
        db.execute(select(Encounter).where(Encounter.enc_id.in_(enc_ids)))
        .scalars()
        .all()
    )

    if not encounters:
        logger.warning(
            "No matching encounters found when trying to remove outdated docs"
        )
        return {"message": "No matching encounters found"}

    # Extract the Encounter database primary keys for these encounters
    encounter_db_ids = [enc.id for enc in encounters]

    # Define the subquery to get the latest document for each encounter
    latest_doc_subquery = (
        select(
            GeneratedDoc.encounter_id, func.max(GeneratedDoc.id).label("latest_doc_id")
        )
        .where(
            GeneratedDoc.encounter_id.in_(encounter_db_ids),
            GeneratedDoc.success_ind == "Success",
        )
        .group_by(GeneratedDoc.encounter_id)
        .subquery()
    )

    # Define the main query to fetch outdated documents
    outdated_docs_query = (
        select(GeneratedDoc)
        .join(
            latest_doc_subquery,
            GeneratedDoc.encounter_id == latest_doc_subquery.c.encounter_id,
        )
        .where(GeneratedDoc.id != latest_doc_subquery.c.latest_doc_id)
    )

    # Execute the query
    outdated_docs = db.execute(outdated_docs_query).scalars().all()

    # Remove outdated discharge letters
    for doc in outdated_docs:
        doc.discharge_letter = None
        doc.removed_timestamp = datetime.now()

    end_time = datetime.now()
    runtime = (end_time - start_time).total_seconds()
    request_db.runtime = runtime
    request_db.response_code = 200
    db.commit()

    return {"message": "Success"}


@app.post("/remove-all-discharge-docs")
async def remove_all_discharge_docs(
    enc_ids: list[int],
    db: Session = Depends(get_session),
    key: str = Depends(header_scheme),
) -> dict:
    """Remove all discharge letters for the given encounters. This endpoint is used once
    a patient has been discharged and the AI generated draft discharge letter is no
    longer needed/used after a set period of time.

    Parameters
    ----------
    enc_ids : list[int]
        The encounter IDs of the patients to remove the discharge letters for.
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
    logger.info("Remove all discharge docs endpoint called")
    start_time = datetime.now()
    request_db = Request(
        timestamp=start_time,
        response_code=500,
        api_version=API_VERSION,
        endpoint="/remove-all-discharge-docs",
    )
    db.add(request_db)
    db.commit()

    # Get encounter records matching the provided enc_ids
    encounters = (
        db.execute(select(Encounter).where(Encounter.enc_id.in_(enc_ids)))
        .scalars()
        .all()
    )
    if not encounters:
        logger.warning("No matching encounters found when trying to remove docs")
        return {"message": "No matching encounters found"}

    # Extract the Encounter database primary keys for these encounters
    encounter_db_ids = [enc.id for enc in encounters]

    # Get all discharge documents for the encounters
    all_docs = (
        db.execute(
            select(GeneratedDoc).where(GeneratedDoc.encounter_id.in_(encounter_db_ids))
        )
        .scalars()
        .all()
    )

    # Remove all discharge letters
    for doc in all_docs:
        doc.discharge_letter = None
        doc.removed_timestamp = datetime.now()

    end_time = datetime.now()
    runtime = (end_time - start_time).total_seconds()
    request_db.runtime = runtime
    request_db.response_code = 200
    db.commit()

    return {"message": "Success"}


@app.get("/")
@app.post("/")
async def root():
    return {"message": "Hello World"}
