import logging
import os
import time
from pathlib import Path

import dash
import dash_bootstrap_components as dbc
import pandas as pd
from dash import dcc, html
from dash.dependencies import Input, Output
from dotenv import load_dotenv
from openai import AzureOpenAI

from discharge_docs.dashboard.helper import (
    get_data_from_patient_admission,
    highlight,
)
from discharge_docs.processing.processing import (
    get_patient_file,
)
from discharge_docs.prompts.prompt import (
    load_prompts,
    load_template_prompt,
)
from discharge_docs.prompts.prompt_builder import PromptBuilder

logger = logging.getLogger(__name__)

# define whether the dashboard is rigged or not
RIGGED = False


# initialise Azure
load_dotenv()
TEMPERATURE = 0.2
ITERATIVE = False

client = AzureOpenAI(
    api_version="2024-02-01",
    api_key=os.getenv("AZURE_OPENAI_KEY"),
    azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT", ""),
)
deployment_name = "aiva-gpt4"

# add demo patient
patient_1_demo = pd.read_csv(
    Path(__file__).parents[1] / "data" / "processed" / "DEMO_patient_1_eng.csv", sep=";"
)
patient_1_demo["date"] = pd.to_datetime(patient_1_demo["date"])
demo_item = [
    {"label": "Demo patient 1 (10 day admission)", "value": "patient_1_demo"},
]
data_dict = {"patient_1_demo": patient_1_demo}

logger.info("data loaded")

# load prompts
user_prompt, system_prompt = load_prompts()
template_prompt_NICU = load_template_prompt("NICU")

# define the app
app = dash.Dash(
    __name__,
    external_stylesheets=[dbc.themes.BOOTSTRAP],
)
application = app.server  # Neccessary for debugging in vscode, no further use

# Define the layout of the app
navbar = dbc.NavbarSimple(
    children=[],
    brand=[
        html.Img(
            src="https://www.umcutrecht.nl/images/logo-umcu.svg", className="mb-2"
        ),
        "DEMO discharge letter generator",
    ],
    color="#1191fa",
    dark=True,
    id="navbar",
)

patient_selection_div = dbc.Row(
    [
        dbc.Col(
            [
                dbc.Label("Select patient: "),
                dbc.Select(
                    id="patient_admission_dropdown",
                    options=demo_item,
                    value=demo_item[0].get("value"),
                    class_name="me-2",
                ),
            ],
            width=4,
        ),
    ],
)

patient_file_tab = dbc.Card(
    [
        dbc.CardBody(
            [
                html.H2("Patient file"),
                html.Br(),
                dbc.Row(
                    [
                        dbc.Col(
                            dbc.Input(
                                id="search_bar",
                                type="text",
                                placeholder="Search in patient file...",
                                class_name="mb-2",
                            ),
                        ),
                        dbc.Col(
                            dcc.Dropdown(
                                id="sorting_dropdown",
                                options=[
                                    {
                                        "label": "Sort by date",
                                        "value": "sort_by_date",
                                    },
                                    {
                                        "label": "Sort by type",
                                        "value": "sort_by_code",
                                    },
                                ],
                                value="sort_by_date",
                            ),
                        ),
                    ]
                ),
                html.Br(),
                html.Div(
                    ["Placeholder for patient file"],
                    id="output_value",
                    className="bg-light",
                ),
            ]
        ),
    ]
)

original_discharge_docu_tab = dbc.Card(
    dbc.CardBody(
        dcc.Markdown(
            ["Placeholder for original discharge letter"],
            id="output_original_discharge_documentation",
            className="bg-light",
        )
    ),
)


generate_docs_tab = dbc.Card(
    dbc.CardBody(
        [
            dbc.Button(
                "Generate discharge letter",
                id="update_discharge_button",
                color="primary",
                class_name="mt-2 me-2",
            ),
            dbc.Card(
                [
                    dbc.CardHeader(html.H3("Generated discharge letter:")),
                    dbc.CardBody(
                        [
                            dbc.Spinner(
                                html.Div(
                                    [""],
                                    id="output_GPT_discharge_documentation",
                                ),
                            )
                        ]
                    ),
                ],
                className="mt-2",
            ),
        ],
    ),
)

generate_docs_tab_RIGGED = dbc.Card(
    dbc.CardBody(
        [
            dbc.Button(
                "Generate discharge letter",
                id="update_discharge_button",
                color="primary",
                class_name="mt-2 me-2",
            ),
            dbc.Card(
                [
                    dbc.CardHeader(html.H3("Generated discharge letter:")),
                    dbc.CardBody(
                        [
                            dbc.Spinner(
                                dcc.Markdown(
                                    [""],
                                    id="output_GPT_discharge_documentation",
                                    className="bg-light",
                                )
                            )
                        ]
                    ),
                ],
                className="mt-2",
            ),
        ],
    ),
)

