import numpy as np
import pandas as pd
from dash import dcc, html


def get_layout(
    data: pd.DataFrame, user_prompt: str, system_prompt: str, template_prompt
) -> html.Div:
    """
    Returns the layout for the evaluation dashboard.

    Parameters
    ----------
    data : pd.DataFrame
        The DataFrame containing the data for the dashboard.
    user_prompt : str
        The user prompt for generating the discharge documentation.
    system_prompt : str
        The system prompt for generating the discharge documentation.
    template_prompt : str
        The template prompt for generating the discharge documentation.

    Returns
    -------
    html.Div
        The layout for the discharge documentation dashboard.
    """
    patient_selection_div = html.Div(
        [
            html.H1("Bekijk een patiëntendossier en evalueer de ontslagbrief"),
            html.H3("Selecteer patiënt opname:"),
            html.Div(
                [
                    dcc.Dropdown(
                        id="patient_admission_dropdown",
                        options=[
                            {
                                "label": "Patient 1 (NICU)",
                                "value": "patient_1_nicu",
                            },
                        ],
                        value="patient_1_nicu",
                        style={"width": "100%"},
                    ),
                ],
            ),
        ]
    )
    patient_file_tab = dcc.Tab(
        label="Patiënt dossier",
        children=[
            html.Div(id="Encounter_info_div"),
            html.H3("Selecteer datums die je wilt bekijken:"),
            html.Div(
                [
                    html.Button(
                        "Previous",
                        id="previous_date_button",
                        style={"width": "30%"},
                    ),
                    dcc.Dropdown(
                        id="date_dropdown",
                        options=[
                            {
                                "label": date.date(),
                                "value": date,
                            }
                            for date in data.date.unique()
                        ],
                        value=data.date.unique()[0],
                        style={"width": "100%"},
                    ),
                    html.Button(
                        "Next",
                        id="next_date_button",
                        style={"width": "30%"},
                    ),
                ],
                style={
                    "display": "flex",
                    "width": "40%",
                },
            ),
            dcc.Checklist(
                id="date_checklist",
                options=["Bekijk de data van de gehele opname (alle datums)"],
                value=[],
            ),
            html.H3(
                "Selecteer welke delen van het patiëntendossier " + "je wilt bekijken:"
            ),
            dcc.Dropdown(
                id="description_dropdown",
                options=np.sort(data.description.unique()),
                value=[],  # np.sort(data.description.unique()),
                multi=True,
                style={"width": "100%"},
            ),
            html.Div(
                [
                    html.Button(
                        "Selecteer alle opties",
                        id="select_all_button",
                    ),
                    html.Button(
                        "Deselecteer alle opties",
                        id="deselect_all_button",
                    ),
                ],
                style={"width": "40%"},
            ),
            html.Div(
                [
                    html.H2("Patiëntendossier:"),
                    dcc.Dropdown(
                        id="sorting_dropdown",
                        options=[
                            {
                                "label": "Sort by date",
                                "value": "sort_by_date",
                            },
                            {
                                "label": "Sort by code",
                                "value": "sort_by_code",
                            },
                        ],
                        value="sort_by_code",
                        style={"width": "50%"},
                    ),
                    html.Br(),
                    html.Div(
                        ["Placeholder for patient file"],
                        id="output_value",
                    ),
                ],
                style={"width": "100%"},
            ),
        ],
        style={
            "width": "100%",
        },
    )

    original_dischare_docu_tab = dcc.Tab(
        label="Originele ontslagbrief",
        children=[
            html.H2(
                "Originele ontslagbrief:",
                style={
                    "width": "100%",
                },
            ),
            dcc.Markdown(
                ["Placeholder for original discharge letter"],
                id="output_original_discharge_documentation",
                style={"width": "100%"},
            ),
        ],
        style={
            "width": "100%",
        },
    )
    GPT_div = html.Div(
        children=[
            html.H3("GPT settings:"),
            html.H5("Temperatuur:"),
            html.Label("0 is het minst creatief, 1 het meest creatief."),
            dcc.Slider(
                id="temperature_slider",
                min=0,
                max=1,
                step=0.1,
                value=0.1,
            ),
            html.H5("Extra instructies:"),
            html.Label(
                "Voer hier extra instructies in die meegegeven "
                + "worden aan GPT (experimenteel):"
            ),
            html.Br(),
            dcc.Input(id="addition_prompt", type="text"),
            html.Br(),
            html.Button(
                "Update Onstlagbrief",
                id="update_discharge_button",
            ),
            html.H2("Gegenereerde ontslagbrief:"),
            dcc.Loading(
                html.Div(
                    ["Placeholder for GPTdischarge letter"],
                    id="output_GPT_discharge_documentation",
                ),
                type="default",
            ),
        ],
        style={"width": "50%"},
    )

    show_prompts_div = html.Details(
        [
            html.Summary("Gebruikte prompt tonen/verbergen"),
            html.Div(
                [
                    html.H5("System prompt"),
                    html.P(system_prompt),
                ]
            ),
            html.Div(
                [
                    html.H5("User prompt"),
                    html.P(user_prompt),
                ]
            ),
            html.Div(
                [
                    html.H5("Template prompt"),
                    html.P(template_prompt),
                ]
            ),
        ]
    )

    layout = html.Div(
        children=[
            patient_selection_div,
            html.Div(
                children=[
                    html.Div(
                        dcc.Tabs(
                            [
                                patient_file_tab,
                                original_dischare_docu_tab,
                            ],
                            style={
                                "display": "flex",
                                "flex-direction": "row",
                                "width": "100%",
                            },
                        ),
                        style={"width": "50%"},
                    ),
                    GPT_div,
                ],
                style={"display": "flex", "flex-direction": "row"},
            ),
            html.Div(style={"border": "1px solid black", "margin": "10px 0"}),
            show_prompts_div,
        ]
    )
    return layout
