import json
import logging
import random
import re
import tomllib
from pathlib import Path
from typing import Union

import pandas as pd
from dash import html
from flask import Request
from sqlalchemy import select
from sqlalchemy.orm import sessionmaker

from discharge_docs.config import (
    DEPLOYMENT_NAME_BULK,
    TEMPERATURE,
    AuthConfig,
)
from discharge_docs.config_models import DepartmentConfig
from discharge_docs.database.models import DashEncounter, PatientFile, StoredDoc
from discharge_docs.llm.connection import initialise_azure_connection
from discharge_docs.llm.helper import DischargeLetter
from discharge_docs.llm.prompt_builder import (
    PromptBuilder,
)
from discharge_docs.processing.processing import (
    get_patient_file,
)

logger = logging.getLogger(__name__)


def highlight(
    text: Union[str, list],
    selected_words: str,
    mark_color: str = "yellow",
    text_color: str = "black",
) -> list:
    """Highlight selected words in the given text.

    Parameters
    ----------
    text : str or list
        The text or list of texts to be highlighted.
    selected_words : str
        The words to be highlighted in the text.

    Returns
    -------
    list
        The text with the selected words highlighted.
    """
    if isinstance(text, str):
        sequences = re.split(re.escape(selected_words), text, flags=re.IGNORECASE)
        i = 1
        while i < len(sequences):
            sequences.insert(
                i,
                html.Mark(
                    selected_words.upper(),
                    style={"backgroundColor": mark_color, "color": text_color},
                ),
            )
            i += 2
        # Can contain empty strings if the selected word is at the start or end
        sequences = [s for s in sequences if s != ""]
        return sequences
    else:
        for i, t in enumerate(text):
            if isinstance(t, str):
                text[i] = highlight(t, selected_words, mark_color, text_color)
        flat_list = []

        for sublist in text:
            if isinstance(sublist, list):
                for item in sublist:
                    flat_list.append(item)
            else:
                flat_list.append(sublist)
        return flat_list


def replace_newlines(elements: str | list) -> list:
    """Replace newlines in a string with html.Br().

    Parameters
    ----------
    elements : str | list
        The elements to be processed.

    Returns
    -------
    list
        The elements with newlines replaced by html.Br().
    """
    if isinstance(elements, str):
        elements = [elements]
    new_elements = []
    for element in elements:
        if isinstance(element, str):
            # Split the string on new line and intersperse html.Br()
            parts = element.split("\n")
            for part in parts:
                new_elements.append(part)
                new_elements.append(html.Br())
        else:
            # Assume it is an HTML component and append directly
            new_elements.append(element)
    return new_elements


def load_enc_ids() -> dict[str, list[int]]:
    """Load the encounter IDs for the evaluation dashboard from the TOML file.

    Returns
    -------
    dict
        A dictionary containing the encounter IDs in the format
        {"department": [list of enc_ids]}
    """
    with open(
        Path(__file__).parent / "enc_ids.toml",
        "rb",
    ) as f:
        data = tomllib.load(f)
        return {key: value["ids"] for key, value in data.items()}


def get_user(req: Request) -> str | None:
    """
    Get the user email from RStudio credentials in the request headers.

    Parameters
    ----------
    req : Request
        The request object containing headers.

    Returns
    -------
    str | None
        The user's email address if found, otherwise None.
    """
    credential_header = req.headers.get("RStudio-Connect-Credentials")
    if not credential_header:
        logger.warning("No credentials found in request headers")
        return None

    credential_header = json.loads(credential_header)
    user = credential_header.get("user").lower()
    return user


def get_authorization(
    req: Request, authorization_config: AuthConfig, development_authorizations: list
) -> tuple[str | None, list[str]]:
    """
    Get the user's email and authorization groups from the request headers and config.

    Credentials are expected in the form: {user: "email", groups: ["group1", ...]}
    If no credentials are found, development mode is used.

    Parameters
    ----------
    req : Request
        The request object containing headers.
    authorization_config : AuthConfig
        The configuration object containing user authorization information.
    development_authorizations : list
        A list of authorization groups for development mode.

    Returns
    -------
    tuple[str | None, list[str]]
        A tuple containing:
        - The user's email (or 'Development user'/None)
        - A list of authorization groups
    """
    user = get_user(req)
    if user is None:
        logger.warning("Running in development mode, overriding authorization group.")
        return "Development user", development_authorizations

    for value in authorization_config.users.values():
        if value.email == user:
            if value.full_access:
                logger.info(f"User {user} has full access.")
                return user, development_authorizations
            else:
                return user, value.groups

    logger.warning(f"No authorization groups found for user {user}")
    return None, []


