import logging
import os
import random
from datetime import datetime
from pathlib import Path

import dash
import dash_bootstrap_components as dbc
import flask
import numpy as np
import pandas as pd
import tomli
from dash import ctx, dcc, html
from dash._callback import NoUpdate
from dash.dependencies import Input, Output, State
from dash.exceptions import PreventUpdate
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from discharge_docs.dashboard.helper import (
    get_data_from_patient_admission,
    get_patients_from_list_names,
    get_user,
    highlight,
    load_stored_discharge_letters,
)
from discharge_docs.dashboard.pre_release_eval_dashboard_layout import get_layout
from discharge_docs.database.models import (
    Base,
    EvalPhase1,
)
from discharge_docs.processing.processing import (
    get_patient_discharge_docs,
    get_patient_file,
)

logger = logging.getLogger(__name__)


# load data
df_metavision = pd.read_parquet(
    Path(__file__).parents[1] / "data" / "processed" / "metavision_new_data.parquet"
)

df_HIX = pd.read_parquet(
    Path(__file__).parents[1] / "data" / "processed" / "HiX_data.parquet"
)

# Define your DataFrames for each department
df_dict = {
    "NICU": df_metavision,
    "IC": df_metavision,
    "CAR": df_HIX,
    "PSY": df_HIX,
}

# load used enc_ids
with open(
    Path(__file__).parents[1]
    / "src"
    / "discharge_docs"
    / "dashboard"
    / "enc_ids_dashboard.toml",
    "rb",
) as f:
    enc_ids_dict = tomli.load(f)
    for key in enc_ids_dict:
        enc_ids_dict[key] = enc_ids_dict[key]["ids"]

for key in enc_ids_dict:
    if key != "PSY":  # TODO verwijderen na check saskia
        enc_ids_dict[key] = enc_ids_dict[key][:25]

data_dict, values_list = get_patients_from_list_names(df_dict, enc_ids_dict)

# Database config
with open(Path(__file__).parents[1] / "pyproject.toml", "rb") as f:
    project_info = tomli.load(f)

DB_USER = os.getenv("DB_USER", "")
DB_PASSWD = os.getenv("DB_PASSWD", "")
DB_HOST = os.getenv("DB_HOST", "")
DB_PORT = os.getenv("DB_PORT", 1433)
DB_DATABASE = os.getenv("DB_DATABASE", "")

if DB_USER == "":
    logging.warning("Using debug SQLite database...")
    SQLALCHEMY_DATABASE_URL = "sqlite:///./sql_app.db"
    execution_options = {"schema_translate_map": {"discharge_aiva": None}}
else:
    SQLALCHEMY_DATABASE_URL = (
        rf"mssql+pymssql://{DB_USER}:{DB_PASSWD}@{DB_HOST}:{DB_PORT}/{DB_DATABASE}"
    )
    execution_options = None


engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    execution_options=execution_options,
)
Base.metadata.create_all(engine)

# load stored discharge letters
df_discharge4 = pd.read_csv(
    Path(__file__).parents[1] / "data" / "processed" / "bulk_generated_docs_gpt4.csv"
    # TODO change to pre-release export
)

# storage for highlighted text
highlighted_missings = []
highlighted_halucinations = []
highlighted_trivial = []

# define the app
app = dash.Dash(
    __name__,
    external_stylesheets=[dbc.themes.BOOTSTRAP],
)
application = app.server  # Neccessary for debugging in vscode, no further use

# Define the layout of the app
app.layout = get_layout()


@app.callback(
    Output("patient_admission_dropdown", "options"),
    Output("patient_admission_dropdown", "value"),
    Input("navbar", "children"),
)
def load_patient_selection_dropdown(_) -> tuple[list, str | None, list]:
    """
    Load the patient admission dropdown with the available patient admissions when
    the app is starting. Available patients are based on the user's authorization.

    Returns
    -------
    tuple[list, str]
        The list of options for the patient admission dropdown and the first patient
        value.
    """
    authorization_group = ["NICU", "IC", "CAR", "PSY", "DEMO"]

    authorized_patients = [
        item
        for key, values in values_list.items()
        if key in authorization_group
        for item in values
    ]

    fist_patient = authorized_patients[0]["value"] if authorized_patients else None

    return authorized_patients, fist_patient


