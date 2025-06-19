import logging
import os
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv
from openai import AzureOpenAI
from sqlalchemy import create_engine, text
from sqlalchemy.engine.url import URL
from striprtf.striprtf import rtf_to_text

from discharge_docs.dashboard.helper import load_enc_ids
from discharge_docs.llm.connection import initialise_azure_connection
from discharge_docs.processing.bulk_generation import bulk_generate
from discharge_docs.processing.deduce_text import apply_deduce
from discharge_docs.processing.processing import (
    combine_patient_and_docs_data_hix,
    process_data,
    write_encounter_ids,
)

load_dotenv()

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Suppress DEBUG logs from OpenAI SDK, httpcore, and httpx
logging.getLogger("openai").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
logging.getLogger("httpx").setLevel(logging.WARNING)

# config
DATA_SOURCE_HIX = False
DATA_SOURCE_METAVISION = False
DATA_SOURCE_DEMO = True

EXPORT_DATAPLATFORM = False  # only set to False when data export has already been done
START_DATE = "2025-02-01"
END_DATE = "2025-02-03"
DB_USER = os.getenv("DB_USER")
DB_PASSWD = os.getenv("DB_PASSWD")

PROCESSING = True  # set only to False when processing has already been done
# and enc_ids.toml is filled with the desired encounter ids
COMBINE_WITH_PREVIOUS_DATA = False

BULK_GENERATE_LETTERS = False
MOVE_OLD_BULK_TO_BACKUP = False
DEPARTMENTS = ["DEMO"]  # ["IC", "NICU", "CAR", "DEMO"]


def run_export(
    data_source_hix: bool,
    data_source_metavision: bool,
    query_data_folder: Path,
    raw_data_folder: Path,
) -> None:
    """This function exports data from the dataplatform to the raw_data_folder based on
    the queries in data/sql. Data_source_hix and data_source_metavision are booleans
    to indicate whether to export data from HiX and Metavision respectively"""
    if not data_source_hix and not data_source_metavision:
        logger.warning("No data sources selected for export.")
        return

    queries = []

    if data_source_hix:
        with open(Path(query_data_folder / "hix_patient_files_retro_stg.sql")) as f:
            query_hix_patient = text(f.read())
            queries.append(query_hix_patient)

        with open(Path(query_data_folder / "hix_discharge_docs_retro.sql")) as f:
            query_hix_docs = text(f.read())
            queries.append(query_hix_docs)

    if data_source_metavision:
        with open(Path(query_data_folder / "metavision_retro.sql")) as f:
            query_metavision = text(f.read())
            queries.append(query_metavision)

    db_url = URL.create(
        drivername="mssql+pymssql",
        username=DB_USER,
        password=DB_PASSWD,
        host="dataplatform",
        port=1433,
        database="PUB",
    )
    engine = create_engine(db_url)
    data = []

    for query in queries:
        query_result = pd.read_sql(
            query,
            engine,
            params={"start_date": START_DATE, "end_date": END_DATE},
        )
        data.append(query_result)
        if query_result.empty:
            logger.warning("One of the queries returned no data.")

    if data_source_hix:
        data_hix_patient, data_hix_docs = data[:2]
        data_hix_patient.to_json(
            raw_data_folder / f"{START_DATE}_{END_DATE}_hix_patient.json", index=False
        )
        data_hix_docs.to_json(
            raw_data_folder / f"{START_DATE}_{END_DATE}_hix_docs.json", index=False
        )

    if data_source_metavision:
        data_metavision = data[-1]
        data_metavision.to_json(
            raw_data_folder / f"{START_DATE}_{END_DATE}_metavision.json", index=False
        )

    logger.info("Data export complete and saved to datamanager folder")


