import re
from pathlib import Path
from typing import Optional, Tuple

import pandas as pd
import tomli_w


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
        df["length_of_stay"] = pd.to_timedelta(
            (df["dischargeDate"].dt.date - df["admissionDate"].dt.date)
        ).dt.days

    if remove_encs_no_docs:
        encs_with_docs = df.loc[df["description"] == "Ontslagbrief", "enc_id"].unique()
        df = df[df["enc_id"].isin(encs_with_docs)]

    df["department"] = df["department"].replace(
        {
            "Intensive Care Centrum": "IC",
            "Neonatologie": "NICU",
            "CAR": "CAR",
        }
    )

    df = (
        df.groupby("department")
        .apply(
            lambda x: filter_data(x, x.name).assign(department=x.name),
            include_groups=False,
        )
        .reset_index(drop=True)
    )

    df = df.sort_values(by=["department", "enc_id", "date", "description"]).reset_index(
        drop=True
    )

    return df


def filter_data(df: pd.DataFrame, department: str) -> pd.DataFrame:
    # filtering and renaming the 'description' column per department
    metavision_tracti = {
        "Dagstatus - Tractus 01 Lichamelijk Onderzoek": "Dagstatus - Lichamelijk "
        + "Onderzoek",
        "Dagstatus - Tractus 02 Respiratie": "Dagstatus - Respiratie",
        "Dagstatus - Tractus 03 Circulatie": "Dagstatus - Circulatie",
        "Dagstatus - Tractus 04 Neurologie": "Dagstatus - Neurologie",
        "Dagstatus - Tractus 05 Infectie": "Dagstatus - Infectie",
        "Dagstatus - Tractus 06 VB/nierfunctie": "Dagstatus - VB/nierfunctie",
        "Dagstatus - Tractus 07 Gastro-Intestinaal": "Dagstatus - Gastro-Intestinaal",
        "Dagstatus - Tractus 08 Milieu Interieur": "Dagstatus - Milieu Interieur",
        "Dagstatus - Tractus 09 Extr/huid": "Dagstatus - Extr/huid",
        "Dagstatus - Tractus 10 Psych/soc": "Dagstatus - Psych/sociaal",
        "Dagstatus - Tractus 11 Overig": "Dagstatus - Overig",
    }

    metavision_general = {
        "Dagstatus - Tractus 12 Conclusie": "Dagstatus - Conclusie",
        "Dagstatus - Tractus 13 Opm dagdienst": "Dagstatus - Opmerkingen dagdienst",
        "Dagstatus - Tractus 14 Opm A/N dienst": "Dagstatus - Opmerkingen avond/nacht"
        + " dienst",
        "Dagstatus Print Afspraken": "Afspraken",
        "Dagstatus Print Behandeldoelen": "Behandeldoelen",
        # "Form MS Diagnose 1": "Diagnosecode 1",
        # "Form MS Diagnose 2": "Diagnosecode 2",
        "MS Anamnese Overzicht": "Anamnese",
        "MS Chronologie Eventlijst Print": "Eventlijst",
        "MS Dagstatus Beleid KT": "Korte Termijn Beleid",
        "MS Dagstatus Beleid LT Print": "Lange Termijn Beleid",
        "MS Decursus Thuismedicatie": "Thuismedicatie",
        "MS Decursus Toedracht bij Opname": "Toedracht bij Opname",
        "MS Decursus Item Tekst": "Familiegesprek",
        "MS Probleemlijst Print": "Probleemlijst",
        "MS VoorGeschiedenis Overzicht": "Voorgeschiedenis Overzicht",
        "Ontslagbrief": "Ontslagbrief",
        "Ontslagregistratie - Ontslagbestemming - "
        + "Naam ander ziekenhuis/afdeling (niet UMCU)": "Ontslagbestemming - Naam"
        + " ander ziekenhuis/afdeling",
        "Ontslagregistratie - Ontslagbestemming - "
        + "Toelichting bij ontslag naar overige bestemmingen": "Ontslagbestemming - "
        + "Toelichting bij ontslag naar overige bestemmingen",
    }

    cardio_general = {
        "Aanvullend onderzoek": "Aanvullend onderzoek",
        "Conclusie": "Conclusie",
        # "Correspondentie": "Correspondentie",
        "Lichamelijk onderzoek": "Lichamelijk onderzoek",
        "Beleid": "Beleid",
        "Anamnese": "Anamnese",
        "Functieonderzoeken": "Functieonderzoeken",
        # "Aangevraagde onderzoeken": "Aangevraagde onderzoeken",
        # "Laboratorium": "Laboratorium",
        "Reden van komst / Verwijzing": "Reden van komst / Verwijzing",
        "Uitgevoerde behandeling/verrichting": "Uitgevoerde behandeling/verrichting",
        "Overige acties": "Overige acties",
        "Overweging / Differentiaal diagnose": "Overweging / Differentiaal diagnose",
        "Beloop": "Beloop",
        "Overdracht": "Overdracht",
        "Samenvatting": "Samenvatting",
        # "Vitale functies": "Vitale functies",
        # "Radiologie": "Radiologie",
        "Diagnose": "Diagnose",
        "Actuele medicatie": "Actuele medicatie",
        # "Microbiologie": "Microbiologie",
        "Plan": "Plan",
        "Complicatie": "Complicatie",
        # "Pathologie": "Pathologie",
        # "Informed Consent": "Informed Consent",
        "Familieanamnese": "Familieanamnese",
        "Medicatie": "Medicatie",
        "Advies": "Advies",
        "Voorgeschiedenis": "Voorgeschiedenis",
        "Ontslagbrief": "Ontslagbrief",
    }

    if department == "IC":
        df = df[df["description"].isin(metavision_general.keys())].replace(
            metavision_general
        )
    elif department == "NICU":
        df = (
            df[
                df["description"].isin(metavision_general.keys())
                | df["description"].isin(metavision_tracti.keys())
            ]
            .replace(metavision_general)
            .replace(metavision_tracti)
        )
    elif department == "CAR":
        df = df[df["description"].isin(cardio_general.keys())].replace(cardio_general)
    else:
        raise ValueError(f"Department {department} not recognized")
    return df


def write_encounter_ids(data: pd.DataFrame, n_enc_ids: int) -> None:
    """
    Writes the encounter IDs from the data to a TOML file.

    This function processes the provided DataFrame to extract unique encounter IDs
    for each department, limits the number of encounter IDs per department to the
    specified number, and writes the result to a TOML file.

    Parameters
    ----------
    data : pd.DataFrame
        The DataFrame containing the encounter data.
    n_enc_ids : int
        The number of encounter IDs to keep per department.
    """
    # replace certain values in department
    enc_ids = data[["enc_id", "department"]].drop_duplicates()

    # keep only first n_enc_ids per department
    enc_ids = enc_ids.groupby("department").head(n_enc_ids)
    # combine and save as TOML where the table is the department and the encs are a list
    enc_ids = enc_ids.groupby("department")["enc_id"].apply(list).to_dict()
    toml_data = {dept: {"ids": ids} for dept, ids in enc_ids.items()}

    with open(
        Path(__file__).parents[3]
        / "src"
        / "discharge_docs"
        / "dashboard"
        / "enc_ids.toml",
        "wb",
    ) as f:
        tomli_w.dump(toml_data, f)


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
    patient_file_string = "# Patienten dossier\n\n" + patient_file_string

    return patient_file_string, patient_file
