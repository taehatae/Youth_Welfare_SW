import type {
  MatchedPoliciesResponse,
  ReverseRecommendationsResponse,
  SaveProfileResponse,
  UserProfileInput,
  WelfareAnalysis,
} from "../types/welfareApi"

import { DEMO_ANALYSIS } from "../data/demoAnalysis"

import { isSnapshot } from "./analysisSession"

export const IS_DEMO_MODE = import.meta.env.VITE_DEMO_MODE === "true"

const API_BASE_URL = (
  import.meta.env.VITE_API_BASE_URL || "http://localhost:8000/api/v1"
).replace(/\/$/, "")

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const controller = new AbortController()

  const timeout = window.setTimeout(() => controller.abort(), 20000)

  try {
    const response = await fetch(`${API_BASE_URL}${path}`, {
      ...init,

      signal: controller.signal,

      headers: { "Content-Type": "application/json", ...init?.headers },
    })

    if (!response.ok) {
      throw new Error(
        response.status === 404
          ? "저장된 프로필을 찾지 못했어요. 내 정보를 확인한 뒤 다시 진단해주세요."
          : response.status === 422
            ? "서버에서 입력값을 처리하지 못했어요. 선택한 정보를 확인해주세요."
            : "조회에 실패했어요. 잠시 후 다시 시도해주세요.",
      )
    }

    return (await response.json()) as T
  } catch (error) {
    if (controller.signal.aborted)
      throw new Error("응답이 지연되고 있어요. 잠시 후 다시 시도해주세요.")

    if (error instanceof TypeError)
      throw new Error(
        "서버에 연결하지 못했어요. 입력한 내용은 유지됩니다. 잠시 후 다시 시도해주세요.",
      )

    if (error instanceof SyntaxError)
      throw new Error("서버 응답을 읽지 못했어요. 잠시 후 다시 시도해주세요.")

    throw error
  } finally {
    window.clearTimeout(timeout)
  }
}

export async function analyzeWelfareProfile(
  profile: UserProfileInput,
): Promise<WelfareAnalysis> {
  if (IS_DEMO_MODE) {
    await new Promise((resolve) => window.setTimeout(resolve, 650))

    return structuredClone(DEMO_ANALYSIS)
  }

  const saved = await request<SaveProfileResponse>("/users/profile", {
    method: "POST",

    body: JSON.stringify({
      ...profile,
      employment_status:
        profile.employment_status === "PART_TIME"
          ? "OTHER"
          : profile.employment_status,
    }),
  })

  if (!saved.user_id) throw new Error("프로필 저장 응답에 user_id가 없습니다.")

  return refreshWelfareAnalysis(saved.user_id, profile)
}

export async function refreshWelfareAnalysis(
  savedUserId: string,
  profile: UserProfileInput,
): Promise<WelfareAnalysis> {
  if (IS_DEMO_MODE) {
    await new Promise((resolve) => window.setTimeout(resolve, 650))

    return structuredClone(DEMO_ANALYSIS)
  }

  const userId = encodeURIComponent(savedUserId)

  const [matched, reverse] = await Promise.all([
    request<MatchedPoliciesResponse>(`/welfare/matched?user_id=${userId}`),

    request<ReverseRecommendationsResponse>(
      `/welfare/reverse-engineering?user_id=${userId}`,
    ),
  ])

  const result = { userId: savedUserId, matched, reverse }

  if (
    !isSnapshot({
      profile,
      analysis: result,
      checkedAt: new Date().toISOString(),
    })
  )
    throw new Error(
      "조회 결과의 형식이 올바르지 않아요. 이전 결과는 유지됩니다.",
    )

  result.matched.policies = result.matched.policies.map((policy) => ({
    ...policy,

    detail_url:
      policy.detail_url ||
      result.matched.analysis_results?.find(
        (item) => item.policy_id === policy.policy_id,
      )?.detail_url,
  }))

  return result
}
