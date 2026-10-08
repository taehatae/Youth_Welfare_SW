from enum import Enum

from pydantic import BaseModel, Field


class EmploymentStatus(str, Enum):
    EMPLOYED = "EMPLOYED"
    EMPLOYED_SME = "EMPLOYED_SME"
    UNEMPLOYED = "UNEMPLOYED"
    STUDENT = "STUDENT"
    SELF_EMPLOYED = "SELF_EMPLOYED"
    FREELANCER = "FREELANCER"
    OTHER = "OTHER"


class UserProfileCreate(BaseModel):
    age: int = Field(
        ...,
        ge=19,
        le=34,
        description="청년 연령",
    )

    region: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="거주 지역",
    )

    income_level: int = Field(
        ...,
        ge=0,
        description="월 소득. 단위: 원",
    )

    employment_status: EmploymentStatus


class SaveProfileResponse(BaseModel):
    user_id: str
    status: str
    message: str