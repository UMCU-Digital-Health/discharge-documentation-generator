"""This module contains the SQLAlchemy models for the database.
The main function of this database is to store logging, feedback and evaluation data.
"""

from datetime import datetime
from typing import List

from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    MappedAsDataclass,
    mapped_column,
    relationship,
)


class Base(DeclarativeBase, MappedAsDataclass):
    pass


class DashSession(Base):
    """Table that stores information about the current session of the dashboard"""

    __tablename__ = "dashsession"
    __table_args__ = {"schema": "discharge_aiva"}

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True, init=False)
    timestamp: Mapped[datetime] = mapped_column(DateTime)
    user: Mapped[str]
    groups: Mapped[str]
    version: Mapped[str]


class DashUserPrompt(Base):
    """Table that stores the input (user prompt & selected patient) for the dashboard"""

    __tablename__ = "dashuserprompt"
    __table_args__ = {"schema": "discharge_aiva"}

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True, init=False)
    prompt: Mapped[str]
    patient: Mapped[str] = mapped_column(String)
    session: Mapped[int] = mapped_column(
        Integer, ForeignKey(DashSession.id), init=False
    )

    session_relation: Mapped["DashSession"] = relationship()
    evaluation_relation: Mapped[List["DashEvaluation"]] = relationship(
        init=False, back_populates="user_prompt_relation"
    )
    output_relation: Mapped[List["DashOutput"]] = relationship(
        init=False, back_populates="user_prompt_relation"
    )


class DashEvaluation(Base):
    """Table that stores the output and the different performance metrics
    of the custom user prompt."""

    __tablename__ = "dashevaluation"
    __table_args__ = {"schema": "discharge_aiva"}

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True, init=False)
    user_prompt_id: Mapped[int] = mapped_column(
        Integer, ForeignKey(DashUserPrompt.id), init=False
    )
    evaluation_metric: Mapped[str]
    evaluation_value: Mapped[str]

    user_prompt_relation: Mapped["DashUserPrompt"] = relationship(
        init=False, back_populates="evaluation_relation"
    )


class DashOutput(Base):
    """Table that stores the output of the GPT call."""

    __tablename__ = "dashoutput"
    __table_args__ = {"schema": "discharge_aiva"}

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True, init=False)
    user_prompt_id: Mapped[int] = mapped_column(
        Integer, ForeignKey(DashUserPrompt.id), init=False
    )

    gpt_output_value: Mapped[str]

    user_prompt_relation: Mapped["DashUserPrompt"] = relationship(
        init=False, back_populates="output_relation"
    )


class ApiRequest(Base):
    """Table that stores information on API requests. This includes the timestamp,
    response code, endpoint, runtime, api version and logging number.
    The logging number's purpose is to do variable logging per endpoint.
        /process-and-generate-discharge-docs: number of encounters processed
        /remove_old_discharge_docs: number of discharge letters removed
        /retrieve_discharge_doc: {encounter_id}_{generated_doc_id} to show for which
            patient which discharge letter was retrieved
        /save-feedback: number of feedbacks entries saved (by default 1)
    """

    __tablename__ = "apirequest"
    __table_args__ = {"schema": "discharge_aiva"}

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True, init=False)
    timestamp: Mapped[datetime] = mapped_column(DateTime)
    response_code: Mapped[int] = mapped_column(Integer, index=True, init=False)
    endpoint: Mapped[str]
    runtime: Mapped[float] = mapped_column(init=False)
    api_version: Mapped[str]
    logging_number: Mapped[str] = mapped_column(init=False)

    encounter_relation: Mapped[List["ApiEncounter"]] = relationship(init=False)
    feedback_relation: Mapped[List["ApiFeedback"]] = relationship(init=False)


