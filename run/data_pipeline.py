import logging
import os
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from striprtf.striprtf import rtf_to_text

from discharge_docs.processing.bulk_generation import bulk_generate
from discharge_docs.processing.deduce_text import apply_deduce
from discharge_docs.processing.processing import (
    combine_patient_and_docs_data_hix,
    process_data,
    write_encounter_ids,
)

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# config
EXPORT_DATAPLATFORM = True  # only set to False when data export has already been done
START_DATE = "2025-01-01"
END_DATE = "2025-01-02"
DB_USER = os.getenv("DB_USER")
DB_PASSWD = os.getenv("DB_PASSWD")

PROCESSING = True  # set only to False when processing has already been done
ADD_DEMO_PATIENT = True

BULK_GENERATE_LETTERS = False
KEEP_OLD_BULK_LETTERS = True


def run_export() -> None:
    # this function exports data from the dataplatform to the raw_data_folder based on
    # the queries in data/sql
    with open(
        Path(__file__).parents[1] / "data" / "sql" / "hix_patient_files_retro_stg.sql"
    ) as f:
        query_hix_patient = text(f.read())

    with open(
        Path(__file__).parents[1] / "data" / "sql" / "hix_discharge_docs_retro.sql"
    ) as f:
        query_hix_docs = text(f.read())

    with open(Path(__file__).parents[1] / "data" / "sql" / "metavision_retro.sql") as f:
        query_metavision = text(f.read())

    engine = create_engine(
        rf"mssql+pymssql://{DB_USER}:{DB_PASSWD}@dataplatform:1433/PUB"
    )

    queries = [query_hix_patient, query_hix_docs, query_metavision]
    data = []

    for query in queries:
        data.append(
            pd.read_sql(
                query,
                engine,
                params={"start_date": START_DATE, "end_date": END_DATE},
            )
        )

    data_hix_patient, data_hix_docs, data_metavision = data

    data_hix_patient.to_json(
        raw_data_folder / f"{START_DATE}_{END_DATE}_hix_patient.json"
    )
    data_hix_docs.to_json(raw_data_folder / f"{START_DATE}_{END_DATE}_hix_docs.json")
    data_metavision.to_json(
        raw_data_folder / f"{START_DATE}_{END_DATE}_metavision.json", index=False
    )
    logger.info("Data export complete and saved to datamanager folder")


def run_processing() -> None:
    # this function processes the data from the raw_data_folder and saves it to the
    # processed_data_folder
    file_names = ["metavision", "hix_docs", "hix_patient"]

    data_frames = {
        name: pd.read_json(
            Path(raw_data_folder / f"{START_DATE}_{END_DATE}_{name}.json"),
            convert_dates=["admissionDate", "dischargeDate", "date"],
        )
        for name in file_names
    }

    metavision_data, hix_docs_data, hix_patient_data = data_frames.values()

    hix_patient_data["content"] = hix_patient_data["content"].apply(rtf_to_text)

    hix_data = combine_patient_and_docs_data_hix(hix_patient_data, hix_docs_data)

    if set(hix_data["enc_id"]) & set(metavision_data["enc_id"]):
        logger.warning(
            "There is an enc_id overlapping in both HiX and Metavision data."
        )
    combined_data = pd.concat([hix_data, metavision_data], axis=0).reset_index(
        drop=True
    )

    combined_data = apply_deduce(combined_data, "content")

    combined_data = combined_data.drop(columns="patient_id")

    combined_data = process_data(
        combined_data,
        remove_encs_no_docs=True,
    )

    if ADD_DEMO_PATIENT:
        demo_patient = pd.read_csv(
            Path(__file__).parents[1] / "data" / "examples" / "DEMO_patient_1.csv",
            sep=";",
            parse_dates=["admissionDate", "dischargeDate", "date"],
        )
        combined_data = pd.concat([demo_patient, combined_data], axis=0).reset_index(
            drop=True
        )

    write_encounter_ids(combined_data, n_enc_ids=25)

    combined_data.to_parquet(Path(processed_data_folder / "evaluation_data.parquet"))

    logger.info('Processing complete and saved to "data/processed" folder')


def run_bulk_generation() -> None:
    # this function generates bulk letters based for the processed data
    if KEEP_OLD_BULK_LETTERS:
        bulk_letters = pd.read_parquet(
            Path(processed_data_folder / "bulk_generated_docs_gpt.parquet")
        )
        bulk_letters.to_parquet(
            Path(processed_data_folder / "bulk_generated_docs_gpt_old.parquet")
        )
        logger.info("Old bulk letters saved to 'bulk_generated_docs_gpt_old.parquet'")

    data = pd.read_parquet(Path(processed_data_folder / "evaluation_data.parquet"))
    bulk_generate(data, save_folder=processed_data_folder)
    logger.info("Bulk generation of letters complete")


if __name__ == "__main__":
    raw_data_folder = Path(
        "/mapr/administratielast/administratielast_datamanager/ontslagdocumentatie/"
    )
    processed_data_folder = Path(__file__).parents[1] / "data" / "processed"
    load_dotenv()

    if EXPORT_DATAPLATFORM:
        run_export()

    if PROCESSING:
        run_processing()

    if BULK_GENERATE_LETTERS:
        run_bulk_generation()
