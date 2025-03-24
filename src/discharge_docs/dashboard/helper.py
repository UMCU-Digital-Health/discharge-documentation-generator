import json
import logging
import os
import re
from pathlib import Path
from typing import Union

import pandas as pd
import tomli
from dash import html
from flask import Request

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


def load_enc_ids() -> dict:
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
        data = tomli.load(f)
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
    req: Request, authorization_dict: dict, development_authorizations: list
) -> tuple[str, list[str]]:
    """
    Get the RStudio Connect credentials from the request headers.
    Credentials are of the form: {user: "email", groups: ["group1", "group2"]}
    TODO: Use the groups from the RStudio Connect credentials instead of the lookup

    Parameters
    ----------
    req : Request
        The request object.
    authorization_dict : Dict
        A dictionary containing the user's email and their authorization groups.
        see auth_example.toml for an example.
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
        for value in authorization_dict["users"].values():
            if value["email"] == user:
                return user, value["groups"]

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
    patient_admission: str, data: pd.DataFrame
) -> pd.DataFrame:
    """
    Get data from patient admission.

    Parameters
    ----------
    patient_admission : str
        The identifier of the patient admission.
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
