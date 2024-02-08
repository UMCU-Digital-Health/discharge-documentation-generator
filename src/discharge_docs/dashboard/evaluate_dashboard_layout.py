import numpy as np
import pandas as pd
from dash import dcc, html

colors = {
    "white": "#FFFFFF",
    "umcu_blue": "#1191fa",
    "umcu_dark_blue": "#004285",
    "umcu_light_blue": "#e0f2ff",
    "umcu_orange": "#fc6039",
    "umcu_light_orange": "#fdbfaf",
    "black": "#000000",
}


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
            html.H1(
                "Bekijk een patiëntendossier en evalueer de ontslagbrief",
                style={
                    "color": colors["white"],
                    "backgroundColor": colors["umcu_blue"],
                    "borderRadius": "15px",
                    "text-indent": "20px",
                    "padding": "20px",
                    "text-align": "center",
                },
            ),
            html.H3("Selecteer patiënt opname:"),
            html.Div(
                [
                    dcc.Dropdown(
                        id="patient_admission_dropdown",
                        options=[
                            {
                                "label": "Patient 1 (NICU: 6 dagen)",
                                "value": "patient_1_nicu",
                            },
                        ],
                        value="patient_1_nicu",
                        style={"width": "100%"},
                    ),
                ],
            ),
        ],
        style={
            "padding": "10px",
        },
    )
    patient_file_tab = dcc.Tab(
        label="Patiënt dossier",
        children=[
            html.H3("Selecteer deel van het patiëntendossier"),
            html.Label(html.B("Welke datum wil je bekijken?")),
            html.Div(
                [
                    html.Button(
                        "Vorige",
                        id="previous_date_button",
                        style={
                            "width": "30%",
                            "margin-right": "10px",
                            "border-radius": "10px",
                        },
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
                        "Volgende",
                        id="next_date_button",
                        style={
                            "width": "30%",
                            "margin-left": "10px",
                            "border-radius": "10px",
                        },
                    ),
                ],
                style={
                    "display": "flex",
                },
            ),
            dcc.Checklist(
                id="date_checklist",
                options=["Bekijk de data van de gehele opname (alle datums)"],
                value=[],
            ),
            html.Br(),
            html.Label(
                html.B(
                    "Selecteer welke delen van het patiëntendossier je wilt bekijken:"
                )
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
                        style={
                            "margin-right": "5px",
                            "border-radius": "10px",
                        },
                    ),
                    html.Button(
                        "Deselecteer alle opties",
                        id="deselect_all_button",
                        style={
                            "margin-left": "5px",
                            "border-radius": "10px",
                        },
                    ),
                ],
                style={"flex-direction": "row", "display": "flex"},
            ),
            html.Br(),
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
                style={
                    "width": "50%",
                    # align to thr right border
                    "float": "right",
                },
            ),
            html.Br(),
            html.Div(
                ["Placeholder for patient file"],
                id="output_value",
                style={
                    "width": "100%",
                    "padding": "10px",
                    "border-radius": "10px",
                    "background-color": "whitesmoke",
                },
            ),
        ],
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
                style={
                    "width": "100%",
                    "padding": "10px",
                    "border-radius": "10px",
                    "background-color": "whitesmoke",
                },
            ),
        ],
    )

    GPT_div = html.Div(
        children=[
            html.Div(
                [
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
                    dcc.Input(
                        id="addition_prompt", type="text", style={"width": "100%"}
                    ),
                    html.Br(),
                    html.Button(
                        "Update en genereer onstlagbrief",
                        id="update_discharge_button",
                        style={
                            "height": "50px",
                            "border-radius": "10px",
                            "background-color": colors["umcu_orange"],
                            "border": f"1px solid {colors['umcu_orange']}",
                            "padding": "10px",
                        },
                    ),
                    html.Label(
                        "Klik op de knop hierboven om een ontslagbrief te genereren!"
                    ),
                ],
                style={
                    "background-color": colors["umcu_light_orange"],
                    "border-radius": "10px",
                    "padding": "10px",
                },
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
    )

    eval_div = html.Div(
        children=[
            html.H2("Evaluatie"),
            html.H5("Geef een score aan de ontslagbrief:"),
            html.Label("1 is het minst goed, 10 is het best."),
            dcc.Slider(
                id="evaluation_slider",
                min=1,
                max=10,
                step=1,
                value=6,
            ),
            html.H5("Opmerkingen:"),
            dcc.Textarea(
                id="evaluation_text",
                value="",
                style={"width": "100%"},
            ),
            html.Button(
                "Sla evaluatie op",
                id="evaluate_button",
                style={
                    "height": "50px",
                    "border-radius": "10px",
                    "background-color": "#5484B3",
                    "border": f"1px solid {'#5484B3'}",
                    "padding": "10px",
                },
            ),
            html.Br(),
            html.Label("", id="evaluation_saved_label"),
        ],
        style={
            "background-color": colors["umcu_light_blue"],
            "border-radius": "10px",
            "padding": "10px",
        },
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
        ],
        style={
            "background-color": "lightgrey",
            "border-radius": "10px",
            "padding": "10px",
        },
    )

    layout = html.Div(
        children=[
            patient_selection_div,
            html.Div(
                children=[
                    html.Div(
                        dcc.Tabs(
                            [
                                original_dischare_docu_tab,
                                patient_file_tab,
                            ],
                            style={
                                "display": "flex",
                                "flex-direction": "row",
                                "width": "100%",
                            },
                        ),
                        style={"width": "50%", "padding": "10px"},
                    ),
                    html.Div(
                        [GPT_div, eval_div],
                        style={"width": "50%"},
                    ),
                ],
                style={"display": "flex", "flex-direction": "row"},
            ),
            html.Div(style={"border": "1px solid black", "margin": "10px 0"}),
            show_prompts_div,
        ]
    )
    return layout