@app.callback(
    Output("output_value", "children"),
    [
        Input("patient_admission_dropdown", "value"),
    ],
)
def display_value(
    selected_patient_admission: str,
) -> list:
    """Display the discharge documentation for the selected patient admission.

    Parameters
    ----------
    selected_patient_admission : str
        The selected patient admission.

    Returns
    -------
    list
        The discharge documentation for the selected patient admission.
    """
    if selected_patient_admission is None:
        return [""]

    data = get_data_from_patient_admission(selected_patient_admission, data_dict)
    patient_file = data.sort_values(by=["date", "description"])

    patient_file = patient_file.sort_values(by=["date", "description"])

    if patient_file.empty:
        return ["De geselecteerde data is niet ingevuld voor deze patient."]
    else:
        returnable = []
        for index in patient_file.index:
            returnable.append(
                html.B(
                    str(patient_file.loc[index, "description"])
                    + " - "
                    + str(patient_file.loc[index, "date"].date())
                )
            )
            returnable.append(html.Br())
            returnable.append(patient_file.loc[index, "value"])
            returnable.append(html.Br())

        return returnable


@app.callback(
    Output("output_original_discharge_documentation", "value"),
    [
        Input("patient_admission_dropdown", "value"),
    ],
)
def display_original_discharge_documentation(selected_patient_admission: str) -> str:
    """
    Display the discharge documentation for the selected patient admission.

    Parameters:
    ----------
     selected_patient_admission : str
        The selected patient admission.

    Returns:
    -------
    list
        The discharge documentation for the selected patient admission.
    """
    if selected_patient_admission is None:
        return ""

    data = get_data_from_patient_admission(selected_patient_admission, data_dict)
    discharge_documentation = get_patient_discharge_docs(df=data)
    # patient_file, _ = get_patient_file(data)
    # print(patient_file)
    # return str(patient_file)
    return str(discharge_documentation.values[0])


@app.callback(
    Output("output_generated_discharge_documentation", "children"),
    [
        Input("patient_admission_dropdown", "value"),
    ],
)
def display_generated_discharge_documentation(
    selected_patient_admission: str,
) -> tuple[list, list]:
    """
    Display the generated discharge documentation for the selected patient admission.

    Parameters:
    ----------
    selected_patient_admission : str
        The selected patient admission.

    Returns:
    -------
    tuple[list, list]
        A tuple containing two lists:
        - The discharge docs for the selected patient admission from discharge35
        - The discharge docs for the selected patient admission from discharge4
    """
    if selected_patient_admission is None:
        return ""

    output_4 = load_stored_discharge_letters(df_discharge4, selected_patient_admission)

    return output_4


@app.callback(
    Output("output_discharge_documentation", "children"),
    [
        Input("patient_admission_dropdown", "value"),
        Input("next_button", "n_clicks"),
    ],
    State("output_discharge_documentation", "children"),
)
def display_chosen_discharge_documentation(
    selected_patient_admission: str, n_clicks: int, current_text: str
) -> str:
    """
    Display the chosen discharge documentation for the selected patient admission.

    Parameters:
    ----------
    selected_patient_admission : str
        The selected patient admission.

    Returns:
    -------
    list
        The discharge documentation for the selected patient admission.
    """
    if selected_patient_admission is None:
        return ""

    text_GPT = str(
        load_stored_discharge_letters(df_discharge4, selected_patient_admission)
    )

    data = get_data_from_patient_admission(selected_patient_admission, data_dict)
    text_ORG = str(get_patient_discharge_docs(df=data).values[0])

    # Check if we're displaying the first or the second text
    if n_clicks % 2 == 0:
        # Even clicks - show first text
        if current_text != text_GPT and current_text != text_ORG:
            # Randomize initial text if it's not already one of them
            return random.choice([text_GPT, text_ORG])
        return current_text
    else:
        # Odd clicks - show second text
        if current_text == text_GPT:
            return text_ORG
        else:
            return text_GPT

    return ""


