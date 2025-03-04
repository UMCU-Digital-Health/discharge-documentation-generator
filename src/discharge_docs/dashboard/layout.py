import dash_bootstrap_components as dbc
from dash import dcc, html


def get_navbar(view_user: bool, header_title: str) -> dbc.NavbarSimple:
    """Create and return a Bootstrap navbar.

    Parameters
    ----------
    view_user : bool
        Whether to display the logged in user information.
    header_title : str
        The title to display in the navbar.

    Returns
    -------
    dbc.NavbarSimple
        The created navbar.
    """
    navbar = dbc.NavbarSimple(
        children=[
            dbc.NavItem(html.Div(id="logged_in_user", className="text-white me-5"))
            if view_user
            else None,
        ],
        brand=[
            html.Img(
                src="https://www.umcutrecht.nl/images/logo-umcu.svg", className="mb-2"
            ),
            header_title,
        ],
        color="#1191fa",
        dark=True,
        id="navbar",
    )
    return navbar


def get_patient_selection_div(add_discharge_selection: bool = False) -> dbc.Row:
    """Create and return a Bootstrap card for patient selection.

    Parameters
    ----------
    add_discharge_selection : bool, optional
        Flag indicating whether to include discharge selection dropdown,
        by default False

    Returns
    -------
    dbc.Row
        The created row containing a patient selection dropdown and optionally a
        discharge selection dropdown.
    """
    if add_discharge_selection:
        discharge_selection = dbc.Col(
            [
                dbc.Label(
                    "Selecteer ontslagbrief:",
                    className="my-2",
                ),
                dbc.Select(
                    id="selected_letter_dropdown",
                    class_name="my-2",
                    value="ORG letter",
                    options=[
                        {"label": "Originele ontslagbrief", "value": "ORG letter"},
                        {
                            "label": "Gegenereerde ontslagbrief",
                            "value": "GPT letter",
                        },
                    ],
                ),
            ],
            width=4,
        )
    else:
        discharge_selection = None

    patient_selection_div = dbc.Row(
        [
            dbc.Col(
                [
                    dbc.Label("Selecteer patiëntopname:", className="my-2"),
                    dbc.Select(
                        id="patient_admission_dropdown",
                    ),
                ],
                class_name="m-2",
                width=4,
            ),
            discharge_selection,
        ],
    )
    return patient_selection_div


def get_patient_data_card(
    type_view: str, date_and_section_selection: bool = True
) -> dbc.Card:
    """Create and return a Bootstrap card for patient data.

    Parameters
    ----------
    type_view : str
        The type of view for the patient data; either "order and searchable" or
        "markings". 'order and searchable' includes the nice formatting and ordering
        and filtering options. 'markings' includes the ability to mark missings as used
        in the pre-pilot evaluation
    date_and_section_selection : bool, optional
        Flag indicating whether to include date and section selection, by default True.
        Not used in markings as all patient data is displayed and no filtering is used.

    Returns
    -------
    dbc.Card
        The created card.
    """
    if type_view == "order and searchable":
        patient_file_card = dbc.Card(
            [
                dbc.CardHeader(
                    [
                        html.H2("Patiëntendossier:"),
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
                )
                if date_and_section_selection
                else None,
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
    elif type_view == "markings":
        patient_file_card = dbc.Card(
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
                        style={"margin-top": "10px"},
                    ),
                    dcc.Input(
                        id="hidden-input_missings",
                        type="text",
                        style={"display": "none", "margin-top": "10px"},
                    ),
                    html.Div(
                        id="output-container_missings",
                        children="Nog geen missings gemarkeerd.",
                        style={"margin-top": "10px"},
                    ),
                    dbc.Row(
                        [
                            dbc.Col(
                                dbc.Button(
                                    "Verwijder missings",
                                    id="remove_missings_button",
                                    n_clicks=0,
                                    class_name="mt-2",
                                    color="secondary",
                                ),
                                width="auto",
                            ),
                            dbc.Col(
                                html.Div(
                                    style={"width": "15px"}
                                ),  # This div acts as the horizontal spacer
                                width="auto",
                            ),
                            dbc.Col(
                                dcc.Input(
                                    id="missings_remove_index",
                                    type="number",
                                    min=0,
                                    style={"margin-top": "10px"},
                                ),
                                width="auto",
                            ),
                        ],
                        align="center",
                    ),
                ]
            )
        )
    return patient_file_card


def get_discharge_doc_card(
    placeholder_text: str, id: str, markdown_or_div: str
) -> dbc.Card:
    """Create and return a Bootstrap card with functionality to show the discharge
    documentation.

    Parameters
    ----------
    placeholder_text : str
        The text to display in the card.
    id : str
        The id of the card.
    markdown_or_div : str
        The type of content to display in the card; either "markdown" or "div".

    Returns
    -------
    dbc.Card
        The created card.
    """
    discharge_doc_card = dbc.Card(
        dbc.CardBody(
            dcc.Markdown(
                [placeholder_text],
                id=id,
                className="bg-light",
            )
            if markdown_or_div == "markdown"
            else html.Div(  # markdown_or_div == "div"
                [placeholder_text],
                id=id,
                className="bg-light",
            )
        ),
    )
    return discharge_doc_card


