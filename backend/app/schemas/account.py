from typing import Literal
from pydantic import BaseModel, Field, field_validator

from app.schemas.user import UserProfileCreate
from app.schemas.welfare import MatchedPoliciesResponse, MatchedPolicy, ReverseRecommendationsResponse


class LoginInput(BaseModel):
    username: str = Field(min_length=3, max_length=30, pattern=r"^[a-zA-Z0-9_]+$")
    password: str = Field(min_length=10, max_length=128)

    @field_validator("username")
    @classmethod
    def normalize_username(cls, value: str) -> str:
        return value.lower()


class SignupInput(LoginInput):
    display_name: str = Field(min_length=1, max_length=40)

    @field_validator("display_name")
    @classmethod
    def clean_name(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("이름을 입력해주세요.")
        return value.strip()


class AccountView(BaseModel):
    account_id: str
    username: str
    display_name: str


class AnalysisData(BaseModel):
    userId: str
    matched: MatchedPoliciesResponse
    reverse: ReverseRecommendationsResponse


class AnalysisSnapshot(BaseModel):
    profile: UserProfileCreate | None = None
    profileKey: str = ""
    analysis: AnalysisData
    checkedAt: str


class SavedCondition(BaseModel):
    field: str
    current: str
    required: str
    status: str
    guide: str


class SavedCounts(BaseModel):
    evaluated: int = Field(ge=0)
    passed: int = Field(ge=0)
    failed: int = Field(ge=0)
    review: int = Field(ge=0)


class SavedPolicyRow(BaseModel):
    id: str = Field(max_length=100)
    title: str = Field(max_length=500)
    status: Literal["eligible", "ineligible", "needs_review"]
    url: str | None = None
    description: str
    counts: SavedCounts | None = None
    conditions: list[SavedCondition] = Field(max_length=500)


TrackingStatus = Literal["interested", "preparing", "applied", "archived"]


class SavedPolicy(BaseModel):
    profileKey: str = Field(max_length=50000)
    profile: UserProfileCreate | None = None
    policy: SavedPolicyRow
    savedAt: str
    trackingStatus: TrackingStatus = "interested"
    note: str = Field(default="", max_length=500)


class SavedPoliciesInput(BaseModel):
    items: list[SavedPolicy] = Field(max_length=200)


class ProfileViewInput(LoginInput):
    snapshot: Literal["current", "diagnosis"] = "current"


class SavedPolicyToggle(BaseModel):
    profileKey: str = Field(min_length=64, max_length=64)
    policyId: str = Field(min_length=1, max_length=100)


class SavedPolicyUpdate(SavedPolicyToggle):
    trackingStatus: TrackingStatus
    note: str = Field(max_length=500)


class WorkspaceState(BaseModel):
    profile: UserProfileCreate | None = None
    diagnosis: AnalysisSnapshot | None = None
    previousDiagnosis: AnalysisSnapshot | None = None
    current: AnalysisSnapshot | None = None
    previous: AnalysisSnapshot | None = None
    knownPolicies: list[MatchedPolicy] = Field(default_factory=list)
    savedPolicies: list[SavedPolicy] = Field(default_factory=list)
