import logging
import re
from typing import Optional, Tuple, cast

import pandas as pd
from striprtf.striprtf import rtf_to_text

from discharge_docs.api.pydantic_models import HixInput
from discharge_docs.config import load_department_config

logger = logging.getLogger(__name__)


def replace_text(input_text):
    """
    Replaces specific text patterns in the input text with formatted text.

    This function uses regular expressions to find and replace patterns in the input
    text. The patterns are of the format $RepeatedText|...#RepeatedText|...# and
    RepeatedText|...#RepeatedText|...#. The matched text is replaced with the
    uppercase version of the repeated text, each surrounded by newlines.

    Parameters
    ----------
    input_text : str
        The input text in which the patterns will be searched and replaced.

    Returns
    -------
    str
        The text with the specified patterns replaced by the formatted text.
    """
    pattern = r"\$(.*?)(\|.*?#)\1\|.*?#"

    def replacement(match):
        return f"\n{match.group(1).upper()}\n"

    replaced_text = re.sub(pattern, replacement, input_text)

    pattern = r"(.*?)(\|.*?#)\1\|.*?#"

    replaced_text = re.sub(pattern, replacement, replaced_text)
    return replaced_text


def combine_patient_and_docs_data_hix(
    patient_data: pd.DataFrame, discharge_data: pd.DataFrame
) -> pd.DataFrame:
    # combine patient and discharge data for HiX data
    discharge_data["description"] = "Ontslagbrief"
    patient_file = pd.concat([patient_data, discharge_data], axis=0).reset_index(
        drop=True
    )
    return patient_file


def pre_process_hix_data(data: HixInput) -> pd.DataFrame:
    validated_data = data.model_dump()
    data_df = pd.DataFrame.from_records(validated_data["ALLPARTS"]).rename(
        columns={
            "TEXT": "content",
            "NAAM": "description",
            "DATE": "date",
            "SPECIALISM": "department",
        },
    )
    data_df["content"] = data_df["content"].apply(rtf_to_text)
    processed_data = data_df[["date", "department", "description", "content"]].copy()
    processed_data.loc[:, "enc_id"] = "TEMP_ENC_ID"
    return processed_data


def process_data(
    patient_data: pd.DataFrame,
    remove_encs_no_docs: bool = False,
) -> pd.DataFrame:
    """
    Processes patient data.

    This function processes the provided patient data DataFrame by filtering,
    formatting, and combining relevant information. It can also remove encounters
    without discharge documents if specified.

    Parameters
    ----------
    patient_data : pd.DataFrame
        The DataFrame containing patient data.
    remove_encs_no_docs : bool, optional
        If True, removes encounters without discharge documents, by default False

    Returns
    -------
    pd.DataFrame
        The processed patient data DataFrame.
    """
    if patient_data.empty:
        logger.warning("No patient data to process.")
        return patient_data
    df = patient_data.copy()

    df["date"] = pd.to_datetime(df["date"].dt.date)

    df = df[df["content"].str.strip() != ""]
    df = df[df["description"].str.strip() != ""]
    df = df.dropna(subset=["date", "description", "content"])

    df["description"] = df["description"].replace(
        "Medische Ontslagbrief - Beloop", "Ontslagbrief"
    )

    if "Ontslagbrief" in df["description"].unique():
        df = df.sort_values(by=["enc_id", "date"])

        last_docs = df[df["description"] == "Ontslagbrief"].drop_duplicates(
            subset=["enc_id"], keep="last"
        )

        df = pd.concat(
            [
                df[df["description"] != "Ontslagbrief"],
                last_docs,
            ],
            axis=0,
        ).reset_index(drop=True)

    if "dischargeDate" in df.columns:
        df["length_of_stay"] = (
            df["dischargeDate"].dt.normalize() - df["admissionDate"].dt.normalize()
        ).dt.days
    elif "admissionDate" in df.columns:
        today = pd.Timestamp.now().tz_localize(None).normalize()
        df["length_of_stay"] = (
            today - df["admissionDate"].dt.tz_localize(None).dt.normalize()
        ).dt.days
    else:
        df["length_of_stay"] = None

    if remove_encs_no_docs:
        encs_with_docs = df.loc[df["description"] == "Ontslagbrief", "enc_id"].unique()
        df = df[df["enc_id"].isin(encs_with_docs)]

    df["department"] = df["department"].replace(
        {
            "Intensive Care Centrum": "IC",
            "Neonatologie": "NICU",
            "CAR": "CAR",
            "High Care Kinderen": "PICU",
            "Intensive Care Kinderen": "PICU",
        }
    )

    department_config = load_department_config()
    department_mappings = {
        dept: cfg.get_column_descriptions(department_config.column_description)
        for dept, cfg in department_config.department.items()
    }

    df = (
        df.groupby("department", group_keys=False)[df.columns]
        .apply(
            lambda g: filter_data(g, cast(str, g.name), department_mappings).assign(
                department=cast(str, g.name)
            )
        )
        .reset_index(drop=True)
    )

    df = df.sort_values(by=["department", "enc_id", "date", "description"]).reset_index(
        drop=True
    )

    return df


def filter_data(
    df: pd.DataFrame, department: str, department_mappings: dict[str, dict[str, str]]
) -> pd.DataFrame:
    """
    Filters and renames the column with descriptions for a given department.

    Parameters
    ----------
        df : pd.DataFrame
            containing at least a 'description' column.
        department : str
            Name of the department to filter columns for.
        department_mappings : Dict
            Mapping department to all sets of renamed column
            descriptions of that department.

    Returns
    -------
        df Filtered and renamed DataFrame.
    """
    if department not in department_mappings:
        raise ValueError(f"Department {department} not recognized")

    if department in {"ORT", "DEMO"}:
        return df

    dept_descriptions = department_mappings[department]
    df = df[df["description"].isin(dept_descriptions.keys())].replace(dept_descriptions)

    return df


def get_patient_discharge_docs(
    df: pd.DataFrame, enc_id: int | None = None
) -> pd.Series:
    """
    Retrieves the discharge documentation for a specific patient based on their
    encounter ID or if the data is only for one end_id.

    Parameters
    ----------
    df : DataFrame
        The DataFrame containing the patient data.
    enc_id : int, optional
        The encounter ID of the patient.

    Returns
    -------
    str
        The discharge documentation for the patient.
    """
    if enc_id is not None:
        discharge_documentation = df[df["enc_id"] == enc_id]
    else:
        discharge_documentation = df

    discharge_documentation = df[df["description"].isin(["Ontslagbrief"])]["content"]
    return discharge_documentation


def get_patient_file(
    df: pd.DataFrame, enc_id: Optional[int] = None
) -> Tuple[str, pd.DataFrame]:
    """
    Retrieves the patient file for a given encounter ID from a DataFrame.

    Parameters
    ----------
    enc_id : int
        The encounter ID of the patient.
    df : pandas.DataFrame
        The DataFrame containing the patient files.

    Returns
    -------
    tuple
        A tuple containing the patient file string and the filtered DataFrame.
    """
    if enc_id is not None:
        patient_file = df[df.enc_id == enc_id]
    else:
        patient_file = df

    # remove rows with ontslag in the description
    patient_file = patient_file[~patient_file["description"].isin(["Ontslagbrief"])]

    patient_file_string = "\n\n".join(
        patient_file.apply(
            lambda row: (
                f"## {row['description']}\n### Datum: {row['date']}\n\n{row['content']}"
            ),
            axis=1,
        )
    )
    patient_file_string = "# Patiënten dossier\n\n" + patient_file_string

    return patient_file_string, patient_file
