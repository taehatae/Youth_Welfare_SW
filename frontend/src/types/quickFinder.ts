import type { MatchedPoliciesResponse } from "./welfareApi"

// 간편 정책 찾기 공개 API(backend/app/schemas/quick_finder.py)와 같은 형식.
export interface QuickCategory {
  id: string
  label: string
  policy_count: number
}

export interface QuickCategoryDetail extends QuickCategory {
  path_policy_count: number
  questions: string[]
  question_policy_counts: Record<string, number>
  fields: { field: string; policy_count: number; questions: string[] }[]
  unsupported_fields: string[]
  check_count: number
}

// 입력하지 않은 항목은 보내지 않는다(서버도 기본값을 채우지 않는다).
export type QuickAnswers = { age: number } & Record<string, string | number | string[]>

// 문장 해석 결과. 알아듣지 못하면 category가 null이다.
export interface QuickInterpretResponse {
  category: string | null
  category_label: string | null
  keywords: string[]
  source: "llm" | "dictionary" | "none"
}

export interface QuickEvaluateResponse {
  category: string
  category_label: string
  evaluated_at: string
  matched: MatchedPoliciesResponse
}
