import logging
import os
from datetime import datetime
from pathlib import Path

import dash
import dash_bootstrap_components as dbc
import flask
import pandas as pd
import tomli
from dash import ctx, html
from dash.dependencies import Input, Output, State
from dash.exceptions import PreventUpdate
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from discharge_docs.dashboard.dashboard_layout import get_phase_2_layout
from discharge_docs.dashboard.helper import (
    get_authorization,
    get_authorized_patients,
    get_data_from_patient_admission,
    get_patients_from_list_names,
    get_suitable_enc_ids,
    get_user,
    highlight,
    load_stored_discharge_letters_pre_release,
    replace_newlines,
)
from discharge_docs.database.models import (
    Base,
    EvalPhase2,
    EvalPhase2Annotation,
    EvalPhase2ExtraQuestions,
)
from discharge_docs.database.student_annotation import get_student_annotations
from discharge_docs.processing.processing import get_patient_discharge_docs

logger = logging.getLogger(__name__)


# load data
data_folder = Path(__file__).parents[1] / "data" / "processed" / "pre-pilot"

df_metavision = pd.read_parquet(data_folder / "metavision_data_april_dp.parquet")

df_HIX = pd.read_parquet(data_folder / "HiX_CAR_data_pre_pilot.parquet")

# Define your DataFrames for each department
df_dict = {
    "NICU": df_metavision,
    "IC": df_metavision,
    "CAR": df_HIX,
    "PSY": df_HIX,
}

# load stored discharge letters
df_discharge2 = pd.read_csv(data_folder / "bulk_generated_docs_gpt4_PReval_2.csv")
df_discharge4 = pd.read_csv(data_folder / "bulk_generated_docs_gpt4_PReval_4.csv")
df_discharge3 = pd.read_csv(data_folder / "bulk_generated_docs_gpt4_PReval_3.csv")
df_discharge_total = pd.concat(
    [df_discharge2, df_discharge3, df_discharge4]
).drop_duplicates("enc_id", keep="last")

# load used enc_ids
enc_ids_dict = get_suitable_enc_ids(
    file_name="enc_ids_pre_release_phase2.toml", type="department", first_25=False
)

data_dict, values_list = get_patients_from_list_names(
    df_dict, enc_ids_dict, phase2=True
)


# Authorization config
with open(Path(__file__).parent / "config" / "auth_fase2.toml", "rb") as f:
    authorization_dict = tomli.load(f)

# Database config
with open(Path(__file__).parents[1] / "pyproject.toml", "rb") as f:
    project_info = tomli.load(f)

DB_USER = os.getenv("DB_USER", "")
DB_PASSWD = os.getenv("DB_PASSWD", "")
DB_HOST = os.getenv("DB_HOST", "")
DB_PORT = os.getenv("DB_PORT", 1433)
DB_DATABASE = os.getenv("DB_DATABASE", "")

if DB_USER == "":
    logging.warning("Using debug SQLite database...")
    SQLALCHEMY_DATABASE_URL = "sqlite:///./sql_app.db"
    execution_options = {"schema_translate_map": {"discharge_aiva": None}}
else:
    SQLALCHEMY_DATABASE_URL = (
        rf"mssql+pymssql://{DB_USER}:{DB_PASSWD}@{DB_HOST}:{DB_PORT}/{DB_DATABASE}"
    )
    execution_options = None


engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    execution_options=execution_options,
)
Base.metadata.create_all(engine)

# Custom CSS neccessary for datatable funtionality like dropdown
dbc_css = "https://cdn.jsdelivr.net/gh/AnnMarieW/dash-bootstrap-templates/dbc.min.css"

# define the app
app = dash.Dash(
    __name__,
    external_stylesheets=[dbc.themes.BOOTSTRAP, dbc_css],
)
application = app.server  # Neccessary for debugging in vscode, no further use

# Define the layout of the app
app.layout = get_phase_2_layout()


