import os
import re
from pathlib import Path
from typing import Tuple

import pandas as pd
import tomli

os.environ["TIKTOKEN_CACHE_DIR"] = ""


def replace_text(input_text):
    # Regular expression pattern to capture and replace the format
    # $RepeatedText|...#RepeatedText|...#
    pattern = r"\$(.*?)(\|.*?#)\1\|.*?#"

    def replacement(match):
        return f"\n{match.group(1).upper()}\n"

    replaced_text = re.sub(pattern, replacement, input_text)

    pattern = r"(.*?)(\|.*?#)\1\|.*?#"

    replaced_text = re.sub(pattern, replacement, replaced_text)
    return replaced_text


def process_data_metavision_dp(df: pd.DataFrame) -> pd.DataFrame:
    """
    Process the given DataFrame containing metavision data.
    The steps were:
    1. include enc_id per admission
    2. remove columns not necessary
    3. Rename columns
    3.5 add full discharge docs from dataplatform export (TODO)
    4. include date column
    5. add length of stay
    6. remove patients with length of stay 0 days
    7. remove encounters that do not have a discharge letter
    8. replace date in rows with 1899 in the date
    9. rename ontslagbrief
    10. remove the MS Probleemlijst Date as it is the same as MS Probleemlijst Print but
        formatted worse
    11. pseudonomise by hand



    Parameters
    ----------
    df : pandas.DataFrame
        The DataFrame containing metavision data.
    df_discharge_docs_dp : pandas.DataFrame
        The DataFrame containing full discharge documentation from the dataplatform.

    Returns
    -------
    pandas.DataFrame
        The processed DataFrame.
    """
    # include enc_id per admission
    df["enc_id"] = df.groupby(["period_start", "period_end"]).ngroup()

    # Rename and drop columns
    df = df.drop(columns=["pseudo_id"]).rename(
        columns={
            "period_start": "admissionDate",
            "period_end": "dischargeDate",
            "location_Location_value_original": "department",
            "effectiveDateTime": "time",
            "code_display_original": "description",
            "valueString": "value",
            "enc_id": "enc_id",
        }
    )

    # include date column
    df["time"] = pd.to_datetime(df["time"])
    df["date"] = pd.to_datetime(df["time"].dt.date)

    # add length of stay
    df["admissionDate"] = pd.to_datetime(df["admissionDate"])
    df["dischargeDate"] = pd.to_datetime(df["dischargeDate"])
    df["length_of_stay"] = (df["dischargeDate"] - df["admissionDate"]).dt.days

    # remove patients with length of stay 0 days
    df = df[df["length_of_stay"] != 0]

    # remove rows where value is empty
    df = df[
        ~(
            df["value"]
            == "Lichamelijk Onderzoek|Titel#Lichamelijk Onderzoek|Bespreking#"
        )
    ]

    df.dropna(subset=["value"], inplace=True)
    df.drop_duplicates(inplace=True)

    # apply replace_text to all values in the value column
    df["value"] = df["value"].apply(replace_text)

    # remove encounters that do not have a discharge letter
    encounters_with_discharge = df.loc[
        df["description"] == "Medische Ontslagbrief - Beloop", "enc_id"
    ].unique()

    df = df[df["enc_id"].isin(encounters_with_discharge)]

    # Function to replace 1899 dates with the most recent date in the group
    # as the 1899 dates are not valid and contain the discharge docs
    def replace_1899_dates(dates):
        # Replace 1899 dates with the most recent date in the series
        mask = dates.dt.year == 1899
        if mask.any():
            max_date = dates.max()
            dates = dates.where(~mask, max_date)
        return dates

    df["date"] = df.groupby("enc_id")["date"].transform(replace_1899_dates)

    # subset the data based on the names for sections in patient file
    df = df[
        ~(
            (df["department"] == "Intensive Care Centrum")
            & (
                ~df["description"].isin(
                    [
                        "Dagstatus - Tractus 12 Conclusie",
                        "Dagstatus - Tractus 13 Opm dagdienst",
                        "Dagstatus - Tractus 14 Opm A/N dienst",
                        "Dagstatus Print Afspraken",
                        "Dagstatus Print Behandeldoelen",
                        "Form MS Diagnose 1",
                        "Form MS Diagnose 2",
                        "MS Anamnese Overzicht",
                        "MS Chronologie Eventlijst Print",
                        "MS Dagstatus Beleid KT",
                        "MS Dagstatus Beleid LT Print",
                        "MS Decursus Thuismedicatie",
                        "MS Decursus Toedracht bij Opname",
                        "MS Probleemlijst Print",
                        "MS VoorGeschiedenis Overzicht",
                        "Medische Ontslagbrief - Beloop",
                        # "Medische ontslagbrief - Beloop Dictionary",
                        "Ontslagregistratie - Ontslagbestemming - "
                        + "Naam ander ziekenhuis/afdeling (niet UMCU)",
                        "Ontslagregistratie - Ontslagbestemming - "
                        + "Toelichting bij ontslag naar overige bestemmingen",
                    ]
                )
            )
        )
    ]
    df = df[
        ~(
            (df["department"] == "Neonatologie")
            & (
                ~df["description"].isin(
                    [
                        "Dagstatus - Tractus 01 Lichamelijk Onderzoek",
                        "Dagstatus - Tractus 02 Respiratie",
                        "Dagstatus - Tractus 03 Circulatie",
                        "Dagstatus - Tractus 04 Neurologie",
                        "Dagstatus - Tractus 05 Infectie",
                        "Dagstatus - Tractus 06 VB/nierfunctie",
                        "Dagstatus - Tractus 07 Gastro-Intestinaal",
                        "Dagstatus - Tractus 08 Milieu Interieur",
                        "Dagstatus - Tractus 09 Extr/huid",
                        "Dagstatus - Tractus 10 Psych/soc",
                        "Dagstatus - Tractus 11 Overig",
                        "Dagstatus - Tractus 12 Conclusie",
                        "Dagstatus - Tractus 13 Opm dagdienst",
                        "Dagstatus - Tractus 14 Opm A/N dienst",
                        "Dagstatus Print Afspraken",
                        "Dagstatus Print Behandeldoelen",
                        "Form MS Diagnose 1",
                        "Form MS Diagnose 2",
                        "MS Anamnese Overzicht",
                        "MS Chronologie Eventlijst Print",
                        "MS Dagstatus Beleid KT",
                        "MS Dagstatus Beleid LT Print",
                        "MS Decursus Thuismedicatie",
                        "MS Decursus Toedracht bij Opname",
                        "MS Probleemlijst Print",
                        "MS VoorGeschiedenis Overzicht",
                        "MS Gesprek Item Tekst",
                        # "Medische ontslagbrief - Beloop Dictionary",
                        "Medische Ontslagbrief - Beloop",
                        "Ontslagregistratie - Ontslagbestemming - "
                        + "Naam ander ziekenhuis/afdeling (niet UMCU)",
                        "Ontslagregistratie - Ontslagbestemming - "
                        + "Toelichting bij ontslag naar overige bestemmingen",
                    ]
                )
            )
        )
    ]
    df = df.sort_values(by=["department", "description"])

    # rename ontslagbrief
    df["description"] = (
        df["description"]
        .replace("Dagstatus Print Afspraken", "Afspraken")
        .replace("Dagstatus Print Behandeldoelen", "Behandeldoelen")
        .replace("Form MS Diagnose 1", "Diagnosecode 1")
        .replace("Form MS Diagnose 2", "Diagnosecode 2")
        .replace("MS Anamnese Overzicht", "Anamnese")
        .replace("MS Chronologie Eventlijst Print", "Eventlijst")
        .replace("MS Dagstatus Beleid KT", "Korte Termijn Beleid")
        .replace("MS Dagstatus Beleid LT Print", "Lange Termijn Beleid")
        .replace("MS Decursus Thuismedicatie", "Thuismedicatie")
        .replace("MS Decursus Toedracht bij Opname", "Toedracht bij Opname")
        .replace("MS Probleemlijst Print", "Probleemlijst")
        .replace("MS VoorGeschiedenis Overzicht", "Voorgeschiedenis Overzicht")
        .replace("MS Gesprek Item Tekst", "Oudergesprek")
        .replace("Medische Ontslagbrief - Beloop", "Ontslagbrief")
        .replace(
            "Ontslagregistratie - Ontslagbestemming - "
            + "Naam ander ziekenhuis/afdeling (niet UMCU)",
            "Ontslagbestemming - Naam ander ziekenhuis/afdeling",
        )
        .replace(
            "Ontslagregistratie - Ontslagbestemming - "
            + "Toelichting bij ontslag naar overige bestemmingen",
            "Ontslagbestemming - Toelichting bij ontslag naar overige bestemmingen",
        )
    )
    return df


