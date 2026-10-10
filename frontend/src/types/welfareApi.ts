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
  eligibility_conditions: EligibilityConditions
}

export type YesNoUnknown = 'YES' | 'NO' | 'UNKNOWN'

export interface EligibilityConditions {
  gender: 'MALE' | 'FEMALE' | 'UNKNOWN'
  household_size: number | null
  income_type: 'LABOR' | 'BUSINESS' | 'FREELANCE' | 'NONE' | 'UNKNOWN'
  asset_range: string | null
  housing_type: string | null
  owns_home: boolean | null
  disability_status: YesNoUnknown
  student_status: YesNoUnknown
  marital_status: 'SINGLE' | 'MARRIED' | 'DIVORCED' | 'WIDOWED' | 'UNKNOWN'
  children_count: number | null
  qualifications: string[]
  additional_conditions: Record<string, string | number | boolean | null>
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
