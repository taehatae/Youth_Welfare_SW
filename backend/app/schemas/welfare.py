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


class DecisionEvidence(BaseModel):
    """Public policy evidence; input field references, never raw profile values."""

    condition_ref: str
    condition_type: str
    operator: str
    value_text: str
    value_number: float | None = None
    upper_value_number: float | None = None
    unit: str
    source_field: str
    source_text: str
    comparison_result: Literal["passed", "failed", "unknown", "not_evaluated"]
    input_fields: list[str] = Field(default_factory=list)
    role: str = "unresolved"
    subject: str = "unresolved"
    scope: str = "unresolved"
    time_basis: str = "unresolved"
    semantics_verified: bool = False
    decision_usable: bool = False
    reason_codes: list[str] = Field(default_factory=list)
    comparison_semantics: Literal["eligibility_gate"] = "eligibility_gate"
    parser_version: str = ""
    decision_ruleset_version: str = ""


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
    # Defaults keep previously saved workspace snapshots readable.
    recommendation_decision: Literal["candidate", "excluded", "unverified"] = "unverified"
    decision_reason: str = "추천 근거를 아직 확인하지 않은 이전 분석 결과입니다."
    decision_warnings: list[str] = Field(default_factory=list)
    decision_evidence: list[DecisionEvidence] = Field(default_factory=list)
    semantic_analysis: list[dict] = Field(default_factory=list)


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
