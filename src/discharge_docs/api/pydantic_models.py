import logging
from datetime import datetime

from pydantic import BaseModel, field_validator

logger = logging.getLogger(__name__)


class PatientFile(BaseModel):
    enc_id: int
    pseudo_id: str
    patient_id: str
    admissionDate: datetime
    department: str
    date: datetime | None
    content: str
    description: str

    @field_validator("date", mode="after")
    @classmethod
    def convert_date(cls, value: datetime | None) -> datetime | None:
        """Convert dates with year 2999 to None.

        This is a workaround for HiX dates that use dates with year 2999 as None
        """
        if value is not None and value.year == 2999:
            logger.warning("Received date with year 2999, converting to None.")
            return None
        return value


class LLMOutput(BaseModel):
    message: str


class HixInputEntry(BaseModel):
    CLASSID: str
    SPECIALISM: str
    TEXT: str
    TEXTTYPE: str
    DATE: datetime
    NAAM: str
    CATID: str
    MAINCATID: str


class HixInput(BaseModel):
    ALLPARTS: list[HixInputEntry]


class HixOutput(BaseModel):
    department: str
    value: str