def process_data_metavision_new(
    df: pd.DataFrame, df_discharge_docs_dp: pd.DataFrame
) -> pd.DataFrame:
    """
    Process the given DataFrame containing metavision data.
    The steps were:
    1. include enc_id per admission
    2. remove columns not necessary
    3. Rename columns
    3.5 add full discharge docs from dataplatform export (TODO)
    4. include date column
    5. add length of stay
    6. remove patients with length of stay 0 days
    7. remove encounters that do not have a discharge letter
    8. replace date in rows with 1899 in the date
    9. rename ontslagbrief
    10. remove the MS Probleemlijst Date as it is the same as MS Probleemlijst Print but
         formatted worse
    11. pseudonomise by hand



    Parameters
    ----------
    df : pandas.DataFrame
        The DataFrame containing metavision data.
    df_discharge_docs_dp : pandas.DataFrame
        The DataFrame containing full discharge documentation from the dataplatform.

    Returns
    -------
    pandas.DataFrame
        The processed DataFrame.
    """
    # include enc_id per admission
    df["enc_id"] = df.groupby(["AddmissionDate", "DischargeDate"]).ngroup()

    # Rename and drop columns
    df = df.drop(columns=["ParameterID", "ValidationTime", "pseudo_id"]).rename(
        columns={
            "AddmissionDate": "admissionDate",
            "DischargeDate": "dischargeDate",
            "Name": "department",
            "pseudo_id": "pseudo_id",
            "Time": "time",
            "Abbreviation": "description",
            "Value": "value",
            "enc_id": "enc_id",
        }
    )

    # add full discharge docs from dataplatform export
    # TODO

    # include date column
    df["time"] = pd.to_datetime(df["time"])
    df["date"] = pd.to_datetime(df["time"].dt.date)

    # add length of stay
    df["admissionDate"] = pd.to_datetime(df["admissionDate"])
    df["dischargeDate"] = pd.to_datetime(df["dischargeDate"])
    df["length_of_stay"] = (df["dischargeDate"] - df["admissionDate"]).dt.days

    # remove patients with length of stay 0 days
    df = df[df["length_of_stay"] != 0]

    # remove encounters that do not have a discharge letter
    encounters_with_discharge = df.loc[
        df["description"] == "Medische Ontslagbrief - Beloop", "enc_id"
    ].unique()
    df = df[df["enc_id"].isin(encounters_with_discharge)]

    # Function to replace 1899 dates with the most recent date in the group
    # as the 1899 dates are not valid and contain the discharge docs
    def replace_1899_dates(dates):
        # Replace 1899 dates with the most recent date in the series
        mask = dates.dt.year == 1899
        if mask.any():
            max_date = dates.max()
            dates = dates.where(~mask, max_date)
        return dates

    df["date"] = df.groupby("enc_id")["date"].transform(replace_1899_dates)

    # rename ontslagbrief
    df["description"] = df["description"].replace(
        "Medische Ontslagbrief - Beloop", "Ontslagbrief"
    )

    # remove the MS Probleemlijst Date in description column
    df = df[df["description"] != "MS Probleemlijst Date"]

    # pseudonomise by hand
    df["value"] = df["value"].apply(pseudonomise_by_hand)

    # subset the data based on the names for sections in patient file
    df = df[
        ~(
            (df["department"] == "Intensive Care Centrum")
            & (
                ~df["description"].isin(
                    [
                        "Dagstatus Print Afspraken",  # afspraken
                        "Korte Termijn Beleid (ms)",  # korte termijn beleid
                        "Lange termijn beleid (ms)",  # lange termijn beleid
                        "Medische ontslagbrief - Beloop Dictionary",  # ontslagbrief
                        "MS Diagnose 1",  # diagnose code
                        "MS Probleemlijst Print",  # probleemlijst
                        "Opname Toedracht (ms)",  # reden van opname
                        "Overige afspraken",  # overige afspraken
                        "Print Behandeldoelen",  # behandeldoelen
                        "Print Chronologie Eventlijst",  # beloop (events)
                        "Print Chronologie Titels",  # de titels van de events beloop
                        "Thuismedicatie (ms)",  # Thuismedicatie
                        "Tractus 12 Conclusie",  # conclusie
                        "Tractus 13 Opm dagdienst",  # opmerkingen van de dagdienst
                        "Tractus 14 Opm A/N dienst",  # opmerkingen van de nachtdienst
                        "VG Overzicht (ms)",  # Voorgeschiedenis Overzicht
                        "Ontslagbrief",  # ontslagbrief
                    ]
                )
            )
        )
    ]
    df = df.sort_values(by=["department", "description"])
    df = df[
        ~(
            (df["department"] == "Neonatologie")
            & (
                ~df["description"].isin(
                    [
                        "Anamnese (ms)",
                        "Chronologie Eventlijst Data",
                        "Dagstatus Print Afspraken",
                        "Dec Item Tekst (ms)",
                        "Evaluatie Gemaakte Afspraken (ms)",
                        "Gesprek Item Tekst (ms)",
                        "Korte Termijn Beleid (ms)",
                        "Lange termijn beleid (ms)",
                        "Medicatie bij Opname (ms)",
                        "Medische ontslagbrief - Beloop Dictionary",
                        "MS Diagnose 1",
                        "MS Diagnose 2",
                        "MS Probleemlijst Print",
                        "OntslagCriteria (ms)",
                        "Ontslagbrief",
                        "Opname Toedracht (ms)",
                        "Print Behandeldoelen",
                        "Print Chronologie Eventlijst",
                        "Print Chronologie Titels",
                        "Reden (isol)",
                        "Samenvatting MS onderzoeken",
                        "Thuismedicatie (ms)",
                        "Tractus 01 Lichamelijk Onderzoek",
                        "Tractus 02 Respiratie",
                        "Tractus 03 Circulatie",
                        "Tractus 04 Neurologie",
                        "Tractus 05 Infectie",
                        "Tractus 06 VB/nierfunctie",
                        "Tractus 07 Gastro-Intestinaal",
                        "Tractus 08 Milieu Interieur",
                        "Tractus 09 Extr/huid",
                        "Tractus 10 Psych/soc",
                        "Tractus 11 Overig",
                        "Tractus 12 Conclusie",
                        "Tractus 13 Opm dagdienst",
                        "Tractus 14 Opm A/N dienst",
                        "VG Overzicht (ms)",
                    ]
                )
            )
        )
    ]

    # rename Opname Toedracht (ms) to Reden van Opname
    df["description"] = (
        df["description"]
        .replace("Opname Toedracht (ms)", "Reden van Opname")
        .replace("VG Overzicht (ms)", "Voorgeschiedenis Overzicht")
        .replace("Korte Termijn Beleid (ms)", "Korte Termijn Beleid")
        .replace("Lange termijn beleid (ms)", "Lange Termijn Beleid")
        .replace("Print Behandeldoelen", "Behandeldoelen")
        .replace("MS Probleemlijst Print", "Probleemlijst")
        .replace("Tractus 12 Conclusie", "Conclusie")
        .replace("Tractus 13 Opm dagdienst", "Opmerkingen dagdienst")
        .replace("Tractus 14 Opm A/N dienst", "Opmerkingen nachtdienst")
        .replace("Print Chronologie Eventlijst", "Eventlijst")
        .replace("Print Chronologie Titels", "Eventlijst Titels")
        .replace("MS Diagnose 1", "Diagnosecode 1")
        .replace("MS Diagnose 2", "Diagnosecode 2")
        .replace("Thuismedicatie (ms)", "Thuismedicatie")
        .replace("Dagstatus Print Afspraken", "Dagstatus afspraken")
        .replace("Gesprek Item Tekst (ms)", "Oudergesprek")
        .replace("Anamnese (ms)", "Anamnese")
        .replace(r"Tractus \d\d", "Dagstatus", regex=True)
    )
    return df


