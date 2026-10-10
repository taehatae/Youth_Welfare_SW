from pydantic import BaseModel, Field


class MatchedPolicy(BaseModel):
    policy_id: str
    title: str
    category: str
    support_amount: str
    match_score: float


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