@app.callback(
    Output("patient_admission_dropdown", "options"),
    Output("patient_admission_dropdown", "value"),
    Output("logged_in_user", "children"),
    Input("navbar", "children"),
)
def load_patient_selection_dropdown(_) -> tuple[list, str | None, list]:
    """
    Load the patient admission dropdown with the available patient admissions when
    the app is starting. Available patients are based on the user's authorization.

    Returns
    -------
    tuple[list, str]
        The list of options for the patient admission dropdown and the first patient
        value.
    """
    user, authorization_group = get_authorization(
        flask.request,
        authorization_dict,
        development_authorizations=["NICU", "IC", "CAR", "PSY", "DEMO"],
    )
    authorized_patients, first_patient = get_authorized_patients(
        authorization_group, values_list
    )

    return authorized_patients, first_patient, [f"Ingelogd als: {user}"]


@app.callback(
    Output("annotation_dict", "data"),
    Output("selected_letter_dropdown", "value"),
    Input("patient_admission_dropdown", "value"),
    Input("selected_letter_dropdown", "value"),
)
def get_annotations(
    selected_patient_admission: str, selected_letter: str
) -> tuple[list[dict], str]:
    """
    Get the annotations for the selected patient admission.

    Optionally reset the selected letter, if the patient admission dropdown was
    changed.

    Parameters
    ----------
    selected_patient_admission : str
        The selected patient admission.
    selected_letter : str
        The selected letter.

    Returns
    -------
    list[dict]
        A list of dictionaries containing annotations for highlighting specific
        information in the discharge documentation.
    str
        The selected letter.
    """
    if selected_patient_admission is None:
        return [{}], selected_letter

    if ctx.triggered_id == "patient_admission_dropdown":
        selected_letter = "ORG letter"

    annotation_dict = get_student_annotations(
        engine, selected_patient_admission, selected_letter
    )

    return annotation_dict, selected_letter


@app.callback(
    Output("output_value", "children"),
    Input("annotation_dict", "data"),
    State("patient_admission_dropdown", "value"),
)
def display_patient_file(
    annotation_dict: list[dict], selected_patient_admission: str
) -> list:
    """Display the patient file for the selected patient admission.

    This callback function retrieves the discharge documentation for the selected
    patient admission and formats it for display.

    Parameters
    ----------
    annotation_dict : list[dict]
        A list of dictionaries containing the annotations for the selected patient
        admission. Each dictionary should have the following keys:
        - "user": The user who made the annotation.
        - "type": The type of annotation.
        - "text": The text to be annotated.
    selected_patient_admission : str
        The selected patient admission.

    Returns
    -------
    list
        A list containing the formatted discharge documentation for the selected
        patient admission.
    """
    if selected_patient_admission is None:
        raise ValueError("selected_patient_admission cannot be None.")

    data = get_data_from_patient_admission(selected_patient_admission, data_dict)
    patient_file = data.sort_values(by=["date", "description"])

    if patient_file.empty:
        return ["Er is geen patientendossier voor deze patient."]

    patient_file = patient_file[patient_file["description"] != "Ontslagbrief"]
    patient_file_string = [
        [
            html.H4(f"{row['description'].upper()} - {row['date'].date()}"),
            row["value"],
            html.Br(),
            html.Hr(),
        ]
        for _, row in patient_file.iterrows()
    ]
    patient_file_string = [item for sublist in patient_file_string for item in sublist]

    highlighted_missings = [
        record["text"]
        for record in annotation_dict
        if record["type"] == "highlighted_missings"
    ]
    for annotation_str in highlighted_missings:
        patient_file_string = highlight(
            patient_file_string, annotation_str, "#EEC170", "white"
        )

    return patient_file_string


@app.callback(
    Output("extra_questions_div", "className"),
    Input("selected_letter_dropdown", "value"),
)
def toggle_extra_questions(letter_shown: str) -> str:
    """
    Toggle the extra questions div based on the selected letter.

    Parameters
    ----------
    letter_shown : str
        The letter that was shown to the user.

    Returns
    -------
    list
        The extra questions div if the selected letter is the GPT letter.
    """
    if letter_shown == "GPT letter":
        return "d-block"
    else:
        return "d-none"


