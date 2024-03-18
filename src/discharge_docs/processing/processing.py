import os
from pathlib import Path
from typing import Tuple

import pandas as pd
import tiktoken
import tomli

os.environ["TIKTOKEN_CACHE_DIR"] = ""


def process_data_metavision(df: pd.DataFrame) -> pd.DataFrame:
    """
    Process the given DataFrame containing metavision data.

    - Remove patients with length of stay 0 days.
    - Remove encounters that do not have a discharge letter.
    - Create columns with nr of words, nr of characters, & nr of tokens
    - Keep only the latest input per category per date.
    - Drop rows where columns are NaN.

    Parameters
    ----------
    df : pandas.DataFrame
        The DataFrame containing metavision data.

    Returns
    -------
    processed_df : pandas.DataFrame
        The processed DataFrame.
    """
    # Remove patients with length of stay 0 days
    df["date"] = pd.to_datetime(df["effectiveDateTime"].dt.date)
    df["length_of_stay"] = (df["period_end"] - df["period_start"]).dt.days
    df = df[df["length_of_stay"] != 0]

    # remove encounters that do not have a discharge letter
    encounters_with_discharge = df.loc[
        df["code_display_original"] == "Medische Ontslagbrief - Beloop",
        "enc_id",
    ].unique()
    df = df[df["enc_id"].isin(encounters_with_discharge)]

    # create columns with nr words, nr characters and nr tokens
    df["nr_words"] = df["valueString"].str.split().str.len()
    df["nr_characters"] = df["valueString"].str.len()
    encoding = tiktoken.get_encoding("cl100k_base")
    df["nr_tokens"] = df["valueString"].apply(lambda x: len(encoding.encode(x)))
    df["encodings"] = df["valueString"].apply(lambda x: encoding.encode(x))

    # keep only the latest input per category per date
    df = (
        df.rename(columns={"location_Location_value_original": "department"})
        .sort_values(by=["enc_id", "date"])
        .drop_duplicates(
            subset=["enc_id", "date", "code_display_original"], keep="last"
        )
        .dropna(
            subset=[
                "pseudo_id",
                "enc_id",
                "period_start",
                "period_end",
                "department",
                "code_display_original",
                "valueString",
                "date",
            ],
        )
        .reset_index(drop=True)
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
    def replace_1899_dates(group):
        # Replace 1899 dates with the most recent date in the group
        group.loc[group["date"].dt.year == 1899, "date"] = group["date"].max()
        return group

    # Group by 'enc_id' and apply the function
    df = df.groupby("enc_id").apply(replace_1899_dates).reset_index(drop=True)

    # rename ontslagbrief
    df["description"] = df["description"].replace(
        "Medische Ontslagbrief - Beloop", "Ontslagbrief"
    )

    # remove the MS Probleemlijst Date in description column
    df = df[df["description"] != "MS Probleemlijst Date"]

    # pseudonomise by hand
    df["value"] = df["value"].apply(pseudonomise_by_hand)

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

    patient_file_string = "\n".join(
        patient_file.apply(
            lambda row: (f"{row['description']} ( {row['date']} ): {row['value']}"),
            axis=1,
        )
    )

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

    # load and process metavision data
    df_metavision = pd.read_parquet(
        data_folder / "raw" / "pseudonomised_metavision_data.parquet"
    ).pipe(process_data_metavision)
    df_metavision_new = pd.read_parquet(
        data_folder / "raw" / "pseudonomised_new_metavision_data.parquet"
    ).pipe(lambda df: process_data_metavision_new(df, df_HiX_discharge))

    # combined data for visualisation
    df_combined = combine_hix_and_metavision_for_visualisation(
        df_HiX, df_metavision_new
    )

    # Store the processed data
    df_metavision.to_parquet(data_folder / "processed" / "metavision_data.parquet")
    df_metavision_new.to_parquet(
        data_folder / "processed" / "metavision_new_data.parquet"
    )
    df_HiX.to_parquet(data_folder / "processed" / "HiX_data.parquet")
    df_combined.to_parquet(
        data_folder / "processed" / "combined_data_for_visualisation.parquet"
    )
