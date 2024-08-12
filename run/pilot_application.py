import os

import dash
import dash_bootstrap_components as dbc
from dash import dcc, html
from dash.dependencies import Input, Output
from sqlalchemy import create_engine, desc, select
from sqlalchemy.orm import sessionmaker

from discharge_docs.dashboard.dashboard_layout import get_navbar
from discharge_docs.database.models import ApiEncounter, ApiGeneratedDoc

# Database connection setup
DB_USER = os.getenv("DB_USER", "")
DB_PASSWD = os.getenv("DB_PASSWD", "")
DB_HOST = os.getenv("DB_HOST", "")
DB_PORT = os.getenv("DB_PORT", 1433)
DB_DATABASE = os.getenv("DB_DATABASE", "")
SQLALCHEMY_DATABASE_URL = (
    f"mssql+pymssql://{DB_USER}:{DB_PASSWD}@{DB_HOST}:{DB_PORT}/{DB_DATABASE}"
)

engine = create_engine(SQLALCHEMY_DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)

# Dash app setup
app = dash.Dash(
    __name__,
    external_stylesheets=[dbc.themes.BOOTSTRAP],
)
app.layout = html.Div(
    [
        get_navbar(
            view_user=True,
            header_title="Dashboard voor ophalen gegenereerde ontslagbrief",
        ),
        dcc.Dropdown(
            id="patient-dropdown",
            options=[],
            value=None,
            clearable=False,
        ),
        dcc.Markdown(id="discharge-letter-display"),
    ]
)


@app.callback(Output("patient-dropdown", "options"), [Input("patient-dropdown", "id")])
def update_dropdown(_) -> list:
    """Update the dropdown list with patient IDs.

    This function retrieves distinct patient IDs from the database and formats them
    into a list of dictionaries, where each dictionary contains the label and value
    of an patient ID.

    Parameters
    ----------
    _ : NoValue

    Returns
    -------
    list
        A list of dictionaries, where each dictionary represents an patient ID.
        Each dictionary contains two keys: 'label' and 'value'. The 'label' key
        represents the string representation of the patient ID, and the 'value'
        key represents the same value as the 'label' key.
    """
    db = SessionLocal()
    try:
        results = db.execute(select(ApiEncounter.patient_number).distinct()).fetchall()
        return [
            {"label": str(patient_id[0]), "value": str(patient_id[0])}
            for patient_id in results
        ]
    finally:
        db.close()


@app.callback(
    Output("discharge-letter-display", "children"),
    [Input("patient-dropdown", "value")],
)
def display_discharge_letter(selected_patient_id: str) -> str:
    """Display the discharge letter based on the selected patient ID.

    Parameters
    ----------
    selected_patient_id : str
        The selected patient ID.

    Returns
    -------
    str
        A paragraph element containing the discharge letter.
    """
    db = SessionLocal()
    if selected_patient_id:
        try:
            query = (
                select(ApiGeneratedDoc.discharge_letter)
                .join(ApiEncounter, ApiGeneratedDoc.encounter_id == ApiEncounter.id)
                .where(ApiEncounter.patient_number == selected_patient_id)
                .order_by(desc(ApiGeneratedDoc.id))
                .limit(1)
            )

            result = db.execute(query).fetchone()
            discharge_letter = result[0] if result else "No discharge letter found."
            return discharge_letter
        finally:
            db.close()
    return "Select an patient ID to see the discharge letter."


# Run the app
if __name__ == "__main__":
    app.run_server(debug=True, port=8055)