@app.callback(
    Output("output_discharge_documentation", "children"),
    Input("annotation_dict", "data"),
    State("patient_admission_dropdown", "value"),
    State("selected_letter_dropdown", "value"),
)
def display_chosen_discharge_documentation(
    annotation_dict: list[dict],
    selected_patient_admission: str,
    letter_shown: str,
) -> str | list:
    """
    Display the discharge documentation for the selected patient admission.

    This callback function retrieves the discharge documentation for the selected
    patient admission and formats it for display.

    Parameters
    ----------
    annotation_dict : list[dict]
        A list of dictionaries containing the annotations for the selected patient
        admission. Each dictionary should have the following keys:
        - "user": The user who made the annotation.
        - "type": The type of annotation.
        - "text": The text to be annotated.
    selected_patient_admission : str
        The selected patient admission.
    letter_shown : str
        The letter that was shown to the user.

    Returns
    -------
    list
        A list containing the formatted discharge documentation for the selected
        patient admission.
    """
    if selected_patient_admission is None:
        return ""

    text_GPT = str(
        load_stored_discharge_letters_pre_release(
            df_discharge_total, selected_patient_admission, phase2=True
        )
    )

    data = get_data_from_patient_admission(selected_patient_admission, data_dict)
    text_ORG = str(get_patient_discharge_docs(df=data).iloc[0])

    if letter_shown == "GPT letter":
        output_text = text_GPT
    else:
        output_text = text_ORG

    # Add highlighting
    highlighted_hallucinations = [
        record["text"]
        for record in annotation_dict
        if record["type"] == "highlighted_hallucinations"
    ]
    highlighted_trivial = [
        record["text"]
        for record in annotation_dict
        if record["type"] == "highlighted_trivial_information"
    ]

    for annotation_str in highlighted_hallucinations:
        output_text = highlight(output_text, annotation_str, "#FE5F55", "white")
    for annotation_str in highlighted_trivial:
        output_text = highlight(output_text, annotation_str, "#C6DDF0", "white")

    output_text = replace_newlines(output_text)

    return output_text


@app.callback(
    Output("save_modal_container", "is_open"),
    Output("save_modal", "children"),
    Output("likert_slider", "value"),
    Output("evaluation_text", "value"),
    Output("extra_question_1", "value"),
    Output("extra_question_2", "value"),
    Output("extra_question_3", "value"),
    Input("evaluate_button", "n_clicks"),
    State("selected_letter_dropdown", "value"),
    State("likert_slider", "value"),
    State("evaluation_text", "value"),
    State("patient_admission_dropdown", "value"),
    State("omission_table", "data"),
    State("hallucination_table", "data"),
    State("trivial_table", "data"),
    State("extra_question_1", "value"),
    State("extra_question_2", "value"),
    State("extra_question_3", "value"),
)
def gather_feedback(
    n_clicks: int,
    letter_shown: str,
    evaluation_slider: int,
    evaluation_text: str,
    selected_patient_admission: str,
    omission_data: list[dict],
    hallucination_data: list[dict],
    trivial_data: list[dict],
    extra_question_1: str,
    extra_question_2: str,
    extra_question_3: str,
) -> tuple[bool, str, int, str, str, str, str]:
    """
    Save the evaluation/feedback from the user.

    Parameters
    ----------
    n_clicks : int
        The number of times the feedback button was clicked.
    letter_shown : str
        The letter that was shown to the user.
    evaluation_slider : int
        The score given by the user on the evaluation slider.
    evaluation_text : str
        The feedback text provided by the user.
    selected_patient_admission : str
        The selected patient admission.
    omission_data : list[dict]
        The list of omission data.
    hallucination_data : list[dict]
        The list of hallucination data.
    trivial_data : list[dict]
        The list of trivial data.
    extra_question_1 : str
        The answer to the first extra question.
    extra_question_2 : str
        The answer to the second extra question.
    extra_question_3 : str
        The answer to the third extra question.

    Returns
    -------
    tuple[bool, str, int, str, str, str, str]
        A tuple containing the following information:
        - A boolean indicating if the saved modal should be open.
        - A string for the succes message in the modal
        - The default value for the likert slider.
        - The default value for the evaluation text.
        - The default value for the first extra question.
        - The default value for the second extra question.
        - The default value for the third extra question.
    """
    if n_clicks is None:
        raise PreventUpdate

    user = get_user(flask.request)

    evaluation_instance = EvalPhase2(
        user=user,
        timestamp=datetime.now(),
        patientid=selected_patient_admission,
        usability_likert=evaluation_slider,
        comments=evaluation_text,
        evaluated_letter=letter_shown,
    )

    # Save the feedback to database
    for item in omission_data:
        item["type"] = "omission"
    for item in hallucination_data:
        item["type"] = "hallucination"
    for item in trivial_data:
        item["type"] = "trivial"
    total_data = omission_data + hallucination_data + trivial_data

    for item in total_data:
        evaluation_annotation = EvalPhase2Annotation(
            text=item["text"],
            importance=item["importance"],
            duplicate=item["duplicate"],
            duplicate_id=item["id"],
            type=item["type"],
            annotation_user=item["user"],
        )
        evaluation_instance.annotation_relation.append(evaluation_annotation)

    # Optionally save extra questions
    if letter_shown == "GPT letter":
        extra_questions = [extra_question_1, extra_question_2, extra_question_3]

        for id, answer in enumerate(extra_questions):
            question_instance = EvalPhase2ExtraQuestions(
                question=f"Vraag {id + 1}",
                answer=answer,
            )
            evaluation_instance.extra_questions_relation.append(question_instance)

    with Session(engine) as session:
        session.add(evaluation_instance)
        session.commit()

    human_readable_letter = (
        "de GPT brief" if letter_shown == "GPT letter" else "de originele brief"
    )
    succes_text = (
        f"De feedback is opgeslagen voor {human_readable_letter} "
        f"over patient: {selected_patient_admission}."
    )

    return True, succes_text, 3, "", "ORG letter", "ORG letter", "ORG letter"