def get_GPT_card() -> dbc.Card:
    """Create and return a Bootstrap card with functionality to generate discharge
    documentation using GPT and adapt the department prompt.

    Returns
    -------
    dbc.Card
        The created card.
    """
    GPT_card = dbc.Card(
        dbc.CardBody(
            children=[
                dbc.Card(
                    [
                        dbc.CardHeader(html.H3("GPT instellingen:")),
                        dbc.CardBody(
                            [
                                html.H5("Afdeling prompt:"),
                                dbc.Label(
                                    """Hierin wordt de afdeling specifieke vraag gesteld
                                 . De huidige versie is vooringevuld. Pas deze aan om
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
                                    "Het kan zijn dat de gegenereerde ontslagbrief soms"
                                    " niet goed laadt. Probeer het dan opnieuw door "
                                    "nog een keer op de knop te drukken."
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
        ),
    )
    return GPT_card


def get_random_letter_with_markings_card() -> dbc.Card:
    """card to view a random letter with the ability to mark in the letter
    hallucinations and trivial informatio. Including the functionality to remove the
    markings

    Returns
    -------
    dbc.Card
        The card containing the layout for the dashboard.
    """
    view_letter_card = dbc.Card(
        [
            dbc.CardHeader(html.H3("Bekijk ontslagbrief")),
            dbc.CardBody(
                [
                    dbc.Button(
                        "Volgende ontslagbrief",
                        id="next_button",
                        n_clicks=0,
                        class_name="mt-2",
                        color="warning",
                    ),
                    html.Br(),
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
                    dbc.Row(
                        [
                            dbc.Col(
                                dbc.Button(
                                    "Verwijder hallunicatie",
                                    id="remove_hall_button",
                                    n_clicks=0,
                                    class_name="mt-2",
                                    color="secondary",
                                ),
                                width="auto",
                            ),
                            dbc.Col(
                                html.Div(
                                    style={"width": "15px"}
                                ),  # This div acts as the horizontal spacer
                                width="auto",
                            ),
                            dbc.Col(
                                dcc.Input(
                                    id="hall_remove_index",
                                    type="number",
                                    min=0,
                                    style={"margin-top": "10px"},
                                ),
                                width="auto",
                            ),
                        ],
                        align="center",
                    ),
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
                    dbc.Row(
                        [
                            dbc.Col(
                                dbc.Button(
                                    "Verwijder triviale informatie",
                                    id="remove_trivial_button",
                                    n_clicks=0,
                                    class_name="mt-2",
                                    color="secondary",
                                ),
                                width="auto",
                            ),
                            dbc.Col(
                                html.Div(
                                    style={"width": "15px"}
                                ),  # This div acts as the horizontal spacer
                                width="auto",
                            ),
                            dbc.Col(
                                dcc.Input(
                                    id="trivial_remove_index",
                                    type="number",
                                    min=0,
                                    style={"margin-top": "10px"},
                                ),
                                width="auto",
                            ),
                        ],
                        align="center",
                    ),
                ]
            ),
        ]
    )
    return view_letter_card


def get_layout_evaluation_dashboard(system_prompt: str, user_prompt: str) -> html.Div:
    navbar = get_navbar(view_user=True, header_title="Ontslagbrief evaluatie")

    patient_selection_div = get_patient_selection_div()

    patient_file_card = get_patient_data_card(
        type_view="order and searchable", date_and_section_selection=True
    )

    original_discharge_docu_card = get_discharge_doc_card(
        placeholder_text="Placeholder for original discharge letter",
        id="output_original_discharge_documentation",
        markdown_or_div="markdown",
    )

    GPT_card = get_GPT_card()

    view_docs_new_card = get_discharge_doc_card(
        "Placeholder for newer GPT discharge letter",
        "output_stored_generated_discharge_documentation_new",
        "div",
    )

    view_docs_old_card = get_discharge_doc_card(
        "Placeholder for older GPT discharge letter",
        "output_stored_generated_discharge_documentation_old",
        "div",
    )

    show_prompts_card = dbc.Offcanvas(
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
                    html.H5("Afdeling prompt"),
                    html.P("Laden...", id="template_prompt_space"),
                ]
            ),
        ],
        id="offcanvas",
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
                                    original_discharge_docu_card,
                                    label="Originele ontslagbrief",
                                ),
                                dbc.Tab(patient_file_card, label="Patiëntendossier"),
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
                                        GPT_card,
                                        label="Genereer zelf ontslagbrieven",
                                        tab_id="generate_docs_tab",
                                    ),
                                    dbc.Tab(
                                        view_docs_old_card,
                                        label="Opgeslagen GPT brieven (Oude versie)",
                                        tab_id="view_docs_old_tab",
                                    ),
                                    dbc.Tab(
                                        view_docs_new_card,
                                        label="Opgeslagen GPT brieven (Nieuwe versie)",
                                        tab_id="view_docs_tab",
                                    ),
                                ],
                                class_name="mt-2",
                                active_tab="view_docs_tab",
                            ),
                        ],
                        width=6,
                    ),
                ],
            ),
            show_prompts_card,
        ]
    )
    return layout


def get_demo_layout() -> html.Div:
    navbar = get_navbar(view_user=False, header_title="AI-ontslagbrief Generator Demo")

    patient_selection_div = get_patient_selection_div(add_discharge_selection=False)
    gpt_card = get_GPT_card()

    patient_file_card = dbc.Card(
        [
            dbc.CardHeader(html.H2("Patiënt dossier:")),
            dbc.CardBody(
                dcc.Textarea(
                    id="patient_file",
                    readOnly=False,
                    style={
                        "width": "100%",
                        "height": "600px",
                    },
                )
            ),
        ]
    )

    layout = html.Div(
        [
            navbar,
            patient_selection_div,
            dbc.Row(
                [
                    dbc.Col(patient_file_card, width=6),
                    dbc.Col(gpt_card, width=6),
                ]
            ),
        ]
    )
    return layout