def run_processing(
    data_source_hix: bool,
    data_source_metavision: bool,
    data_source_demo: bool,
    raw_data_folder: Path,
    processed_data_folder: Path,
    combine_with_previous_data: bool,
) -> None:
    """This function processes the data from the raw_data_folder and saves it to the
    processed_data_folder. Data_source_hix and data_source_metavision are booleans
    to indicate whether to process data from HiX and Metavision respectively. If the
    combine_with_previous_data is set to True, the new data is combined with the
    previously processed data"""
    if not data_source_hix and not data_source_metavision and not data_source_demo:
        logger.warning("No data sources selected for processing.")
        return

    data_frames = []

    if data_source_hix:
        hix_patient_data = pd.read_json(
            Path(raw_data_folder / f"{START_DATE}_{END_DATE}_hix_patient.json"),
            convert_dates=["admissionDate", "dischargeDate", "date"],
        )
        hix_docs_data = pd.read_json(
            Path(raw_data_folder / f"{START_DATE}_{END_DATE}_hix_docs.json"),
            convert_dates=["admissionDate", "dischargeDate", "date"],
        )
        hix_patient_data["content"] = hix_patient_data["content"].apply(rtf_to_text)
        hix_data = combine_patient_and_docs_data_hix(hix_patient_data, hix_docs_data)
        data_frames.append(hix_data)

    if data_source_metavision:
        metavision_data = pd.read_json(
            Path(raw_data_folder / f"{START_DATE}_{END_DATE}_metavision.json"),
            convert_dates=["admissionDate", "dischargeDate", "date"],
        )
        data_frames.append(metavision_data)

    if (
        data_source_hix
        and data_source_metavision
        and set(hix_data["enc_id"]) & set(metavision_data["enc_id"])
    ):
        logger.warning(
            "There is an enc_id overlapping in both HiX and Metavision data."
        )

    if data_frames:
        data = (
            pd.concat(data_frames, axis=0)
            .reset_index(drop=True)
            .pipe(apply_deduce, "content")
            .drop(columns="patient_id")
            .pipe(process_data, remove_encs_no_docs=True)
        )
    else:
        # Initialize empty dataframe with expected structure if no main data sources
        data = pd.DataFrame()

    if data_source_demo:
        demo_patient = pd.read_csv(
            Path(__file__).parents[1] / "data" / "examples" / "DEMO_patient_1.csv",
            sep=";",
            parse_dates=["admissionDate", "dischargeDate", "date"],
        )
        if not data.empty and demo_patient["enc_id"].isin(data["enc_id"]).any():
            logger.warning("Demo patient enc_id already in data.")
        data = pd.concat([demo_patient, data], axis=0).reset_index(drop=True)

    if combine_with_previous_data:
        data_old = pd.read_parquet(
            Path(processed_data_folder / "evaluation_data.parquet")
        )
        if set(data_old["enc_id"]) & set(data["enc_id"]):
            logger.warning(
                "There is an enc_id overlapping in old and new processed data."
            )
        data = pd.concat([data_old, data], axis=0).reset_index(drop=True)

    write_encounter_ids(data, n_enc_ids=25)

    data.to_parquet(Path(processed_data_folder / "evaluation_data.parquet"))

    logger.info('Processing complete and saved to "data/processed" folder')


def run_bulk_generation(
    client: AzureOpenAI, departments: list[str], processed_data_folder: Path
) -> None:
    """This function runs the bulk generation of discharge letters for the departments
    specified in the departments list. The generated letters are saved to the
    processed_data_folder. If KEEP_OLD_BULK_LETTERS is set to True, the old bulk letters
    are saved to 'bulk_generated_docs_gpt_old.parquet'"""
    old_bulk_letters = pd.read_parquet(
        Path(processed_data_folder / "bulk_generated_docs_gpt.parquet")
    )

    if MOVE_OLD_BULK_TO_BACKUP:
        old_bulk_letters.to_parquet(
            Path(processed_data_folder / "bulk_generated_docs_gpt_old.parquet")
        )
        logger.info("Old bulk letters saved to 'bulk_generated_docs_gpt_old.parquet'")

    data = pd.read_parquet(Path(processed_data_folder / "evaluation_data.parquet"))
    enc_ids_dict = load_enc_ids()

    # filter based on the departments that are selected
    data = data[data["department"].isin(departments)]
    enc_ids_dict = {
        department: enc_ids
        for department, enc_ids in enc_ids_dict.items()
        if department in departments
    }

    bulk_generate(
        data,
        save_folder=processed_data_folder,
        enc_ids_dict=enc_ids_dict,
        client=client,
        skip_old_enc_ids=True,
        old_bulk_letters=old_bulk_letters,
    )
    logger.info("Bulk generation of letters complete")


if __name__ == "__main__":
    query_data_foler = Path(__file__).parents[1] / "data" / "sql"
    raw_data_folder = Path(
        "/mapr/administratielast/administratielast_datamanager/ontslagdocumentatie/export"
    )
    processed_data_folder = Path(__file__).parents[1] / "data" / "processed"

    if EXPORT_DATAPLATFORM:
        run_export(
            DATA_SOURCE_HIX, DATA_SOURCE_METAVISION, query_data_foler, raw_data_folder
        )

    if PROCESSING:
        run_processing(
            DATA_SOURCE_HIX,
            DATA_SOURCE_METAVISION,
            DATA_SOURCE_DEMO,
            raw_data_folder,
            processed_data_folder,
            COMBINE_WITH_PREVIOUS_DATA,
        )

    if BULK_GENERATE_LETTERS:
        client = initialise_azure_connection()
        run_bulk_generation(client, DEPARTMENTS, processed_data_folder)
