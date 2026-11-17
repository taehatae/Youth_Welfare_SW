import type { ConditionGuideTarget, EligibilityPathAnalysis, PrivateConditionGuides } from "../types/welfareApi"
import { getDifficultyPrefs, weighted, type DifficultyPrefs } from "./difficultyPrefs"

// 안내를 생성하거나 조건을 재판정하지 않는다. 백엔드가 인증한 변화 안내의 표시만 결정한다.
export const samePolicyText = (a?: string, b?: string) => {
  const normalize = (value?: string) => (value ?? "").replace(/\s+/gu, "").replace(/[.!。]+$/u, "")
  return normalize(a) === normalize(b)
}

export function stateChangeGuide(
  guide: string | undefined, kind: "state_change" | null | undefined,
  required: string, evidence: string | undefined, failed: boolean,
): string | null {
  if (!failed || kind !== "state_change" || !guide?.trim()) return null
  if (samePolicyText(guide, required) || samePolicyText(guide, evidence)) return null
  return guide
}

// 맞춤 안내의 위치 키. 대표 경로 미충족은 "gap:순번", 경로별 조건은 "path:경로id:조건순번".
export const gapKey = (index: number) => `gap:${index}`
export const pathConditionKey = (pathId: string, index: number) => `path:${pathId}:${index}`
const validIndex = (n: unknown): n is number => Number.isInteger(n) && (n as number) >= 0
function guideKey(r: PrivateConditionGuides["items"][number]): string | null {
  if (validIndex(r.gap_index) && r.path_id == null) return gapKey(r.gap_index)
  if (r.gap_index == null && typeof r.path_id === "string" && r.path_id && validIndex(r.condition_index))
    return pathConditionKey(r.path_id, r.condition_index)
  return null
}
export const guideTargetKey = (target: ConditionGuideTarget) => JSON.stringify([
  target.snapshot, target.profile_key, target.checked_at, target.policy_id,
])

// 컴포넌트 수명 안에서만 사용하는 비공개 메모리. 응답/정책 객체와 저장소를 수정하지 않는다.
export function createPrivateGuideSession() {
  let generation = 0
  let activeKey = ""
  let items = new Map<string, string>()
  const clear = () => { generation++; activeKey = ""; items = new Map() }
  return {
    clear,
    begin(target: ConditionGuideTarget) {
      // 같은 진단을 다시 확인할 때는 응답이 올 때까지 기존 안내를 유지해 화면이 깜빡이지 않게 한다.
      const key = guideTargetKey(target)
      if (key === activeKey) generation++
      else { clear(); activeKey = key }
      return { generation, key: activeKey }
    },
    accept(target: ConditionGuideTarget, ticket: { generation: number; key: string }, response: PrivateConditionGuides) {
      if (ticket.generation !== generation || ticket.key !== guideTargetKey(target) || ticket.key !== activeKey ||
          response.profile_key !== target.profile_key || response.checked_at !== target.checked_at || response.policy_id !== target.policy_id ||
          !Array.isArray(response.items) || response.items.some((r) => guideKey(r) === null ||
            r.guide_kind !== "state_change" || typeof r.condition_guide !== "string" || !r.condition_guide.trim()) ||
          new Set(response.items.map(guideKey)).size !== response.items.length) return false
      items = new Map(response.items.map((r) => [guideKey(r)!, r.condition_guide]))
      return true
    },
    read(target: ConditionGuideTarget): ReadonlyMap<string, string> {
      if (guideTargetKey(target) !== activeKey) clear()
      return items
    },
  }
}

// 표시용 메모리의 수명과 늦은 응답 폐기를 관리한다. 진단 결과 자체는 변경하지 않는다.
export function createPrivateGuideLoader(
  request: (target: ConditionGuideTarget) => Promise<PrivateConditionGuides>,
  changed: () => void,
) {
  const session = createPrivateGuideSession()
  let generation = 0
  let status: "idle" | "loading" | "ready" | "error" = "idle"
  let error = ""
  return {
    clear(message = "") {
      generation++; session.clear(); status = message ? "error" : "idle"; error = message; changed()
    },
    async load(target: ConditionGuideTarget) {
      const shown = session.read(target).size > 0
      const version = ++generation, ticket = session.begin(target)
      // 재검증 중에는 '불러오는 중'을 다시 띄우지 않는다.
      if (!shown) status = "loading"
      error = ""; changed()
      try {
        const response = await request(target)
        if (version !== generation) return
        if (!session.accept(target, ticket, response)) throw new Error("snapshot mismatch")
        status = "ready"
      } catch (e) {
        if (version !== generation) return
        session.clear(); status = "error"
        error = (e as { status?: number })?.status === 401
          ? "로그인이 만료되었거나 계정이 변경됐어요. 다시 로그인해주세요."
          : "맞춤 안내를 불러오지 못했어요. 기본 안내를 확인하거나 화면을 다시 열어주세요."
      }
      changed()
    },
    read(target: ConditionGuideTarget) { return { guides: session.read(target), status, error } },
  }
}

export type GuideLine = { key: string; field: string; required: string; evidence: string; guide?: string
  guideKind?: "state_change" | null; common: boolean }
export type PathCard = { pathId: string; label: string; labels: string[]; rank: number; impossible: boolean; statusRank: number
  difficulty: number | null; failed: GuideLine[]; review: GuideLine[]; checks: string[]; passed: string[]
  passedLines: GuideLine[] }
export type PathTab = "failed" | "review" | "passed"