# JavaScript to capture the highlighted text and store it in the hidden input
app.clientside_callback(
    """
    function(n_clicks) {
        const textarea = document.getElementById('text-area');
        const text = document.getSelection().toString();
        document.getElementById('hidden-input_hall').value = text;
        return text;
    }
    """,
    Output("hidden-input_hall", "value"),
    Input("save_hall-button", "n_clicks"),
)


# Callback to update output and save highlighted text to DataFrame
@app.callback(
    Output("output-container_hall", "children"),
    Input("hidden-input_hall", "value"),
    prevent_initial_call=True,
)
def update_hallucination_markings(text):
    if text:
        highlighted_halucinations.append(text)
        return f'Geselecteerde hallucinaties: "{str(highlighted_halucinations)}"'
    return "Nog geen hallucinaties gemarkeerd."


# JavaScript to capture the highlighted text and store it in the hidden input
app.clientside_callback(
    """
    function(n_clicks) {
        const textarea = document.getElementById('text-area');
        const text = document.getSelection().toString();
        document.getElementById('hidden-input_trivial').value = text;
        return text;
    }
    """,
    Output("hidden-input_trivial", "value"),
    Input("save_trivial-button", "n_clicks"),
)


# Callback to update output and save highlighted text to DataFrame
@app.callback(
    Output("output-container_trivial", "children"),
    Input("hidden-input_trivial", "value"),
    prevent_initial_call=True,
)
def update_trivial_markings(text):
    if text:
        highlighted_trivial.append(text)
        return f'Geselecteerde hallucinaties: "{str(highlighted_trivial)}"'
    return "Nog geen triviale informatie gemarkeerd."


@app.callback(
    Output("evaluation_saved_label", "children"),
    [Input("evaluate_button", "n_clicks")],
    [
        State("likert_slider", "value"),
        State("evaluation_text", "value"),
        State("patient_admission_dropdown", "value"),
    ],
)
def gather_feedback(
    n_clicks: int,
    evaluation_slider: int,
    evaluation_text: str,
    selected_patient_admission: str,
) -> str:
    """
    Gather feedback from the user.

    Parameters
    ----------
    n_clicks : int
        The number of times the feedback button was clicked.
    evaluation_slider : int
        The score given by the user on the evaluation slider.
    evaluation_text : str
        The feedback text provided by the user.
    selected_patient_admission : str
        The selected patient admission.

    Returns
    -------
    str
        A string indicating that the feedback was saved.

    Raises
    ------
    PreventUpdate
        If the feedback button was clicked without any changes.

    """
    if n_clicks is None:
        raise PreventUpdate

    # Save the feedback to database
    user = get_user(flask.request)
    evaluation_instance = EvalPhase1(
        user=user,
        timestamp=datetime.now(),
        patientid=selected_patient_admission,
        letter_evaluated="test letter GPT",
        highlighted_missings=str(highlighted_missings),
        highlighted_halucinations=str(highlighted_halucinations),
        highlighted_trivial_information=str(highlighted_trivial),
        usability_likert=evaluation_slider,
        comments=evaluation_text,
    )

    with Session(engine) as session:
        session.add(evaluation_instance)
        session.commit()

    return "De feedback is opgeslagen voor deze patiënt, bedankt!"


# @app.callback(
#     Output("evaluation_text", "value"), [Input("patient_admission_dropdown", "value")]
# )
# def clear_feedback(_):
#     # This function clears the feedback field whenever a new patient is selected
#     return ""


# Run the app
if __name__ == "__main__":
    app.run_server(debug=True, port=8050)
