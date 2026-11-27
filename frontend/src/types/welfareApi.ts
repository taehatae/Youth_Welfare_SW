export type EmploymentStatus = "EMPLOYED" | "EMPLOYED_SME" | "PART_TIME" | "UNEMPLOYED" | "SELF_EMPLOYED" | "FREELANCER" | "OTHER"

export interface UserProfileInput {
  age: number

  region: string

  income_level: number

  employment_status: EmploymentStatus

  eligibility_conditions: EligibilityConditions
}

export type YesNoUnknown = "YES" | "NO" | "UNKNOWN"

export type JsonValue =
  | string
  | number
  | boolean
  | null
  | JsonValue[]
  | { [key: string]: JsonValue }

export interface EligibilityConditions {
  gender: "MALE" | "FEMALE" | "UNKNOWN"

  household_size: number | null

  income_type: "LABOR" | "BUSINESS" | "FREELANCE" | "NONE" | "UNKNOWN"

  asset_range: string | null

  housing_type: string | null

  owns_home: boolean | null

  disability_status: YesNoUnknown

  student_status: YesNoUnknown

  marital_status: "SINGLE" | "MARRIED" | "DIVORCED" | "WIDOWED" | "UNKNOWN"

  children_count: number | null

  qualifications: string[]

  additional_conditions: Record<string, JsonValue>
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

  detail_url?: string

  application_start_date?: string

  application_end_date?: string

  published_at?: string

  application_period_type?: "DATED" | "ALWAYS"
}

export interface MatchedPoliciesResponse {
  matched_count: number

  policies: MatchedPolicy[]

  evaluated_count?: number

  needs_review_count?: number

  ineligible_count?: number

  analysis_results?: PolicyAnalysis[]
}

export interface ConditionAnalysis {
  condition_type: string

  status: string

  current_value: string

  required_value: string

  message: string

  action_guide: string

  source_field: string

  source_text: string

  condition_guide?: string

  guide_kind?: "state_change" | null

  reason_code?: string | null
}

export interface PolicyAnalysis {
  policy_id: string

  title: string

  status: "eligible" | "ineligible" | "needs_review"

  match_score: number

  evaluated_conditions: number

  passed_conditions: number

  gap_conditions: ConditionAnalysis[]

  review_conditions: ConditionAnalysis[]

  recommendation_status?: RecommendationStatus

  recommendation_reason?: string

  recommendation_uncertainty?: string | null

  confirmed_conditions?: ConditionAnalysis[]

  eligibility_paths?: EligibilityPathAnalysis[]

  matched_path_id?: string | null

  blocked_by_common?: string[]

  preferences?: string[]

  path_review?: "reviewed" | "converted" | null

  notes: string[]

  detail_url: string
}

export interface EligibilityPathCondition {
  condition_type: string

  status: "passed" | "failed" | "needs_review"

  current_value: string

  required_value: string

  evidence: string

  // 모든 경로에 공통인 조건(이전 결과에는 없음)
  common?: boolean

  // 정의상 다시 충족할 수 없는 미충족(나이·혼인 기간 상한 초과 등). 이전 결과에는 없음
  impossible?: boolean

  // 미충족 조건의 개선 난이도(추천 경로 계산용). 이전 결과에는 없음
  difficulty?: number | null

  // 난이도 종류(apply·money·time·life·family·identity·other). 사용자 가중치를 곱할 때 쓴다
  difficulty_group?: string | null

  // 백엔드가 생성한 조건 단위 안내. 이전 스냅샷에는 없을 수 있다.
  condition_guide?: string

  reason_code?: string | null

  guide_kind?: "state_change" | null
}

export interface EligibilityPathAnalysis {
  path_id: string

  label: string

  kind: string

  priority: number | null

  status: "eligible" | "needs_review" | "ineligible"

  conditions: EligibilityPathCondition[]

  checks: string[]

  // 사실 기반 순위(0이 가장 가까움, 같은 값은 우열 없음)와 다시 충족할 수 없는 경로 여부. 이전 결과에는 없음
  rank?: number | null

  impossible?: boolean

  // 미충족 조건 개선 난이도의 합(낮을수록 추천). 이전 결과에는 없음
  difficulty?: number | null
}

export type RecommendationStatus =
  | "priority_recommendation"
  | "priority_consideration"
  | "condition_mismatch"
  | "additional_review"

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

// 매번 본인 확인 후에만 조회하며 진단/관심 정책 스냅샷에 합치지 않는다.
export interface ConditionGuideTarget {
  snapshot: "current" | "diagnosis"
  profile_key: string
  checked_at: string
  policy_id: string
}

export interface PrivateConditionGuides {
  profile_key: string
  checked_at: string
  policy_id: string
  // gap_index: 대표 경로 미충족 순번. 경로별 안내는 path_id + condition_index(경로 조건 순번)로 가리킨다.
  items: { gap_index?: number | null; path_id?: string | null; condition_index?: number | null
    condition_guide: string; guide_kind: "state_change" }[]
  difficulties?: PrivateConditionDifficulty[]
  unavailable_reason?: string | null
}

// 로그인 전용 응답의 메모리 데이터. PolicyRow/스냅샷에 병합하지 않는다.
export interface PrivateConditionDifficulty {
  path_id: string
  condition_index: number
  difficulty: number | null
  difficulty_group: string | null
}