def query_patient_file(
    patient_admission_id: str, session_factory: sessionmaker
) -> pd.DataFrame:
    """
    Query the patient file from the database for a specific patient admission ID.

    Parameters
    ----------
    patient_admission_id : int
        The identifier of the patient admission.
    session : Sessionmaker
        The database session maker.

    Returns
    -------
    pd.DataFrame
        The DataFrame containing the patient file data.
    """

    with session_factory() as session:
        patient_file = session.execute(
            select(PatientFile.description, PatientFile.content, PatientFile.date)
            .join(DashEncounter, PatientFile.encounter_id == DashEncounter.id)
            .where(DashEncounter.enc_id == int(patient_admission_id))
        )
        patient_file = pd.DataFrame(
            patient_file.fetchall(), columns=list(patient_file.keys())
        )
    return patient_file


def query_stored_doc(
    patient_admission_id: str, selected_doc_type: str, session_factory: sessionmaker
) -> pd.DataFrame:
    """
    Query the stored document from the database for a specific patient admission ID.

    Parameters
    ----------
    patient_admission_id : int
        The identifier of the patient admission.
    selected_doc_type : str
        The type of document to retrieve (AI or Human)
    session : Sessionmaker
        The database session maker.

    Returns
    -------
    pd.DataFrame
        The DataFrame containing the patient file data.
    """

    with session_factory() as session:
        stored_doc = session.execute(
            select(StoredDoc.discharge_letter, StoredDoc.timestamp)
            .join(DashEncounter, StoredDoc.encounter_id == DashEncounter.id)
            .where(DashEncounter.enc_id == int(patient_admission_id))
            .where(StoredDoc.doc_type == selected_doc_type)
            .order_by(StoredDoc.timestamp.desc())
        )
        stored_doc = pd.DataFrame(
            stored_doc.fetchall(), columns=list(stored_doc.keys())
        )
    return stored_doc


def get_data_from_patient_admission(
    patient_admission: str | int, data: pd.DataFrame
) -> pd.DataFrame:
    """
    Get the data for a specific patient admission from the DataFrame.

    Parameters
    ----------
    patient_admission : str | int
        The identifier of the patient admission (converted to int).
    data : pd.DataFrame
        The DataFrame containing patient admissions.

    Returns
    -------
    pd.DataFrame
        The subset of data associated with the patient admission.
    """
    if int(patient_admission) not in data["enc_id"].unique():
        logger.warning(f"Patient admission {patient_admission} not found in data")

    return data[data["enc_id"] == int(patient_admission)]


def get_department_prompt(
    patient_admission: str,
    development_admissions: pd.DataFrame,
    department_config: DepartmentConfig,
) -> tuple[str, str]:
    """
    Get the department prompt and department for a patient admission.

    Parameters
    ----------
    patient_admission : str
        The identifier of the patient admission.
    development_admissions : pd.DataFrame
        The DataFrame containing development admissions data and their departments.
    department_config : DepartmentConfig
        The department configuration object.

    Returns
    -------
    tuple[str, str]
        A tuple containing:
        - The department prompt for the patient admission
        - The department name for the patient admission
    """
    department = development_admissions.loc[
        development_admissions["enc_id"] == int(patient_admission), "department"
    ].values[0]
    return department_config.department[department].department_prompt, department


def get_patients_values(data: pd.DataFrame) -> dict[str, list[dict[str, str]]]:
    """
    Get a dictionary of patient values for dropdowns, grouped by department.

    Parameters
    ----------
    data : pd.DataFrame
        The DataFrame containing encounter information.

    Returns
    -------
    dict
        Dictionary with department names as keys and lists of patient dropdown
        values as values.
    """
    values_list = {}

    for department in data.department.unique():
        patients_list = []
        department_data = data[data["department"] == department]
        for idx, (_, row) in enumerate(department_data.iterrows(), start=1):
            text_block = (
                f"Patiënt {idx} ({department} {row['length_of_stay']} dagen) "
                f"[Opname {row['enc_id']}] [Patiëntnummer {int(row['patient_number'])}]"
            )
            patients_list.append(
                {
                    "label": text_block,
                    "value": row["enc_id"],
                }
            )

        if patients_list:
            values_list[department] = patients_list

    return values_list


