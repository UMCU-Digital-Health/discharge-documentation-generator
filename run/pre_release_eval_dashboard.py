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
from dash import callback_context, ctx, html
from dash.dependencies import Input, Output, State
from dash.exceptions import PreventUpdate
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from discharge_docs.dashboard.dashboard_layout import (
    get_layout_pre_release_eval,
)
from discharge_docs.dashboard.helper import (
    get_authorization,
    get_authorized_patients,
    get_data_from_patient_admission,
    get_patients_from_list_names_pilot,
    get_suitable_enc_ids,
    get_user,
    load_stored_discharge_letters_pre_release,
)
from discharge_docs.database.models import Base, EvalPhase1
from discharge_docs.processing.processing import get_patient_discharge_docs

logger = logging.getLogger(__name__)


# load data
data_folder = Path(__file__).parents[1] / "data" / "processed" / "pre-pilot"

df_metavision = pd.read_parquet(data_folder / "metavision_data_april_dp.parquet")

df_HIX = pd.read_parquet(data_folder / "HiX_CAR_data_pre_pilot.parquet")


# Define your DataFrames for each department
df_dict = {
    "NICU": df_metavision,
    "IC": df_metavision,
    "CAR": df_HIX,
    "PSY": df_HIX,
}

# load used enc_ids
id_dep_dict = get_suitable_enc_ids(
    "enc_ids_pre_release_phase1_1.toml", "department_user"
)

data_dict, values_list = get_patients_from_list_names_pilot(df_dict, id_dep_dict)

# Authorization config
with open(Path(__file__).parent / "config" / "auth_fase1.toml", "rb") as f:
    authorization_dict = tomli.load(f)

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

df_discharge4 = pd.read_csv(data_folder / "bulk_generated_docs_gpt4_PReval_4.csv")

# define the app
app = dash.Dash(
    __name__,
    external_stylesheets=[dbc.themes.BOOTSTRAP],
)
application = app.server  # Neccessary for debugging in vscode, no further use

# Define the layout of the app
app.layout = get_layout_pre_release_eval()


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
    _, authorization_group = get_authorization(
        flask.request,
        authorization_dict,
        development_authorizations=["student_1", "student_2"],
    )
    authorized_patients, fist_patient = get_authorized_patients(
        authorization_group, values_list
    )
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

    if patient_file.empty:
        return ["Er is geen patientendossier voor deze patient."]
    else:
        patient_file = patient_file[patient_file["description"] != "Ontslagbrief"]
        patient_file_string = "\n\n".join(
            patient_file.apply(
                lambda row: (
                    f"{row['description'].upper()} -"
                    + f" {row['date'].date()} \n{row['value']}"
                    + f"\n\n{'#'*50}"
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
        Input("remove_hall_button", "n_clicks"),
        Input("hidden-input_trivial", "value"),
        Input("remove_trivial_button", "n_clicks"),
        Input("hidden-input_missings", "value"),
        Input("remove_missings_button", "n_clicks"),
        Input("patient_admission_dropdown", "value"),
        Input("evaluate_button", "n_clicks"),
        Input("next_button", "n_clicks"),
    ],
    [
        State("hall_store", "data"),
        State("hall_remove_index", "value"),
        State("trivial_store", "data"),
        State("trivial_remove_index", "value"),
        State("missings_store", "data"),
        State("missings_remove_index", "value"),
    ],
)
def handle_markings(  # noqa: C901
    hall_text: str,
    remove_hall_clicks: int,
    trivial_text: str,
    remove_trivial_clicks: int,
    missings_text: str,
    remove_missings_clicks: int,
    patient_value: str,
    evaluate_clicks: int,
    next_clicks: int,
    stored_hall: list,
    hall_remove_index: int,
    stored_trivial: list,
    trivial_remove_index: int,
    stored_missings: list,
    missings_remove_index: int,
) -> tuple:
    """Handle the markings made by the user.

    This function handles the markings made by the user in the evaluation dashboard.
    It updates the stored hallucinations, trivial information, and missings based on
    the user's input it also updates the shown text containing the marked text.

    Also it resets the stored values when a new patient is selected or the evaluate
    button is pressed.

    Parameters
    ----------
    hall_text : str
        The text of the hallucinations marked by the user.
    trivial_text : str
        The text of the trivial information marked by the user.
    missings_text : str
        The text of the missings marked by the user.
    patient_value : str
        The value of the selected patient.
    evaluate_clicks : int
        The number of times the evaluate button has been clicked.
    next_clicks : int
        The number of times the next button has been clicked.
    stored_hall : list
        The list of stored hallucinations.
    stored_trivial : list
        The list of stored trivial information.
    stored_missings : list
        The list of stored missings.

    Returns
    -------
    tuple
        A tuple containing the updated values of the stored hallucinations,
        trivial information, and missings.

    """
    if not ctx.triggered:
        raise PreventUpdate

    trigger_id = ctx.triggered[0]["prop_id"].split(".")[0]

    # Clearing all data either on new patient selection or evaluate button pressed
    if trigger_id in ["patient_admission_dropdown", "evaluate_button", "next_button"]:
        return (
            "",
            3,
            "Nog geen hallucinaties/fouten gemarkeerd.",
            [],
            "Nog geen triviale informatie gemarkeerd.",
            [],
            "Nog geen missings gemarkeerd.",
            [],
        )

    def format_list(items):
        return html.Ol([html.Li(item) for item in items])

    no_update_returnable = (dash.no_update,) * 8

    def handle_trigger(
        trigger_id, text, remove_index, stored_list, update_index, store_index
    ):
        if trigger_id == f"hidden-input_{trigger_id.split('_')[1]}" and text:
            stored_list.append(text)
            updates = list(no_update_returnable)
            updates[update_index] = format_list(stored_list)
            updates[store_index] = stored_list
            return tuple(updates)
        elif (
            trigger_id == f"remove_{trigger_id.split('_')[1]}_button"
            and remove_index is not None
        ):
            if 1 <= remove_index <= len(stored_list):
                stored_list.pop(remove_index - 1)
                updates = list(no_update_returnable)
                if not stored_list:
                    updates[update_index] = "Alle markeeringen zijn verwijderd."
                else:
                    updates[update_index] = format_list(stored_list)
                updates[store_index] = stored_list
                return tuple(updates)
            else:
                return no_update_returnable
        return no_update_returnable

    if trigger_id in ["hidden-input_hall", "remove_hall_button"]:
        return handle_trigger(
            trigger_id, hall_text, hall_remove_index, stored_hall, 2, 3
        )
    elif trigger_id in ["hidden-input_trivial", "remove_trivial_button"]:
        return handle_trigger(
            trigger_id, trivial_text, trivial_remove_index, stored_trivial, 4, 5
        )
    elif trigger_id in ["hidden-input_missings", "remove_missings_button"]:
        return handle_trigger(
            trigger_id, missings_text, missings_remove_index, stored_missings, 6, 7
        )

    return no_update_returnable


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
    app.run_server(debug=True, port=8052)
