import json
import logging
from datetime import datetime
from pathlib import Path

import pandas as pd
import tomli
from dateutil.relativedelta import relativedelta
from dotenv import load_dotenv
from fastapi import Depends, FastAPI
from fastapi.responses import PlainTextResponse
from fastapi.security.api_key import APIKeyHeader
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from discharge_docs.api.api_helper import (
    ApiEndpoint,
    check_authorisation,
    process_retrieved_discharge_letters,
    remove_outdated_discharge_docs,
)
from discharge_docs.api.pydantic_models import MetavisionPatientFile
from discharge_docs.config import DEPLOYMENT_NAME_ENV, TEMPERATURE, setup_root_logger
from discharge_docs.database.connection import get_engine
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

setup_root_logger()
logger = logging.getLogger(__name__)
load_dotenv()

with open(Path(__file__).parents[3] / "pyproject.toml", "rb") as f:
    config = tomli.load(f)
API_VERSION = config["project"]["version"]

engine = get_engine()
Base.metadata.create_all(engine)

header_scheme = APIKeyHeader(name="X-API-KEY")

app = FastAPI()

client = initialise_azure_connection()

logger.info(f"Using deployment {DEPLOYMENT_NAME_ENV}")


def get_session():
    with Session(engine, autoflush=False) as session:
        yield session


@app.post(ApiEndpoint.PROCESS_GENERATE_DOC.value)
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
    check_authorisation(key, "X_API_KEY_generate")

    start_time = datetime.now()
    logger.info("Processing and generating endpoint called")
    request_db = Request(
        timestamp=start_time,
        response_code=500,
        api_version=API_VERSION,
        endpoint=ApiEndpoint.PROCESS_GENERATE_DOC.value,
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

        try:
            discharge_letter = prompt_builder.generate_discharge_doc(
                patient_file=patient_file_string,
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                template_prompt=template_prompt,
            )
            discharge_letter = json.dumps(discharge_letter)

            outcome = "Success"
        except (ContextLengthError, JSONError, GeneralError) as e:
            outcome = e.type
            discharge_letter = None

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
            success_ind=outcome,
        )
        requestgenerate.generated_doc_relation.append(gendoc_db)
        encounter_db.gen_doc_relation.append(gendoc_db)
        db.add(gendoc_db)
        db.commit()

        remove_outdated_discharge_docs(db, encounter_db.id)

    end_time = datetime.now()
    runtime = (end_time - start_time).total_seconds()
    request_db.runtime = runtime
    request_db.response_code = 200
    db.commit()

    logger.info("Processing and generating endpoint finished")
    return {
        "message": "Success",
    }


@app.get("/retrieve-discharge-doc/{enc_id}", response_class=PlainTextResponse)
@app.get(  # TODO remove this endpoint in the next release
    "/retrieve_discharge_doc/{enc_id}",
    response_class=PlainTextResponse,
    deprecated=True,
    operation_id="retrieve_discharge_doc_deprecated",
)
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
        The discharge document for the patient in plain text or a message.

    Raises
    ------
    HTTPException
        Raises a 403 error when the API key is not authorized.
    """
    check_authorisation(key, "X_API_KEY_retrieve")

    logger.info("Retrieve discharge doc endpoint called")

    start_time = datetime.now()
    request_db = Request(
        timestamp=start_time,
        response_code=500,
        api_version=API_VERSION,
        endpoint=ApiEndpoint.RETRIEVE_DISCHARGE_DOC.value,
    )

    requestretrieve = RequestRetrieve(
        request_enc_id=enc_id,
        request_relation=request_db,
    )
    db.add(requestretrieve)

    query = (
        select(
            GeneratedDoc.discharge_letter,
            GeneratedDoc.id,
            GeneratedDoc.success_ind,
            Encounter.enc_id,
            Encounter.patient_id,
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
            "patient_id",
            "timestamp",
        ],
    )

    message, success_ind, generated_doc_id, nr_days_old = (
        process_retrieved_discharge_letters(result_df)
    )
    requestretrieve.success_ind = success_ind
    requestretrieve.generated_doc_id = generated_doc_id
    requestretrieve.nr_days_old = nr_days_old

    end_time = datetime.now()
    runtime = (end_time - start_time).total_seconds()
    request_db.runtime = runtime
    request_db.response_code = 200
    db.commit()

    return message


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
    check_authorisation(key, "X_API_KEY_feedback")

    logger.info("Save feedback endpoint called")

    start_time = datetime.now()
    request_db = Request(
        timestamp=start_time,
        response_code=500,
        api_version=API_VERSION,
        endpoint=ApiEndpoint.SAVE_FEEDBACK.value,
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


@app.post(ApiEndpoint.REMOVE_ALL_DISCHARGE_DOCS.value)
async def remove_all_discharge_docs(
    n_months: int = 7,
    db: Session = Depends(get_session),
    key: str = Depends(header_scheme),
) -> dict:
    """Remove all discharge letters that have been generated n_months months ago, or
    longer.

    Parameters
    ----------
    n_months : int, optional
        The number of months ago the discharge letters should be removed, by default 7
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
    check_authorisation(key, "X_API_KEY_remove")

    logger.info("Remove all discharge docs endpoint called")

    start_time = datetime.now()
    request_db = Request(
        timestamp=start_time,
        response_code=500,
        api_version=API_VERSION,
        endpoint=ApiEndpoint.REMOVE_ALL_DISCHARGE_DOCS.value,
    )
    db.add(request_db)
    db.commit()

    query = (
        select(GeneratedDoc)
        .join(RequestGenerate, GeneratedDoc.request_generate_id == RequestGenerate.id)
        .join(Request, RequestGenerate.request_id == Request.id)
        .where(
            Request.timestamp < datetime.now() - relativedelta(months=n_months),
            GeneratedDoc.removed_timestamp.is_(None),
        )
    )

    docs_to_be_removed = db.execute(query).scalars().all()
    for doc in docs_to_be_removed:
        doc.discharge_letter = None
        doc.removed_timestamp = datetime.now()

    end_time = datetime.now()
    runtime = (end_time - start_time).total_seconds()
    request_db.runtime = runtime
    request_db.response_code = 200
    db.commit()

    if len(docs_to_be_removed) > 0:
        logger.info(f"Removed {len(docs_to_be_removed)} discharge docs")
        return {"message": "Success"}
    else:
        logger.warning("No discharge documents were found to remove")
        return {"message": "No matching discharge docs found"}


@app.get("/")
@app.post("/")
async def root():
    return {"message": "Hello World"}
