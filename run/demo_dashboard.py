# Dashboard for a demo of the generation of discharge letters
import logging
import os
from pathlib import Path

import dash
import dash_bootstrap_components as dbc
import pandas as pd
from dash.dependencies import Input, Output, State
from dotenv import load_dotenv
from openai import AzureOpenAI

from discharge_docs.dashboard.dashboard_layout import get_demo_layout
from discharge_docs.dashboard.helper import format_generated_doc
from discharge_docs.processing.processing import get_patient_file
from discharge_docs.prompts.prompt import load_prompts
from discharge_docs.prompts.prompt_builder import PromptBuilder

logger = logging.getLogger(__name__)

load_dotenv()
TEMPERATURE = 0.2

client = AzureOpenAI(
    api_version="2024-02-01",
    api_key=os.getenv("AZURE_OPENAI_KEY"),
    azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT", ""),
)
deployment_name = "aiva-gpt4"

data_folder = Path(__file__).parents[1] / "data" / "examples"

patient_file = pd.read_csv(data_folder / "DEMO_patient_1.csv", sep=";")

user_prompt, system_prompt = load_prompts()

app = dash.Dash(__name__, external_stylesheets=[dbc.themes.BOOTSTRAP])
application = app.server

app.layout = get_demo_layout()


@app.callback(
    Output("patient_admission_dropdown", "options"),
    Output("patient_admission_dropdown", "value"),
    Output("show_prompt_button", "style"),
    Input("navbar", "children"),
)
def load_patient_selection_dropdown(_) -> tuple[list[str], str, dict]:
    """Adds the demo patient to the dropdown menu"""
    return ["Demo Patient"], "Demo Patient", {"display": "none"}


@app.callback(
    Output("patient_file", "value"),
    Output("template_prompt_field", "value"),
    Input("patient_admission_dropdown", "value"),
)
def load_patient_file(patient: str) -> tuple[str, str]:
    """Loads the patient file and template prompt for the selected patient

    Parameters
    ----------
    patient : str
        The selected patient, currently only "Demo Patient"

    Returns
    -------
    tuple[str, str]
        The patient file and template prompt
    """
    _, patient_data = get_patient_file(patient_file)
    if patient != "Demo Patient":
        raise ValueError("Only 'Demo Patient' is supported")
    output_div = [
        f"{row['description']} - {row['date']}\n{row['value']}"
        for _, row in patient_data.iterrows()
    ]

    template_prompt = (
        "Schrijf een ontslagbrief aan de hand van de volgende categoriën: "
        "respiratie, cardiologie, neurologie en infectie. Onder elk kopje wil ik een "
        "chonologisch beloop van de opname inclusief complicaties en beleid."
    )

    return "\n\n".join(output_div), template_prompt


@app.callback(
    Output("output_GPT_discharge_documentation", "children"),
    State("template_prompt_field", "value"),
    State("patient_file", "value"),
    Input("update_discharge_button", "n_clicks"),
    prevent_initial_call=True,
)
def generate_discharge_letter(
    template_prompt: str, patient_file: str, n_clicks: int
) -> str:
    """Generates a discharge letter for the selected patient

    Parameters
    ----------
    template_prompt : str
        The template prompt for the discharge letter
    patient_file : str
        The patient file from the text area
    n_clicks : int
        The number of times the button has been clicked

    Returns
    -------
    str
        The generated discharge letter
    """
    prompt_builder = PromptBuilder(
        temperature=TEMPERATURE, deployment_name=deployment_name, client=client
    )
    user_prompt, system_prompt = load_prompts()
    discharge_letter = prompt_builder.generate_discharge_doc(
        patient_file=patient_file,
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        template_prompt=template_prompt,
    )
    generated_doc = discharge_letter
    generated_output = format_generated_doc(generated_doc, format_type="markdown")
    return generated_output


if __name__ == "__main__":
    app.run_server(debug=True, port=8153)