def process_data_HiX(
    patient_data: pd.DataFrame, discharge_data: pd.DataFrame
) -> pd.DataFrame:
    """
    Process patient data and discharge data from HiX system.

    Parameters
    ----------
    patient_data : DataFrame
        DataFrame containing patient data.
    discharge_data : DataFrame
        DataFrame containing discharge data.

    Returns
    -------
    DataFrame
        Processed patient file with merged data, sorted by enc ID and time.

    Notes
    -----
    This function performs the following steps:
    1. Remove enc that are not present in both patient_data and discharge_data
    2. Converts some cols to datetime in both patient_data and discharge_data
    3. Renames columns in both patient_data and discharge_data.
    4. Subsets the necessary columns in both patient_data and discharge_data.
    5. Keeps only the last discharge letter in discharge_data.
    6. Merges patient_data and discharge_data.
    7. Adds a "date" column based on the "time" column in the merged data.
    8. Calculates the length of stay for each encounter in the merged data.
    9. Rename ontslagbrief
    10. start with a 1000 index in enc_id
    11. pseudonomise by hand

    """
    # remove encounters that are not in both datasets
    encounters_in_patient_files = patient_data.enc_id.unique()
    encounter_in_discharge_data = discharge_data.enc_id.unique()
    encounters_in_both = set(encounters_in_patient_files).intersection(
        encounter_in_discharge_data
    )

    # Use copy to avoid SettingWithCopyWarning
    patient_data = patient_data[patient_data.enc_id.isin(encounters_in_both)].copy()
    discharge_data = discharge_data[
        discharge_data.enc_id.isin(encounters_in_both)
    ].copy()

    # rename columns
    discharge_data = discharge_data.rename(
        columns={
            "period_end": "dischargeDate",
            "period_start": "admissionDate",
            "created": "time",
            "content_attachment1_plain_data": "value",
            "specialty_Organization_value": "department",
        }
    )
    patient_data = patient_data.rename(
        columns={
            "period_end": "dischargeDate",
            "period_start": "admissionDate",
            "authored": "time",
            "item_text": "description",
            "item_answer_value_valueString": "value",
            "specialty_Organization_value": "department",
        }
    )

    # subset the returned columns
    discharge_data = discharge_data[
        [
            "enc_id",
            "dischargeDate",
            "admissionDate",
            "department",
            "time",
            "description",
            "value",
        ]
    ]
    patient_data = patient_data[
        [
            "enc_id",
            "admissionDate",
            "dischargeDate",
            "department",
            "time",
            "description",
            "value",
        ]
    ]

    # only keep the last discharge letter
    discharge_data = discharge_data.sort_values(by=["enc_id", "time"])
    discharge_data = discharge_data.drop_duplicates(subset=["enc_id"], keep="last")

    # merge
    patient_file = pd.concat([patient_data, discharge_data], axis=0)

    # add cols date and length of stay
    patient_file["date"] = pd.to_datetime(patient_file.time.dt.date)

    # add length of stay
    patient_file["length_of_stay"] = (
        patient_file.dischargeDate - patient_file.admissionDate
    ).dt.days

    # sorting
    patient_file = patient_file.sort_values(by=["enc_id", "time"]).reset_index(
        drop=True
    )

    # rename ontslagbrief
    patient_file["description"] = patient_file["description"].replace(
        "Ontslagbericht", "Ontslagbrief"
    )
    patient_file["description"] = patient_file["description"].replace(
        "Klinische Brief", "Ontslagbrief"
    )

    # map enc_id to start with 1000
    enc_id_map = {
        enc_id: 1000 + i for i, enc_id in enumerate(patient_file.enc_id.unique())
    }
    patient_file["enc_id"] = patient_file["enc_id"].map(enc_id_map)

    # pseudonomise by hand
    patient_file["value"] = patient_file["value"].apply(pseudonomise_by_hand)

    return patient_file


