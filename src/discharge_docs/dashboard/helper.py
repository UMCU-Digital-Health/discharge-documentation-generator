import json
import logging
import os
import re
import tomllib
from pathlib import Path
from typing import Union

import pandas as pd
from dash import html
from flask import Request

from discharge_docs.config import AuthConfig
from discharge_docs.llm.prompt_builder import (
    ContextLengthError,
    GeneralError,
    JSONError,
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


def get_user(req: Request) -> str:
    """
    Get the user email from RStudio credentials.
    TODO: Use the groups from the RStudio Connect credentials instead of the lookup

    Parameters
    ----------
    req : Request
        The request object.

    Returns
    -------
    str
        the user's email
    """
    credential_header = req.headers.get("RStudio-Connect-Credentials")
    if not credential_header:
        logger.warning("No credentials found in request headers")
        return "No user"

    credential_header = json.loads(credential_header)
    user = credential_header.get("user").lower()
    return user


def get_authorization(
    req: Request, authorization_config: AuthConfig, development_authorizations: list
) -> tuple[str, list[str]]:
    """
    Get the RStudio Connect credentials from the request headers.
    Credentials are of the form: {user: "email", groups: ["group1", "group2"]}
    TODO: Use the groups from the RStudio Connect credentials instead of the lookup

    Parameters
    ----------
    req : Request
        The request object.
    authorization_config : AuthConfig
        The configuration object containing user authorization information.
        See auth_example.toml for an example.
    development_authorizations : List
        A list of authorization groups for development mode. Development mode is
        activated if ENC is set to "development".

    Returns
    -------
    Tuple[str, List[str]]
        A tuple containing the user's email
        and a list of authorization groups for the user.
    """
    if os.getenv("ENV", "") == "development":
        logger.warning("Running in development mode, overriding authorization group.")
        # Never add this in production!
        return "Development user", development_authorizations
    else:
        user = get_user(req)
        for value in authorization_config.users.values():
            if value.email == user:
                return user, value.groups

        logger.warning(f"No authorization groups found for user {user}")
        return "", []


def get_authorized_patients(
    authorization_group: list, patients: dict
) -> tuple[list, str | None]:
    """Get authorized patients based on authorization group.

    Parameters
    ----------
    authorization_group : list
        The list of authorization groups.
    patients : dict
        A dictionary containing patient data.

    Returns
    -------
    tuple[list, dict]
        A tuple containing the authorized patients and a dictionary of patient data.
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
    Get data from patient admission.

    Parameters
    ----------
    patient_admission : str
        The identifier of the patient admission. It can be a string or an integer, but
        it will be converted to an integer.
    data : pd.DataFrame
        The dataframe containing information on patient admissions.

    Returns
    -------
    pd.DataFrame
        The data associated with the patient admission.
    """
    if int(patient_admission) not in data["enc_id"].unique():
        logger.warning(f"Patient admission {patient_admission} not found in data")

    return data[data["enc_id"] == int(patient_admission)]


def get_template_prompt(
    patient_admission: str, template_prompt_dict: dict, enc_ids_dict: dict
) -> tuple[str, str]:
    """
    Get the template prompt for a patient admission and the department.

    Parameters
    ----------
    patient_admission : str
        The identifier of the patient admission.
    template_prompt_dict : dict
        A dictionary containing template prompts for patient admissions.
    enc_ids_dict : dict
        A dictionary containing enc_ids for different departments.

    Returns
    -------
    str
        The template prompt for the patient admission.
    str
        The department for the patient admission.
    """
    for department, encounters in enc_ids_dict.items():
        if int(patient_admission) in encounters:
            return template_prompt_dict[department], department
    raise ValueError("Patient admission not found in enc_ids_dict")


def get_patients_values(data: pd.DataFrame, enc_ids_dict: dict) -> dict:
    """
    Get patients' data and values list from a dictionary of dataframes and a dictionary
    of enc_ids.

    Parameters
    ----------
    data : pd.DataFrame
        A dictionary containing dataframes for different departments.
    enc_ids_dict : dict
        A dictionary containing enc_ids for different departments.

    Returns
    -------
    dict
        The values list is a dictionary with department names as keys and a list of
        patients as values.
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


def load_stored_discharge_letters(df: pd.DataFrame, selected_enc_id: str) -> dict:
    """Load discharge letters for a specific patient.

    Parameters
    ----------
    df : pd.DataFrame
        The DataFrame containing the discharge letters data.
    selected_enc_id : str
        The encounter id of the patient.

    Returns
    -------
    dict
        The pre-generated and stored discharge letters for the patient.
    """
    if int(selected_enc_id) not in df["enc_id"].values:
        return {
            "Geen Vooraf Gegenereerde Ontslagbrief Beschikbaar": (
                "Er is geen opgeslagen documentatie voor deze patiënt."
            )
        }

    discharge_document = df.loc[
        df["enc_id"] == int(selected_enc_id), "generated_doc"
    ].values[0]

    discharge_document = json.loads(discharge_document)

    return discharge_document


def get_department_name(selected_patient_admission: int, enc_ids_dict: dict) -> str:
    """Return the department name based on the encounter ID.

    Parameters
    ----------
    selected_patient_admission : int
        The encounter ID of the selected patient admission.
    enc_ids_dict : dict
        A dictionary mapping department names to lists of encounter IDs.

    Returns
    -------
    str
        The name of the department associated with the selected patient admission.
    """
    for dep, enc_ids in enc_ids_dict.items():
        if selected_patient_admission in enc_ids:
            return dep
    raise ValueError("Department not found for given patient admission.")


def backup_old_department_docs(
    department_name: str,
    old_stored_bulk_path: Path,
    stored_bulk_path: Path,
    stored_bulk: pd.DataFrame | None = None,
    stored_bulk_old: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """
    Update the 'bulk_generated_docs_gpt_old.parquet' file with current docs of the
    selected department. Docs of other departments remain unchanged.

    Parameters
    ----------
    department_name : str
        The name of the department for which the documents are being stored.
    old_stored_bulk_path : Path
        The path to the old stored bulk documents file.
    stored_bulk_path : Path
        The path to the current stored bulk documents file.
    stored_bulk : pd.DataFrame, optional
        The current stored bulk documents DataFrame.
    stored_bulk_old : pd.DataFrame, optional
        The old stored bulk documents DataFrame.

    Returns
    -------
    pd.DataFrame
        The stored bulk DataFrame read from the current stored bulk path.
    """
    if stored_bulk_old is None or stored_bulk is None:
        stored_bulk_old = pd.read_parquet(old_stored_bulk_path)
        stored_bulk = pd.read_parquet(stored_bulk_path)

    # Filter out current department in old backup
    other_depts_old = stored_bulk_old[stored_bulk_old["department"] != department_name]
    selected_dep_docs = stored_bulk[stored_bulk["department"] == department_name]
    combined = pd.concat([other_depts_old, selected_dep_docs], ignore_index=True)
    combined.to_parquet(old_stored_bulk_path)
    logger.info(
        f"Old bulk docs updated with current {department_name} data to "
        f"{old_stored_bulk_path.name}"
    )

    return stored_bulk


def generate_bulk_docs_for_department(
    department_name: str,
    enc_ids: list[int],
    data: pd.DataFrame,
    template_prompt: str,
    prompt_builder,
    system_prompt: str,
    user_prompt: str,
) -> pd.DataFrame:
    """
    Generate discharge letters for all encounters in a department.

    Parameters
    ----------
    department_name : str
        The name of the department for which discharge letters are generated.
    enc_ids : list[int]
        A list of encounter IDs for which discharge letters are to be generated.
    data : pd.DataFrame
        The DataFrame containing patient admission data.
    template_prompt : str
        The template prompt to be used for generating discharge letters.
    prompt_builder : PromptBuilder
        An instance of the PromptBuilder class used to generate discharge documents.
    system_prompt : str
        The system prompt to be used in the document generation.
    user_prompt : str
        The user prompt to be used in the document generation.

    Returns
    -------
    pd.DataFrame
        A DataFrame containing the generated discharge letters for the specified
        department and encounters.
    """
    docs = []

    for enc_id in enc_ids:
        logger.info(f"Generating discharge letter for encounter ID: {enc_id}")
        patient_data = get_data_from_patient_admission(enc_id, data)
        patient_file_string, _ = get_patient_file(patient_data)

        try:
            discharge_letter = prompt_builder.generate_discharge_doc(
                patient_file=patient_file_string,
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                template_prompt=template_prompt,
            )
            content = json.dumps(discharge_letter)
        except (ContextLengthError, JSONError, GeneralError) as e:
            content = json.dumps(
                {"Geen Vooraf Gegenereerde Ontslagbrief Beschikbaar": e.dutch_message}
            )

        docs.append(
            {"enc_id": enc_id, "department": department_name, "generated_doc": content}
        )

    return pd.DataFrame(docs)


def update_stored_bulk_docs(
    stored_bulk_path: Path,
    department_name: str,
    new_docs: pd.DataFrame,
    stored_bulk: pd.DataFrame,
) -> None:
    """
    Update the 'bulk_generated_docs_gpt.parquet' file with new generated docs of the
    selected department. Docs of other departments remain unchanged.

    Parameters
    ----------
    stored_bulk_path : Path
        The path to the stored bulk documents file.
    department_name : str
        The name of the department for which the documents are being updated.
    new_docs : pd.DataFrame
        A DataFrame containing the newly generated discharge documents.
    stored_bulk : pd.DataFrame
        The current stored bulk documents DataFrame.

    Returns
    -------
    None
        This function does not return anything. It updates the stored bulk documents.
    """
    other_depts = stored_bulk[stored_bulk["department"] != department_name]
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
