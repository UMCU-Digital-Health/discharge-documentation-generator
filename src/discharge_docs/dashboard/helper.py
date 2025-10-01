import json
import logging
import re
import tomllib
from pathlib import Path
from typing import Union

import pandas as pd
from dash import html
from flask import Request

from discharge_docs.config import AuthConfig
from discharge_docs.config_models import DepartmentConfig
from discharge_docs.llm.helper import DischargeLetter, generate_single_doc
from discharge_docs.llm.prompt_builder import (
    ContextLengthError,
    GeneralError,
    JSONError,
    PromptBuilder,
)
from discharge_docs.processing.processing import get_patient_file

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
            return user, value.groups

    logger.warning(f"No authorization groups found for user {user}")
    return None, []


def get_authorized_patients(
    authorization_group: list, patients: dict
) -> tuple[list, str | None]:
    """
    Get authorized patients based on the user's authorization group.

    Parameters
    ----------
    authorization_group : list
        The list of authorization groups for the user.
    patients : dict
        A dictionary containing patient data per department.

    Returns
    -------
    tuple[list, str | None]
        A tuple containing:
        - The list of authorized patients for the user
        - The value of the first patient (or None if no patients)
    """
    authorized_patients = [
        item
        for key, values in patients.items()
        if key in authorization_group
        for item in values
    ]

    first_patient = authorized_patients[0]["value"] if authorized_patients else None

    return authorized_patients, str(first_patient)


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
    patient_admission: str, enc_ids_dict: dict, department_config: DepartmentConfig
) -> tuple[str, str]:
    """
    Get the department prompt and department for a patient admission.

    Parameters
    ----------
    patient_admission : str
        The identifier of the patient admission.
    enc_ids_dict : dict
        A dictionary mapping departments to lists of encounter IDs.
    department_config : DepartmentConfig
        The department configuration object.

    Returns
    -------
    tuple[str, str]
        A tuple containing:
        - The department prompt for the patient admission
        - The department name for the patient admission
    """
    for department, encounters in enc_ids_dict.items():
        if int(patient_admission) in encounters:
            return department_config.department[
                department
            ].department_prompt, department
    raise ValueError("Patient admission not found in enc_ids_dict")


