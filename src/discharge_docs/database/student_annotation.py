from ast import literal_eval
from typing import cast

import pandas as pd
from sqlalchemy import Engine, select
from sqlalchemy.orm import Session

from discharge_docs.database.models import EvalPhase1


def get_student_annotations(
    engine: Engine, selected_patient: str, letter_shown: str
) -> list[dict]:
    """
    Get student annotations for a selected patient.

    Gets the info from the database and parses and processes the lists of annotations.

    Parameters
    ----------
    engine : Engine
        The SQLAlchemy engine.
    selected_patient : str
        The selected patient.

    Returns
    -------
    list[dict]
        A list of dictionaries containing the student annotations for the selected
        patient. Each dictionary represents an annotation and contains the
        following keys:
        - 'user': The user who made the annotation.
        - 'type': The type of annotation.
        - 'text': The text of the annotation.
    """
    with Session(engine) as session:
        student_annotations = session.execute(
            select(
                EvalPhase1.user,
                EvalPhase1.highlighted_trivial_information,
                EvalPhase1.highlighted_halucinations,
                EvalPhase1.highlighted_missings,
                EvalPhase1.patientid,
            ).where(
                (EvalPhase1.patientid.endswith(f"#_{selected_patient}", escape="#"))
                & (EvalPhase1.letter_evaluated == letter_shown)
            )
        ).all()

    if len(student_annotations) == 0:
        return []

    # Check if patientid is in the correct format (ending with enc_id)
    student_annotations_df = pd.DataFrame(student_annotations)
    student_annotations_df = student_annotations_df[
        student_annotations_df["patientid"].str.split("_").apply(len) == 4
    ]
    student_annotations_df = student_annotations_df.drop(columns=["patientid"])

    student_annotations_series = (
        student_annotations_df.set_index("user").map(literal_eval).stack()
    )
    student_annotations_series = cast(pd.Series, student_annotations_series)
    student_annotations_df = student_annotations_series.explode().dropna().reset_index()
    student_annotations_df.columns = ["user", "type", "text"]

    # Fix misspelling of hallucination
    student_annotations_df["type"] = student_annotations_df["type"].replace(
        "highlighted_halucinations", "highlighted_hallucinations"
    )

    return student_annotations_df.to_dict(orient="records")
