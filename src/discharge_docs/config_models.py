from typing import Dict, Optional

from pydantic import BaseModel, ConfigDict, EmailStr


# All config models moved from config.py
class LLMConfig(BaseModel):
    """Configuration for the LLM deployments.

    Environments are:
    - acc: Acceptance environment for test pipeline
    - prod: Production environment for production pipeline
    - bulk: Bulk generation environment for bulk generating letters for evaluation
    - eval: Evaluation environment for evaluation dashboard
    - env: Environment variable to determine the current environment
    """

    temperature: float
    DEPLOYMENT_NAME_ACC: str
    DEPLOYMENT_NAME_PROD: str
    DEPLOYMENT_NAME_BULK: str
    DEPLOYMENT_NAME_EVAL: str
    DEPLOYMENT_NAME_ENV: str


class AuthUser(BaseModel):
    email: EmailStr
    groups: list[str]
    developer: bool = False
    full_access: bool = False


class AuthConfig(BaseModel):
    users: dict[str, AuthUser]


class LengthRangeItem(BaseModel):
    min_days: Optional[int] = None
    max_days: Optional[int] = None
    length: str


class LengthRange(BaseModel):
    short: Optional[LengthRangeItem] = None
    medium: Optional[LengthRangeItem] = None
    long: Optional[LengthRangeItem] = None


class DepartmentItem(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    display_name: str
    ehr: str
    department_prompt: str
    post_processing: bool
    department_examples: Optional[str] = None
    post_processing_prompt: Optional[str] = None
    length_range: Optional[LengthRange] = None


class DepartmentConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    department: Dict[str, DepartmentItem]