class ApiEncounter(Base):
    """Table that stores per API request the encounters for which the discharge
    letter was updated
    "encounter_hix_id" is the unique identifier for the encounter.
        In dp this is identifier_value from Encounter table.
    """

    __tablename__ = "apiencounter"
    __table_args__ = {"schema": "discharge_aiva"}

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True, init=False)
    encounter_hix_id: Mapped[str]
    patient_number: Mapped[str]

    request_id: Mapped[int] = mapped_column(
        Integer, ForeignKey(ApiRequest.id), init=False
    )

    department: Mapped[str]

    generated_doc_relation: Mapped[List["ApiGeneratedDoc"]] = relationship(init=False)


class ApiFeedback(Base):
    """Table that stores the feedback given by the user on the retrieved discharge
    letter.
    "encounter_hix_id" is the unique identifier for the encounter.
        In dp this is identifier_value from Encounter table.
    """

    __tablename__ = "apifeedback"
    __table_args__ = {"schema": "discharge_aiva"}

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True, init=False)
    feedback: Mapped[str]
    encounter_hix_id: Mapped[int]
    request_id: Mapped[int] = mapped_column(
        Integer, ForeignKey(ApiRequest.id), init=False
    )


class ApiGeneratedDoc(Base):
    """Table that stores the generated discharge letters and patiënt numbers"""

    __tablename__ = "apigenerateddoc"
    __table_args__ = {"schema": "discharge_aiva"}

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True, init=False)
    discharge_letter: Mapped[str]
    input_token_length: Mapped[int]
    success: Mapped[str]
    generation_date: Mapped[datetime] = mapped_column(DateTime)
    encounter_id: Mapped[str] = mapped_column(ForeignKey(ApiEncounter.id), init=False)


class EvalPhase1(Base):
    """Table that stores the evaluation data for phase 1."""

    __tablename__ = "evalphase1"
    __table_args__ = {"schema": "discharge_aiva"}

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True, init=False)
    user: Mapped[str] = mapped_column(String, nullable=False)
    timestamp: Mapped[DateTime] = mapped_column(DateTime, nullable=False)
    patientid: Mapped[str] = mapped_column(String, nullable=False)
    letter_evaluated: Mapped[str] = mapped_column(String, nullable=False)
    highlighted_missings: Mapped[str] = mapped_column(String, nullable=True)
    highlighted_halucinations: Mapped[str] = mapped_column(String, nullable=True)
    highlighted_trivial_information: Mapped[str] = mapped_column(String, nullable=True)
    usability_likert: Mapped[int] = mapped_column(Integer, nullable=False)
    comments: Mapped[str] = mapped_column(String, nullable=True)


class EvalPhase2(Base):
    """Table that stores the evaluation data for phase 2."""

    __tablename__ = "evalphase2"
    __table_args__ = {"schema": "discharge_aiva"}

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True, init=False)
    user: Mapped[str]
    timestamp: Mapped[datetime]
    patientid: Mapped[str]
    usability_likert: Mapped[int]
    comments: Mapped[str]
    evaluated_letter: Mapped[str]

    annotation_relation: Mapped[List["EvalPhase2Annotation"]] = relationship(init=False)
    extra_questions_relation: Mapped[List["EvalPhase2ExtraQuestions"]] = relationship(
        init=False
    )


class EvalPhase2Annotation(Base):
    """Table that stores the annotations for phase 2."""

    __tablename__ = "evalphase2annotation"
    __table_args__ = {"schema": "discharge_aiva"}

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True, init=False)
    annotation_user: Mapped[str]
    text: Mapped[str]
    importance: Mapped[str]
    duplicate_id: Mapped[int]  # id to refer to by the duplicate column
    duplicate: Mapped[int] = mapped_column(nullable=True)
    type: Mapped[str]
    evalphase2_id: Mapped[int] = mapped_column(
        Integer, ForeignKey(EvalPhase2.id), nullable=True, init=False
    )


class EvalPhase2ExtraQuestions(Base):
    """Table that stores extra questions for GPT generated letters"""

    __tablename__ = "evalphase2extraquestions"
    __table_args__ = {"schema": "discharge_aiva"}

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True, init=False)
    question: Mapped[str]
    answer: Mapped[str]
    evalphase2_id: Mapped[int] = mapped_column(
        Integer, ForeignKey(EvalPhase2.id), nullable=True, init=False
    )
