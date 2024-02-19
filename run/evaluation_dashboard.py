import logging
import os
from datetime import datetime
from pathlib import Path

import dash
import dash_bootstrap_components as dbc
import flask
import pandas as pd
import tomli
from dash import ctx, dcc, html
from dash.dependencies import Input, Output, State
from dash.exceptions import PreventUpdate
from dotenv import load_dotenv
from openai import AzureOpenAI
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from discharge_docs.dashboard.evaluate_dashboard_layout import get_layout
from discharge_docs.dashboard.helper import (
    get_authorization,
    get_data_from_patient_admission,
    get_template_prompt,
    highlight,
)
from discharge_docs.dashboard.prompt import (
    get_GPT_discharge_docs,
    load_pompts,
    load_template_prompt,
)
from discharge_docs.database.models import (
    Base,
    DashEvaluation,
    DashSession,
    DashUserPrompt,
)
from discharge_docs.processing.processing import (
    get_patient_discharge_docs,
    get_patient_file,
)

logger = logging.getLogger(__name__)

# initialise Azure
load_dotenv()
deployment_name = "aiva-gpt"

client = AzureOpenAI(
    api_version="2023-05-15",
    api_key=os.getenv("AZURE_OPENAI_KEY"),
    azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
)

# Authorization config
with open(Path(__file__).parent / "config" / "auth.toml", "rb") as f:
    authorization_dict = tomli.load(f)

# Database config
with open(Path(__file__).parents[1] / "pyproject.toml", "rb") as f:
    project_info = tomli.load(f)

API_VERSION = project_info["project"]["version"]
SQLALCHEMY_DATABASE_URL = "sqlite:///./sql_app.db"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    execution_options={"schema_translate_map": {"aiva-discharge": None}},
)
Base.metadata.create_all(engine)

# load data
df_metavision = pd.read_parquet(
    Path(__file__).parents[1] / "data" / "processed" / "metavision_new_data.parquet"
)
patient_1_NICU = df_metavision[df_metavision["enc_id"] == 107]
patient_1_IC = df_metavision[df_metavision["enc_id"] == 48]

df_HIX = pd.read_parquet(
    Path(__file__).parents[1] / "data" / "processed" / "HiX_data.parquet"
)
patient_1_CAR = df_HIX[df_HIX["enc_id"] == 1001374101]

data_dict = {
    "patient_1_nicu": patient_1_NICU,
    "patient_1_ic": patient_1_IC,
    "patient_1_car": patient_1_CAR,
}

# load prompts
user_prompt, system_prompt = load_pompts()
template_prompt_NICU = load_template_prompt("NICU")
template_prompt_IC = load_template_prompt("IC")
template_prompt_CAR = load_template_prompt("CAR")
template_prompt_dict = {
    "nicu": template_prompt_NICU,
    "ic": template_prompt_IC,
    "car": template_prompt_CAR,
}

# define the app
app = dash.Dash(__name__, external_stylesheets=[dbc.themes.BOOTSTRAP])
application = app.server  # Neccessary for debugging in vscode, no further use

# Define the layout of the app
app.layout = get_layout(user_prompt, system_prompt)


@app.callback(
    Output("patient_admission_dropdown", "options"),
    Output("patient_admission_dropdown", "value"),
    Output("logged_in_user", "children"),
    Input("navbar", "children"),
)
def load_patient_selection_dropdown(_) -> tuple[list, str, list]:
    """
    Load the patient admission dropdown with the available patient admissions when
    the app is starting. Available patients are based on the user's authorization.

    Returns
    -------
    tuple[list, str]
        The list of options for the patient admission dropdown and the first patient
        value.
    """
    user, authorization_group = get_authorization(flask.request, authorization_dict)
    if os.getenv("ENV", "") == "development":
        logger.warning("Running in development mode, overriding authorization group.")
        # Never add this in production!
        authorization_group = ["NICU", "IC", "CAR"]
    values_list = {
        "NICU": {"label": "Patient 1 (NICU 6 dagen)", "value": "patient_1_nicu"},
        "IC": {"label": "Patient 1 (IC 2 dagen)", "value": "patient_1_ic"},
        "CAR": {"label": "Patient 1 (CAR 2 dagen)", "value": "patient_1_car"},
    }
    authorized_patients = [
        value for key, value in values_list.items() if key in authorization_group
    ]
    fist_patient = authorized_patients[0]["value"] if authorized_patients else None

    return authorized_patients, fist_patient, [f"Ingelogd als: {user}"]


