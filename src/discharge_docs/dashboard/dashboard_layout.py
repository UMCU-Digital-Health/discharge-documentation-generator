import dash_bootstrap_components as dbc
from dash import dcc, html

from discharge_docs.dashboard.helper import generate_annotation_datatable


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


def get_eval_card(
    question_header: str,
    question_explanation: str,
    slider: str,
    notes_explanation: list | str,
) -> dbc.Card:
    """Create and return a Bootstrap card for evaluation questions.

    Parameters
    ----------
    question_header : str
        The header for the evaluation question.
    question_explanation : str
        The explanation for the evaluation question.
    slider : str
        The type of slider to use for the evaluation question.
    notes_explanation : str
        The explanation for the evaluation notes.

    Returns
    -------
    dbc.Card
        The card containing the layout for the evaluation question.
    """
    eval_card = dbc.Card(
        [
            dbc.CardHeader(html.H3("Evaluatie")),
            dbc.CardBody(
                [
                    html.H5(question_header),
                    html.Label(question_explanation),
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
                    )
                    if slider == "likert"
                    else dcc.Slider(
                        id="evaluation_slider",
                        min=1,
                        max=10,
                        step=1,
                        value=6,
                    )
                    if slider == "one_to_ten"
                    else None,
                    html.Br(),
                    html.H5("Opmerkingen"),
                    dbc.Label(notes_explanation),
                    dbc.Textarea(
                        id="evaluation_text",
                        value="",
                    ),
                    dbc.Button(
                        "Sla evaluatie op",
                        id="evaluate_button",
                        color="danger",
                        class_name="mt-2",
                        style={"margin-right": "15px"},
                    ),
                    dbc.Label("", id="evaluation_saved_label"),
                ]
            ),
        ],
        class_name="mt-2",
    )
    return eval_card


def get_layout_pre_release_eval() -> html.Div:
    navbar = get_navbar(view_user=False, header_title="Ontslagbrief evaluatie - Fase 1")

    patient_selection_div = get_patient_selection_div()

    patient_file_card = get_patient_data_card(type_view="markings")

    view_letter_card = get_random_letter_with_markings_card()

    eval_div = get_eval_card(
        question_header="Geef scores aan de ontslagbriefbrief:",
        question_explanation="Ben je het eens met de volgende stelling: Deze "
        + "ontslgbrief is geschikt om te worden ingezet als basis voor een "
        + "ontslagbrief die met kleine aanpassingen van een arts in "
        + "de praktijk kan worden gebruikt",
        slider="likert",
        notes_explanation="Voeg hier nog overige opmerkingen toe:",
    )

    layout = html.Div(
        children=[
            navbar,
            patient_selection_div,
            dbc.Row(
                children=[
                    dbc.Col(
                        [
                            patient_file_card,
                        ],
                        width=6,
                    ),
                    dbc.Col(
                        [
                            view_letter_card,
                            eval_div,
                        ],
                        width=6,
                    ),
                ],
            ),
        ]
    )
    return layout


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

    eval_card = get_eval_card(
        question_header="Geef een score voor de gegenereerde ontslagbrief:",
        question_explanation="1 is het minst goed, 10 is het best.",
        slider="one_to_ten",
        notes_explanation=(
            [
                html.Strong(
                    "Benoem in de opmerkingen of het over de GPT4 brief gaat of"
                    + " over de zelf gegenereerde GPT 3.5 brief."
                ),
                html.Br(),
                " Staat alle informatie erin? Zo nee: staat de informatie"
                + " wel in het dossier? Is de verwoording acceptabel? etc.",
            ]
        ),
    )

    GPT_card = get_GPT_card()

    view_docs4_card = get_discharge_doc_card(
        "Placeholder for GPT4 discharge letter",
        "output_stored_generated_discharge_documentation4",
        "div",
    )

    view_docs35_card = get_discharge_doc_card(
        "Placeholder for GPT3.5 discharge letter",
        "output_stored_generated_discharge_documentation35",
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
                                        view_docs35_card,
                                        label="Opgeslagen GPT3.5 brieven",
                                        tab_id="view_docs3.5_tab",
                                    ),
                                    dbc.Tab(
                                        view_docs4_card,
                                        label="Opgeslagen GPT4 brieven",
                                        tab_id="view_docs4_tab",
                                    ),
                                ],
                                class_name="mt-2",
                                active_tab="view_docs4_tab",
                            ),
                            eval_card,
                        ],
                        width=6,
                    ),
                ],
            ),
            show_prompts_card,
        ]
    )
    return layout


