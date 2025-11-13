import logging
import os
import sys
from datetime import datetime
from pathlib import Path

import click
import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import create_engine, select, text
from sqlalchemy.engine.url import URL
from sqlalchemy.orm import sessionmaker
from striprtf.striprtf import rtf_to_text
from umcu_ai_utils.database_connection import get_engine

from discharge_docs.config import (
    DEPLOYMENT_NAME_BULK,
    load_department_config,
    setup_root_logger,
)
from discharge_docs.dashboard.helper import (
    write_encounter_ids,
)
from discharge_docs.database.models import Base, DashEncounter, PatientFile, StoredDoc
from discharge_docs.llm.connection import initialise_azure_connection
from discharge_docs.processing.bulk_generation import run_bulk_generation
from discharge_docs.processing.deduce_text import apply_deduce
from discharge_docs.processing.processing import (
    combine_patient_and_docs_data_hix,
    process_data,
)

load_dotenv()

logger = logging.getLogger(__name__)


def run_export(data_source: str, start_date: str, end_date: str) -> None:
    """Export data from the dataplatform to raw_data_folder based on SQL in data/sql.

    Parameters
    ----------
    data_source : str
        The source of the data ("hix" or "metavision").
    start_date : str
        The start date for the data export.
    end_date : str
        The end date for the data export.

    Raises
    ------
    ValueError
        If the data_source is unknown.
    """
    query_data_folder = Path(__file__).parents[1] / "data" / "sql"
    raw_data_folder = Path(
        "/mapr/administratielast/administratielast_datamanager/ontslagdocumentatie/export"
    )

    # Determine which SQL files to run based on data source
    if data_source == "hix":
        sql_files = [
            ("hix_patient_files_retro_stg.sql", "hix_patient"),
            ("hix_discharge_docs_retro.sql", "hix_docs"),
        ]
    elif data_source == "metavision":
        sql_files = [("metavision_retro.sql", "metavision")]
    else:
        raise ValueError(
            f"Unknown data_source '{data_source}'. Expected 'hix' or 'metavision'."
        )

    # Database connection
    db_url = URL.create(
        drivername="mssql+pymssql",
        username=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWD"),
        host="dataplatform",
        port=1433,
        database="PUB",
    )
    engine = create_engine(db_url)
    logger.info("Connected to dataplatform database, running queries...")
    # Run queries and export results
    for sql_file, label in sql_files:
        sql_path = query_data_folder / sql_file
        query = text(sql_path.read_text())

        df = pd.read_sql(
            query,
            engine,
            params={"start_date": start_date, "end_date": end_date},
        )

        if df.empty:
            logger.warning("Query returned no data.")

        output_path = raw_data_folder / f"{start_date}_{end_date}_{label}.json"
        df.to_json(output_path, index=False)

    logger.info("Data export complete and saved to datamanager folder")


def _remove_department_encs_from_db(
    session_factory: sessionmaker, department: str
) -> None:
    """Remove all encounter IDs including patient files and docs for a given department
    from the DB."""
    with session_factory() as session:
        logger.info(f"Removing previous encounter IDs for department {department}.")
        existing_encounters = session.execute(
            select(DashEncounter).where(DashEncounter.department == department)
        ).scalars()
        for enc in existing_encounters:
            if enc.stored_doc_relation is not None:
                for entry in list(enc.stored_doc_relation):
                    session.delete(entry)
            if enc.patient_file_relation is not None:
                for entry in list(enc.patient_file_relation):
                    session.delete(entry)
            session.delete(enc)
        session.commit()


def _remove_patient_file_and_letters_from_db(
    session_factory: sessionmaker, enc_id: int
) -> None:
    """remove patient file and discharge letters for a given enc ID from the DB."""
    with session_factory() as session:
        encounter_db = session.execute(
            select(DashEncounter).where(DashEncounter.enc_id == str(enc_id))
        ).scalar_one_or_none()

        if encounter_db:
            if encounter_db.stored_doc_relation is not None:
                for entry in list(encounter_db.stored_doc_relation):
                    session.delete(entry)
            if encounter_db.patient_file_relation is not None:
                for entry in list(encounter_db.patient_file_relation):
                    session.delete(entry)
            session.commit()