@app.callback(
    [Output("date_dropdown", "options"), Output("date_dropdown", "value")],
    [
        Input("patient_admission_dropdown", "value"),
        Input("previous_date_button", "n_clicks"),
        Input("next_date_button", "n_clicks"),
    ],
    [State("date_dropdown", "value")],
)
def update_date_dropdown_combined(
    selected_patient_admission: str,
    previous_clicks: int,
    next_clicks: int,
    current_date: str,
):
    """
    Update the options and value for the date dropdown based on the selected patient
    admission and interaction with previous and next buttons.

    Parameters
    ----------
    selected_patient_admission : str
        The selected patient admission.
    previous_clicks : int
        Number of clicks on the 'previous_date_button'.
    next_clicks : int
        Number of clicks on the 'next_date_button'.
    current_date : str
        Current value of the 'date_dropdown'.

    Returns
    -------
    tuple
        First element is the list of options for the date dropdown.
        Second element is the selected (or updated) value for the date dropdown.
    """
    if selected_patient_admission is None:
        raise PreventUpdate
    data = get_data_from_patient_admission(selected_patient_admission, data_dict)
    date_options = [
        {"label": date.date(), "value": date} for date in data["date"].unique()
    ]

    changed_id = ctx.triggered_id

    updated_date = date_options[0]["value"] if date_options else None

    if changed_id == "previous_date_button":
        prev_dates = data[data["date"] < current_date]["date"]
        if not prev_dates.empty:
            updated_date = prev_dates.iloc[-1]
    elif changed_id == "next_date_button":
        next_dates = data[data["date"] > current_date]["date"]
        if not next_dates.empty:
            updated_date = next_dates.iloc[0]
    elif changed_id == "patient_admission_dropdown":
        updated_date = date_options[0]["value"] if date_options else None

    if not date_options:
        raise PreventUpdate

    return date_options, updated_date


@app.callback(
    Output("description_dropdown", "options"),
    [Input("patient_admission_dropdown", "value")],
)
def update_description_dropdown(selected_patient_admission: str) -> list:
    """
    Update the options for the description dropdown based on the selected patient
    admission.

    Parameters
    ----------
    selected_patient_admission : str
        The selected patient admission.

    Returns
    -------
    list
        The updated list of options for the description dropdown.
    """
    if selected_patient_admission is None:
        raise PreventUpdate
    data = get_data_from_patient_admission(selected_patient_admission, data_dict)
    _, patient_file_df = get_patient_file(df=data)
    description_options = patient_file_df["description"].sort_values().unique()
    return description_options


@app.callback(
    Output("description_dropdown", "value"),
    [
        Input("select_all_button", "n_clicks"),
        Input("deselect_all_button", "n_clicks"),
    ],
    [State("description_dropdown", "options")],
)
def handle_select_button_clicks(
    select_all_clicks: int, deselect_all_clicks: int, options: list[str]
) -> list:
    """
    Handle action for select all and deselect all buttons for selecting the
    sections shown.

    Args:
        select_all_clicks (int): nr of times the select all button is clicked.
        deselect_all_clicks (int): nr of times deselect all button is clicked.
        options (list): List of options for the description dropdown.

    Returns:
        list: Updated value for the description dropdown.
    """
    button_id = ctx.triggered_id

    if button_id == "select_all_button":
        return options
    elif button_id == "deselect_all_button":
        return []
    else:
        raise PreventUpdate


@app.callback(
    Output("output_value", "children"),
    [
        Input("patient_admission_dropdown", "value"),
        Input("date_dropdown", "value"),
        Input("date_checklist", "value"),
        Input("description_dropdown", "value"),
        Input("sorting_dropdown", "value"),
        Input("search_bar", "value"),
    ],
)
def display_value(
    selected_patient_admission: str,
    selected_date: str,
    selected_all_dates: bool,
    selected_description: list,
    sort_dropdown_choice: str,
    search_bar_input: str,
) -> list:
    """Display the discharge documentation for the selected patient admission.

    Parameters
    ----------
    selected_patient_admission : str
        The selected patient admission.
    selected_date : str
        The selected date.
    selected_all_dates : bool
        Flag indicating whether all dates are selected.
    selected_description : list
        The selected descriptions.
    sort_dropdown_choice: str
        The choice for sorting the discharge documentation.

    Returns
    -------
    list
        The discharge documentation for the selected patient admission.
    """
    if (
        selected_description is None
        or selected_date is None
        or selected_patient_admission is None
    ):
        return [""]
    data = get_data_from_patient_admission(selected_patient_admission, data_dict)
    if selected_all_dates:
        patient_file = data[data["description"].isin(selected_description)].sort_values(
            by=["date", "description"]
        )
    else:
        patient_file = data[
            (data["date"] == selected_date)
            & (data["description"].isin(selected_description))
        ].sort_values(by=["date", "description"])

    if sort_dropdown_choice == "sort_by_date":
        patient_file = patient_file.sort_values(by=["date", "description"])
    elif sort_dropdown_choice == "sort_by_code":
        patient_file = patient_file.sort_values(by=["description", "date"])

    if patient_file.empty:
        return ["De geselecteerde data is niet ingevuld voor deze patient."]
    else:
        returnable = []
        for index in patient_file.index:
            returnable.append(
                html.B(
                    str(
                        patient_file.loc[index, "description"]
                        + " - "
                        + str(patient_file.loc[index, "date"].date())
                    )
                )
            )
            returnable.append(html.Br())
            returnable.append(patient_file.loc[index, "value"])
            returnable.append(html.Br())

        if search_bar_input is not None:
            returnable = highlight(returnable, search_bar_input)

        return returnable


