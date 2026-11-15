import type { ConditionGuideTarget, PrivateConditionGuides } from "../types/welfareApi"

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

export const guideTargetKey = (target: ConditionGuideTarget) => JSON.stringify([
  target.snapshot, target.profile_key, target.checked_at, target.policy_id,
])

// 컴포넌트 수명 안에서만 사용하는 비공개 메모리. 응답/정책 객체와 저장소를 수정하지 않는다.
export function createPrivateGuideSession() {
  let generation = 0
  let activeKey = ""
  let items = new Map<number, string>()
  const clear = () => { generation++; activeKey = ""; items = new Map() }
  return {
    clear,
    begin(target: ConditionGuideTarget) {
      clear()
      activeKey = guideTargetKey(target)
      return { generation, key: activeKey }
    },
    accept(target: ConditionGuideTarget, ticket: { generation: number; key: string }, response: PrivateConditionGuides) {
      if (ticket.generation !== generation || ticket.key !== guideTargetKey(target) || ticket.key !== activeKey ||
          response.profile_key !== target.profile_key || response.checked_at !== target.checked_at || response.policy_id !== target.policy_id ||
          !Array.isArray(response.items) || response.items.some((r) => !Number.isInteger(r.gap_index) || r.gap_index < 0 ||
            r.guide_kind !== "state_change" || typeof r.condition_guide !== "string" || !r.condition_guide.trim()) ||
          new Set(response.items.map((r) => r.gap_index)).size !== response.items.length) return false
      items = new Map(response.items.map((r) => [r.gap_index, r.condition_guide]))
      return true
    },
    read(target: ConditionGuideTarget): ReadonlyMap<number, string> {
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
      const version = ++generation, ticket = session.begin(target)
      status = "loading"; error = ""; changed()
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
