# Processing file to pseudonomise data by applying Deduce

from hashlib import sha256
from pathlib import Path

import pandas as pd
from deduce import Deduce
from tqdm import tqdm

tqdm.pandas()
deduce = Deduce()


def apply_deduce(df: pd.DataFrame, col_name: str) -> pd.DataFrame:
    """
    Apply deduce function to deidentify text in a specific column of a DataFrame.

    Parameters
    ----------
    df : pd.DataFrame
        The DataFrame containing the text data.
    col_name : str
        The name of the column to apply deduce function on.

    Returns
    -------
    pd.DataFrame
        The DataFrame with deidentified text in the specified column.

    """
    df[col_name] = (
        df[col_name]
        .fillna("")  # some None values, which are not handled by deduce
        .progress_apply(
            lambda x: deduce.deidentify(x, disabled={"dates"}).deidentified_text
        )
    )
    return df


def deduce_metavision_database(
    metavision_admissions: pd.DataFrame,
    metavision_freetext: pd.DataFrame,
    data_path: Path,
    save: bool = True,
):
    """Deduce metavision database.

    Parameters
    ----------
    metavision_admissions : pd.DataFrame
        The DataFrame containing metavision admissions data.
    metavision_freetext : pd.DataFrame
        The DataFrame containing metavision freetext data.
    data_path : Path
        The path to save the deduced data.

    """
    metavision_admissions["pseudo_id"] = (
        metavision_admissions["HospitalNumber"].astype(str) + "aiva"
    ).apply(lambda x: sha256(x.encode("utf-16le")).hexdigest())

    metavision_admissions = metavision_admissions.rename(
        columns={"HospitalNumber": "subject_Patient_value"}
    ).drop(columns=["LogicalUnitID"])

    metavision_freetext = metavision_freetext.drop(
        columns=["LogicalUnitID", "CategoryID"]
    )

    metavision_data = metavision_admissions.merge(
        metavision_freetext, on="PatientID"
    ).drop(columns="PatientID")

    metavision_data = apply_deduce(metavision_data, "Value")

    # save data
    if save:
        metavision_data[
            ["pseudo_id", "subject_Patient_value"]
        ].drop_duplicates().to_csv(
            data_path / "metavision_pseudo_table.csv", index=False
        )
        metavision_data.drop(columns="subject_Patient_value").to_csv(
            data_path / "pseudonomised_metavision_data.csv", index=False
        )
        metavision_data.drop(columns="subject_Patient_value").to_parquet(
            data_path / "pseudonomised_metavision_data.parquet"
        )


def apply_and_save_deduce_hix(
    data: pd.DataFrame,
    column: str,
    save: bool,
    save_path: Path = Path(""),
    save_file_name: str = "",
    staging=False,
):
    """Apply deduce function to deidentify text in a specific column of a DataFrame
    and save the results.

    Parameters
    ----------
    data : pd.DataFrame
        The DataFrame containing the text data.
    column : str
        The name of the column to apply deduce function on.
    save : bool
        Flag indicating whether to save the results.
    save_path : Path, optional
        The path to save the deduced data, by default Path("").
    save_file_name : str, optional
        The name of the file to save the deduced data, by default "".
    staging : bool, optional
        Flag indicating whether the deduced data is for staging purposes, default False.
    """
    hix_patient_files = apply_deduce(data, column)

    if save:
        # pseudo keylist table
        hix_patient_files[
            ["pseudo_id", "subject_Patient_value"]
        ].drop_duplicates().to_csv(
            save_path / (save_file_name + "pseudo_table.csv"),
            index=False,
        )
        if not staging:
            # save discharge data to csv
            hix_patient_files.drop(columns="subject_Patient_value").to_csv(
                save_path / ("pseudonomised_" + save_file_name + ".csv"),
                index=False,
            )

        # save discharge data to parquet
        hix_patient_files.drop(columns="subject_Patient_value").to_parquet(
            save_path / ("pseudonomised_" + save_file_name + ".parquet"),
        )


if __name__ == "__main__":
    data_folder = Path(
        "/mapr/"
        "administratielast/"
        "administratielast_datamanager/"
        "ontslagdocumentatie/"
    )

    # change this to only run part of the deduce flow
    deduce_metavision_db_export_dev = False
    deduce_hix_dp_export_dev = False
    deduce_pre_pilot = True

    if deduce_metavision_db_export_dev:
        # Metavision deduce (metavision database export)
        export_folder_name = "Metavision export development IC NICU"
        data_path = data_folder / export_folder_name

        metavision_admissions = pd.read_csv(
            data_path / "2024-01-09 MV6 admissions LMM.csv",
            sep=";",
            parse_dates=["AddmissionDate", "DischargeDate"],
            dtype={"HospitalNumber": str},
        )
        metavision_freetext = pd.read_csv(
            data_path / "2024-01-09 MV6 freetexts LMM.csv",
            sep=";",
            parse_dates=["Time", "ValidationTime"],
        )

        deduce_metavision_database(
            metavision_admissions, metavision_freetext, data_path, save=True
        )

    if deduce_hix_dp_export_dev:
        # HiX deduce (dataplatform export)
        export_folder_name = "HiX export development CAR"
        data_path = data_folder / export_folder_name

        file_name = "HiX_discharge_docs_3.json"
        hix_discharge_data = pd.read_json(
            Path(data_path) / file_name,
            convert_dates=["period_start", "period_end", "created"],
            dtype={"subject_Patient_value": str},
        )

        file_name = "HiX_patient_files_3.json"
        hix_patient_files = pd.read_json(
            Path(data_path) / file_name,
            convert_dates=["period_start", "period_end", "created", "authored"],
            dtype={"subject_Patient_value": str},
        )

        apply_and_save_deduce_hix(
            hix_discharge_data, column="content_attachment1_plain_data", save=True
        )
        apply_and_save_deduce_hix(
            hix_patient_files, column="item_answer_value_valueString", save=True
        )

    if deduce_pre_pilot:
        # HiX Pre-Pilot deduce (dataplatform export)
        export_folder_name = "pre-pilot IC NICU CAR"
        data_path = data_folder / export_folder_name

        file_name = "HiX_discharge_docs_CAR_april.json"
        hix_discharge_data = pd.read_json(
            Path(data_path) / file_name,
            convert_dates=["period_start", "period_end", "created"],
            dtype={"subject_Patient_value": str},
        )

        file_name = "HiX_patient_files_CAR_april_rtf_decoded.json"
        hix_patient_files = pd.read_json(
            Path(data_path) / file_name,
            convert_dates=["period_start", "period_end", "created", "authored"],
            dtype={"subject_Patient_value": str},
        )

        apply_and_save_deduce_hix(
            hix_discharge_data, column="content_attachment1_plain_data", save=True
        )
        apply_and_save_deduce_hix(
            hix_patient_files, column="TEXT", save=True, staging=True
        )
