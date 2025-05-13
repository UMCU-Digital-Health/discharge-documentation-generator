from datetime import datetime

from pydantic import BaseModel


class PatientFile(BaseModel):
    enc_id: int
    pseudo_id: str
    patient_id: str
    admissionDate: datetime
    department: str
    date: datetime
    content: str
    description: str


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