@app.callback(
    Output("output_original_discharge_documentation", "children"),
    [
        Input("patient_admission_dropdown", "value"),
    ],
)
def display_discharge_documentation(selected_patient_admission: str) -> list:
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
        return [""]

    data = get_data_from_patient_admission(selected_patient_admission, data_dict)
    discharge_documentation = get_patient_discharge_docs(df=data)
    return discharge_documentation


@app.callback(
    Output("template_prompt_space", "children"),
    [Input("patient_admission_dropdown", "value")],
)
def update_shown_template_prompt(selected_patient_admission: str) -> list:
    if selected_patient_admission is None:
        return [""]
    template_prompt, _ = get_template_prompt(
        selected_patient_admission, template_prompt_dict
    )
    return [template_prompt]


@app.callback(
    Output("output_GPT_discharge_documentation", "children"),
    [
        Input("update_discharge_button", "n_clicks"),
    ],
    [
        State("patient_admission_dropdown", "value"),
        State("temperature_slider", "value"),
        State("addition_prompt", "value"),
    ],
)
def display_GPT_discharge_documentation(
    n_clicks: int,
    selected_patient_admission: str,
    temperature: float,
    addition_prompt: str,
) -> list:
    """
    Display the discharge documentation generated by GPT
    for the selected patient admission.

    Parameters:
    ----------
     selected_patient_admission : str
        The selected patient admission.

    Returns:
    -------
    list
        The discharge documentation for the selected patient admission.
    """
    if selected_patient_admission is None or n_clicks is None:
        return [""]

    data = get_data_from_patient_admission(selected_patient_admission, data_dict)
    patient_file_string, _ = get_patient_file(df=data)

    template_prompt, department = get_template_prompt(
        selected_patient_admission, template_prompt_dict
    )

    if addition_prompt is None:
        GPT_reply = get_GPT_discharge_docs(
            patient_file=patient_file_string,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            template_prompt=template_prompt,
            temperature=temperature,
            engine=deployment_name,
            client=client,
        )
    else:
        GPT_reply = get_GPT_discharge_docs(
            patient_file=patient_file_string,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            template_prompt=template_prompt,
            temperature=temperature,
            engine=deployment_name,
            client=client,
            addition_prompt=addition_prompt,
        )

    GPT_output = []
    for category_pair in GPT_reply:
        GPT_output.append(
            html.Div(
                [
                    html.Strong(category_pair["Categorie"]),
                    dcc.Markdown(category_pair["Beloop tijdens opname"]),
                ]
            )
        )
    return GPT_output


@app.callback(
    Output("evaluation_saved_label", "children"),
    [Input("evaluate_button", "n_clicks")],
    [
        State("evaluation_slider", "value"),
        State("evaluation_text", "value"),
        State("addition_prompt", "value"),
    ],
)
def gather_feedback(
    n_clicks: int, evaluation_slider: int, evaluation_text: str, additional_prompt: str
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
    additional_prompt : str
        The additional prompt provided by the user.

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
    user, authorized_groups = get_authorization(flask.request, authorization_dict)
    dash_session = DashSession(
        timestamp=datetime.now(),
        user=user,
        groups=str(authorized_groups),
        version=API_VERSION,
    )
    custom_prompt = DashUserPrompt(
        prompt=additional_prompt, session_relation=dash_session
    )
    evaluation_user_score = DashEvaluation(
        evaluation_metric="slider-score",
        evaluation_value=str(evaluation_slider),
    )
    evaluation_remarks = DashEvaluation(
        evaluation_metric="remarks",
        evaluation_value=evaluation_text,
    )
    custom_prompt.evaluation_relation.append(evaluation_user_score)
    custom_prompt.evaluation_relation.append(evaluation_remarks)

    with Session(engine) as session:
        session.add(custom_prompt)
        session.commit()

    return "De feedback is opgeslagen, bedankt!"


@app.callback(
    Output("offcanvas", "is_open"),
    Input("show_prompt_button", "n_clicks"),
    State("offcanvas", "is_open"),
)
def show_prompts(n: int, is_open: bool) -> bool:
    """Toggle the offcanvas menu.

    Parameters
    ----------
    n : int
        the number of times the button was clicked.
    is_open : bool
        if the offcanvas menu is open.

    Returns
    -------
    bool
        if the offcanvas menu should be open.
    """
    if n:
        return not is_open
    return is_open


# Run the app
if __name__ == "__main__":
    app.run_server(debug=True, port=8051)
