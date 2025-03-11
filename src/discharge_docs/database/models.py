"""This module contains the SQLAlchemy models for the database.
The main function of this database is to store logging, feedback and evaluation data.
"""

from datetime import datetime
from typing import List, Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    MappedAsDataclass,
    mapped_column,
    relationship,
)


class Base(DeclarativeBase, MappedAsDataclass):
    pass


class Request(Base):
    """The request table stores general information about each request to the API.
    This includes the timestamp, response code, runtime, and API version.
    Each request in the request table is linked to a single row in one of the tables:
        RequestRetrieve, RequestGenerate, or RequestFeedback, depending on the endpoint.
    """

    __tablename__ = "request"
    __table_args__ = {"schema": "discharge_aiva"}

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True, init=False)
    timestamp: Mapped[datetime] = mapped_column(DateTime)
    response_code: Mapped[int] = mapped_column(Integer)
    runtime: Mapped[float] = mapped_column(init=False, nullable=True)
    api_version: Mapped[str] = mapped_column(String(10))
    endpoint: Mapped[str] = mapped_column(String(50))

    retrieve_relation: Mapped["RequestRetrieve"] = relationship(
        back_populates="request_relation", init=False
    )
    generate_relation: Mapped["RequestGenerate"] = relationship(
        back_populates="request_relation", init=False
    )
    feedback_relation: Mapped["RequestFeedback"] = relationship(
        back_populates="request_relation", init=False
    )


class RequestRetrieve(Base):
    """The RequestRetrieve table stores information about the endpoint
    "/retrieve_discharge_doc".
    This includes:
    - the linked Request ID
    - the request_enc_id: the encounter ID for which the generated doc was requested
    - a success indicator whether the retrieval request was successful
        (1 if successful; 0 if unsuccessful)
    - if the request was succesful, the returned generated document ID
        if the request was not successful, this field is NULL
    - if the request was succesful, the number of days old the returned generated doc is
        if the request was not successful, this field is NULL
    """

    __tablename__ = "requestretrieve"
    __table_args__ = {"schema": "discharge_aiva"}

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True, init=False)
    request_id: Mapped[int] = mapped_column(
        ForeignKey(Request.id), nullable=False, init=False
    )
    request_enc_id: Mapped[str]
    success_ind: Mapped[bool] = mapped_column(Boolean, init=False)
    generated_doc_id: Mapped[int] = mapped_column(Integer, nullable=True, init=False)
    nr_days_old: Mapped[int] = mapped_column(Integer, nullable=True, init=False)

    request_relation: Mapped["Request"] = relationship(
        back_populates="retrieve_relation"
    )


class RequestGenerate(Base):
    """The RequestGenerate table stores information about the endpoint
    "/process_and_generate_discharge_docs".  This includes:
    - the linked Request ID
    This table serves as a link between the Request table and the GeneratedDoc table.
    """

    __tablename__ = "requestgenerate"
    __table_args__ = {"schema": "discharge_aiva"}

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True, init=False)
    request_id: Mapped[int] = mapped_column(
        ForeignKey(Request.id), init=False, nullable=False
    )
    # TODO bedenk of hier nog andere dingen gelogd moeten worden

    request_relation: Mapped["Request"] = relationship(
        back_populates="generate_relation"
    )

    generated_doc_relation: Mapped[List["GeneratedDoc"]] = relationship(init=False)


class Encounter(Base):
    """The Encounter table stores information about the encounters for which the API was
    called. This includes:
    - the enc ID (the "identifier_value" in the dataplatform Encounter table)
    - the patient ID
    - the department in which the encounter took place
    """

    __tablename__ = "encounter"
    __table_args__ = {"schema": "discharge_aiva"}

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True, init=False)
    enc_id: Mapped[Optional[str]] = mapped_column(
        String(20), unique=True, nullable=True
    )
    patient_id: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    department: Mapped[str] = mapped_column(String(20))
    admissionDate: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    gen_doc_relation: Mapped[List["GeneratedDoc"]] = relationship(init=False)


class GeneratedDoc(Base):
    """The GeneratedDoc table stores the generated discharge letters and its attributes.
    This includes:
    - the linked RequestGenerate ID
    - the linked Encounter ID
    - the discharge letter in string format. (this is replaced by "" once removed)
    - the input token length
    - a success indicator whether the generation was successful
        (Success if successful;
        An error code [LengthError, JSONError, GeneralError] if unsuccessful)
    - the timestamp of the removal of the generated document
        (if the document was removed, otherwise NULL)
    """

    __tablename__ = "generateddoc"
    __table_args__ = {"schema": "discharge_aiva"}

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True, init=False)
    request_generate_id: Mapped[int] = mapped_column(
        ForeignKey(RequestGenerate.id), init=False
    )
    encounter_id: Mapped[str] = mapped_column(ForeignKey(Encounter.id), init=False)
    discharge_letter: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    input_token_length: Mapped[int]
    success_ind: Mapped[str] = mapped_column(String(20))
    removed_timestamp: Mapped[datetime] = mapped_column(
        DateTime, init=False, nullable=True
    )


class RequestFeedback(Base):
    """The RequestFeedback table stores information about the endpoint
    "/save_feeddack". This includes:
    - the linked FeedbackRequest ID
    - the request_enc_id: the encounter ID for which the feedback was given
    This table serves as a link between the Request table and the FeedbackDetails table.
    """

    __tablename__ = "requestfeedback"
    __table_args__ = {"schema": "discharge_aiva"}

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True, init=False)
    request_id: Mapped[int] = mapped_column(
        ForeignKey(Request.id), nullable=False, init=False
    )
    request_enc_id: Mapped[str]

    request_relation: Mapped["Request"] = relationship(
        back_populates="feedback_relation"
    )

    feedback_relation: Mapped[List["FeedbackDetails"]] = relationship(init=False)


class FeedbackDetails(Base):
    """The FeedbackDetails table stores the feedback questions and its corresponding
    answers. This includes:
    - the linked RequestFeedback ID
    - the feedback question
    - the feedback answer
    """

    __tablename__ = "feedbackdetails"
    __table_args__ = {"schema": "discharge_aiva"}

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True, init=False)
    request_feedback_id: Mapped[int] = mapped_column(
        Integer, ForeignKey(RequestFeedback.id), init=False
    )
    feedback_question: Mapped[str] = mapped_column(String(100))
    feedback_answer: Mapped[str]