def _save_patient_file_to_db(
    session_factory: sessionmaker, data: pd.DataFrame, remove_previous_encs: bool
) -> None:
    """Save patient file dataframe to the database."""
    with session_factory() as session:
        if remove_previous_encs:
            _remove_department_encs_from_db(
                session_factory, department=data["department"].iloc[0]
            )

        for enc in data.enc_id.unique():
            encounter_data = data[data["enc_id"] == enc]

            encounter_db = session.execute(
                select(DashEncounter).where(DashEncounter.enc_id == str(enc))
            ).scalar_one_or_none()

            if not encounter_db:
                encounter_db = DashEncounter(
                    enc_id=int(encounter_data["enc_id"].iloc[0]),
                    patient_number=int(encounter_data["patient_id"].iloc[0]),
                    department=encounter_data["department"].iloc[0],
                    admission_date=encounter_data["admissionDate"].iloc[0],
                    discharge_date=encounter_data["dischargeDate"].iloc[0],
                    length_of_stay=int(encounter_data["length_of_stay"].iloc[0]),
                )
                session.add(encounter_db)
            else:
                _remove_patient_file_and_letters_from_db(session_factory, enc_id=enc)

            for _, row in encounter_data.iterrows():
                if row["description"] == "Ontslagbrief":
                    stored_doc_db = StoredDoc(
                        timestamp=row["date"],
                        discharge_letter=row["content"],
                        doc_type="Human",
                    )
                    encounter_db.stored_doc_relation.append(stored_doc_db)
                    session.add(stored_doc_db)
                else:
                    patient_file_db = PatientFile(
                        description=row["description"],
                        content=row["content"],
                        date=row["date"],
                    )
                    encounter_db.patient_file_relation.append(patient_file_db)
                    session.add(patient_file_db)
            session.commit()