// 다른 경로 중 탭에 보일 내용이 똑같은 경로는 카드 하나로 합친다(경로 이름만 나열).
const signature = (c: PathCard, tab: PathTab) =>
  (tab === "failed" ? c.failed.map((l) => `${l.field}=${l.required}`)
    : tab === "passed" ? c.passedLines.map((l) => `${l.field}=${l.required}`)
      : [...c.review.map((l) => `${l.field}=${l.required}`), ...c.checks]).join("\n")
function mergeSame(cards: PathCard[], tab: PathTab): PathCard[] {
  const out: PathCard[] = [], seen = new Map<string, PathCard>()
  for (const card of cards) {
    const key = signature(card, tab), found = seen.get(key)
    if (found) { found.labels.push(card.label); found.passed = []; continue }
    const copy = { ...card, labels: [card.label] }
    seen.set(key, copy); out.push(copy)
  }
  return out
}

// 경로 카드: 경로마다 미충족·미입력 조건(공통 조건 포함)과 확인 사항을 모은다.
// 순위: 판정(가능 > 확인 필요 > 불가) → 다시 충족할 수 없는 경로는 뒤 → 사용자 가중치를 곱한 난이도 합
// → 미충족 수 → 백엔드 순위. 맨 앞 하나만 추천 경로다. 가중치를 바꾸지 않으면 백엔드 순위와 같다.
// 시간이 지나도 다시 충족할 수 없는 경로(나이 상한 초과 등)는 숨긴다. 모든 경로가 그렇다면 이유를 보여주려고 남긴다.
const STATUS_RANK: Record<string, number> = { eligible: 0, needs_review: 1, ineligible: 2 }
export function pathCards(paths: EligibilityPathAnalysis[] | undefined, tab: PathTab = "failed",
  prefs: DifficultyPrefs = getDifficultyPrefs()) {
  const cards: PathCard[] = (paths ?? []).map((path) => {
    const pick = (status: string) => path.conditions.flatMap((c, i) => c.status === status ? [{
      key: pathConditionKey(path.path_id, i), field: c.condition_type, required: c.required_value, evidence: c.evidence,
      guide: c.condition_guide, guideKind: c.guide_kind, common: !!c.common }] : [])
      .sort((a, b) => Number(b.common) - Number(a.common))
    const failed = pick("failed")
    const score = path.conditions.reduce((sum, c) => sum + (c.status === "failed" ? weighted(c.difficulty, c.difficulty_group, prefs) : 0), 0)
    return { pathId: path.path_id, label: path.label, labels: [path.label], impossible: !!path.impossible,
      difficulty: path.difficulty == null ? null : Math.round(score * 100) / 100, statusRank: STATUS_RANK[path.status] ?? 2,
      rank: path.rank ?? failed.length, failed, review: pick("needs_review"), checks: path.checks, passedLines: pick("passed"),
      passed: path.conditions.filter((c) => c.status === "passed").map((c) => c.condition_type) }
  })
  const possible = cards.filter((c) => !c.impossible)
  const scored = cards.every((c) => c.difficulty != null || !c.failed.length)
  // 추천 경로는 순위 0(개선 난이도 합이 가장 낮은 경로) 하나다.
  const sorted = (possible.length ? possible : cards)
    .map((c, i) => [c, i] as const)
    .sort(([a, i], [b, j]) => a.statusRank - b.statusRank
      // 난이도 점수가 없는 이전 결과가 섞이면 다시 매기지 않고 백엔드 순위를 따른다.
      || (scored ? (a.difficulty ?? 0) - (b.difficulty ?? 0) || a.failed.length - b.failed.length : 0)
      || a.rank - b.rank || i - j).map(([c]) => c)
  return { best: sorted.slice(0, 1), others: mergeSame(sorted.slice(1), tab),
    hidden: possible.length ? cards.length - possible.length : 0, allImpossible: !possible.length && !!cards.length }
}

export type OtherPathCondition = {
  field: string; required: string; evidence: string; status: "passed" | "failed" | "needs_review"
  labels: string[]; conditionGuide?: string; guideKind?: "state_change" | null
}
export type OtherPathCheck = { text: string; labels: string[] }

// 대표 경로 밖의 조건도 모두 보여주되, 같은 조건(항목+기준)은 한 줄로 합치고 어느 경로의 조건인지 붙인다.
export function otherPathDetails(paths: EligibilityPathAnalysis[] | undefined, matchedPathId?: string | null) {
  const conditions: OtherPathCondition[] = [], checks: OtherPathCheck[] = []
  if (!paths || paths.length < 2) return { conditions, checks }
  const main = paths.find((p) => p.path_id === matchedPathId) ?? paths[0]
  const shown = new Set(main.conditions.map((c) => `${c.condition_type}|${c.required_value}`))
  const shownChecks = new Set(main.checks)
  const byKey = new Map<string, OtherPathCondition>(), byCheck = new Map<string, OtherPathCheck>()
  for (const path of paths) {
    if (path === main) continue
    for (const c of path.conditions) {
      const key = `${c.condition_type}|${c.required_value}`
      if (shown.has(key)) continue
      const found = byKey.get(key)
      if (found) { if (!found.labels.includes(path.label)) found.labels.push(path.label); continue }
      const row: OtherPathCondition = { field: c.condition_type, required: c.required_value, evidence: c.evidence,
        status: c.status, labels: [path.label], conditionGuide: c.condition_guide, guideKind: c.guide_kind }
      byKey.set(key, row); conditions.push(row)
    }
    for (const text of path.checks) {
      if (shownChecks.has(text)) continue
      const found = byCheck.get(text)
      if (found) { if (!found.labels.includes(path.label)) found.labels.push(path.label); continue }
      const row = { text, labels: [path.label] }
      byCheck.set(text, row); checks.push(row)
    }
  }
  return { conditions, checks }
}
