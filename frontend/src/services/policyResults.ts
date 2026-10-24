import type { Snapshot } from "./analysisSession"

import type { UserProfileInput } from "../types/welfareApi"

export type PolicyStatus = "eligible" | "ineligible" | "needs_review"

export interface PolicyRow {
  id: string

  title: string

  status: PolicyStatus

  url?: string

  description: string

  counts?: {
    evaluated: number
    passed: number
    failed: number
    review: number
  }

  conditions: {
    field: string
    current: string
    required: string
    status: string
    guide: string
  }[]
}

export const trackingLabels = {
  interested: "관심 있음",
  preparing: "준비 중",
  applied: "신청 완료",
  archived: "보관",
} as const
export type TrackingStatus = keyof typeof trackingLabels

export interface SavedPolicy {
  profileKey: string

  profile: UserProfileInput | null

  policy: PolicyRow

  savedAt: string
  trackingStatus?: TrackingStatus
  note?: string
}

const stable = (value: unknown): string => {
  if (Array.isArray(value)) return JSON.stringify(value.map(stable))

  if (value && typeof value === "object")
    return JSON.stringify(
      Object.entries(value)
        .sort(([a], [b]) => a.localeCompare(b))
        .map(([k, v]) => [k, stable(v)]),
    )

  return JSON.stringify(value) ?? "null"
}

// 같은 입력으로 재진단해 사용자 ID가 바뀌어도 동일 프로필의 목록을 사용한다.

export const profileKey = (profile: UserProfileInput) => stable(profile)

export function policyResults(snapshot: Snapshot): PolicyRow[] {
  const rows = new Map<string, PolicyRow>()

  for (const p of snapshot.analysis.matched.analysis_results ?? [])
    rows.set(p.policy_id, {
      id: p.policy_id,
      title: p.title,

      status:
        p.status === "eligible" || p.status === "ineligible"
          ? p.status
          : "needs_review",

      url: p.detail_url,
      description: (p.notes ?? []).join(" "),

      counts:
        Number.isInteger(p.evaluated_conditions) &&
        p.evaluated_conditions >= 0 &&
        Number.isInteger(p.passed_conditions) &&
        p.passed_conditions >= 0 &&
        p.passed_conditions <= p.evaluated_conditions
          ? {
              evaluated: p.evaluated_conditions,
              passed: p.passed_conditions,
              failed: p.gap_conditions.length,
              review: p.review_conditions.length,
            }
          : undefined,

      conditions: [
        ...p.gap_conditions.map((c) => ({
          field: c.condition_type,
          current: c.current_value,
          required: c.required_value,
          status: "미충족",
          guide: c.action_guide || c.message,
        })),

        ...p.review_conditions.map((c) => ({
          field: c.condition_type,
          current: c.current_value,
          required: c.required_value,
          status: "추가 확인",
          guide: c.action_guide || c.message,
        })),
      ],
    })

  for (const p of snapshot.analysis.matched.policies) {
    const existing = rows.get(p.policy_id)

    rows.set(p.policy_id, {
      id: p.policy_id,
      title: p.title,
      status: existing?.status ?? "eligible",
      url: p.detail_url || existing?.url,
      description: p.support_amount,
      counts: existing?.counts,
      conditions: existing?.conditions ?? [],
    })
  }

  for (const r of snapshot.analysis.reverse.recommendations) {
    // 추천 API에는 ID가 없어 제목이 같은 분석 결과를 보완한다.

    const existing = [...rows.values()].find((p) => p.title === r.target_policy)

    const id = existing?.id ?? `recommendation:${r.target_policy}`

    rows.set(id, {
      id,
      title: r.target_policy,
      status:
        existing?.status ?? (r.current_eligibility ? "eligible" : "ineligible"),
      url: existing?.url,
      description: existing?.description ?? "",
      counts: existing?.counts,
      conditions: [
        ...(existing?.conditions ?? []),

        ...r.missing_conditions.map((c) => ({
          field: c.field,
          current: c.current_value,
          required: c.required_value,
          status: "필요 조건",
          guide: c.action_guide,
        })),
      ],
    })
  }

  return [...rows.values()]
}

export function restoreSavedPolicies(raw: string | null): SavedPolicy[] {
  if (!raw) return []

  const value: unknown = JSON.parse(raw)

  if (
    !Array.isArray(value) ||
    !value.every(
      (item) =>
        item &&
        typeof item.profileKey === "string" &&
        (item.profile === null || (item.profile &&
        typeof item.profile.age === "number" &&
        typeof item.profile.region === "string")) &&
        typeof item.savedAt === "string" &&
        Number.isFinite(Date.parse(item.savedAt)) &&
        item.policy &&
        typeof item.policy.id === "string" &&
        typeof item.policy.title === "string" &&
        typeof item.policy.description === "string" &&
        ["eligible", "ineligible", "needs_review"].includes(
          item.policy.status,
        ) &&
        (item.policy.url == null ||
          typeof item.policy.url === "string") &&
        Array.isArray(item.policy.conditions) &&
        item.policy.conditions.every(
          (c: Record<string, unknown>) =>
            c &&
            ["field", "current", "required", "status", "guide"].every(
              (k) => typeof c[k] === "string",
            ),
        ),
    )
  )
    throw new Error("관심 정책 저장 형식 오류")

  return (value as SavedPolicy[]).map((item) => {
    const counts = item.policy.counts

    const valid =
      counts &&
      [counts.evaluated, counts.passed, counts.failed, counts.review].every(
        (n) => Number.isInteger(n) && n >= 0,
      ) &&
      counts.passed <= counts.evaluated

    return {
      ...item,
      trackingStatus: item.trackingStatus && Object.prototype.hasOwnProperty.call(trackingLabels, item.trackingStatus) ? item.trackingStatus : "interested",
      note: typeof item.note === "string" ? item.note : "",
      policy: { ...item.policy, url: item.policy.url ?? undefined, counts: valid ? counts : undefined },
    }
  })
}