def process_data_HiX_stg(
    patient_data: pd.DataFrame, discharge_data: pd.DataFrame
) -> pd.DataFrame:
    """
    Process patient data and discharge data from HiX system staging database

    Parameters
    ----------
    patient_data : DataFrame
        DataFrame containing patient data.
    discharge_data : DataFrame
        DataFrame containing discharge data.

    Returns
    -------
    DataFrame
        Processed patient file with merged data, sorted by enc ID and time.

    Notes
    -----
    This function performs the following steps:
    1. Remove enc that are not present in both patient_data and discharge_data
    2. Converts some cols to datetime in both patient_data and discharge_data
    3. Renames columns in both patient_data and discharge_data.
    4. Subsets the necessary columns in both patient_data and discharge_data.
    5. Keeps only the last discharge letter in discharge_data.
    6. Merges patient_data and discharge_data.
    7. Adds a "date" column based on the "time" column in the merged data.
    8. Calculates the length of stay for each encounter in the merged data.
    9. Rename ontslagbrief
    10. start with a 1000 index in enc_id
    11. pseudonomise by hand

    """
    # remove encounters that are not in both datasets
    encounters_in_patient_files = patient_data.enc_id.unique()
    encounter_in_discharge_data = discharge_data.enc_id.unique()
    encounters_in_both = set(encounters_in_patient_files).intersection(
        encounter_in_discharge_data
    )

    # Use copy to avoid SettingWithCopyWarning
    patient_data = patient_data[patient_data.enc_id.isin(encounters_in_both)].copy()
    discharge_data = discharge_data[
        discharge_data.enc_id.isin(encounters_in_both)
    ].copy()

    # drop rows with empty value in date and time
    patient_data = patient_data.dropna(subset=["DATE", "TIME"])

    patient_data["DATE"] = patient_data["DATE"].astype(str)
    patient_data["TIME"] = patient_data["TIME"].astype(str)
    # Combine DATE and TIME into one column
    patient_data["time"] = pd.to_datetime(
        patient_data["DATE"] + " " + patient_data["TIME"]
    )

    # rename columns
    discharge_data = discharge_data.rename(
        columns={
            "period_end": "dischargeDate",
            "period_start": "admissionDate",
            "created": "time",
            "content_attachment1_plain_data": "value",
            "specialty_Organization_value": "department",
            "type2_display_original": "description",
        }
    )
    patient_data = patient_data.rename(
        columns={
            "period_end": "dischargeDate",
            "period_start": "admissionDate",
            "subcat": "description",
            "TEXT": "value",
            "specialty_Organization_value": "department",
        }
    )

    # subset the returned columns
    discharge_data = discharge_data[
        [
            "enc_id",
            "dischargeDate",
            "admissionDate",
            "department",
            "time",
            "description",
            "value",
        ]
    ]
    patient_data = patient_data[
        [
            "enc_id",
            "admissionDate",
            "dischargeDate",
            "department",
            "time",
            "description",
            "value",
        ]
    ]

    # only keep the last discharge letter per encounter
    discharge_data = discharge_data.sort_values(by=["enc_id", "time"])
    discharge_data = discharge_data.drop_duplicates(subset=["enc_id"], keep="last")

    # merge
    patient_file = pd.concat([patient_data, discharge_data], axis=0)

    # add cols date and length of stay
    patient_file["date"] = pd.to_datetime(patient_file.time.dt.date)

    # add length of stay
    patient_file["length_of_stay"] = (
        patient_file.dischargeDate - patient_file.admissionDate
    ).dt.days

    # drop rows with empty value
    patient_file = patient_file[~patient_file["value"].isna()]
    patient_file = patient_file[patient_file["value"] != ""]

    # sorting
    patient_file = patient_file.sort_values(by=["enc_id", "time"]).reset_index(
        drop=True
    )

    # rename ontslagbrief
    patient_file["description"] = patient_file["description"].replace(
        "Ontslagbericht", "Ontslagbrief"
    )
    patient_file["description"] = patient_file["description"].replace(
        "Klinische Brief", "Ontslagbrief"
    )

    # map enc_id to start with 1000
    enc_id_map = {
        enc_id: 1000 + i for i, enc_id in enumerate(patient_file.enc_id.unique())
    }
    patient_file["enc_id"] = patient_file["enc_id"].map(enc_id_map)

    return patient_file


