import os
from pathlib import Path

import dash
import dash_bootstrap_components as dbc
import pandas as pd
from dash import ctx, dcc, html
from dash.dependencies import Input, Output, State
from dash.exceptions import PreventUpdate
from dotenv import load_dotenv
from openai import AzureOpenAI

from discharge_docs.dashboard.evaluate_dashboard_layout import get_layout
from discharge_docs.dashboard.prompt import (
    get_GPT_discharge_docs,
    load_NICU_template_prompt,
    load_pompts,
)
from discharge_docs.processing.processing import (
    get_patient_discharge_docs,
    get_patient_file,
)

# initialise Azure
load_dotenv()
deployment_name = "aiva-gpt"

client = AzureOpenAI(
    api_version="2023-05-15",
    api_key=os.getenv("AZURE_OPENAI_KEY"),
    azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
)

# load data
df_metavision = pd.read_parquet(
    Path(__file__).parents[1] / "data" / "processed" / "metavision_new_data.parquet"
)
enc_id = 107
department = "NICU"
patient_1_NICU = df_metavision[df_metavision["enc_id"] == enc_id]

# load prompts
user_prompt, system_prompt = load_pompts()
template_prompt_NICU = load_NICU_template_prompt()

# define the app
app = dash.Dash(__name__, external_stylesheets=[dbc.themes.BOOTSTRAP])
application = app.server  # Neccessary for debugging in vscode, no further use

# Define the layout of the app
app.layout = get_layout(
    patient_1_NICU, user_prompt, system_prompt, template_prompt_NICU
)


@app.callback(
    Output("date_dropdown", "value"),
    [
        Input("previous_date_button", "n_clicks"),
        Input("next_date_button", "n_clicks"),
    ],
    [State("date_dropdown", "value")],
)
def update_date_dropdown(
    previous_clicks: int, next_clicks: int, current_date: str
) -> str:
    """
    Update the value of the 'enc_id_dropdown' based on user interaction with
    previous and next buttons.

    Parameters
    ----------
    previous_clicks : int
        Number of clicks on the 'previous_date_button'.
    next_clicks : int
        Number of clicks on the 'next_date_button'.
    current_date : str
        Current value of the 'date_dropdown'.

    Returns
    -------
    str
        Updated value for the 'date_dropdown'.

    Raises
    ------
    PreventUpdate
        If no button is clicked.

    """
    data = patient_1_NICU
    changed_id = ctx.triggered_id
    if changed_id == "previous_date_button":
        return data[data["date"] < current_date]["date"].iloc[-1]
    elif changed_id == "next_date_button":
        return data[data["date"] > current_date]["date"].iloc[0]
    else:
        raise PreventUpdate


@app.callback(
    Output("description_dropdown", "value"),
    [
        Input("select_all_button", "n_clicks"),
        Input("deselect_all_button", "n_clicks"),
    ],
    [State("description_dropdown", "options")],
)
def handle_button_clicks(
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
    ],
)
def display_value(
    selected_patient_admission: str,
    selected_date: str,
    selected_all_dates: bool,
    selected_description: list,
    sort_dropdown_choice: str,
) -> list:
    """_summary_

    Parameters
    ----------
    selected_patient_admission : str
        _description_
    selected_date : str
        _description_
    selected_all_dates : bool
        _description_
    selected_description : list
        _description_
    sort_dropdown_choice: str
        _description_

    Returns
    -------
    list
        _description_
    """
    if (
        selected_description is None
        or selected_date is None
        or selected_patient_admission is None
    ):
        return [""]
    if selected_all_dates:
        patient_file = patient_1_NICU[
            patient_1_NICU["description"].isin(selected_description)
        ].sort_values(by=["date", "description"])
    else:
        patient_file = patient_1_NICU[
            (patient_1_NICU["date"] == selected_date)
            & (patient_1_NICU["description"].isin(selected_description))
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
            returnable.append(str(patient_file.loc[index, "value"]))
            returnable.append(html.Br())
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

    discharge_documentation = get_patient_discharge_docs(
        enc_id=enc_id, df=patient_1_NICU
    )
    return discharge_documentation


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

    (patient_file_string, patient_file_df) = get_patient_file(enc_id, df=patient_1_NICU)
    if addition_prompt is None:
        GPT_reply = get_GPT_discharge_docs(
            patient_file=patient_file_string,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            template_prompt=template_prompt_NICU,
            temperature=temperature,
            engine=deployment_name,
            client=client,
        )
    else:
        GPT_reply = get_GPT_discharge_docs(
            patient_file=patient_file_string,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            template_prompt=template_prompt_NICU,
            temperature=temperature,
            engine=deployment_name,
            client=client,
            addition_prompt=addition_prompt,
        )

    GPT_output = []
    if department == "NICU":
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
    [State("evaluation_slider", "value"), State("evaluation_text", "value")],
)
def gather_feedback(n_clicks: int, evaluation_slider: int, evaluation_text: str) -> str:
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

    Returns
    -------
    str
        A string containing the user's score and feedback.

    Raises
    ------
    PreventUpdate
        If the feedback button was clicked without any changes.

    """
    if n_clicks is None:
        raise PreventUpdate
    # TODO add functionality to save the feedback to database
    # using evaluation slider and evaluation text
    return "De feedback is opgeslagen, bedankt!"


# Run the app
if __name__ == "__main__":
    app.run_server(debug=True)
