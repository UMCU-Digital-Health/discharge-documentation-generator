import logging
from datetime import datetime
from pathlib import Path

import dash
import dash_bootstrap_components as dbc
import flask
import numpy as np
import pandas as pd
from dash import ctx, html
from dash.dependencies import Input, Output, State
from dash.exceptions import PreventUpdate
from dotenv import load_dotenv

from discharge_docs.config import (
    DEPLOYMENT_NAME_BULK,
    DEPLOYMENT_NAME_ENV,
    TEMPERATURE,
    load_auth_config,
    setup_root_logger,
)
from discharge_docs.dashboard.helper import (
    backup_old_department_docs,
    generate_bulk_docs_for_department,
    get_authorization,
    get_authorized_patients,
    get_data_from_patient_admission,
    get_department_name,
    get_patients_values,
    get_template_prompt,
    highlight,
    load_enc_ids,
    load_stored_discharge_letters,
    update_stored_bulk_docs,
)
from discharge_docs.dashboard.layout import get_layout_evaluation_dashboard
from discharge_docs.llm.connection import initialise_azure_connection
from discharge_docs.llm.helper import format_generated_doc
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
setup_root_logger()

load_dotenv()

client = initialise_azure_connection()

logger.info(f"Running with deployment name: {DEPLOYMENT_NAME_ENV}")

# Authorization config
authorization_config = load_auth_config()

# load data
data_folder = Path(__file__).parents[1] / "data" / "processed"
data = pd.read_parquet(data_folder / "evaluation_data.parquet")

# load stored discharge letters + old version
stored_bulk_path = Path(data_folder / "bulk_generated_docs_gpt.parquet")
old_stored_bulk_path = Path(data_folder / "bulk_generated_docs_gpt_old.parquet")
stored_bulk_gpt = None
stored_bulk_gpt_old = None

# load used enc_ids
enc_ids_dict = load_enc_ids()
values_list = get_patients_values(data, enc_ids_dict)

logger.info("Data loaded...")

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
        authorization_config,
        development_authorizations=["NICU", "IC", "CAR", "PICU", "DEMO"],
    )

    authorized_patients, first_patient = get_authorized_patients(
        authorization_group, values_list
    )
    return authorized_patients, first_patient, [f"Ingelogd als: {user}"]


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
    patient_data = get_data_from_patient_admission(selected_patient_admission, data)
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
    return discharge_documentation.to_numpy()[0]


@app.callback(
    Output("output_stored_generated_discharge_documentation_old", "children"),
    Output("output_stored_generated_discharge_documentation_new", "children"),
    Input("patient_admission_dropdown", "value"),
)
def display_stored_discharge_documentation(
    selected_patient_admission: str,
) -> tuple[html.Div | str, html.Div | str]:
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
        return "", ""

    stored_bulk_gpt = pd.read_parquet(stored_bulk_path)
    stored_bulk_gpt_old = pd.read_parquet(old_stored_bulk_path)

    output_old = load_stored_discharge_letters(
        stored_bulk_gpt_old, selected_patient_admission
    )
    output = load_stored_discharge_letters(stored_bulk_gpt, selected_patient_admission)

    formatted_output_old = format_generated_doc(
        output_old, format_type="markdown", manual_filtering=True
    )
    formatted_output = format_generated_doc(
        output, format_type="markdown", manual_filtering=True
    )

    return html.Div(formatted_output_old), html.Div(formatted_output)