def get_phase_2_layout() -> html.Div:
    navbar = get_navbar(view_user=True, header_title="Ontslagbrief evaluatie - Fase 2")

    patient_selection_div = get_patient_selection_div(add_discharge_selection=True)

    patient_file_tab = dbc.Card(
        [
            dbc.CardBody(
                [
                    html.H2("Patiëntendossier:"),
                    html.Br(),
                    html.Div(
                        "Placeholder for patient file",
                        id="output_value",
                        style={
                            "height": "600px",
                            "overflow": "scroll",
                            "border": "1px solid lightgrey",
                            "padding": "10px",
                        },
                    ),
                    html.Br(),
                    html.H4("Ontbrekende informatie"),
                    html.Details(
                        [
                            html.Summary("Uitleg ontbrekende informatie"),
                            html.P(
                                "In de tabel hieronder staat de ontbrekende "
                                " informatie die de studenten hebben geannoteerd. "
                                "Het gaat hierbij dus om informatie die wel in het "
                                "patiëntendossier staat, maar niet in de geselecteerde "
                                "ontslagbrief. "
                                "Geef in de kolom `Beoordeling` aan hoe belangrijk "
                                "je deze annotatie vindt; ben je het eens dat de "
                                "annotatie missend is en is het belangrijk dat het wel "
                                "in de ontslagbrief staat, geef dan `Eens`; ernstig` "
                                "aan. Ben je het eens met de annotatie maar is het "
                                "niet zo ernstig, geef dan `Eens; minder ernstig` aan. "
                                "Ben je het niet eens met de annotatie, geef dan "
                                "`Oneens` aan. Geef in de kolom "
                                "`Dubbeling` aan of de annotatie al eerder is gemaakt, "
                                "door in die kolom de ID in te vullen van de eerste "
                                "rij waarin deze informatie is geannoteerd."
                            ),
                        ]
                    ),
                    generate_annotation_datatable("omission", "#EEC170"),
                    dcc.Store(id="annotation_dict"),
                ]
            ),
        ]
    )

    view_letter_div = dbc.Card(
        [
            dbc.CardHeader(html.H3("Bekijk ontslagbrief")),
            dbc.CardBody(
                [
                    html.Br(),
                    html.Div(
                        "Placeholder for discharge letter",
                        id="output_discharge_documentation",
                        style={
                            "height": "600px",
                            "overflow": "scroll",
                            "border": "1px solid lightgrey",
                            "padding": "10px",
                        },
                    ),
                    html.H4("Foutieve informatie"),
                    html.Details(
                        [
                            html.Summary("Uitleg foutieve informatie"),
                            html.P(
                                "In de tabel hieronder staat de informatie die door "
                                "studenten is geannoteerd als fout. "
                                "Dit gaat dus om informatie die wel in de ontslagbrief "
                                "staat, maar niet in het patiëntendossier. "
                                "Geef in de kolom `Beoordeling` aan hoe belangrijk "
                                "je deze annotatie vindt; ben je het eens dat de "
                                "annotatie fout is en is het een erstige fout  "
                                "geef dan `Eens`; ernstig` "
                                "aan. Ben je het eens met de annotatie maar is het "
                                "niet zo ernstig, geef dan `Eens; minder ernstig` aan. "
                                "Ben je het niet eens met de annotatie, geef dan "
                                "`Oneens` aan. Geef in de kolom "
                                "`Dubbeling` aan of de annotatie al eerder is gemaakt, "
                                "door in die kolom de ID in te vullen van de eerste "
                                "rij waarin deze informatie is geannoteerd."
                            ),
                        ]
                    ),
                    generate_annotation_datatable("hallucination", "#FE5F55"),
                    html.Hr(),
                    html.H4("Triviale informatie"),
                    html.Details(
                        [
                            html.Summary("Uitleg triviale informatie"),
                            html.P(
                                "In de tabel hieronder staat de informatie die door "
                                "studenten is geannoteerd als triviaal. "
                                "Dit gaat dus om informatie die in de ontslagbrief "
                                "staat, maar daar niet perse in hoeft te staan. "
                                "Geef in de kolom `Beoordeling` aan hoe belangrijk "
                                "je deze annotatie vindt; ben je het eens dat de "
                                "annotatie triviaal is en vind je het erg dat het er  "
                                "toch in staat, geef dan `Eens`; ernstig` "
                                "aan. Ben je het eens met de annotatie maar is het "
                                "niet zo ernstig, geef dan `Eens; minder ernstig` aan. "
                                "Ben je het niet eens met de annotatie, geef dan "
                                "`Oneens` aan. Geef in de kolom "
                                "`Dubbeling` aan of de annotatie al eerder is gemaakt, "
                                "door in die kolom de ID in te vullen van de eerste "
                                "rij waarin deze informatie is geannoteerd."
                            ),
                        ]
                    ),
                    generate_annotation_datatable("trivial", "#C6DDF0"),
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
                    html.Div(
                        children=[
                            html.Br(),
                            html.H5("Extra vragen:"),
                            dbc.Label(
                                "Welke ontslagbrief organiseert de relevante "
                                "informatie beter in een goed gestructureerde "
                                "samenvatting?"
                            ),
                            dbc.RadioItems(
                                options=[
                                    {
                                        "label": "Originele ontslagbrief",
                                        "value": "ORG letter",
                                    },
                                    {
                                        "label": "Gegenereerde ontslagbrief",
                                        "value": "GPT letter",
                                    },
                                ],
                                value="ORG letter",
                                id="extra_question_1",
                                inline=True,
                            ),
                            html.Br(),
                            dbc.Label(
                                "Welke ontslagbrief is beter in het opnemen van alleen "
                                "belangrijke informatie uit het patiëntendossier?"
                            ),
                            dbc.RadioItems(
                                options=[
                                    {
                                        "label": "Originele ontslagbrief",
                                        "value": "ORG letter",
                                    },
                                    {
                                        "label": "Gegenereerde ontslagbrief",
                                        "value": "GPT letter",
                                    },
                                ],
                                value="ORG letter",
                                id="extra_question_2",
                                inline=True,
                            ),
                            html.Br(),
                            dbc.Label(
                                "Welke samenvatting zou u in de praktijk het liefst "
                                "gebruiken als basis voor een ontslagbrief?"
                            ),
                            dbc.RadioItems(
                                options=[
                                    {
                                        "label": "Originele ontslagbrief",
                                        "value": "ORG letter",
                                    },
                                    {
                                        "label": "Gegenereerde ontslagbrief",
                                        "value": "GPT letter",
                                    },
                                ],
                                value="ORG letter",
                                id="extra_question_3",
                                inline=True,
                            ),
                            html.Br(),
                        ],
                        id="extra_questions_div",
                    ),
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
                        style={"margin-right": "15px"},
                    ),
                ]
            ),
        ],
        class_name="mt-2",
    )

    layout = html.Div(
        children=[
            navbar,
            dbc.Modal(
                [
                    dbc.ModalHeader(dbc.ModalTitle("Evaluatie opgeslagen!")),
                    dbc.ModalBody(id="save_modal"),
                ],
                id="save_modal_container",
                is_open=False,
            ),
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
                ]
            ),
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