def get_patients_values(data: pd.DataFrame, enc_ids_dict: dict) -> dict:
    """
    Get a dictionary of patient values for dropdowns, grouped by department.

    Parameters
    ----------
    data : pd.DataFrame
        The DataFrame containing patient data.
    enc_ids_dict : dict
        A dictionary mapping department names to lists of encounter IDs.

    Returns
    -------
    dict
        Dictionary with department names as keys and lists of patient dropdown
        values as values.
    """
    values_list = {}

    for department, enc_ids in enc_ids_dict.items():
        patients_list = []
        for idx, enc_id in enumerate(enc_ids, start=1):
            if data is not None:
                if data[data["enc_id"] == enc_id].empty:
                    continue
                length_of_stay = pd.Series(
                    data.loc[data["enc_id"] == enc_id, "length_of_stay"]
                ).to_numpy()[0]
                patients_list.append(
                    {
                        "label": f"Patiënt {idx} ({department} {length_of_stay} dagen)"
                        f" [opname {enc_id}]",
                        "value": enc_id,
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


def backup_old_department_docs(
    department: str,
    old_stored_bulk_path: Path,
    stored_bulk_path: Path,
    stored_bulk: pd.DataFrame | None = None,
    stored_bulk_old: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """
    Update the old bulk docs file with current docs for the selected department.
    Docs for other departments remain unchanged.

    Parameters
    ----------
    department : str
        The name of the department to update.
    old_stored_bulk_path : Path
        Path to the old stored bulk docs file.
    stored_bulk_path : Path
        Path to the current stored bulk docs file.
    stored_bulk : pd.DataFrame, optional
        Current stored bulk docs DataFrame.
    stored_bulk_old : pd.DataFrame, optional
        Old stored bulk docs DataFrame.

    Returns
    -------
    pd.DataFrame
        The stored bulk DataFrame read from the current stored bulk path.
    """
    if stored_bulk_old is None or stored_bulk is None:
        stored_bulk_old = pd.read_parquet(old_stored_bulk_path)
        stored_bulk = pd.read_parquet(stored_bulk_path)

    # Filter out current department in old backup
    other_depts_old = stored_bulk_old[stored_bulk_old["department"] != department]
    selected_dep_docs = stored_bulk[stored_bulk["department"] == department]
    combined = pd.concat([other_depts_old, selected_dep_docs], ignore_index=True)
    combined.to_parquet(old_stored_bulk_path)
    logger.info(
        f"Old bulk docs updated with current {department} data to "
        f"{old_stored_bulk_path.name}"
    )

    return stored_bulk


def generate_bulk_docs_for_department(
    department: str,
    enc_ids: list[int],
    data: pd.DataFrame,
    prompt_builder: PromptBuilder,
    system_prompt: str,
    general_prompt: str,
    department_config: DepartmentConfig,
    department_prompt: str | None = None,
    post_processing_prompt: str | None = None,
) -> pd.DataFrame:
    """
    Generate discharge letters for all encounters in a department.

    Parameters
    ----------
    department : str
        The name of the department for which discharge letters are generated.
    enc_ids : list[int]
        List of encounter IDs for which discharge letters are generated.
    data : pd.DataFrame
        DataFrame containing patient admission data.
    prompt_builder : PromptBuilder
        Instance of PromptBuilder used to generate discharge documents.
    system_prompt : str
        The system prompt to use in document generation.
    general_prompt : str
        The user prompt to use in document generation.
    department_config : DepartmentConfig
        The department configuration object.
    department_prompt : str | None, optional
        The department-specific prompt to use (if any).
    post_processing_prompt : str | None, optional
        The post-processing prompt to refine the generated documents (if any).

    Returns
    -------
    pd.DataFrame
        DataFrame containing the generated discharge letters for the department
        and encounters.
    """
    docs = []

    for enc_id in enc_ids:
        logger.info(f"Generating discharge letter for encounter ID: {enc_id}")
        patient_data = get_data_from_patient_admission(enc_id, data)
        patient_file_string, _ = get_patient_file(patient_data)

        discharge_letter = generate_single_doc(
            prompt_builder=prompt_builder,
            patient_file_string=patient_file_string,
            system_prompt=system_prompt,
            general_prompt=general_prompt,
            department=patient_data["department"].iloc[0],
            department_config=department_config,
            length_of_stay=patient_data["length_of_stay"].values[0],
            department_prompt=department_prompt,
            post_processing_prompt=post_processing_prompt,
        )

        try:
            content = json.dumps(discharge_letter.generated_doc)
        except (ContextLengthError, JSONError, GeneralError) as e:
            content = json.dumps(
                {"Geen Vooraf Gegenereerde Ontslagbrief Beschikbaar": e.dutch_message}
            )

        docs.append(
            {
                "enc_id": enc_id,
                "department": department,
                "generated_doc": content,
                "generation_time": discharge_letter.generation_time,
            }
        )

    docs = pd.DataFrame(docs)
    return docs


def update_stored_bulk_docs(
    stored_bulk_path: Path,
    department: str,
    new_docs: pd.DataFrame,
    stored_bulk: pd.DataFrame,
) -> None:
    """
    Update the stored bulk docs file with new generated docs for the selected
    department. Docs for other departments remain unchanged.

    Parameters
    ----------
    stored_bulk_path : Path
        Path to the stored bulk documents file.
    department : str
        The name of the department to update.
    new_docs : pd.DataFrame
        DataFrame containing the newly generated discharge documents.
    stored_bulk : pd.DataFrame
        The current stored bulk documents DataFrame.

    Returns
    -------
    None
        This function does not return anything. It updates the stored bulk
        documents file.
    """
    other_depts = stored_bulk[stored_bulk["department"] != department]
    updated = pd.concat([other_depts, new_docs], ignore_index=True)
    updated.to_parquet(stored_bulk_path)

    logger.info("Updated stored bulk discharge documents.")


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