def run_processing(
    data_source: str,
    start_date: str,
    end_date: str,
    selected_department: str,
    storage_location: str,
    remove_previous_encs: bool,
    n_enc_ids: int | None = None,
    selection_enc_ids: str | None = None,
    length_of_stay_cutoff: int | None = None,
) -> None:
    """Run the data processing pipeline based on the specified parameters.

    Parameters
    ----------
    data_source : str
        The source of the data to be processed ("hix", "metavision", "demo").
    start_date : str
        The start date of the period from which the discharges are in the exported data.
        This date is used in the name of the exported data file to be read.
    end_date : str
        The end date of the period from which the discharges are in the exported data.
        This date is used in the name of the exported data file to be read.
    selected_department : str
        The department to run the processing for.
    storage_location : str
        The location to store the processed data ("database", "data/processed").
    remove_previous_encs : bool
        Whether to remove previous encounter IDs from the database.
    n_enc_ids : int
        The number of encounter IDs to be selected.
    selection_enc_ids : str
        How the selection for the encounter ids is done. Either random or balanced.
    length_of_stay_cutoff : int | None, optional
        The cutoff for length of stay, by default None.
        This is only used when selection_enc_ids is balanced.
        Half of the selected encounters will have a length of stay below and half above
        this value.
    """
    if data_source not in ["hix", "metavision", "demo"]:
        raise ValueError(
            f"Unknown data_source '{data_source}'. "
            "Expected 'hix', 'metavision' or 'demo'."
        )
    if storage_location not in ["database", "data/processed"]:
        raise ValueError(
            f"Unknown storage_location '{storage_location}'. "
            "Expected 'database' or 'data/processed'."
        )

    raw_data_folder = Path(
        "/mapr/administratielast/administratielast_datamanager/ontslagdocumentatie/export"
    )
    processed_data_folder = Path(__file__).parents[1] / "data" / "processed"

    if data_source == "hix":
        hix_patient_data = pd.read_json(
            Path(raw_data_folder / f"{start_date}_{end_date}_hix_patient.json"),
            convert_dates=["admissionDate", "dischargeDate", "date"],
        )
        hix_docs_data = pd.read_json(
            Path(raw_data_folder / f"{start_date}_{end_date}_hix_docs.json"),
            convert_dates=["admissionDate", "dischargeDate", "date"],
        )
        hix_patient_data["content"] = hix_patient_data["content"].apply(rtf_to_text)
        data = combine_patient_and_docs_data_hix(hix_patient_data, hix_docs_data)

    elif data_source == "metavision":
        data = pd.read_json(
            Path(raw_data_folder / f"{start_date}_{end_date}_metavision.json"),
            convert_dates=["admissionDate", "dischargeDate", "date"],
        )

    elif data_source == "demo":
        data = pd.read_csv(
            Path(__file__).parents[1] / "data" / "examples" / "DEMO_patient_1.csv",
            sep=";",
            parse_dates=["admissionDate", "dischargeDate", "date"],
        )

    data = data.pipe(apply_deduce, "content").pipe(
        process_data, remove_encs_no_docs=True
    )

    data = data[data["department"] == selected_department]

    if data_source != "demo":
        selected_encounter_ids = write_encounter_ids(
            data,
            n_enc_ids=n_enc_ids,
            length_of_stay_cutoff=length_of_stay_cutoff,
            selection=selection_enc_ids,
        )
        data = data[data["enc_id"].isin(selected_encounter_ids)].reset_index(drop=True)
    if storage_location == "database":
        engine = get_engine(
            db_env=os.getenv("DB_ENVIRONMENT"),
            schema_name=DashEncounter.__table__.schema,
        )
        tables_to_create = [
            table
            for table in Base.metadata.tables.values()
            if table.schema == "discharge_aiva_dev"
        ]
        Base.metadata.create_all(bind=engine, tables=tables_to_create)
        session_factory = sessionmaker(bind=engine)
        _save_patient_file_to_db(session_factory, data, remove_previous_encs)

        logger.info("Processed data loaded into development database")
    elif storage_location == "data/processed":
        data.to_parquet(Path(processed_data_folder / "evaluation_data.parquet"))
        logger.info('Processed data saved to "data/processed" folder')


def _parse_date(value: str):
    """Parse YYYY-MM-DD dates and give a friendly error if invalid."""
    try:
        return datetime.strptime(value.strip(), "%Y-%m-%d").date()
    except ValueError as exc:
        raise click.BadParameter("Use format YYYY-MM-DD (e.g., 2025-01-31).") from exc


def _prompt_date_range() -> tuple[str, str]:
    """Ask for and validate a start/end date pair."""
    click.echo(
        "You will now be prompted to enter the date range in which the encounters"
        " were discharged. Make sure that the end date is after the start date."
    )
    start_date = click.prompt(
        "Start date of period (YYYY-MM-DD)", value_proc=_parse_date
    )
    end_date = click.prompt("End date of period (YYYY-MM-DD)", value_proc=_parse_date)
    if end_date < start_date:
        raise click.BadParameter("End date must be on or after start date.")
    return str(start_date), str(end_date)


def _compute_export_flag(purpose: str, ehr: str) -> bool:
    """Determine whether data export is needed based on purpose and EHR."""
    if ehr == "demo":
        return False
    return purpose == "eval" or (
        purpose == "dev"
        and click.confirm(
            "Do you need to export new data? "
            "You can also continue on an old export by selecting no and providing "
            "the start and end date of the previous export in the next step.",
            default=False,
            show_default=True,
        )
    )


