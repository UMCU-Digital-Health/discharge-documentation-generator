from pathlib import Path

import pandas as pd
from deduce import Deduce
from striprtf.striprtf import rtf_to_text
from tqdm import tqdm

tqdm.pandas()

deduce = Deduce(cache_path=Path(__file__).parents[3] / "run")


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


if __name__ == "__main__":
    # Load all data
    base_path = Path(
        "/mapr/administratielast/administratielast_datamanager/ontslagdocumentatie/"
    )
    export_path = base_path / "2025-01-22_compare_new_gpt"

    hix_patient_data = pd.read_csv(
        export_path / "hix_patient_files.csv",
        dtype={"subject_Patient_value": str},
        parse_dates=["period_start", "period_end", "DATE"],
    )
    # Contains RTF encoded text
    hix_patient_data.loc[hix_patient_data["TEXT"].isna(), "TEXT"] = ""
    hix_patient_data["TEXT"] = hix_patient_data["TEXT"].apply(rtf_to_text)

    hix_discharge_data = pd.read_csv(
        export_path / "hix_discharge_docs.csv",
        dtype={"subject_Patient_value": str},
        parse_dates=["period_start", "period_end", "created"],
    )

    metavision_data = pd.read_csv(
        export_path / "metavision_data.csv",
        dtype={"HospitalNumber": str},
        parse_dates=["period_start", "period_end", "effectiveDateTime"],
    )

    # Apply Deduce
    hix_patient_data = apply_deduce(hix_patient_data, "TEXT")
    hix_discharge_data = apply_deduce(
        hix_discharge_data, "content_attachment1_plain_data"
    )
    metavision_data = apply_deduce(metavision_data, "valueString")

    # Store pseudonomised data
    hix_patient_data[["pseudo_id", "subject_Patient_value"]].to_csv(
        export_path / "hix_pseudo_table.csv", index=False
    )
    hix_patient_data.drop(columns=["subject_Patient_value"]).to_parquet(
        export_path / "pseudonomised_HiX_patient_files.parquet"
    )
    hix_discharge_data.drop(columns=["subject_Patient_value"]).to_parquet(
        export_path / "pseudonomised_HiX_discharge_data.parquet"
    )

    metavision_data[["pseudo_id", "subject_Patient_value"]].to_csv(
        export_path / "metavision_pseudo_table.csv", index=False
    )
    metavision_data.drop(columns=["subject_Patient_value"]).to_parquet(
        export_path / "pseudonomised_new_metavision_data.parquet"
    )