def get_patient_file(df: pd.DataFrame, enc_id: int = None) -> Tuple[str, pd.DataFrame]:
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
    patient_file = patient_file[
        ~patient_file.description.str.contains("ontslag", case=False)
    ]

    patient_file_string = "\n\n".join(
        patient_file.apply(
            lambda row: (
                rf"## {row['description']}\n### Datum: {row['date']}\n\n{row['value']}"
            ),
            axis=1,
        )
    )
    patient_file_string = "# Patienten dossier\n\n" + patient_file_string

    return patient_file_string, patient_file


def get_patient_discharge_docs(df: pd.DataFrame, enc_id: int = None) -> str:
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

    discharge_documentation = df[df["description"].isin(["Ontslagbrief"])].sort_values(
        by=["date", "description"]
    )
    return discharge_documentation.value


def split_discharge_docs_NICU(discharge_doc: pd.DataFrame) -> pd.DataFrame:
    """
    Split the discharge document into sections based on predefined headers
    that are available in the string.

    Parameters
    ----------
    discharge_doc : str
        The discharge document text.

    Returns
    -------
    pandas.DataFrame
        A DataFrame containing the sections of the discharge document, with
        the category and text columns.

    """
    headers = [
        "Lichamelijk Onderzoek",
        "Respiratie",
        "Circulatie",
        "Neurologie",
        "Infectie",
        "Milieu Interieure",
        "VB/Nierfunctie",
        "Gastro-Intenstinaal",
        "Psych/Soc",
        "Overig",
        "Conclusie",
    ]

    # sort headers based on the order in the document
    headers = sorted(headers, key=lambda x: discharge_doc.find(x))
    # remove headers that are not in the document
    headers = [header for header in headers if header in discharge_doc]

    # remove # | & and Titel and Bespreking from discharge doc
    discharge_doc = (
        discharge_doc.replace("#", "")
        .replace("|", "")
        .replace("$", "")
        .replace("Titel", "")
        .replace("Bespreking", "")
    )
    # replace headerheader by header in discharge doc
    for header in headers:
        discharge_doc = discharge_doc.replace(header + header, header)

    # Find the start and end indices for each section
    indices = [
        (
            discharge_doc.find(headers[i]) + len(headers[i]),
            discharge_doc.find(headers[i + 1]),
        )
        for i in range(len(headers) - 1)
    ]

    # Extract the sections
    split_strings = [discharge_doc[start:end].strip() for start, end in indices]

    # Include the last section
    split_strings.append(discharge_doc[(indices[-1][1] + len(headers[-1])) :].strip())

    # make a dataframe
    df = pd.DataFrame({"category": headers, "text": split_strings})
    return df