@app.callback(
    Output("omission_table", "data"),
    Output("hallucination_table", "data"),
    Output("trivial_table", "data"),
    Output("omission_table", "tooltip_data"),
    Output("hallucination_table", "tooltip_data"),
    Output("trivial_table", "tooltip_data"),
    Input("annotation_dict", "data"),
    State("patient_admission_dropdown", "value"),
)
def display_student_annotations(
    student_annotations: list[dict], selected_patient_admission: str
) -> tuple[list[dict], list[dict], list[dict], list[dict], list[dict], list[dict]]:
    """
    Display the student annotations in the datatables

    Parameters
    ----------
    student_annotations : list[dict]
        The student annotations.
    selected_patient_admission : str
        The selected patient admission.

    Returns
    -------
    tuple[list[dict], list[dict], list[dict], list[dict], list[dict], list[dict]
        The omission, hallucination and trivial data and the corresponding tooltips.
    """
    if selected_patient_admission is None or len(student_annotations) == 0:
        return [], [], [], [], [], []

    omission_components, omission_tooltips = generate_annotation_data(
        student_annotations, "highlighted_missings"
    )

    hallucination_components, hallucination_tooltips = generate_annotation_data(
        student_annotations, "highlighted_hallucinations"
    )

    trivial_components, trivial_tooltips = generate_annotation_data(
        student_annotations, "highlighted_trivial_information"
    )

    return (
        omission_components,
        hallucination_components,
        trivial_components,
        omission_tooltips,
        hallucination_tooltips,
        trivial_tooltips,
    )


def generate_annotation_data(
    student_annotations: list[dict], annotation_type: str
) -> tuple[list[dict], list[dict]]:
    """
    Generate the annotation data for the student annotations.

    Parameters
    ----------
    student_annotations : list[dict]
        The student annotations.
    annotation_type : str
        The type of annotation.

    Returns
    -------
    list[dict]
        The annotation data.
    list[dict]
        The annotation data for the tooltips
    """
    output_list = []
    tooltip_list = []
    index_number = 0

    for item in student_annotations:
        if item["type"] == annotation_type:
            tooltip_list.append(
                {
                    "text": {
                        "value": str(item["text"]),
                        "type": "markdown",
                    }
                }
            )
            output_list.append(
                {
                    "id": index_number,
                    "text": item["text"],
                    "importance": "Important",
                    "duplicate": None,
                    "user": item["user"],
                }
            )
            index_number += 1

    return output_list, tooltip_list


# Run the app
if __name__ == "__main__":
    app.run_server(debug=True, port=8483)
