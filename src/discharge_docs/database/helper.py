from datetime import date

import pandas as pd
from sqlalchemy import Date, select
from sqlalchemy.orm import sessionmaker

from discharge_docs.database.models import (
    Encounter,
    FeedbackDetails,
    GeneratedDoc,
    Request,
    RequestFeedback,
    RequestGenerate,
    RequestRetrieve,
)


def get_generated_doc_table(
    min_date: date, max_date: date, session_object: sessionmaker
) -> pd.DataFrame:
    """Retrieves the generated doc table for the monitoring admin page and merges
    it with the encounter, request and request_generate tables

    Parameters
    ----------
    min_date : date
        Minimum date for the request table
    max_date : date
        Maximum date for the request table

    Returns
    -------
    pd.DataFrame
        Dataframe containing the generated doc table
    """
    with session_object() as session:
        generated_doc = session.execute(
            select(
                Encounter.enc_id,
                Encounter.department,
                Request.timestamp,
                GeneratedDoc.id.label("generated_doc_id"),
                GeneratedDoc.success_ind,
                GeneratedDoc.encounter_id,
                GeneratedDoc.discharge_letter,
            )
            .join(Encounter, GeneratedDoc.encounter_id == Encounter.id)
            .join(
                RequestGenerate, GeneratedDoc.request_generate_id == RequestGenerate.id
            )
            .join(Request, RequestGenerate.request_id == Request.id)
            .where(Request.timestamp.cast(Date) >= min_date)
            .where(Request.timestamp.cast(Date) <= max_date)
        )

        generated_doc_table = pd.DataFrame(
            generated_doc.fetchall(), columns=generated_doc.keys()
        )

    return generated_doc_table


def get_feedback_table(
    min_date: date, max_date: date, session_object: sessionmaker
) -> pd.DataFrame:
    """Retrieves the feedback details table for the monitoring admin page and merges
    it with the encounter, request and request_feedback tables

    Parameters
    ----------
    min_date : date
        Minimum date for the request table
    max_date : date
        Maximum date for the request table

    Returns
    -------
    pd.DataFrame
        Dataframe containing the feedback table
    """
    with session_object() as session:
        feedback = session.execute(
            select(
                RequestFeedback.id.label("request_feedback_id"),
                Encounter.enc_id,
                Encounter.department,
                FeedbackDetails.feedback_answer,
            )
            .join(
                RequestFeedback,
                FeedbackDetails.request_feedback_id == RequestFeedback.id,
            )
            .join(Request, RequestFeedback.request_id == Request.id)
            .join(Encounter, RequestFeedback.request_enc_id == Encounter.enc_id)
            .where(Request.timestamp.cast(Date) >= min_date)
            .where(Request.timestamp.cast(Date) <= max_date)
        )
        feedback_table = pd.DataFrame(feedback.fetchall(), columns=feedback.keys())
    return feedback_table


def get_request_retrieve_table(
    min_date: date, max_date: date, session_object: sessionmaker
) -> pd.DataFrame:
    """Retrieves the information on retrieve requests for the monitoring admin page

    Parameters
    ----------
    min_date : date
        Minimum date for the request table
    max_date : date
        Maximum date for the request table
    session_object : sessionmaker
        Session object for the database connection

    Returns
    -------
    pd.DataFrame
        Dataframe containing the request retrieve table
    """
    with session_object() as session:
        request_retrieve = session.execute(
            select(
                Encounter.enc_id,
                Encounter.department,
                Request.id.label("request_id"),
                Request.timestamp,
                Request.runtime,
            )
            .join(RequestRetrieve, RequestRetrieve.request_id == Request.id)
            .join(
                Encounter,
                RequestRetrieve.request_enc_id == Encounter.enc_id,
                isouter=True,
            )
            .where(Request.timestamp.cast(Date) >= min_date)
            .where(Request.timestamp.cast(Date) <= max_date)
        )

        request_retrieve_table = pd.DataFrame(
            request_retrieve.fetchall(), columns=request_retrieve.keys()
        )
    return request_retrieve_table


def get_request_generate_table(
    min_date: date, max_date: date, session_object: sessionmaker
) -> pd.DataFrame:
    """Retrieves the information on generate requests for the monitoring admin page

    Parameters
    ----------
    min_date : date
        Minimum date for the request table
    max_date : date
        Maximum date for the request table
    session_object : sessionmaker
        Session object for the database connection

    Returns
    -------
    pd.DataFrame
        Dataframe containing the request generate table
    """
    with session_object() as session:
        request_generate = session.execute(
            select(
                Encounter.enc_id,
                Encounter.department,
                Request.id.label("request_id"),
                Request.timestamp,
                Request.api_version,
                Request.runtime,
            )
            .join(RequestGenerate, RequestGenerate.request_id == Request.id)
            .join(
                GeneratedDoc,
                GeneratedDoc.request_generate_id == RequestGenerate.id,
                isouter=True,
            )
            .join(Encounter, GeneratedDoc.encounter_id == Encounter.id, isouter=True)
            .where(Request.timestamp.cast(Date) >= min_date)
            .where(Request.timestamp.cast(Date) <= max_date)
        )

        request_generate_table = pd.DataFrame(
            request_generate.fetchall(), columns=request_generate.keys()
        )
    return request_generate_table
