import dash_bootstrap_components as dbc
from dash import dcc, html


def get_layout() -> html.Div:
    """
    Returns the layout for the evaluation dashboard.

    Parameters
    ----------
    user_prompt : str
        The user prompt for generating the discharge documentation.
    system_prompt : str
        The system prompt for generating the discharge documentation.

    Returns
    -------
    html.Div
        The layout for the discharge documentation dashboard.
    """
    navbar = dbc.NavbarSimple(
        children=[],
        brand=[
            html.Img(
                src="https://www.umcutrecht.nl/images/logo-umcu.svg", className="mb-2"
            ),
            "Ontslagbrief evaluatie - Fase 1",
        ],
        color="#1191fa",
        dark=True,
        id="navbar",
    )

    patient_selection_div = dbc.Row(
        [
            dbc.Col(
                [
                    dbc.Label("Selecteer patiëntopname:"),
                    dbc.Select(id="patient_admission_dropdown", class_name="me-2"),
                ],
                width=4,
            ),
        ],
    )

    patient_file_tab = dbc.Card(
        [
            dbc.CardBody(
                [
                    html.H2("Patiëntendossier:"),
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

    view_letter_div = dbc.Card(
        [
            dbc.CardHeader(html.H3("Bekijk ontslagbrief")),
            dbc.CardBody(
                [
                    dcc.Textarea(
                        value="Placeholder for original discharge letter",
                        id="output_discharge_documentation",
                        readOnly=True,
                        style={
                            "width": "100%",
                            "whiteSpace": "pre-line",
                            "overflow": "hidden",  # To hide the scrollbar
                        },
                    ),
                    dcc.Interval(  # To update the textarea
                        id="interval", interval=1000, n_intervals=0
                    ),
                    dbc.Button(
                        "Volgende",
                        id="next_button",
                        n_clicks=0,
                        class_name="mt-2",
                    ),
                ]
            ),
        ]
    )

    original_discharge_docs_tab = dbc.Card(
        dbc.CardBody(
            [
                dcc.Textarea(
                    value="Placeholder for original discharge letter",
                    id="output_original_discharge_documentation",
                    readOnly=True,
                    style={
                        "width": "100%",
                        "whiteSpace": "pre-line",
                        "height": "1000px",
                    },
                ),
                dbc.Button(
                    "Sla gemarkeerde halucinaties op", id="save_hall-button", n_clicks=0
                ),
                dbc.Button(
                    "Sla gemarkeerde triviale informatie op",
                    id="save_trivial-button",
                    n_clicks=0,
                ),
                dcc.Input(
                    id="hidden-input_trivial", type="text", style={"display": "none"}
                ),
                dcc.Input(
                    id="hidden-input_hall", type="text", style={"display": "none"}
                ),
                html.Div(
                    id="output-container_hall",
                    children="",
                ),
                html.Div(
                    id="output-container_trivial",
                    children="",
                ),
            ]
        ),
    )

    generated_discharge_docs_tab = dbc.Card(
        dbc.CardBody(
            html.Div(
                ["Placeholder for generated discharge letter"],
                id="output_generated_discharge_documentation",
                className="bg-light",
            )
        ),
    )

    eval_div = dbc.Card(
        [
            dbc.CardHeader(html.H3("Evaluatie")),
            dbc.CardBody(
                [
                    html.H5("Geef scores aan de ontslagbriefbrief:"),
                    html.Label('Vraag 1 hier: "Hoe duidelijk is de brief?"'),
                    dcc.Slider(
                        id="likert_slider",
                        min=1,
                        max=5,
                        step=1,
                        marks={
                            1: {
                                "label": "Strongly\nDisagree",
                                "style": {"white-space": "pre-line"},
                            },
                            2: {"label": "Disagree"},
                            3: {"label": "Neutral"},
                            4: {"label": "Agree"},
                            5: {
                                "label": "Strongly\nAgree",
                                "style": {"white-space": "pre-line"},
                            },
                        },
                        value=3,
                    ),
                    html.Br(),
                    html.H5("Opmerkingen"),
                    dbc.Label("Voeg hier nog overige opmerkingen toe:"),
                    dbc.Textarea(
                        id="evaluation_text",
                        value="",
                    ),
                    dbc.Button(
                        "Sla evaluatie op",
                        id="evaluate_button",
                        color="primary",
                        class_name="mt-2",
                    ),
                    dbc.Label("", id="evaluation_saved_label"),
                ]
            ),
        ],
        class_name="mt-2",
    )

    layout = html.Div(
        children=[
            navbar,
            patient_selection_div,
            dbc.Row(
                children=[
                    dbc.Col(
                        dbc.Tabs(
                            [
                                dbc.Tab(patient_file_tab, label="Patiëntendossier"),
                                dbc.Tab(
                                    original_discharge_docs_tab,
                                    label="Originele brief",
                                ),
                                dbc.Tab(
                                    generated_discharge_docs_tab,
                                    label="Gegenereerde brief",
                                ),
                            ],
                            class_name="mt-2",
                        ),
                        width=6,
                    ),
                    dbc.Col(
                        [
                            view_letter_div,
                            eval_div,
                        ],
                        width=6,
                    ),
                ],
            ),
        ]
    )
    return layout
