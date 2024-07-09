import os

import dash
from dash import dcc, html
from dash.dependencies import Input, Output
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from discharge_docs.database.models import ApiGeneratedDoc

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
app = dash.Dash(__name__)
app.layout = html.Div(
    [
        html.H1("Dashboard for Discharge Documentation"),
        dcc.Dropdown(
            id="encounter-dropdown",
            options=[],
            value=None,
            clearable=False,
        ),
        html.Div(id="discharge-letter-display"),
    ]
)


@app.callback(
    Output("encounter-dropdown", "options"), [Input("encounter-dropdown", "id")]
)
def update_dropdown(_) -> list:
    """Update the dropdown list with encounter IDs.

    This function retrieves distinct encounter IDs from the database and formats them
    into a list of dictionaries, where each dictionary contains the label and value
    of an encounter ID.

    Parameters
    ----------
    _ : NoValue

    Returns
    -------
    list
        A list of dictionaries, where each dictionary represents an encounter ID.
        Each dictionary contains two keys: 'label' and 'value'. The 'label' key
        represents the string representation of the encounter ID, and the 'value'
        key represents the same value as the 'label' key.
    """
    db = SessionLocal()
    try:
        results = db.execute(select(ApiGeneratedDoc.encounter_id).distinct()).fetchall()
        return [
            {"label": str(enc_id[0]), "value": str(enc_id[0])} for enc_id in results
        ]
    finally:
        db.close()


@app.callback(
    Output("discharge-letter-display", "children"),
    [Input("encounter-dropdown", "value")],
)
def display_discharge_letter(selected_encounter_id: str) -> html.P:
    """Display the discharge letter based on the selected encounter ID.

    Parameters
    ----------
    selected_encounter_id : str
        The selected encounter ID.

    Returns
    -------
    html.P
        A paragraph element containing the discharge letter.
    """
    db = SessionLocal()
    if selected_encounter_id:
        try:
            stmt = select(ApiGeneratedDoc.discharge_letter).where(
                ApiGeneratedDoc.encounter_id == selected_encounter_id
            )
            result = db.execute(stmt).fetchone()
            discharge_letter = result[0] if result else "No discharge letter found."
            return html.P(discharge_letter)
        finally:
            db.close()
    return html.P("Select an encounter ID to see the discharge letter.")


# Run the app
if __name__ == "__main__":
    app.run_server(debug=True, port=8055)