@app.callback(
    Output("template_prompt_space", "children"),
    Output("template_prompt_field", "value"),
    Input("patient_admission_dropdown", "value"),
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
    Output("output_gen_time", "children"),
    Input("update_discharge_button", "n_clicks"),
    Input("patient_admission_dropdown", "value"),
    State("template_prompt_field", "value"),
    State("use_system_prompt", "value"),
)
def display_generated_discharge_doc(
    n_clicks: int,
    selected_patient_admission: str,
    template_prompt: str,
    use_system_prompt: bool,
) -> tuple[html.Div | str, str]:
    """
    Display the discharge documentation generated by GPT
    for the selected patient admission.

    Parameters:
    ----------
     selected_patient_admission : str
        The selected patient admission.

    Returns:
    -------
    list | str
        The discharge documentation for the selected patient admission.
    str
        The generation time of the discharge documentation
    """
    if selected_patient_admission is None or n_clicks is None:
        return "", ""

    # If this is triggered by selecting another patient, just return empty
    if ctx.triggered_id == "patient_admission_dropdown":
        return "", ""

    patient_data = get_data_from_patient_admission(selected_patient_admission, data)

    prompt_builder = PromptBuilder(
        temperature=TEMPERATURE, deployment_name=DEPLOYMENT_NAME_ENV, client=client
    )
    if use_system_prompt:
        user_prompt, system_prompt = load_prompts()
    else:
        user_prompt, system_prompt = None, None
    patient_file_string, _ = get_patient_file(patient_data)
    logger.info("Generating discharge documentation...")
    discharge_letter = prompt_builder.generate_discharge_doc(
        patient_file=patient_file_string,
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        template_prompt=template_prompt,
    )
    generated_output = format_generated_doc(
        discharge_letter, format_type="markdown", manual_filtering=True
    )

    return (
        html.Div(generated_output),
        f"Output gegenereerd om: {datetime.now():%Y-%m-%d %H:%M:%S}",
    )


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
    State("template_prompt_field", "value"),
)
def bulk_generate_letters(
    n_clicks: int, selected_patient_admission: str, template_prompt: str
) -> list | str:
    """
    Generate bulk discharge letters for the selected department.

    Parameters
    ----------
    n_clicks : int
        The number of clicks on the bulk generate button.
    selected_patient_admission : str
        The selected patient admission.
    template_prompt : str
        The template prompt to use for generating the letters.

    Returns
    -------
    str
        A message indicating the status of the bulk generation.
    """
    if selected_patient_admission is None or n_clicks is None:
        return [""]

    if ctx.triggered_id == "patient_admission_dropdown":
        return [""]

    logger.info(f"Running with deployment name: {DEPLOYMENT_NAME_ENV}")

    # Determine department
    department_name = get_department_name(int(selected_patient_admission), enc_ids_dict)
    enc_ids_for_department = enc_ids_dict[department_name]
    logger.info(
        (
            f"Generating for department: {department_name} with "
            f"{len(enc_ids_for_department)} encounters"
        )
    )

    # Backup existing docs for this department
    stored_bulk_loaded = backup_old_department_docs(
        department_name=department_name,
        old_stored_bulk_path=old_stored_bulk_path,
        stored_bulk_path=stored_bulk_path,
        stored_bulk=stored_bulk_gpt,
        stored_bulk_old=stored_bulk_gpt_old,
    )

    # Load prompts and prepare generator
    user_prompt, system_prompt = load_prompts()
    prompt_builder = PromptBuilder(
        temperature=TEMPERATURE,
        deployment_name=DEPLOYMENT_NAME_BULK,
        client=client,
    )

    # Generate documents
    bulk_generated_docs = generate_bulk_docs_for_department(
        department_name=department_name,
        enc_ids=enc_ids_for_department,
        data=data,
        template_prompt=template_prompt,
        prompt_builder=prompt_builder,
        system_prompt=system_prompt,
        user_prompt=user_prompt,
    )

    # Store updated bulk
    update_stored_bulk_docs(
        stored_bulk_path=stored_bulk_path,
        department_name=department_name,
        new_docs=bulk_generated_docs,
        stored_bulk=stored_bulk_loaded,
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
        return {"display": "none"}, {"display": "none"}, {"display": "none"}
    return {"display": "inline"}, {"display": "block"}, {"display": "block"}


if __name__ == "__main__":
    app.run(debug=True, port=8050)