def load_stored_discharge_letters(
    df: pd.DataFrame, selected_enc_id: str
) -> DischargeLetter:
    """
    Load discharge letters for a specific patient encounter from a DataFrame.

    Parameters
    ----------
    df : pd.DataFrame
        The DataFrame containing discharge letters data.
    selected_enc_id : str
        The encounter ID of the patient.

    Returns
    -------
    DischargeLetter
        The stored discharge letter object for the patient. Returns a default
        message if not found.
    """
    if int(selected_enc_id) not in df["enc_id"].values:
        return DischargeLetter(
            {
                "Geen Vooraf Gegenereerde Ontslagbrief Beschikbaar": (
                    "Er is geen opgeslagen documentatie voor deze patiënt."
                )
            },
            None,
            False,
            None,
        )

    stored_patient = df.loc[df["enc_id"] == int(selected_enc_id)].iloc[0]
    generation_time = stored_patient["generation_time"]
    discharge_document = json.loads(stored_patient["generated_doc"])

    return DischargeLetter(discharge_document, generation_time, success_indicator=True)


def get_department(selected_patient_admission: int, enc_ids_dict: dict) -> str:
    """
    Return the department name for a given patient admission encounter ID.

    Parameters
    ----------
    selected_patient_admission : int
        The encounter ID of the selected patient admission.
    enc_ids_dict : dict
        Dictionary mapping department names to lists of encounter IDs.

    Returns
    -------
    str
        The department name associated with the selected patient admission.
    """
    for dep, enc_ids in enc_ids_dict.items():
        if selected_patient_admission in enc_ids:
            return dep
    raise ValueError("Department not found for given patient admission.")


def remove_conclusion(doc: str | None) -> str | None:
    """Remove the 'Conclusie' section from the discharge letter JSON.

    Parameters
    ----------
    doc : str | None
        The discharge letter JSON as a string.

    Returns
    -------
    str | None
        The discharge letter JSON without the 'Conclusie' section,
        or None if input is None.
    """
    if doc is None:
        return None
    try:
        doc_json = json.loads(doc)
        if "Conclusie" in doc_json.keys():
            del doc_json["Conclusie"]
        return json.dumps(doc_json)
    except ValueError:
        logger.error("Failed to parse discharge letter JSON.")
        return doc


def _filter_large_encounters(encounter_df: pd.DataFrame) -> pd.DataFrame:
    """Filter out encounters that exceed the token limit for the LLM."""
    prompt_builder = PromptBuilder(
        temperature=TEMPERATURE,
        deployment_name=DEPLOYMENT_NAME_BULK,
        client=initialise_azure_connection(),
    )
    big_encounters = []
    for enc_id in encounter_df["enc_id"].unique():
        patient_file, _ = get_patient_file(encounter_df, enc_id=enc_id)
        token_length = prompt_builder.get_token_length(
            patient_file=patient_file,
            system_prompt="",
            general_prompt="",
            department_prompt="",
        )
        if token_length > prompt_builder.max_context_length - 5000:
            big_encounters.append(enc_id)
            logger.info(
                f"Encounter {enc_id} has token length {token_length}, "
                "removing from selection."
            )
    return encounter_df[~encounter_df["enc_id"].isin(big_encounters)]


