"""Dashboard that can be used to retrieve discharge letters for a specific patient.
This dashboard is only used when integration in EHR is not possible."""

import logging
from datetime import datetime
from typing import Sequence

import dash_bootstrap_components as dbc
import flask
import pandas as pd
from dash import Dash
from dash.dependencies import Input, Output, State
from sqlalchemy import select
from sqlalchemy.orm import sessionmaker

from discharge_docs.api.api_helper import process_retrieved_discharge_letters
from discharge_docs.config import setup_root_logger
from discharge_docs.dashboard.helper import get_user
from discharge_docs.dashboard.layout import get_external_dashboard_layout
from discharge_docs.database.connection import get_engine
from discharge_docs.database.models import (
    DashboardLogging,
    Encounter,
    GeneratedDoc,
    Request,
    RequestGenerate,
)

logger = logging.getLogger(__name__)
setup_root_logger()

SESSIONMAKER = sessionmaker(bind=get_engine())

app = Dash(__name__, external_stylesheets=[dbc.themes.BOOTSTRAP])
application = app.server

app.layout = get_external_dashboard_layout()


@app.callback(
    Output("patient-select", "options"),
    Output("patient-select", "value"),
    Output("logged_in_user", "children"),
    Input("navbar", "children"),
)
def load_patient_selection_dropdown(_) -> tuple[Sequence | None, str | None, list]:
    """
    Populate the patient selection dropdown with available patient admissions
    when the app starts. The available patients are the patients currently admitted
    at the cardiology department.

    Parameters
    ----------
    _ : Any
        Placeholder input parameter for the callback, not used.

    Returns
    -------
    tuple[Sequence | None, str | None, list]
        A tuple containing:
        - A list of patient ids for the dropdown options, or None if no patients
        are available.
        - The value of the first patient in the dropdown, or None if no patients
        are available.
        - A list containing a message about the logged-in user to be used in the navbar.
    """

    user = get_user(flask.request)

    with SESSIONMAKER() as session:
        query = (
            select(
                Encounter.patient_id.distinct(),
            )
            .join(GeneratedDoc)
            .where(
                GeneratedDoc.success_ind == "Success",
                GeneratedDoc.removed_timestamp.is_(None),
                Encounter.department == "CAR",
            )
        )
        result = session.execute(query).scalars().all()

    if not result:
        logger.warning("No patients found when loading the patient selection dropdown.")

    logger.info(f"Loaded dropdown with {len(result)} patients.")
    return result, None, [f"Ingelogd als: {user}"]


@app.callback(
    Output("doc-card", "children"),
    Output("success-td", "children"),
    Output("days-td", "children"),
    Input("patient-select", "value"),
)
def load_discharge_doc(patient_admission: str | None) -> tuple[str, str, str]:
    """
    Load the discharge document and related information for the selected patient
    admission.

    Parameters
    ----------
    patient_admission : str
        The identifier of the patient admission.

    Returns
    -------
    tuple[str, str, str]
        A tuple containing:
        - The discharge document content or a placeholder message.
        - The status of the document retrieval ("OK" or "Fout").
        - The number of days since the document was generated.
    """
    if not patient_admission:
        logger.warning("No patient admission selected.")
        return (
            "Selecteer een patiënt om de AI-concept ontslagbrief te bekijken.",
            "OK",
            "",
        )

    with SESSIONMAKER() as session:
        query = (
            select(
                GeneratedDoc.discharge_letter,
                GeneratedDoc.id.label("generated_doc_id"),
                GeneratedDoc.success_ind,
                Encounter.enc_id,
                Encounter.patient_id,
                Request.timestamp,
            )
            .join(Encounter, GeneratedDoc.encounter_id == Encounter.id)
            .join(
                RequestGenerate, GeneratedDoc.request_generate_id == RequestGenerate.id
            )
            .join(Request, RequestGenerate.request_id == Request.id)
            .where(Encounter.patient_id == patient_admission)
            .order_by(Request.timestamp.desc())
        )

        result = session.execute(query)
        result_df = pd.DataFrame(result.fetchall(), columns=list(result.keys()))
        logger.info(f"Retrieved {len(result_df)} discharge letters")

    message, success_ind, doc_id, nr_days_old = process_retrieved_discharge_letters(
        result_df
    )

    if doc_id is not None:
        with SESSIONMAKER() as session:
            dashboard_logging = DashboardLogging(
                user_email=get_user(flask.request),
                discharge_letter_id=doc_id,
                timestamp=datetime.now(),
            )
            session.add(dashboard_logging)
            session.commit()
            logger.info(
                "Dashboard logging entry created for user "
                f"{dashboard_logging.user_email}"
            )

    return message, "OK" if success_ind else "Fout", str(nr_days_old)


@app.callback(
    Output("copy-to-clipboard", "content"),
    Input("copy-to-clipboard", "n_clicks"),
    State("doc-card", "children"),
    prevent_initial_call=True,
)
def copy_to_clipboard(n_clicks: int, content: str | None) -> str:
    """
    Copy the content of the discharge document to the clipboard.

    Parameters
    ----------
    n_clicks : int
        The number of clicks on the copy button.
    content : str | None
        The content to be copied to the clipboard.

    Returns
    -------
    str
        The content to be copied to the clipboard, or an empty string if content is
        None.
    """
    if n_clicks and content:
        logger.info("Discharge document copied to clipboard")
        return content
    return ""


if __name__ == "__main__":
    app.run(debug=False, port=8050)
