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
