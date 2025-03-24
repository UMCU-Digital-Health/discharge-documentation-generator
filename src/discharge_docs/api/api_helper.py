import json
import logging
import os
from datetime import datetime

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from discharge_docs.database.models import GeneratedDoc
from discharge_docs.llm.helper import format_generated_doc, manual_filtering_message

logger = logging.getLogger(__name__)


def check_authorisation(key: str, stored_key: str) -> None:
    # Check if the provided key matches the stored key in the environment variables.
    if key != os.environ[stored_key]:
        raise HTTPException(
            status_code=403, detail="You are not authorized to access this endpoint"
        )


def remove_outdated_discharge_docs(db: Session, encounter_db_id: int) -> None:
    """
    Remove outdated discharge documents for a given encounter from the database.
    Outdated documents are defined as those that are not the two most recent successful
    discharge documents for the encounter.

    Parameters
    ----------
    db : Session
        The database session to use for querying and updating the database.
    encounter_db_id : int
        The ID of the encounter for which to remove outdated discharge documents.
    """
    latest_two_docs_subquery = (
        select(GeneratedDoc.encounter_id, GeneratedDoc.id)
        .where(
            GeneratedDoc.encounter_id == encounter_db_id,
            GeneratedDoc.success_ind == "Success",
            GeneratedDoc.removed_timestamp.is_(None),
        )
        .order_by(GeneratedDoc.encounter_id, GeneratedDoc.id.desc())
        .limit(2)
        .subquery()
    )

    outdated_docs_query = select(GeneratedDoc).where(
        GeneratedDoc.encounter_id == encounter_db_id,
        GeneratedDoc.id.notin_(select(latest_two_docs_subquery.c.id)),
        GeneratedDoc.removed_timestamp.is_(None),
    )

    outdated_docs = db.execute(outdated_docs_query).scalars().all()

    for doc in outdated_docs:
        doc.discharge_letter = None
        doc.removed_timestamp = datetime.now()

    db.commit()
    logger.info(
        f"Removed {len(outdated_docs)} outdated discharge docs from "
        f"patient {encounter_db_id}."
    )


def process_retrieved_discharge_letters(
    result_df,
) -> tuple[str, bool, int | None, int | None]:
    """
    Process the result DataFrame to determine the appropriate message and status.
    There are a 3 options:
    1. no discharge document was found --> only a message is returned
    2. no succesful discharge document was found --> only a message is returned
    3. a succesful discharge document was found --> the discharge document is returned

    A few additional messages are added in the following cases:
    - a succesful discharge document was found, but it is older than today
    - a succesful discharge document was found, but it is older than a week ago
    - the reason for not finding a discharge document is due to the patient file being
    too long for the AI model to process

    Parameters
    ----------
    result_df : pandas.DataFrame
        DataFrame containing the results of the discharge document query.

    Returns
    -------
    tuple[str, bool, int | None, int | None]
        A tuple containing:
        - The message to be returned to the user (str).
        - A success indicator whether a successful discharge letter was found (bool).
        - The ID of the generated document if found (int or None).
        - The number of days old the most recent successful letter is (int or None).
    """
    if result_df.empty:  # option 1
        returned_message = (
            "Er is geen ontslagbrief in de database gevonden voor deze patiënt. "
            "Dit komt voor bij patiënten in hun eerste 24 uur van de opname. "
            "Indien de patiënt nog is opgenomen, zal morgen een AI-ontslagbrief worden "
            "gegenereerd.\n\n"
            "Als dit toch onverwachts is, neem dan contact op met de afdeling Digital "
            "Health via ai-support@umcutrecht.nl"
        )
        return returned_message, False, None, None

    successful_letters = result_df[result_df["success_ind"] == "Success"]
    if successful_letters.empty:  # option 2
        message = [
            "Er is geen succesvol gegenereerde ontslagbrief in de database gevonden "
            "voor deze patiënt."
        ]
        if result_df.iloc[0]["success_ind"] == "LengthError":
            message.append(
                "Dit komt doordat het patiëntendossier te lang is geworden voor het AI"
                " model.\n\n"
            )
        message.append(
            "Als dit toch onverwachts is, neem dan contact op met de afdeling Digital "
            "Health via ai-support@umcutrecht.nl"
        )
        returned_message = "".join(message)
        return returned_message, False, None, None

    # option 3
    most_recent_successful = successful_letters.iloc[0]
    patient_id = most_recent_successful["patient_id"]
    timestamp = most_recent_successful["timestamp"]
    discharge_letter = json.loads(most_recent_successful["discharge_letter"])
    discharge_letter = format_generated_doc(discharge_letter, "plain")
    generated_doc_id = int(most_recent_successful["generated_doc_id"])

    message_parts = [
        f"Deze brief is door AI gegenereerd voor patiëntnummer: "
        f"{patient_id} op: {timestamp:%d-%m-%Y %H:%M}\n\n"
    ]

    nr_days_old = (datetime.now().date() - timestamp.date()).days
    if nr_days_old > 0:
        if nr_days_old > 7:
            message_parts.append(
                "NB Let erop dat deze AI-brief meer dan een week geleden is "
                f"gegenereerd, namelijk {nr_days_old} dagen geleden.\n"
            )
        else:
            message_parts.append(
                "NB Let erop dat deze AI-brief niet afgelopen nacht is "
                f"gegenereerd, maar {nr_days_old} dagen geleden.\n"
            )
        if result_df.iloc[0]["success_ind"] == "LengthError":
            message_parts.append(
                "Dit komt doordat het patientendossier te lang is geworden voor het "
                "AI model."
            )

    message_parts.append(f"\n\n{discharge_letter}")
    message = "".join(message_parts)
    message = manual_filtering_message(message)

    return message, True, generated_doc_id, nr_days_old