view_docs4_tab = dbc.Card(
    dbc.CardBody(
        dcc.Markdown(
            ["Placeholder for stored AI-discharge letter"],
            id="output_stored_generated_discharge_documentation4",
            className="bg-light",
        )
    )
)

if not RIGGED:
    layout = html.Div(
        children=[
            navbar,
            patient_selection_div,
            dbc.Row(
                children=[
                    dbc.Col(
                        dbc.Tabs(
                            [
                                dbc.Tab(patient_file_tab, label="Patient file"),
                                dbc.Tab(
                                    original_discharge_docu_tab,
                                    label="Physician's discharge letter",
                                ),
                            ],
                            class_name="mt-2",
                        ),
                        width=6,
                    ),
                    dbc.Col(
                        [
                            dbc.Tabs(
                                [
                                    dbc.Tab(
                                        generate_docs_tab,
                                        label="Generate discharge letter",
                                        tab_id="generate_docs_tab",
                                    ),
                                    dbc.Tab(
                                        view_docs4_tab,
                                        label="View saved discharge letter",
                                        tab_id="view_docs4_tab",
                                    ),
                                ],
                                class_name="mt-2",
                                active_tab="generate_docs_tab",
                            ),
                        ],
                        width=6,
                    ),
                ],
            ),
        ]
    )
else:
    layout = html.Div(
        children=[
            navbar,
            patient_selection_div,
            dbc.Row(
                children=[
                    dbc.Col(
                        dbc.Tabs(
                            [
                                dbc.Tab(patient_file_tab, label="Patient file"),
                                dbc.Tab(
                                    original_discharge_docu_tab,
                                    label="Physician's discharge letter",
                                ),
                            ],
                            class_name="mt-2",
                        ),
                        width=6,
                    ),
                    dbc.Col(
                        [
                            generate_docs_tab_RIGGED,
                        ],
                        width=6,
                    ),
                ],
            ),
        ]
    )

app.layout = layout


@app.callback(
    Output("output_value", "children"),
    [
        Input("patient_admission_dropdown", "value"),
        Input("sorting_dropdown", "value"),
        Input("search_bar", "value"),
    ],
)
def display_value(
    selected_patient_admission: str,
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
    if selected_patient_admission is None:
        return [""]

    patient_file = data_dict[selected_patient_admission]

    patient_file = patient_file[patient_file["description"] != "Ontslagbrief"]

    patient_file = patient_file[patient_file["description"] != "AI-Ontslagbrief"]

    if sort_dropdown_choice == "sort_by_date":
        patient_file = patient_file.sort_values(by=["date", "description"])
    elif sort_dropdown_choice == "sort_by_code":
        patient_file = patient_file.sort_values(by=["description", "date"])

    if patient_file.empty:
        return ["No data for this patient"]
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
            lines = patient_file.loc[index, "value"].split("\n")
            for line in lines:
                returnable.append(line)
                returnable.append(html.Br())

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

    patient_file = data_dict[selected_patient_admission]

    discharge_documentation = patient_file.loc[
        patient_file["description"] == "Ontslagbrief", "value"
    ]

    return discharge_documentation


if not RIGGED:

    @app.callback(
        Output("output_stored_generated_discharge_documentation4", "children"),
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
            - The discharge docs for the selected patient admission from discharge35
            - The discharge docs for the selected patient admission from discharge4
        """
        if selected_patient_admission is None:
            return ""

        patient_file = data_dict[selected_patient_admission]

        discharge_documentation = patient_file.loc[
            patient_file["description"] == "AI-Ontslagbrief", "value"
        ]
        return discharge_documentation


@app.callback(
    Output("output_GPT_discharge_documentation", "children"),
    Input("update_discharge_button", "n_clicks"),
    Input("patient_admission_dropdown", "value"),
)
def display_generated_discharge_doc(
    n_clicks: int,
    selected_patient_admission: str,
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
    if not RIGGED:
        patient_data = get_data_from_patient_admission(
            selected_patient_admission, data_dict
        )

        prompt_builder = PromptBuilder(
            temperature=TEMPERATURE, deployment_name=deployment_name, client=client
        )

        patient_file_string, _ = get_patient_file(patient_data)
        discharge_letter = prompt_builder.generate_discharge_doc(
            patient_file=patient_file_string,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            template_prompt=template_prompt_NICU,
        )
        generated_doc = discharge_letter

        generated_output = []
        for category_pair in generated_doc:
            generated_output.append(
                html.Div(
                    [
                        html.Strong(category_pair["Categorie"]),
                        dcc.Markdown(category_pair["Beloop tijdens opname"]),
                    ]
                )
            )
        return generated_output
    else:
        time.sleep(14)
        patient_file = data_dict[selected_patient_admission]

        discharge_documentation = patient_file.loc[
            patient_file["description"] == "AI-Ontslagbrief", "value"
        ]
        return discharge_documentation


# Run the app
if __name__ == "__main__":
    app.run_server(debug=True, port=8050)