def pseudonomise_by_hand(string):
    """
    Pseudonomises the given string by replacing specific words that are
     identified by hand with placeholders.

    Parameters
    ----------
    string : str
        The input string to be pseudonomised.

    Returns
    -------
    str
        The pseudonomised string.
    """
    with open(Path(__file__).parent / "pseudo.toml", "rb") as f:
        pseudo_dict = tomli.load(f)

    for key, value in pseudo_dict["Pseudonomise_dict"].items():
        string = string.replace(key, value)
    return string


def get_splitted_discharge_docs_NICU(enc_id: int, data: pd.DataFrame) -> pd.DataFrame:
    """
    Retrieves the patient's discharge documentation
    from the given enc ID and data.

    Parameters
    ----------
    enc_id : int
        The encounter ID of the patient.
    data : dict
        The data containing the patient's discharge documentation.

    Returns
    -------
    pandas.DataFrame
        A dataframe containing the splitted discharge letter specific to NICU.
    """
    discharge_letter = get_patient_discharge_docs(enc_id, data)
    discharge_letter = pseudonomise_by_hand(discharge_letter)
    discharge_letter_split_df = split_discharge_docs_NICU(discharge_letter)
    return discharge_letter_split_df


def combine_hix_and_metavision_for_visualisation(
    df_HIX: pd.DataFrame, df_metavision: pd.DataFrame
) -> pd.DataFrame:
    """
    Combines the HIX and metavision data for visualization.

    Parameters
    ----------
    df_HIX : pd.DataFrame
        The HIX data.
    df_metavision : pd.DataFrame
        The metavision data.

    Returns
    -------
    pd.DataFrame
        The combined dataframe for visualization.
    """
    df = pd.concat([df_metavision, df_HIX], axis=0)
    # map enc_id to start from 0
    enc_id_map = {enc_id: i for i, enc_id in enumerate(df.enc_id.unique())}
    df["og_enc_id"] = df["enc_id"]
    df["enc_id"] = df["enc_id"].map(enc_id_map)

    # remove Intensive Care Kinderen and High Care Kinderen
    df = df[~df.department.isin(["Intensive Care Kinderen", "High Care Kinderen"])]
    df["label"] = (
        "Patiënt "
        + df["enc_id"].astype(str)
        + " ("
        + df["department"]
        + ": "
        + df["length_of_stay"].astype(str)
        + " dagen opname)"
        + " ; voorheen "
        + df["og_enc_id"].astype(str)
    )
    # sort by department
    df = df.sort_values(by=["department", "enc_id", "date"])
    return df


