import type { Snapshot } from "./analysisSession"
import type { UserProfileInput } from "../types/welfareApi"

export type PolicyStatus = "eligible" | "ineligible" | "needs_review"
export interface PolicyRow {
  id: string
  title: string
  status: PolicyStatus
  url?: string
  description: string
  conditions: { field: string; current: string; required: string; status: string; guide: string }[]
}
export interface SavedPolicy {
  profileKey: string
  profile: UserProfileInput
  policy: PolicyRow
  savedAt: string
}
const stable = (value: unknown): string => {
  if (Array.isArray(value)) return JSON.stringify(value.map(stable))
  if (value && typeof value === "object") return JSON.stringify(Object.entries(value).sort(([a], [b]) => a.localeCompare(b)).map(([k, v]) => [k, stable(v)]))
  return JSON.stringify(value) ?? "null"
}
// 같은 입력으로 재진단해 사용자 ID가 바뀌어도 동일 프로필의 목록을 사용한다.
export const profileKey = (profile: UserProfileInput) => stable(profile)
export function policyResults(snapshot: Snapshot): PolicyRow[] {
  const rows = new Map<string, PolicyRow>()
  for (const p of snapshot.analysis.matched.analysis_results ?? []) rows.set(p.policy_id, {
    id: p.policy_id, title: p.title,
    status: p.status === "eligible" || p.status === "ineligible" ? p.status : "needs_review",
    url: p.detail_url, description: p.notes.join(" "),
    conditions: [
      ...p.gap_conditions.map(c => ({ field: c.condition_type, current: c.current_value, required: c.required_value, status: "미충족", guide: c.action_guide || c.message })),
      ...p.review_conditions.map(c => ({ field: c.condition_type, current: c.current_value, required: c.required_value, status: "추가 확인", guide: c.action_guide || c.message })),
    ],
  })
  for (const p of snapshot.analysis.matched.policies) {
    const existing = rows.get(p.policy_id)
    rows.set(p.policy_id, { id: p.policy_id, title: p.title, status: existing?.status ?? "eligible", url: p.detail_url || existing?.url, description: p.support_amount, conditions: existing?.conditions ?? [] })
  }
  for (const r of snapshot.analysis.reverse.recommendations) {
    // 추천 API에는 ID가 없어 제목이 같은 분석 결과를 보완한다.
    const existing = [...rows.values()].find(p => p.title === r.target_policy)
    const id = existing?.id ?? `recommendation:${r.target_policy}`
    rows.set(id, { id, title: r.target_policy, status: existing?.status ?? (r.current_eligibility ? "eligible" : "ineligible"), url: existing?.url, description: existing?.description ?? "", conditions: [
      ...(existing?.conditions ?? []),
      ...r.missing_conditions.map(c => ({ field: c.field, current: c.current_value, required: c.required_value, status: "필요 조건", guide: c.action_guide })),
    ] })
  }
  return [...rows.values()]
}
export function restoreSavedPolicies(raw: string | null): SavedPolicy[] {
  if (!raw) return []
  const value: unknown = JSON.parse(raw)
  if (!Array.isArray(value) || !value.every(item => item && typeof item.profileKey === "string" && item.profile && item.profileKey === profileKey(item.profile) && typeof item.profile.age === "number" && typeof item.profile.region === "string" && typeof item.savedAt === "string" && Number.isFinite(Date.parse(item.savedAt)) && item.policy && typeof item.policy.id === "string" && typeof item.policy.title === "string" && typeof item.policy.description === "string" && ["eligible", "ineligible", "needs_review"].includes(item.policy.status) && (item.policy.url === undefined || typeof item.policy.url === "string") && Array.isArray(item.policy.conditions) && item.policy.conditions.every((c: Record<string, unknown>) => c && ["field", "current", "required", "status", "guide"].every(k => typeof c[k] === "string")))) throw new Error("관심 정책 저장 형식 오류")
  return value as SavedPolicy[]
}
