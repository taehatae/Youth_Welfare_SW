import { EMPTY_DRAFT, isDraft, type ProfileDraft } from "../data/profileOptions"
import type {
  MatchedPolicy,
  UserProfileInput,
  WelfareAnalysis,
} from "../types/welfareApi"

export interface Snapshot {
  profile: UserProfileInput | null
  profileKey?: string
  analysis: WelfareAnalysis
  checkedAt: string
}
export interface AnalysisSession {
  draft: ProfileDraft
  step: number
  diagnosis: Snapshot | null
  previousDiagnosis: Snapshot | null
  current: Snapshot | null
  previous: Snapshot | null
  knownPolicies: MatchedPolicy[]
}
export const emptySession = (): AnalysisSession => ({
  draft: { ...EMPTY_DRAFT, qualifications: [] },
  step: 0,
  diagnosis: null,
  previousDiagnosis: null,
  current: null,
  previous: null,
  knownPolicies: [],
})
export const storageKey = (demo: boolean) =>
  "youth-welfare:session:v2:" + (demo ? "demo" : "live")
export function isSnapshot(value: unknown): value is Snapshot {
  try {
    if (!value || typeof value !== "object") return false
    const s = value as Snapshot
    return (
      typeof s.checkedAt === "string" &&
      Number.isFinite(Date.parse(s.checkedAt)) &&
      (s.profile === null || (typeof s.profile?.age === "number" &&
      typeof s.profile?.region === "string" &&
      typeof s.profile?.income_level === "number" &&
      typeof s.profile?.employment_status === "string" &&
      !!s.profile?.eligibility_conditions)) &&
      typeof s.analysis?.userId === "string" &&
      Array.isArray(s.analysis?.matched?.policies) &&
      s.analysis.matched.policies.every(isMatchedPolicy) &&
      Array.isArray(s.analysis?.reverse?.recommendations) &&
      s.analysis.reverse.recommendations.every(
        (p) =>
          typeof p.target_policy === "string" &&
          typeof p.current_eligibility === "boolean" &&
          Array.isArray(p.missing_conditions) &&
          p.missing_conditions.every((c) =>
            ["field", "current_value", "required_value", "action_guide"].every(
              (key) => typeof c[(key as keyof typeof c)] === "string",
            ),
          ),
      ) &&
      (s.analysis.matched.analysis_results === undefined ||
        (Array.isArray(s.analysis.matched.analysis_results) &&
          s.analysis.matched.analysis_results.every(
            (p) =>
              typeof p.title === "string" &&
              Array.isArray(p.gap_conditions) &&
              Array.isArray(p.review_conditions) &&
              (p.recommendation_status === undefined ||
                [
                  "priority_recommendation",
                  "priority_consideration",
                  "condition_mismatch",
                  "additional_review",
                ].includes(p.recommendation_status)) &&
              (p.recommendation_reason === undefined ||
                typeof p.recommendation_reason === "string") &&
              (p.recommendation_uncertainty === undefined ||
                p.recommendation_uncertainty === null ||
                typeof p.recommendation_uncertainty === "string") &&
              (p.confirmed_conditions === undefined ||
                (Array.isArray(p.confirmed_conditions) &&
                  p.confirmed_conditions.every((c) =>
                    [
                      "condition_type",
                      "status",
                      "message",
                      "current_value",
                      "required_value",
                      "action_guide",
                    ].every(
                      (key) => typeof c[(key as keyof typeof c)] === "string",
                    ),
                  ))) &&
              [...p.gap_conditions, ...p.review_conditions].every((c) =>
                [
                  "condition_type",
                  "status",
                  "message",
                  "current_value",
                  "required_value",
                  "action_guide",
                ].every(
                  (key) => typeof c[(key as keyof typeof c)] === "string",
                ),
              ),
          )))
    )
  } catch {
    return false
  }
}
export function isMatchedPolicy(value: unknown): value is MatchedPolicy {
  if (!value || typeof value !== "object") return false
  const p = value as Record<string, unknown>
  return (
    ["policy_id", "title", "category", "support_amount"].every(
      (key) => typeof p[key] === "string",
    ) &&
    [
      "detail_url",
      "application_start_date",
      "application_end_date",
      "published_at",
      "application_period_type",
    ].every((key) => p[key] == null || typeof p[key] === "string")
  )
}
export function restoreSession(raw: string | null): AnalysisSession {
  if (!raw) return emptySession()
  const value = JSON.parse(raw) as AnalysisSession
  if (
    !value ||
    !isDraft(value.draft) ||
    !Number.isInteger(value.step) ||
    value.step < 0 ||
    value.step > 5 ||
    ![
      value.diagnosis,
      value.current,
      value.previous,
      value.previousDiagnosis ?? null,
    ].every((s) => s === null || isSnapshot(s)) ||
    !Array.isArray(value.knownPolicies) ||
    !value.knownPolicies.every(isMatchedPolicy)
  )
    throw new Error("저장 형식 오류")
  return { ...value, previousDiagnosis: value.previousDiagnosis ?? null }
}
export const formatTime = (value: string) =>
  new Date(value).toLocaleString("ko-KR", {
    timeZone: "Asia/Seoul",
    dateStyle: "medium",
    timeStyle: "short",
  })
export function koreaDate(now = new Date()): string {
  const parts = new Intl.DateTimeFormat("en-US", {
    timeZone: "Asia/Seoul",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).formatToParts(now)
  return ["year", "month", "day"]
    .map((type) => parts.find((p) => p.type === type)?.value)
    .join("-")
}
export function validDate(value: unknown): value is string {
  return (
    typeof value === "string" &&
    /^\d{4}-\d{2}-\d{2}$/.test(value) &&
    Number.isFinite(Date.parse(value)) &&
    new Date(value).toISOString().slice(0, 10) === value
  )
}
export type ApplicationState = "open" | "expired" | "upcoming" | "unknown"
export const applicationLabels: Record<ApplicationState, string> = {
  open: "접수 기간 내",
  expired: "신청 종료",
  upcoming: "접수 예정",
  unknown: "기간 확인 필요",
}
export function applicationState(
  policy: MatchedPolicy,
  today: string,
): ApplicationState {
  const start = policy.application_start_date,
    end = policy.application_end_date
  if (
    (start && !validDate(start)) ||
    (end && !validDate(end)) ||
    (start && end && start > end)
  )
    return "unknown"
  if (end && end < today) return "expired"
  if (start && start > today) return "upcoming"
  if (policy.application_period_type === "ALWAYS" || end) return "open"
  return "unknown"
}
export function safeOfficialUrl(value?: string): string | undefined {
  if (!value) return undefined
  try {
    const url = new URL(value)
    return ["https:", "http:"].includes(url.protocol) ? url.href : undefined
  } catch {
    return undefined
  }
}