def select_encounter_ids(
    encounter_df: pd.DataFrame,
    n_enc_ids: int,
    selection: str = "random",
    length_of_stay_cutoff: int | None = None,
    encounters_to_include: list[int] | None = None,
) -> list[int]:
    """
    Selects the encounter IDs for a given department for use in the pipeline.

    This function filters out encounters that exceed the token limit for the LLM
    and selects a specified number of encounter IDs based on the selection method.
    It can also include specific encounter IDs regardless of other selection criteria.

    Parameters
    ----------
    encounter_df : pd.DataFrame
        The DataFrame containing the encounter data.
    n_enc_ids : int
        The number of encounter IDs to keep per department.
    selection : str, optional
        The method to select encounters, by default random.
        Options are:
        - random: Randomly select encounters.
        - balanced: Select 50% long stays and 50% short stays.
    length_of_stay_cutoff : int, optional
        The cutoff for length of stay to differentiate between long and short stays.
    encounters_to_include : list[int] | None
        Specific encounter IDs to include, regardless of other selection criteria.

    Returns
    -------
    list[int]
        A list of selected encounter IDs.
    """
    if selection not in ["random", "balanced"]:
        raise ValueError(f"Selection {selection} not recognized")
    if encounter_df["department"].nunique() > 1:
        raise ValueError("DataFrame contains multiple departments.")
    if selection == "balanced" and length_of_stay_cutoff is None:
        raise ValueError(
            "Length of stay cutoff must be provided for balanced selection."
        )

    encounter_df = _filter_large_encounters(encounter_df)

    enc_ids = encounter_df["enc_id"].unique()
    if len(enc_ids) <= n_enc_ids:
        logger.warning(
            f"Only {len(enc_ids)} encounter IDs available, "
            f"requested {n_enc_ids}. Returning all available IDs."
        )
        return enc_ids.tolist()

    selected_enc_ids = []
    if encounters_to_include:
        selected_enc_ids = list(set(encounters_to_include) & set(enc_ids))
    remaining_enc_ids = list(set(enc_ids) - set(selected_enc_ids))
    encs_to_sample = n_enc_ids - len(selected_enc_ids)
    if not remaining_enc_ids:
        logger.warning("No remaining encounter IDs to select from.")
        return selected_enc_ids
    if encounters_to_include and set(selected_enc_ids) != set(encounters_to_include):
        logger.warning(
            f"Not all specified encounters were present in data, encounters not found: "
            f"{set(encounters_to_include) - set(selected_enc_ids)}"
        )

    if selection == "random":
        random_enc_ids = random.sample(
            remaining_enc_ids,
            k=encs_to_sample,
        )
        return selected_enc_ids + random_enc_ids

    else:  # balanced
        long_encs = encounter_df.loc[
            encounter_df["length_of_stay"] >= length_of_stay_cutoff, "enc_id"
        ].unique()

        short_encs = encounter_df.loc[
            encounter_df["length_of_stay"] < length_of_stay_cutoff, "enc_id"
        ].unique()

        long_encs = list(set(long_encs) & set(remaining_enc_ids))
        short_encs = list(set(short_encs) & set(remaining_enc_ids))

        if (
            len(long_encs) < encs_to_sample // 2
            or len(short_encs) < encs_to_sample // 2
        ):
            logger.warning(
                "Not enough encounters in one of the length of stay categories "
                "to perform balanced sampling. Falling back to random sampling."
            )
            random_enc_ids = random.sample(
                remaining_enc_ids,
                k=encs_to_sample,
            )
            return selected_enc_ids + random_enc_ids

        # If encs_to_sample is odd, then sample one extra from long_encs
        long_encs_sample = random.sample(
            long_encs, k=encs_to_sample // 2 + encs_to_sample % 2
        )
        short_encs_sample = random.sample(short_encs, k=encs_to_sample // 2)

        return selected_enc_ids + long_encs_sample + short_encs_sample


def get_development_admissions(
    authorization_group, session_factory: sessionmaker
) -> pd.DataFrame:
    with session_factory() as session:
        development_admissions = session.execute(
            select(
                DashEncounter.patient_number,
                DashEncounter.enc_id,
                DashEncounter.department,
                DashEncounter.length_of_stay,
            ).where(DashEncounter.department.in_(authorization_group))
        )
        development_admissions = pd.DataFrame(
            development_admissions.fetchall(),
            columns=list(development_admissions.keys()),
        )
        return development_admissions


def validate_enc_list(string_list: str) -> None | list[int]:
    """Validate and parse a comma-separated string of encounter IDs.

    Parameters
    ----------
    enc_list : str
        Comma-separated string of encounter IDs.

    Returns
    -------
    None | list[int]
        List of valid encounter IDs as integers, or None if the input string is empty.

    Raises
    ------
    ValueError
        If any of the encounter IDs are not valid integers.
    """
    if string_list.strip() == "":
        return None
    try:
        enc_ids = [int(enc_id.strip()) for enc_id in string_list.split(",")]
        return enc_ids
    except ValueError as e:
        raise ValueError("Encounter IDs must be integers.") from e
