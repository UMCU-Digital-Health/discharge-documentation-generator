import logging
import os
import random
from datetime import datetime
from pathlib import Path

import dash
import dash_bootstrap_components as dbc
import flask
import pandas as pd
import tomli
from dash import callback_context, ctx
from dash.dependencies import Input, Output, State
from dash.exceptions import PreventUpdate
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from discharge_docs.dashboard.helper import (
    get_data_from_patient_admission,
    get_patients_from_list_names,
    get_user,
    load_stored_discharge_letters_pre_release,
)
from discharge_docs.dashboard.pre_release_eval_dashboard_layout import get_layout
from discharge_docs.database.models import (
    Base,
    EvalPhase1,
)
from discharge_docs.processing.processing import (
    get_patient_discharge_docs,
)

logger = logging.getLogger(__name__)


# load data
df_metavision = pd.read_parquet(
    Path(__file__).parents[1]
    / "data"
    / "processed"
    / "metavision_data_april_dp.parquet"
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
    / "enc_ids_pre_release_phase1_1.toml",
    "rb",
) as f:
    enc_ids_dict = tomli.load(f)
    for key in enc_ids_dict:
        enc_ids_dict[key] = enc_ids_dict[key]["ids"]

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
    Path(__file__).parents[1]
    / "data"
    / "processed"
    / "bulk_generated_docs_gpt4_PReval.csv"
)

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
    Output("output_value", "value"),
    [
        Input("patient_admission_dropdown", "value"),
    ],
)
def display_patient_file(
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
        return ["Er is geen patientendossier voor deze patient."]
    else:
        patient_file = patient_file[patient_file["description"] != "Ontslagbrief"]
        patient_file_string = "\n\n".join(
            patient_file.apply(
                lambda row: (
                    f"{row['description'].upper()} -"
                    + f" {row['date'].date()} \n{row['value']}"
                ),
                axis=1,
            )
        )
        return patient_file_string


@app.callback(
    [
        Output("output_discharge_documentation", "value"),
        Output("next_button", "style"),
        Output("letter_shown", "data"),
    ],
    [
        Input("patient_admission_dropdown", "value"),
        Input("next_button", "n_clicks"),
    ],
    State("output_discharge_documentation", "value"),
    State("letter_shown", "data"),
)
def display_chosen_discharge_documentation(
    selected_patient_admission: str,
    n_clicks: int,
    current_text: str,
    current_letter: str,
) -> tuple:
    """
    Display the chosen discharge documentation for the selected patient admission and
      control next button visibility.

    Parameters:
    ----------
    selected_patient_admission : str
        The selected patient admission.
    n_clicks : int
        Number of times the next button has been clicked.
    current_text : str
        Currently displayed text.
    current_letter : str
        The currently displayed letter label

    Returns:
    -------
    tuple
        The discharge documentation for the selected patient admission and the button
        style.
    """
    if selected_patient_admission is None:
        return "", {"display": "none"}, ""

    text_GPT = str(
        load_stored_discharge_letters_pre_release(
            df_discharge4, selected_patient_admission
        )
    )

    data = get_data_from_patient_admission(selected_patient_admission, data_dict)
    text_ORG = str(get_patient_discharge_docs(df=data).values[0])

    # Initialize the button style where you do show the button
    button_style = {"display": "block"}

    # Check the triggering input
    triggered_input = callback_context.triggered[0]["prop_id"].split(".")[0]

    if triggered_input == "patient_admission_dropdown":
        # reset the button style when a new patient is selected
        choice = random.choice([0, 1])
        if choice == 0:
            return text_GPT, button_style, "GPT letter"
        else:
            return text_ORG, button_style, "ORG letter"

    if triggered_input == "next_button" and n_clicks is not None:
        # hide the button after the first click
        if current_text == text_GPT:
            return text_ORG, {"display": "none"}, "ORG letter"
        else:
            return text_GPT, {"display": "none"}, "GPT letter"

    return current_text, button_style, current_letter


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


# JavaScript to capture the highlighted text and store it in the hidden input
app.clientside_callback(
    """
    function(n_clicks) {
        const textarea = document.getElementById('text-area');
        const text = document.getSelection().toString();
        document.getElementById('hidden-input_missings').value = text;
        return text;
    }
    """,
    Output("hidden-input_missings", "value"),
    Input("save_missings-button", "n_clicks"),
)


# Expanded combined callback for updates, clear actions, and button press
@app.callback(
    [
        Output("evaluation_text", "value"),
        Output("likert_slider", "value"),
        Output("output-container_hall", "children"),
        Output("hall_store", "data"),
        Output("output-container_trivial", "children"),
        Output("trivial_store", "data"),
        Output("output-container_missings", "children"),
        Output("missings_store", "data"),
    ],
    [
        Input("hidden-input_hall", "value"),
        Input("hidden-input_trivial", "value"),
        Input("hidden-input_missings", "value"),
        Input("patient_admission_dropdown", "value"),
        Input("evaluate_button", "n_clicks"),
        Input("next_button", "n_clicks"),
    ],
    [
        State("hall_store", "data"),
        State("trivial_store", "data"),
        State("missings_store", "data"),
    ],
)
def handle_markings(
    hall_text,
    trivial_text,
    missings_text,
    patient_value,
    evaluate_clicks,
    next_clicks,
    stored_hall,
    stored_trivial,
    stored_missings,
):
    if not ctx.triggered:
        # No trigger - unlikely but includes as a safeguard
        raise PreventUpdate

    trigger_id = ctx.triggered[0]["prop_id"].split(".")[0]

    # Clearing all data either on new patient selection or evaluate button pressed
    if trigger_id in ["patient_admission_dropdown", "evaluate_button", "next_button"]:
        return (
            "",
            3,
            "Nog geen hallucinaties gemarkeerd.",
            [],
            "Nog geen triviale informatie gemarkeerd.",
            [],
            "Nog geen missings gemarkeerd.",
            [],
        )

    # Updating stored hallucinations
    if trigger_id == "hidden-input_hall" and hall_text:
        stored_hall.append(hall_text)
        return (
            dash.no_update,
            dash.no_update,
            f'Geselecteerde hallucinaties: "{str(stored_hall)}"',
            stored_hall,
            dash.no_update,
            dash.no_update,
            dash.no_update,
            dash.no_update,
        )

    # Updating stored trivial information
    if trigger_id == "hidden-input_trivial" and trivial_text:
        stored_trivial.append(trivial_text)
        return (
            dash.no_update,
            dash.no_update,
            dash.no_update,
            dash.no_update,
            f'Geselecteerde triviale informatie: "{str(stored_trivial)}"',
            stored_trivial,
            dash.no_update,
            dash.no_update,
        )

    # Updating stored missings
    if trigger_id == "hidden-input_missings" and missings_text:
        stored_missings.append(missings_text)
        return (
            dash.no_update,
            dash.no_update,
            dash.no_update,
            dash.no_update,
            dash.no_update,
            dash.no_update,
            f'Geselecteerde missings: "{str(stored_missings)}"',
            stored_missings,
        )

    return (
        dash.no_update,
        dash.no_update,
        "Nog geen hallucinaties gemarkeerd.",
        stored_hall,
        "Nog geen triviale informatie gemarkeerd.",
        stored_trivial,
        "Nog geen missings gemarkeerd.",
        stored_missings,
    )


@app.callback(
    Output("evaluation_saved_label", "children"),
    [Input("evaluate_button", "n_clicks")],
    [
        State("likert_slider", "value"),
        State("evaluation_text", "value"),
        State("patient_admission_dropdown", "value"),
        State("letter_shown", "data"),
        State("missings_store", "data"),
        State("hall_store", "data"),
        State("trivial_store", "data"),
    ],
)
def gather_feedback(
    n_clicks: int,
    evaluation_slider: int,
    evaluation_text: str,
    selected_patient_admission: str,
    letter_shown: str,
    highlighted_missings: list,
    highlighted_halucinations: list,
    highlighted_trivial: list,
) -> str:
    """
    Save the evaluation/feedback from the user.

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
    letter_shown : str
        The letter that was shown to the user.
    highlighted_missings : list
        The list of highlighted missings.
    highlighted_halucinations : list
        The list of highlighted hallucinations.
    highlighted_trivial : list
        The list of highlighted trivial information.

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
        letter_evaluated=letter_shown,
        highlighted_missings=str(highlighted_missings),
        highlighted_halucinations=str(highlighted_halucinations),
        highlighted_trivial_information=str(highlighted_trivial),
        usability_likert=evaluation_slider,
        comments=evaluation_text,
    )

    with Session(engine) as session:
        session.add(evaluation_instance)
        session.commit()

    return "De feedback is opgeslagen voor deze brief, bedankt!"


# Run the app
if __name__ == "__main__":
    app.run_server(debug=True, port=8050)
