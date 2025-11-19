import logging
import os

import dash
import dash_bootstrap_components as dbc
import flask
import numpy as np
import pandas as pd
from dash import ctx, html
from dash.dependencies import Input, Output, State
from dash.exceptions import PreventUpdate
from dotenv import load_dotenv
from sqlalchemy.orm import sessionmaker
from umcu_ai_utils.database_connection import get_engine

from discharge_docs.config import (
    DEPLOYMENT_NAME_ENV,
    TEMPERATURE,
    load_auth_config,
    load_department_config,
    setup_root_logger,
)
from discharge_docs.dashboard.helper import (
    get_authorization,
    get_department_prompt,
    get_development_admissions,
    get_patients_values,
    highlight,
    query_patient_file,
    query_stored_doc,
)
from discharge_docs.dashboard.layout import get_layout_development_dashboard
from discharge_docs.database.models import DashEncounter
from discharge_docs.llm.connection import initialise_azure_connection
from discharge_docs.llm.helper import generate_single_doc
from discharge_docs.llm.prompt import load_prompts
from discharge_docs.llm.prompt_builder import PromptBuilder
from discharge_docs.processing.bulk_generation import run_bulk_generation
from discharge_docs.processing.processing import (
    get_patient_file,
)

logger = logging.getLogger(__name__)
setup_root_logger()

load_dotenv()

client = initialise_azure_connection()

logger.info(f"Running with deployment name: {DEPLOYMENT_NAME_ENV}")

# Authorization config
authorization_config = load_auth_config()

# create connection to the database

engine = get_engine(
    db_env=os.getenv("DB_ENVIRONMENT"), schema_name=DashEncounter.__table__.schema
)
SESSIONMAKER = sessionmaker(bind=engine)

logger.info("Data loaded...")

general_prompt, system_prompt = load_prompts()

# load deployment config with department specific prompts
department_config = load_department_config()

# define the app
app = dash.Dash(
    __name__,
    external_stylesheets=[dbc.themes.BOOTSTRAP],
)
application = app.server  # Neccessary for debugging in vscode, no further use

# Define the layout of the app
app.layout = get_layout_development_dashboard(system_prompt, general_prompt)


@app.callback(
    Output("llm_env", "children"),
    Input("navbar", "children"),
)
def update_llm_env(_):
    """
    Update the LLM environment display within the navbar

    Returns
    -------
    str
        The updated LLM environment display.
    """
    return f"LLM Environment: {os.getenv('LLM_ENVIRONMENT')}"


@app.callback(
    Output("patient_admission_dropdown", "options"),
    Output("patient_admission_dropdown", "value"),
    Output("logged_in_user", "children"),
    Output("patient_admission_store", "data"),
    Input("navbar", "children"),
)
def load_patient_selection_dropdown(_) -> tuple[list, str | None, list, dict]:
    """
    Populate the patient admission dropdown and return the logged-in user plus
    a store of admissions. Triggered when the navbar changes.

    Returns
    -------
    tuple[list, str | None, list, dict]
        - patient_admission_dropdown options: list[dict] with 'label' and 'value'
        - initial value for patient_admission_dropdown (str or None)
        - logged_in_user children: list with a single string element
        - patient_admission_store data: dict representing admissions dataframe

    Raises
    ------
    PreventUpdate
        If the authenticated user has no authorized patients to view.
    """

    user, authorization_group = get_authorization(
        flask.request,
        authorization_config,
        development_authorizations=[
            department_config.department[key].id
            for key in department_config.department.keys()
        ],
    )

    development_admissions = get_development_admissions(
        authorization_group, SESSIONMAKER
    )

    if development_admissions.empty:
        logger.warning(
            f"User {user} has no authorized patients to view. "
            "Check authorization configuration."
        )
        raise PreventUpdate
    patient_values = get_patients_values(development_admissions)

    patient_values_list = [
        item
        for key, values in patient_values.items()
        if key in authorization_group
        for item in values
    ]
    first_patient = patient_values_list[0]["value"] if patient_values_list else None

    return (
        patient_values_list,
        first_patient,
        [f"Ingelogd als: {user}"],
        development_admissions.to_dict(),
    )


