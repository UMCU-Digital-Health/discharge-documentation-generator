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
                    dcc.Textarea(
                        value="Placeholder for patient file",
                        id="output_value",
                        readOnly=True,
                        style={
                            "width": "100%",
                            "whiteSpace": "pre-line",
                            "height": "700px",
                        },
                    ),
                    html.Br(),
                    dcc.Store(id="missings_store", data=[]),
                    dbc.Button(
                        "Sla gemarkeerde missings op",
                        id="save_missings-button",
                        n_clicks=0,
                    ),
                    dcc.Input(
                        id="hidden-input_missings",
                        type="text",
                        style={"display": "none"},
                    ),
                    html.Div(
                        id="output-container_missings",
                        children="Nog geen missings gemarkeerd.",
                    ),
                    dbc.Button(
                        "Verwijder missings",
                        id="remove_missings_button",
                        n_clicks=0,
                        class_name="mt-2",
                        color="secondary",
                    ),
                    dcc.Input(id="missings_remove_index", type="number", min=0),
                ]
            ),
        ]
    )

    view_letter_div = dbc.Card(
        [
            dbc.CardHeader(html.H3("Bekijk ontslagbrief")),
            dbc.CardBody(
                [
                    dcc.Store(data="", id="letter_shown"),
                    dcc.Textarea(
                        value="Placeholder for original discharge letter",
                        id="output_discharge_documentation",
                        readOnly=True,
                        style={
                            "width": "100%",
                            "whiteSpace": "pre-line",
                            "overflow": "scroll",
                            "height": "600px",
                        },
                    ),
                    dbc.Button(
                        "Volgende ontslagbrief",
                        id="next_button",
                        n_clicks=0,
                        class_name="mt-2",
                        color="warning",
                    ),
                    html.Hr(),
                    dcc.Store(id="hall_store", data=[]),
                    dbc.Button(
                        "Sla gemarkeerde halucinaties/fouten op",
                        id="save_hall-button",
                        n_clicks=0,
                    ),
                    dcc.Input(
                        id="hidden-input_hall", type="text", style={"display": "none"}
                    ),
                    html.Div(
                        id="output-container_hall",
                        children="Nog geen hallucinaties/fouten gemarkeerd.",
                    ),
                    dbc.Button(
                        "Verwijder hallunicatie",
                        id="remove_hall_button",
                        n_clicks=0,
                        class_name="mt-2",
                        color="secondary",
                    ),
                    dcc.Input(id="hall_remove_index", type="number", min=0),
                    html.Hr(),
                    dcc.Store(id="trivial_store", data=[]),
                    dbc.Button(
                        "Sla gemarkeerde triviale informatie op",
                        id="save_trivial-button",
                        n_clicks=0,
                    ),
                    dcc.Input(
                        id="hidden-input_trivial",
                        type="text",
                        style={"display": "none"},
                    ),
                    html.Div(
                        id="output-container_trivial",
                        children="Nog geen triviale informatie gemarkeerd.",
                    ),
                    dbc.Button(
                        "Verwijder triviale informatie",
                        id="remove_trivial_button",
                        n_clicks=0,
                        class_name="mt-2",
                        color="secondary",
                    ),
                    dcc.Input(id="trivial_remove_index", type="number", min=0),
                ]
            ),
        ]
    )

    eval_div = dbc.Card(
        [
            dbc.CardHeader(html.H3("Evaluatie")),
            dbc.CardBody(
                [
                    html.H5("Geef scores aan de ontslagbriefbrief:"),
                    html.Label(
                        "Ben je het eens met de volgende stelling: Deze ontslagbrief "
                        + "is geschikt om te worden ingezet als basis voor een "
                        + "ontslagbrief die met kleine aanpassingen van een arts in "
                        + "de praktijk kan worden gebruikt"
                    ),
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
                        color="danger",
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
                        [
                            patient_file_tab,
                        ],
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
