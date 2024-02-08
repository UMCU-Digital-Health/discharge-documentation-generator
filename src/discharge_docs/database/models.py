"""This module contains the SQLAlchemy models for the database.
The main function of this database is to store logging, feedback and evaluation data.
"""
from datetime import datetime
from typing import List

from sqlalchemy import DateTime, ForeignKey, Integer
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
    __table_args__ = {"schema": "aiva-discharge"}

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True, init=False)
    timestamp: Mapped[datetime] = mapped_column(DateTime)
    user: Mapped[str]
    department: Mapped[str]
    version: Mapped[str]


class DashUserPrompt(Base):
    """Table that stores the user prompt for the dashboard"""

    __tablename__ = "dashuserprompt"
    __table_args__ = {"schema": "aiva-discharge"}

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True, init=False)
    prompt: Mapped[str]
    session: Mapped[int] = mapped_column(
        Integer, ForeignKey(DashSession.id), init=False
    )

    session_relation: Mapped["DashSession"] = relationship()
    evaluation_relation: Mapped[List["DashEvaluation"]] = relationship(
        init=False, back_populates="user_prompt_relation"
    )


class DashEvaluation(Base):
    """Table that stores different performance metrics of the custom user prompt"""

    __tablename__ = "dashevaluation"
    __table_args__ = {"schema": "aiva-discharge"}

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True, init=False)
    user_prompt_id = mapped_column(Integer, ForeignKey(DashUserPrompt.id), init=False)
    evaluation_metric: Mapped[str]
    evaluation_value: Mapped[float]

    user_prompt_relation: Mapped["DashUserPrompt"] = relationship(
        init=False, back_populates="evaluation_relation"
    )
