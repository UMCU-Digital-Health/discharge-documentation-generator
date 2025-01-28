import json
import logging
import os
import re
from pathlib import Path

import pandas as pd
import tomli
from dash import dash_table, dcc, html
from flask import Request

logger = logging.getLogger(__name__)


def highlight(
    text, selected_words: str, mark_color: str = "yellow", text_color: str = "black"
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


def get_suitable_enc_ids(file_name: str, type: str, first_25: bool = True) -> dict:
    """Get suitable ENC IDs based on file name and type.

    Parameters
    ----------
    file_name : str
        The name of the file containing ENC IDs.
    type : str
        The type of ENC IDs to retrieve either per department,
        or per deparmtnet and user
    first_25 : bool
        Whether to show only the first 25 ENC IDs or all.
        only show 25 to minimise the amount of data shown in dashboard

    Returns
    -------
    dict
        A dictionary containing the suitable ENC IDs.
    """
    with open(
        Path(__file__).parent / file_name,
        "rb",
    ) as f:
        enc_ids_dict = tomli.load(f)
        if type == "department":
            for key in enc_ids_dict:
                enc_ids_dict[key] = enc_ids_dict[key]["ids"]
            if first_25:
                for key in enc_ids_dict:
                    enc_ids_dict[key] = enc_ids_dict[key][:25]
            return enc_ids_dict

        elif type == "department_user":
            id_dep_dict = {}
            for key in enc_ids_dict:
                id_dep_dict[key] = list(
                    zip(
                        enc_ids_dict[key]["ids"],
                        enc_ids_dict[key]["department"],
                        strict=False,
                    )
                )
            return id_dep_dict
        else:
            logger.warning("Invalid type, choose department or department_user")
            return {}


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

    fist_patient = authorized_patients[0]["value"] if authorized_patients else None

    return authorized_patients, fist_patient


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
    if patient_admission not in data_dict:
        logger.warning(f"Patient admission {patient_admission} not found in data_dict")

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
    df_dict: dict, enc_ids_dict: dict, phase2: bool = False
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
                if phase2:
                    patient_key = str(enc_id)
                else:
                    patient_key = f"patient_{idx}_{department.lower()}"
                patients_data[patient_key] = df[df["enc_id"] == enc_id]
                if patients_data[patient_key].empty:
                    continue
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


def get_patients_from_list_names_pilot(
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
        A dictionary containing enc_ids and their different departments for different
        users.

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

    for user, enc in enc_ids_dict.items():
        patients_list = []

        for idx, encounter in enumerate(enc, start=1):
            enc_id = encounter[0]
            department = encounter[1]
            df = df_dict.get(department, None)
            if df is not None:
                patient_key = f"patient_{idx}_{department.lower()}_{enc_id}"
                patients_data[patient_key] = df[df["enc_id"] == enc_id]
                label_days = patients_data[patient_key]["length_of_stay"].values[0]
                patients_list.append(
                    {
                        "label": f"Patiënt {idx} ({department} {label_days} dagen)",
                        "value": patient_key,
                    }
                )
        if patients_list:
            values_list[user] = patients_list

    return patients_data, values_list


def load_stored_discharge_letters(
    df: pd.DataFrame, patient_name: str
) -> list[html.Div] | str:
    """Load discharge letters for a specific patient.

    Parameters
    ----------
    df : pd.DataFrame
        The DataFrame containing the discharge letters data.
    patient_name : str
        The name of the patient.

    Returns
    -------
    list[html.Div]
        A list of HTML Div elements representing the discharge letters for the patient.
    """
    if patient_name not in df["name"].values:
        return "Er is geen opgeslagen documentatie voor deze patient."

    discharge_document = df.loc[df["name"] == patient_name, "generated_doc"].values[0]
    discharge_document = eval(discharge_document)

    output = []
    for category_pair in discharge_document:
        output.append(
            html.Div(
                [
                    html.Strong(category_pair["Categorie"]),
                    dcc.Markdown(category_pair["Beloop tijdens opname"]),
                ]
            )
        )
    return output


def load_stored_discharge_letters_pre_release(
    df: pd.DataFrame, patient_name: str, phase2: bool = False
) -> list[html.Div] | str:
    """Load discharge letters for a specific patient formatting according to pre-release

    Parameters
    ----------
    df : pd.DataFrame
        The DataFrame containing the discharge letters data.
    patient_name : str
        The name of the patient.

    Returns
    -------
    list[html.Div]
        A list of HTML Div elements representing the discharge letters for the patient.
    """
    id_column = "enc_id" if phase2 else "name"
    if phase2:
        df[id_column] = df[id_column].astype(str)
    if not phase2 and patient_name not in df[id_column].values:
        return "Er is geen opgeslagen documentatie voor deze patient."

    discharge_document = df.loc[df[id_column] == patient_name, "generated_doc"].values[
        0
    ]
    discharge_document = eval(discharge_document)

    outputstring = ""
    for category_pair in discharge_document:
        formatted_string = (
            f"{category_pair['Categorie'].upper()}"
            + f" \n{category_pair['Beloop tijdens opname']}"
        )
        outputstring += formatted_string + "\n\n"

    return outputstring


def generate_annotation_datatable(type: str, header_color: str) -> dash_table.DataTable:
    """Generate an annotation datatable.

    Parameters
    ----------
    type : str
        The type of annotation datatable, for example: "omission" or "hallucination".
    header_color : str
        The background color of the header.

    Returns
    -------
    dash_table.DataTable
        A DataTable for annotations.
    """
    return dash_table.DataTable(
        columns=[
            {"id": "id", "name": "ID", "editable": False},
            {"id": "text", "name": "Annotatie", "editable": False},
            {
                "id": "importance",
                "name": "Beoordeling",
                "presentation": "dropdown",
                "editable": True,
            },
            {
                "id": "duplicate",
                "name": "Dubbeling",
                "type": "numeric",
                "editable": True,
            },
        ],
        id=f"{type}_table",
        editable=True,
        style_data={
            "overflow": "hidden",
            "textOverflow": "ellipsis",
            "maxWidth": 0,
        },
        tooltip_duration=None,
        style_header={
            "backgroundColor": header_color,
            "fontWeight": "bold",
            "color": "white",
        },
        dropdown={
            "importance": {
                "options": [
                    {"label": "Eens; ernstig", "value": "Important"},
                    {
                        "label": "Eens; minder ernstig",
                        "value": "Less important",
                    },
                    {"label": "Oneens", "value": "False"},
                ]
            }
        },
    )


def format_generated_doc(generated_doc: list[dict], format_type: str) -> str:
    """Convert the generated document to plain text or markdown with headers.

    Parameters
    ----------
    generated_doc : list[dict]
        The generated document in a list of dict.
    format_type : str
        The desired format type of the generated document.

    Returns
    -------
    str
        The plain text version of the generated document.
    """

    output_structured = []
    output_plain = ""
    for category_pair in generated_doc:
        output_structured.append(
            html.Div(
                [
                    html.Strong(category_pair["Categorie"]),
                    dcc.Markdown(category_pair["Beloop tijdens opname"]),
                ]
            )
        )
        output_plain += f"{category_pair['Categorie']}\n"
        output_plain += f"{category_pair['Beloop tijdens opname']}\n\n"
    if format_type == "markdown":
        return output_structured
    elif format_type == "plain":
        return output_plain
    else:
        return ""
