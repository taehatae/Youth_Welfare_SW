from pydantic import BaseModel


class MatchedPolicy(BaseModel):
    policy_id: str
    title: str
    category: str
    support_amount: str
    match_score: float


class MatchedPoliciesResponse(BaseModel):
    matched_count: int
    policies: list[MatchedPolicy]


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