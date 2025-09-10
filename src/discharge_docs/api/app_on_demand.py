import json
import logging
from datetime import datetime

from dotenv import load_dotenv
from fastapi import Depends, FastAPI
from fastapi.security.api_key import APIKeyHeader
from sqlalchemy.orm import Session

from discharge_docs.api.api_helper import ApiEndpoint, check_authorisation
from discharge_docs.api.pydantic_models import (
    HixInput,
    HixOutput,
    LLMOutput,
)
from discharge_docs.config import (
    DEPLOYMENT_NAME_ENV,
    TEMPERATURE,
    get_current_version,
    setup_root_logger,
)
from discharge_docs.database.models import (
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
    pre_process_hix_data,
    process_data,
)

logger = logging.getLogger(__name__)
setup_root_logger()

load_dotenv()

API_VERSION = get_current_version()

header_scheme = APIKeyHeader(name="API-KEY")


app = FastAPI()

client = initialise_azure_connection()

logger.info(f"Using deployment {DEPLOYMENT_NAME_ENV}")


def get_session():
    with Session(app.state.engine, autoflush=False) as session:
        yield session


@app.post(ApiEndpoint.PROCESS_HIX_DATA.value)
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
    data : HixInput
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
    check_authorisation(key, "X_API_KEY_HIX")

    start_time = datetime.now()
    request_db = Request(
        timestamp=start_time,
        response_code=500,
        api_version=API_VERSION,
        endpoint=ApiEndpoint.PROCESS_HIX_DATA.value,
    )
    db.add(request_db)
    db.commit()

    pre_processed_data = pre_process_hix_data(data)
    processed_data = process_data(pre_processed_data)
    processed_data = apply_deduce(processed_data, "content")

    patient_file_string, patient_df = get_patient_file(processed_data)
    department = patient_df["department"].values[0]

    end_time = datetime.now()
    runtime = (end_time - start_time).total_seconds()
    request_db.runtime = runtime
    request_db.response_code = 200
    db.commit()
    logger.info("Finished processing HiX data")

    return HixOutput(department=department, value=patient_file_string)


@app.post(ApiEndpoint.GENERATE_HIX_DOC.value)
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
    check_authorisation(key, "X_API_KEY_HIX")

    start_time = datetime.now()
    request_db = Request(
        timestamp=start_time,
        response_code=500,
        api_version=API_VERSION,
        endpoint=ApiEndpoint.GENERATE_HIX_DOC.value,
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
    logger.info("Finished generating discharge letter")

    return LLMOutput(message=discharge_letter)


@app.get("/")
@app.post("/")
async def root():
    """Root endpoint for the Discharge Docs on-demand API."""
    return {
        "message": "Discharge Docs on-demand API",
        "version": API_VERSION,
        "current_time": datetime.now().isoformat(),
        "llm_deployment": DEPLOYMENT_NAME_ENV,
        "llm_temperature": TEMPERATURE,
    }
