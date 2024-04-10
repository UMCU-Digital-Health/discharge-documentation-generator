import json
import logging
import re

import pandas as pd
from dash import html
from flask import Request

logger = logging.getLogger(__name__)


def highlight(text, selected_words: str) -> list:
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
    # als text string is
    if isinstance(text, str):
        sequences = re.split(re.escape(selected_words), text, flags=re.IGNORECASE)
        i = 1
        while i < len(sequences):
            sequences.insert(i, html.Mark(selected_words.upper()))
            i += 2
        return sequences
    else:  # als text een lijst is
        for i, t in enumerate(text):
            if isinstance(t, str):
                text[i] = highlight(t, selected_words)
        flat_list = []

        for sublist in text:
            if isinstance(sublist, list):
                for item in sublist:
                    flat_list.append(item)
            else:
                flat_list.append(sublist)
        return flat_list


def get_authorization(req: Request, authorization_dict: dict) -> tuple[str, list[str]]:
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

    Returns
    -------
    Tuple[str, List[str]]
        A tuple containing the user's email
        and a list of authorization groups for the user.
    """
    credential_header = req.headers.get("RStudio-Connect-Credentials")
    if not credential_header:
        logger.warning("No credentials found in request headers")
        return "", []

    credential_header = json.loads(credential_header)
    user = credential_header.get("user").lower()
    for value in authorization_dict["users"].values():
        if value["email"] == user:
            return user, value["groups"]

    logger.warning(f"No authorization groups found for user {user}")
    return "", []


def get_data_from_patient_admission(
    patient_admission: str, data_dict: dict
) -> pd.DataFrame:
    """
    Get data from patient admission.

    Parameters
    ----------
    patient_admission : str
        The identifier of the patient admission.
    data_dict : dict
        A dictionary containing data for patient admissions.

    Returns
    -------
    pd.DataFrame
        The data associated with the patient admission.
    """
    return data_dict[patient_admission]


def get_template_prompt(
    patient_admission: str, template_prompt_dict: dict
) -> tuple[str, str]:
    """
    Get the template prompt for a patient admission and the department.

    Parameters
    ----------
    patient_admission : str
        The identifier of the patient admission.
    template_prompt_dict : dict
        A dictionary containing template prompts for patient admissions.

    Returns
    -------
    str
        The template prompt for the patient admission.
    str
        The department for the patient admission.
    """
    department = patient_admission.split("_")[-1]
    return template_prompt_dict[department], department


def get_patients_from_list_names(
    df_dict: dict, enc_ids_dict: dict
) -> tuple[dict, dict]:
    """
    Get patients' data and values list from a dictionary of dataframes and a dictionary
    of enc_ids.

    Parameters
    ----------
    df_dict : dict
        A dictionary containing dataframes for different departments.
    enc_ids_dict : dict
        A dictionary containing enc_ids for different departments.

    Returns
    -------
    tuple[dict, dict]
        A tuple containing patients' data and values list.
        The patients' data is a dictionary with patient keys as keys and corresponding
        dataframes as values.
        The values list is a dictionary with department names as keys and a list of
        patients as values.
    """
    patients_data = {}
    values_list = {}

    for department, enc_ids in enc_ids_dict.items():
        patients_list = []
        for idx, enc_id in enumerate(enc_ids, start=1):
            df = df_dict.get(department, None)
            if df is not None:
                patient_key = f"patient_{idx}_{department.lower()}"
                patients_data[patient_key] = df[df["enc_id"] == enc_id]
                label_days = patients_data[patient_key]["length_of_stay"].values[0]
                patients_list.append(
                    {
                        "label": f"Patiënt {idx} ({department} {label_days} dagen)",
                        "value": patient_key,
                    }
                )
        if patients_list:
            values_list[department] = patients_list

    return patients_data, values_list