@app.callback(
    Output("date_dropdown", "options"),
    Output("date_dropdown", "value"),
    Input("patient_admission_dropdown", "value"),
    Input("previous_date_button", "n_clicks"),
    Input("next_date_button", "n_clicks"),
    State("date_dropdown", "value"),
)
def update_date_dropdown(
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

    patient_data = query_patient_file(selected_patient_admission, SESSIONMAKER)

    date_options = [
        {"label": date.date(), "value": date} for date in patient_data["date"].unique()
    ]

    changed_id = ctx.triggered_id

    updated_date = date_options[0]["value"] if date_options else None

    if changed_id == "previous_date_button":
        prev_dates = patient_data[patient_data["date"] < current_date]["date"]
        if not prev_dates.empty:
            updated_date = prev_dates.iloc[-1]
    elif changed_id == "next_date_button":
        next_dates = patient_data[patient_data["date"] > current_date]["date"]
        if not next_dates.empty:
            updated_date = next_dates.iloc[0]
    elif changed_id == "patient_admission_dropdown":
        updated_date = date_options[0]["value"] if date_options else None

    if not date_options:
        raise PreventUpdate

    return date_options, updated_date


@app.callback(
    Output("description_dropdown", "options"),
    Input("patient_admission_dropdown", "value"),
)
def update_description_dropdown(selected_patient_admission: str) -> np.ndarray:
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
    patient_data = query_patient_file(selected_patient_admission, SESSIONMAKER)
    _, patient_file_df = get_patient_file(patient_data)
    description_options = patient_file_df["description"].sort_values().unique()
    return description_options


@app.callback(
    Output("description_dropdown", "value"),
    Input("select_all_button", "n_clicks"),
    Input("deselect_all_button", "n_clicks"),
    State("description_dropdown", "options"),
)
def handle_select_button_clicks(
    select_all_clicks: int, deselect_all_clicks: int, options: list[str]
) -> list:
    """
    Handle action for select all and deselect all buttons for selecting the
    sections shown.

    Parameters
    ----------
    select_all_clicks : int
        The number of times the select all button is clicked.
    deselect_all_clicks : int
        The number of times the deselect all button is clicked.
    options : list
        List of options for the description dropdown.

    Returns
    -------
    list
        Updated value for the description dropdown.
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
    Input("patient_admission_dropdown", "value"),
    Input("date_dropdown", "value"),
    Input("date_checklist", "value"),
    Input("description_dropdown", "value"),
    Input("sorting_dropdown", "value"),
    Input("search_bar", "value"),
)
def display_patient_file(
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
    patient_data = query_patient_file(selected_patient_admission, SESSIONMAKER)
    if selected_all_dates:
        patient_file = patient_data[
            patient_data["description"].isin(selected_description)
        ].sort_values(by=["date", "description"])
    else:
        patient_file = patient_data[
            (patient_data["date"] == selected_date)
            & (patient_data["description"].isin(selected_description))
        ].sort_values(by=["date", "description"])

    if sort_dropdown_choice == "sort_by_date":
        patient_file = patient_file.sort_values(by=["date", "description"])
    elif sort_dropdown_choice == "sort_by_code":
        patient_file = patient_file.sort_values(by=["description", "date"])

    if patient_file.empty:
        return ["De geselecteerde data is niet ingevuld voor deze patient."]
    else:
        returnable = []
        for _, row in patient_file.iterrows():
            returnable.append(
                html.B(
                    f"{row['description']} - {row['date'].date()}",
                )
            )
            returnable.append(html.Br())
            returnable.append(row["content"])
            returnable.append(html.Br())

        if search_bar_input is not None and search_bar_input != "":
            returnable = highlight(returnable, search_bar_input)

        return returnable


@app.callback(
    Output("output_original_discharge_documentation", "children"),
    Input("patient_admission_dropdown", "value"),
)
def display_discharge_documentation(selected_patient_admission: str) -> str:
    """
    Display the discharge documentation for the selected patient admission.

    Parameters
    ----------
    selected_patient_admission : str
        The selected patient admission.

    Returns
    -------
    str
        The discharge documentation for the selected patient admission as a string.
        Returns an empty string if no patient is selected.
    """
    if selected_patient_admission is None:
        return ""

    discharge_documentation_df = query_stored_doc(
        selected_patient_admission, "Human", SESSIONMAKER
    )
    print(discharge_documentation_df["discharge_letter"].values[0])
    return discharge_documentation_df["discharge_letter"].values[0]


@app.callback(
    Output("output_stored_generated_discharge_documentation_old", "children"),
    Output("output_stored_generated_discharge_documentation_new", "children"),
    Input("patient_admission_dropdown", "value"),
)
def display_stored_discharge_documentation(
    selected_patient_admission: str,
) -> tuple[html.Div | str, html.Div | str]:
    """
    Display the stored discharge documentation for the selected patient admission from
    both old and new iterations.

    Parameters
    ----------
    selected_patient_admission : str
        The selected patient admission.

    Returns
    -------
    tuple[html.Div | str, html.Div | str]
        A tuple containing:
        - The discharge documentation from the older model (html.Div or str)
        - The discharge documentation from the newer model (html.Div or str)
        Returns empty strings if no patient is selected.
    """
    if selected_patient_admission is None:
        return "", ""

    discharge_documentation_df = query_stored_doc(
        selected_patient_admission, "AI", SESSIONMAKER
    )

    try:
        newest_doc = discharge_documentation_df["discharge_letter"].values[0]
    except IndexError:
        newest_doc = "Er is geen opgeslagen GPT brief gevonden voor deze opname."

    try:
        second_newest_doc = discharge_documentation_df["discharge_letter"].values[1]
    except IndexError:
        second_newest_doc = (
            "Er is geen tweede opgeslagen GPT brief gevonden voor deze opname."
        )
    print(newest_doc)
    return second_newest_doc, newest_doc


@app.callback(
    Output("department_prompt_space", "children"),
    Output("department_prompt_field", "value"),
    Output("post_processing_prompt_field", "value"),
    Input("patient_admission_dropdown", "value"),
    State("patient_admission_store", "data"),
)
def update_department_prompt(
    selected_patient_admission: str, development_admissions: dict
) -> tuple[list[str], str, str]:
    """
    Update the department prompt for the selected patient admission.

    Parameters
    ----------
    selected_patient_admission : str
        The selected patient admission.

    Returns
    -------
    tuple[list[str], str]
        A tuple containing:
        - The department prompt as a list (for display)
        - The department prompt as a string (for editing)
        Returns empty values if no patient is selected.
    """
    if selected_patient_admission is None:
        return [""], "", ""
    department_prompt, department = get_department_prompt(
        selected_patient_admission,
        pd.DataFrame(development_admissions),
        department_config,
    )
    post_processing_prompt = department_config.department[
        department
    ].post_processing_prompt
    if post_processing_prompt is None:
        post_processing_prompt = ""
    return [department_prompt], department_prompt, post_processing_prompt


@app.callback(
    Output("output_GPT_discharge_documentation", "children"),
    Input("update_discharge_button", "n_clicks"),
    Input("patient_admission_dropdown", "value"),
    State("department_prompt_field", "value"),
    State("use_system_prompt", "value"),
    State("post_processing_prompt_field", "value"),
)
def display_generated_discharge_doc(
    n_clicks: int,
    selected_patient_admission: str,
    department_prompt: str,
    use_system_prompt: bool,
    post_processing_prompt: str,
) -> html.Div | str:
    """
    Display the discharge documentation generated by GPT for the selected patient
    admission.

    Parameters
    ----------
    n_clicks : int
        Number of clicks on the update button.
    selected_patient_admission : str
        The selected patient admission.
    department_prompt : str
        The department prompt to use for generation.
    use_system_prompt : bool
        Whether to use the system prompt.

    Returns
    -------
    html.Div | str
        The generated discharge documentation as html.Div or an empty string if not
        triggered.
    """
    if selected_patient_admission is None or n_clicks is None:
        return ""

    # If this is triggered by selecting another patient, just return empty
    if ctx.triggered_id == "patient_admission_dropdown":
        return ""

    patient_data = query_patient_file(selected_patient_admission, SESSIONMAKER)

    prompt_builder = PromptBuilder(
        temperature=TEMPERATURE, deployment_name=DEPLOYMENT_NAME_ENV, client=client
    )
    if use_system_prompt:
        general_prompt, system_prompt = load_prompts()
    else:
        general_prompt, system_prompt = None, None
    patient_file_string, _ = get_patient_file(patient_data)
    logger.info("Generating discharge documentation...")

    discharge_letter = generate_single_doc(
        prompt_builder=prompt_builder,
        patient_file_string=patient_file_string,
        system_prompt=system_prompt,
        general_prompt=general_prompt,
        department=patient_data["department"].iloc[0],
        department_config=department_config,
        length_of_stay=patient_data["length_of_stay"].values[0],
        department_prompt=department_prompt,
        post_processing_prompt=post_processing_prompt,
    )

    generated_output = discharge_letter.format(
        format_type="markdown", manual_filtering=False
    )

    return html.Div(generated_output)


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


@app.callback(
    Output("bulk_generation_status", "children"),
    Input("bulk_generate_button", "n_clicks"),
    Input("patient_admission_dropdown", "value"),
    State("department_prompt_field", "value"),
    State("post_processing_prompt_field", "value"),
    State("patient_admission_store", "data"),
)
def bulk_generate_letters(
    n_clicks: int,
    selected_patient_admission: str,
    department_prompt: str,
    post_processing_prompt: str,
    development_admissions: dict,
) -> list | str:
    """
    Generate bulk discharge letters for the selected department.

    Parameters
    ----------
    n_clicks : int
        The number of clicks on the bulk generate button.
    selected_patient_admission : str
        The selected patient admission.
    department_prompt : str
        The department prompt to use for generating the letters.
    post_processing_prompt : str
        The post-processing prompt to refine the generated letters.

    Returns
    -------
    list | str
        A message or list indicating the status of the bulk generation. Returns a list
        with an empty string if not triggered, otherwise a status message string.
    """
    if selected_patient_admission is None or n_clicks is None:
        return [""]

    if ctx.triggered_id == "patient_admission_dropdown":
        return [""]

    logger.info(f"Running with deployment name: {DEPLOYMENT_NAME_ENV}")

    # Determine department
    df_development_admissions = pd.DataFrame(development_admissions)
    _, department = get_department_prompt(
        selected_patient_admission,
        df_development_admissions,
        department_config,
    )

    run_bulk_generation(
        client,
        storage_location="database",
        selected_department=department,
        department_prompt=department_prompt,
        post_processing_prompt=post_processing_prompt,
    )

    return (
        "Generatie batch ontslagbrieven is klaar. "
        "De brieven zijn te vinden onder 'opgeslagen GPT brieven (Nieuwe versie)'. "
        "Selecteer de patient opnieuw om de nieuwe brieven te zien."
    )


@app.callback(
    Output("bulk_generate_button", "style"),
    Output("bulk_generate_label", "style"),
    Output("use_system_prompt", "style"),
    Output("post_processing_prompt_div", "style"),
    Input("dev_mode", "value"),
)
def toggle_bulk_generation_controls(dev_mode: bool) -> tuple:
    """Toggle the visibility of bulk generation controls.

    This function toggles the visibility of advanced functions like bulk generation
    and disabling the system/user prompt. These are hidden by default, but can be
    enabled using a dev toggle.

    Parameters
    ----------
    dev_mode : bool
        The development mode toggle

    Returns
    -------
    tuple
        The styles for the bulk generate button, status label, and system/user prompt
        toggle.
    """
    if not dev_mode:
        return (
            {"display": "none"},
            {"display": "none"},
            {"display": "none"},
            {"display": "none"},
        )
    return (
        {"display": "inline"},
        {"display": "block"},
        {"display": "block"},
        {"display": "block"},
    )


if __name__ == "__main__":
    app.run(debug=True, port=8050)