@click.command()
def get_selected_parameters() -> dict | None:
    """Interactive export assistant that returns a dict with selected parameters used
    in the pipeline.

    We have two ways of using the pipeline:
    1. Development ('dev'): Export and/or process data for development purposes and
        load into development database.
    2. Evaluation ('eval'): Export and process data and bulk generate discharge letters
    for evaluation purposes, saving results as a parquet file within data/processed.
    """
    # general info

    click.echo(
        "Welcome to the Discharge Documentation Generator pipeline runner.\n"
        "You will be prompted to enter several parameters to run the pipeline.\n"
    )

    purpose = click.prompt(
        "For what do you want to run the pipeline?",
        type=click.Choice(["dev", "eval"], case_sensitive=False),
    ).lower()

    department_config = load_department_config()
    department_options = [dep.id for dep in department_config.department.values()]

    department = click.prompt(
        "For which department do you want to run the pipeline? "
        "Only one department is possible per run.",
        type=click.Choice(department_options, case_sensitive=False),
    ).upper()

    department_ehr = department_config.department[department].ehr.lower()

    parameters = {
        "purpose": purpose,
        "department": department,
        "data_source": department_ehr,
    }

    # export dataplatform parameters

    export_dataplatform = _compute_export_flag(purpose, department_ehr)
    parameters.update({"export_dataplatform": export_dataplatform})

    start_date = None
    end_date = None
    n_encounters = None
    selection_method = None
    n_per_class = None
    if department != "DEMO":
        start_date, end_date = _prompt_date_range()

        # processing parameters
        n_encounters = click.prompt(
            "How many patient encounters do you want to get?",
            type=click.IntRange(min=1),
            default=25,
        )

        selection_method = click.prompt(
            "How do you want to select patient encounters? Balanced means half of the "
            "encounters will be below and half above the cutoff value for the length of"
            " stay asked in the next step.",
            type=click.Choice(["random", "balanced"], case_sensitive=False),
        ).lower()

        n_per_class = None
        if selection_method == "balanced":
            n_per_class = click.prompt(
                "At which length of stay do you want the cutoff to be? (in days)\n"
                "Half of the selected encounters will be below and half above this "
                "value.",
                type=click.IntRange(min=1),
                default=7,
            )

    remove_previous_encs = False
    if purpose == "dev":  # and thus storage_location = database
        remove_previous_encs = click.confirm(
            f"Do you want to remove the existing encounter IDs for department"
            f" {department}?",
            default=True,
        )

    parameters.update(
        {
            "start_date": start_date,
            "end_date": end_date,
            "n_encounters": n_encounters,
            "selection_method": selection_method,
            "n_per_class": n_per_class,
            "remove_previous_encs": remove_previous_encs,
        }
    )

    storage_location = "database" if purpose == "dev" else "data/processed"
    parameters["storage_location"] = storage_location

    # bulk generation parameters

    if purpose == "eval":
        bulk_generation = True
    elif purpose == "dev":
        bulk_generation = click.confirm(
            "Do you want to bulk generate AI discharge letters for the selected "
            "encounters?",
            default=False,
            show_default=True,
        )
    parameters.update({"bulk_generation": bulk_generation})

    if bulk_generation:
        click.echo(
            f"The model used for bulk generation will be: {DEPLOYMENT_NAME_BULK}"
        )
        confirm_model = click.confirm("Do you want to continue with this model?")
        if not confirm_model:
            click.echo("Exiting. Please modify the config file to change the model.")
            return None

    return parameters


if __name__ == "__main__":
    # Suppress DEBUG logs from OpenAI SDK, httpcore, and httpx
    logging.getLogger("openai").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)

    setup_root_logger()
    params = get_selected_parameters(standalone_mode=False)

    if params is None:
        sys.exit(0)
    logger.info(f"params: {params}")

    if params["storage_location"] == "database":
        logger.info(
            f"Running pipeline on database environment {os.getenv('DB_ENVIRONMENT')}"
        )

    if params["export_dataplatform"]:
        run_export(
            params["data_source"],
            params["start_date"],
            params["end_date"],
        )

    run_processing(
        data_source=params["data_source"],
        start_date=params["start_date"],
        end_date=params["end_date"],
        selected_department=params["department"],
        storage_location=params["storage_location"],
        remove_previous_encs=params["remove_previous_encs"],
        n_enc_ids=params["n_encounters"],
        selection_enc_ids=params["selection_method"],
        length_of_stay_cutoff=params.get("n_per_class"),
    )

    if params["bulk_generation"]:
        client = initialise_azure_connection()
        run_bulk_generation(
            client,
            params["storage_location"],
            params["department"],
        )
