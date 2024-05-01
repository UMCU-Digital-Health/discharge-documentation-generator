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
    """Table that stores information on API requests"""

    __tablename__ = "apirequest"
    __table_args__ = {"schema": "discharge_aiva"}

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True, init=False)
    timestamp: Mapped[datetime] = mapped_column(DateTime)
    response_code: Mapped[int] = mapped_column(Integer, index=True, init=False)
    endpoint: Mapped[str]
    runtime: Mapped[float] = mapped_column(init=False)
    api_version: Mapped[str]

    encounter_relation: Mapped[List["ApiEncounter"]] = relationship(init=False)


class ApiEncounter(Base):
    """Table that stores per API request the encounters for which the discharge
    letter was updated
    """

    __tablename__ = "apiencounter"
    __table_args__ = {"schema": "discharge_aiva"}

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True, init=False)
    encounter_hix_id: Mapped[str]
    input_token_length: Mapped[int]
    request_id: Mapped[int] = mapped_column(
        Integer, ForeignKey(ApiRequest.id), init=False
    )
    department: Mapped[str]

    generated_doc_relation: Mapped["ApiGeneratedDoc"] = relationship(init=False)


class ApiGeneratedDoc(Base):
    """Table that stores the generated discharge letters"""

    __tablename__ = "apigenerateddoc"
    __table_args__ = {"schema": "discharge_aiva"}

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True, init=False)
    discharge_letter: Mapped[str]
    encounter_id: Mapped[str] = mapped_column(ForeignKey(ApiEncounter.id), init=False)
