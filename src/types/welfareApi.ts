export type EmploymentStatus =
  | 'EMPLOYED'
  | 'EMPLOYED_SME'
  | 'UNEMPLOYED'
  | 'STUDENT'
  | 'SELF_EMPLOYED'
  | 'FREELANCER'
  | 'OTHER'

export interface UserProfileInput {
  age: number
  region: string
  income_level: number
  employment_status: EmploymentStatus
}

export interface SaveProfileResponse {
  user_id: string
  status: string
  message: string
}

export interface MatchedPolicy {
  policy_id: string
  title: string
  category: string
  support_amount: string
  match_score: number
}

export interface MatchedPoliciesResponse {
  matched_count: number
  policies: MatchedPolicy[]
}

export interface MissingCondition {
  field: string
  current_value: string
  required_value: string
  action_guide: string
}

export interface ReverseRecommendation {
  target_policy: string
  current_eligibility: boolean
  missing_conditions: MissingCondition[]
}

export interface ReverseRecommendationsResponse {
  recommendations: ReverseRecommendation[]
}

export interface WelfareAnalysis {
  userId: string
  matched: MatchedPoliciesResponse
  reverse: ReverseRecommendationsResponse
}
