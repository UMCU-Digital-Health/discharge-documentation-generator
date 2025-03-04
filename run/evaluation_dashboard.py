import logging
from pathlib import Path

import dash
import dash_bootstrap_components as dbc
import flask
import numpy as np
import pandas as pd
import tomli
from dash import ctx, html
from dash.dependencies import Input, Output, State
from dash.exceptions import PreventUpdate
from dotenv import load_dotenv

from discharge_docs.config import DEPLOYMENT_NAME_ENV, TEMPERATURE
from discharge_docs.dashboard.helper import (
    format_generated_doc,
    get_authorization,
    get_authorized_patients,
    get_data_from_patient_admission,
    get_patients_values,
    get_template_prompt,
    highlight,
    load_enc_ids,
    load_stored_discharge_letters,
)
from discharge_docs.dashboard.layout import get_layout_evaluation_dashboard
from discharge_docs.llm.connection import initialise_azure_connection
from discharge_docs.llm.prompt import (
    load_all_templates_prompts_into_dict,
    load_prompts,
)
from discharge_docs.llm.prompt_builder import PromptBuilder
from discharge_docs.processing.processing import (
    get_patient_discharge_docs,
    get_patient_file,
)

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

load_dotenv()

client = initialise_azure_connection()

logger.info(f"Running with deployment name: {DEPLOYMENT_NAME_ENV}")

# Authorization config
with open(Path(__file__).parent / "config" / "auth.toml", "rb") as f:
    authorization_dict = tomli.load(f)

# load data
data_folder = Path(__file__).parents[1] / "data" / "processed"
data = pd.read_parquet(data_folder / "evaluation_data.parquet")

# load stored discharge letters + old version
stored_bulk_gpt = pd.read_parquet(data_folder / "bulk_generated_docs_gpt.parquet")
stored_bulk_gpt_old = pd.read_parquet(
    data_folder / "bulk_generated_docs_gpt_old.parquet"
)

# load used enc_ids
enc_ids_dict = load_enc_ids()
values_list = get_patients_values(data, enc_ids_dict)

logger.info("data loaded")

# load prompts
user_prompt, system_prompt = load_prompts()
template_prompt_dict = load_all_templates_prompts_into_dict()

# define the app
app = dash.Dash(
    __name__,
    external_stylesheets=[dbc.themes.BOOTSTRAP],
)
application = app.server  # Neccessary for debugging in vscode, no further use

# Define the layout of the app
app.layout = get_layout_evaluation_dashboard(user_prompt, system_prompt)


@app.callback(
    Output("patient_admission_dropdown", "options"),
    Output("patient_admission_dropdown", "value"),
    Output("logged_in_user", "children"),
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

    user, authorization_group = get_authorization(
        flask.request,
        authorization_dict,
        development_authorizations=["NICU", "IC", "CAR", "PSY", "DEMO"],
    )

    authorized_patients, fist_patient = get_authorized_patients(
        authorization_group, values_list
    )

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
    patient_data = get_data_from_patient_admission(selected_patient_admission, data)
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
    [Input("patient_admission_dropdown", "value")],
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
    patient_data = get_data_from_patient_admission(selected_patient_admission, data)
    _, patient_file_df = get_patient_file(patient_data)
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
    [
        Input("patient_admission_dropdown", "value"),
        Input("date_dropdown", "value"),
        Input("date_checklist", "value"),
        Input("description_dropdown", "value"),
        Input("sorting_dropdown", "value"),
        Input("search_bar", "value"),
    ],
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
    patient_data = get_data_from_patient_admission(selected_patient_admission, data)
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
        for index in patient_file.index:
            returnable.append(
                html.B(
                    str(patient_file.loc[index, "description"])
                    + " - "
                    + str(patient_file.loc[index, "date"].date())
                )
            )
            returnable.append(html.Br())
            returnable.append(patient_file.loc[index, "content"])
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
def display_discharge_documentation(selected_patient_admission: str) -> str:
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

    patient_data = get_data_from_patient_admission(selected_patient_admission, data)
    discharge_documentation = get_patient_discharge_docs(patient_data)
    return discharge_documentation


@app.callback(
    Output("output_stored_generated_discharge_documentation_old", "children"),
    Output("output_stored_generated_discharge_documentation_new", "children"),
    [
        Input("patient_admission_dropdown", "value"),
    ],
)
def display_stored_discharge_documentation(
    selected_patient_admission: str,
) -> tuple[list, list]:
    """
    Display the discharge documentation for the selected patient admission.

    Parameters:
    ----------
    selected_patient_admission : str
        The selected patient admission.

    Returns:
    -------
    tuple[list, list]
        A tuple containing two lists:
        - The discharge docs for the selected patient admission from the older model
        - The discharge docs for the selected patient admission from the newer model
    """
    if selected_patient_admission is None:
        return ""

    output_old = load_stored_discharge_letters(
        stored_bulk_gpt_old, selected_patient_admission
    )
    output = load_stored_discharge_letters(stored_bulk_gpt, selected_patient_admission)

    return output_old, output


@app.callback(
    Output("template_prompt_space", "children"),
    Output("template_prompt_field", "value"),
    [Input("patient_admission_dropdown", "value")],
)
def update_template_prompt(selected_patient_admission: str) -> tuple[list[str], str]:
    if selected_patient_admission is None:
        return [""], ""
    template_prompt, _ = get_template_prompt(
        selected_patient_admission, template_prompt_dict, enc_ids_dict
    )
    return [template_prompt], template_prompt


@app.callback(
    Output("output_GPT_discharge_documentation", "children"),
    Input("update_discharge_button", "n_clicks"),
    Input("patient_admission_dropdown", "value"),
    State("template_prompt_field", "value"),
)
def display_generated_discharge_doc(
    n_clicks: int,
    selected_patient_admission: str,
    template_prompt: str,
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

    patient_data = get_data_from_patient_admission(selected_patient_admission, data)

    prompt_builder = PromptBuilder(
        temperature=TEMPERATURE, deployment_name=DEPLOYMENT_NAME_ENV, client=client
    )
    user_prompt, system_prompt = load_prompts()
    patient_file_string, _ = get_patient_file(patient_data)
    discharge_letter = prompt_builder.generate_discharge_doc(
        patient_file=patient_file_string,
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        template_prompt=template_prompt,
    )
    generated_doc = discharge_letter

    generated_output = format_generated_doc(generated_doc, format_type="markdown")
    return generated_output


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


if __name__ == "__main__":
    app.run_server(debug=True, port=8050)
