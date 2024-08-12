import re
from typing import Tuple

import pandas as pd


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


def process_data_metavision_dp(df: pd.DataFrame, nifi: bool = False) -> pd.DataFrame:
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
    nifi : bool
        Whether the data is from nifi or not to determine datetime processing

    Returns
    -------
    pandas.DataFrame
        The processed DataFrame.
    """
    if not nifi:
        # replace enc_id per admission (start date and pseudo_id) for privacy
        df["enc_id"] = df.groupby(["period_start", "pseudo_id"]).ngroup()

    # Rename and drop columns
    if "pseudo_id" in df.columns:
        df = df.drop(columns=["pseudo_id"])

    df = df.rename(
        columns={
            "period_start": "admissionDate",
            "period_end": "dischargeDate",
            "location_Location_value_original": "department",
            "effectiveDateTime": "time",
            "code_display_original": "description",
            "valueString": "value",
            "enc_id": "enc_id",
            "subject_Patient_value": "patient_number",
        }
    )

    # include date column
    if nifi:
        df["time"] = pd.to_datetime(df["time"].astype(float), unit="ms")
        df["admissionDate"] = pd.to_datetime(
            df["admissionDate"].astype(float), unit="ms"
        )
    else:
        df["time"] = pd.to_datetime(df["time"])
        df["admissionDate"] = pd.to_datetime(df["admissionDate"])
        df["dischargeDate"] = pd.to_datetime(df["dischargeDate"])

    df["date"] = pd.to_datetime(df["time"].dt.date)

    # include length of stay when available
    if "dischargeDate" in df.columns and not df["dischargeDate"].isna().all():
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

    if not nifi:
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
                f"## {row['description']}\n### Datum: {row['date']}\n\n{row['value']}"
            ),
            axis=1,
        )
    )
    patient_file_string = "# Patienten dossier\n\n" + patient_file_string

    return patient_file_string, patient_file
