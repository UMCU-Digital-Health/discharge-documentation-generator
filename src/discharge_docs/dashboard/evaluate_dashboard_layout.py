import dash_bootstrap_components as dbc
from dash import dcc, html


def get_layout(user_prompt: str, system_prompt: str) -> html.Div:
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
        children=[
            dbc.NavItem(html.Div(id="logged_in_user", className="text-white me-5")),
            dbc.DropdownMenu(
                children=[
                    dbc.DropdownMenuItem("Export db", id="export-db"),
                ],
                nav=True,
                in_navbar=True,
            ),
        ],
        brand=[
            html.Img(
                src="https://www.umcutrecht.nl/images/logo-umcu.svg", className="mb-2"
            ),
            "Ontslagbrief evaluatie",
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
            dbc.CardHeader(
                [
                    dbc.Label("Welke datum wil je bekijken?"),
                    dbc.Row(
                        [
                            dbc.Col(
                                dbc.Button(
                                    "Vorige",
                                    id="previous_date_button",
                                    color="secondary",
                                    outline=True,
                                    className="me-2",
                                ),
                                width=2,
                            ),
                            dbc.Col(
                                dbc.Select(id="date_dropdown", class_name="me-2"),
                                width=8,
                            ),
                            dbc.Col(
                                dbc.Button(
                                    "Volgende",
                                    id="next_date_button",
                                    color="secondary",
                                    outline=True,
                                    className="me-2",
                                ),
                                width=2,
                            ),
                        ]
                    ),
                    dbc.Switch(
                        id="date_checklist",
                        label="Bekijk de data van de gehele opname (alle datums)",
                        value=True,
                    ),
                    html.Br(),
                    dbc.Label("Selecteer patiëntendossier type:"),
                    dcc.Dropdown(
                        id="description_dropdown",
                        options=[],
                        value=[],
                        multi=True,
                    ),
                    html.Div(
                        [
                            dbc.Button(
                                "Selecteer alle opties",
                                id="select_all_button",
                                color="secondary",
                                outline=True,
                                class_name="me-2",
                                size="sm",
                            ),
                            dbc.Button(
                                "Deselecteer alle opties",
                                id="deselect_all_button",
                                color="secondary",
                                outline=True,
                                class_name="me-2",
                                size="sm",
                            ),
                        ]
                    ),
                ]
            ),
            dbc.CardBody(
                [
                    html.H2("Patiëntendossier:"),
                    dbc.Row(
                        [
                            dbc.Col(
                                dbc.Input(
                                    id="search_bar",
                                    type="text",
                                    placeholder="Zoeken...",
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
                                            "label": "Sort by code",
                                            "value": "sort_by_code",
                                        },
                                    ],
                                    value="sort_by_code",
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

    original_dischare_docu_tab = dbc.Card(
        dbc.CardBody(
            dcc.Markdown(
                ["Placeholder for original discharge letter"],
                id="output_original_discharge_documentation",
                className="bg-light",
            )
        ),
    )

    GPT_div = html.Div(
        children=[
            dbc.Card(
                [
                    dbc.CardHeader(html.H3("GPT instellingen:")),
                    dbc.CardBody(
                        [
                            html.H5("Template prompt:"),
                            dbc.Label(
                                """Hierin wordt de afdeling specifieke vraag gesteld.
                                 De huidige versie is vooringevuld. Pas deze aan om
                                 te experimenteren wat wel en niet goed werkt voor jou.
                                 """
                            ),
                            dbc.Textarea(
                                id="template_prompt_field",
                                value="",
                                style={"height": "250px"},
                            ),
                            dbc.Button(
                                "Update en genereer onstlagbrief",
                                id="update_discharge_button",
                                color="primary",
                                class_name="mt-2 me-2",
                            ),
                            dbc.Button(
                                "Laat prompt zien",
                                id="show_prompt_button",
                                color="secondary",
                                class_name="mt-2 me-2",
                                outline=True,
                            ),
                            dbc.Label(
                                "Het kan zijn dat de gegenereerde ontslagbrief soms "
                                + "niet goed laadt. Probeer het dan opnieuw door nog "
                                + "een keer op de knop te drukken."
                            ),
                        ]
                    ),
                ]
            ),
            dbc.Card(
                [
                    dbc.CardHeader(html.H3("Gegenereerde ontslagbrief:")),
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
    )

    eval_div = dbc.Card(
        [
            dbc.CardHeader(html.H3("Evaluatie")),
            dbc.CardBody(
                [
                    html.H5("Geef een score voor de gegenereerde ontslagbrief:"),
                    html.Label("1 is het minst goed, 10 is het best."),
                    dcc.Slider(
                        id="evaluation_slider",
                        min=1,
                        max=10,
                        step=1,
                        value=6,
                    ),
                    html.H5("Opmerkingen"),
                    dbc.Label(
                        "Staat alle informatie erin? Zo nee: staat de informatie"
                        " wel in het dossier? Is de verwoording acceptabel? etc."
                    ),
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

    show_prompts_div = dbc.Offcanvas(
        [
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
                    html.P("Laden...", id="template_prompt_space"),
                ]
            ),
        ],
        id="offcanvas",
        is_open=False,
    )

    # Temporary popup to download all logged metadata
    export_popup = dbc.Modal(
        [
            dbc.ModalTitle(html.H2("Download lokale database")),
            dbc.ModalBody(
                [
                    dcc.Input(type="password", id="export-passwd", className="me-1"),
                    dbc.Button(
                        "Download Logs",
                        id="download-logs-btn",
                        color="primary",
                        class_name="me-1",
                    ),
                    dbc.Alert(
                        "Wachtwoord is fout",
                        id="alert-passwd",
                        is_open=False,
                        color="danger",
                        duration=5000,
                    ),
                ]
            ),
        ],
        id="export-modal",
        size="lg",
        is_open=False,
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
                                dbc.Tab(
                                    original_dischare_docu_tab,
                                    label="Originele ontslagbrief",
                                ),
                                dbc.Tab(patient_file_tab, label="Patiëntendossier"),
                            ],
                            class_name="mt-2",
                        ),
                        width=6,
                    ),
                    dbc.Col(
                        [GPT_div, eval_div],
                        width=6,
                    ),
                ],
            ),
            show_prompts_div,
            export_popup,
            dcc.Download(id="download-db"),
        ]
    )
    return layout