if __name__ == "__main__":
    data_folder = Path(__file__).parents[3] / "data"

    # load and process HIX data
    df_HiX_patient_files = pd.read_parquet(
        data_folder / "raw" / "pseudonomised_HiX_patient_files.parquet"
    )
    df_HiX_discharge = pd.read_parquet(
        data_folder / "raw" / "pseudonomised_HiX_discharge_data.parquet"
    )
    df_HiX = process_data_HiX(df_HiX_patient_files, df_HiX_discharge)

    # load and process HIX CAR data for pre-pilot
    df_HiX_patient_files = pd.read_parquet(
        data_folder
        / "raw"
        / "pseudonomised_HiX_patient_files_CAR_april_rtf_decoded.parquet"
    )
    df_HiX_discharge = pd.read_parquet(
        data_folder / "raw" / "pseudonomised_HiX_discharge_docs_CAR_april.parquet"
    )
    df_HiX_CAR_pp = process_data_HiX_stg(df_HiX_patient_files, df_HiX_discharge)

    # load and process metavision data
    df_metavision_dp = pd.read_parquet(
        data_folder / "raw" / "pseudonomised_metavision_data_april.parquet"
    ).pipe(process_data_metavision_dp)
    df_metavision_new = pd.read_parquet(
        data_folder / "raw" / "pseudonomised_new_metavision_data.parquet"
    ).pipe(lambda df: process_data_metavision_new(df, df_HiX_discharge))

    # Store the processed data
    df_metavision_dp.to_parquet(
        data_folder / "processed" / "metavision_data_april_dp.parquet"
    )
    df_metavision_new.to_parquet(
        data_folder / "processed" / "metavision_new_data.parquet"
    )
    df_HiX.to_parquet(data_folder / "processed" / "HiX_data.parquet")

    df_HiX_CAR_pp.to_parquet(
        data_folder / "processed" / "HiX_CAR_data_pre_pilot.parquet"
    )
