from typing import Literal

from pydantic import BaseModel, Field


RecommendationStatus = Literal[
    "priority_recommendation",
    "priority_consideration",
    "condition_mismatch",
    "additional_review",
]


class MatchedPolicy(BaseModel):
    policy_id: str
    title: str
    category: str
    support_amount: str
    match_score: float
    detail_url: str | None = None


class ConditionAnalysis(BaseModel):
    condition_type: str
    status: str
    current_value: str
    required_value: str
    message: str
    action_guide: str
    source_field: str
    source_text: str


class EligibilityAnalysis(BaseModel):
    policy_id: str
    title: str
    status: str
    match_score: float
    evaluated_conditions: int
    passed_conditions: int
    gap_conditions: list[ConditionAnalysis] = Field(
        default_factory=list
    )
    review_conditions: list[ConditionAnalysis] = Field(
        default_factory=list
    )
    # 추천 판정 도입 이전에 저장된 진단 결과도 읽을 수 있도록 기본값을 둔다.
    recommendation_status: RecommendationStatus = "additional_review"
    recommendation_reason: str = "이전에 저장된 진단 결과예요. 다시 진단하면 추천 사유를 확인할 수 있어요."
    recommendation_uncertainty: str | None = None
    confirmed_conditions: list[ConditionAnalysis] = Field(
        default_factory=list
    )
    notes: list[str] = Field(default_factory=list)
    detail_url: str


class MatchedPoliciesResponse(BaseModel):
    matched_count: int
    policies: list[MatchedPolicy]
    evaluated_count: int = 0
    needs_review_count: int = 0
    ineligible_count: int = 0
    analysis_results: list[EligibilityAnalysis] = Field(
        default_factory=list
    )


class MissingCondition(BaseModel):
    field: str
    current_value: str
    required_value: str
    action_guide: str


class ReverseRecommendation(BaseModel):
    target_policy: str
    current_eligibility: bool
    missing_conditions: list[MissingCondition]


class ReverseRecommendationsResponse(BaseModel):
    recommendations: list[ReverseRecommendation]
