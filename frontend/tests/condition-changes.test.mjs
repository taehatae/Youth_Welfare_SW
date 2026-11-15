import test from "node:test"
import assert from "node:assert/strict"
import { createElement as h } from "react"
import { renderToStaticMarkup } from "react-dom/server"
import { PolicyConditionPanel } from "../src/components/policy/AnalysisPolicyCard.tsx"

const condition = (extra = {}) => ({ condition_type: "본인 월소득", status: "failed", current_value: "프로필 보호 중",
  required_value: "본인 월소득 2,699,999원 이하", evidence: "원문: 보수 270만원 미만", ...extra })
const view = (rows) => renderToStaticMarkup(h(PolicyConditionPanel, { tab: "failed", policy: {
  id: "synthetic", title: "합성 정책", status: "ineligible", description: "", conditions: rows.map((c) => ({
    field: c.condition_type, status: c.status === "failed" ? "미충족" : c.status === "passed" ? "충족" : "추가 확인",
    current: c.current_value, required: c.required_value, evidence: c.evidence,
    conditionGuide: c.condition_guide, guideKind: c.guide_kind,
  })),
} }))

test("인증된 상태 변화 안내만 별도 역설계 영역에 표시한다", () => {
  const guide = "입력된 본인 월소득이 상한보다 높아 미충족입니다. 낮아져 2,699,999원 이하가 되면 이 조건을 충족합니다."
  const html = view([condition({ guide_kind: "state_change", condition_guide: guide })])
  assert.match(html, /역설계 안내/)
  assert.ok(html.includes(guide))
  assert.doesNotMatch(html, /충족 기준 안내/)
})

for (const extra of [
  {},
  { condition_guide: "소득이 기준 이하여야 합니다." },
  { guide_kind: "state_change", condition_guide: "" },
  { guide_kind: "state_change", condition_guide: "본인 월소득 2,699,999원 이하" },
  { guide_kind: "state_change", condition_guide: "원문: 보수 270만원 미만" },
  { guide_kind: "state_change", condition_guide: " 본인 월소득 2,699,999원 이하. " },
  { guide_kind: "state_change", condition_guide: "나이가 증가하면 조건을 충족합니다.", status: "passed" },
  { guide_kind: "state_change", condition_guide: "미입력 사항을 확인하세요.", status: "needs_review" },
]) {
  test(`기준 반복·이전 안내·변화 없음은 새 안내 영역을 만들지 않는다: ${JSON.stringify(extra)}`, () => {
    const html = view([condition(extra)])
    assert.doesNotMatch(html, /class="condition-fulfillment-guide"/)
    if (!extra.status) assert.match(html, /본인 월소득 2,699,999원 이하/)
  })
}

test("원문과 요구값이 같으면 같은 문장을 두 번 표시하지 않는다", () => {
  const text = "정책 원문 그대로의 요구 기준"
  const html = view([condition({ required_value: text, evidence: text, condition_guide: text })])
  assert.equal((html.match(new RegExp(text, "g")) ?? []).length, 1)
  assert.doesNotMatch(html, /정책 원문 근거/)
})

test("새 변화 안내가 없어도 네 개의 미충족 조건과 원문은 모두 유지한다", () => {
  const html = view([0, 1, 2, 3].map((i) => condition({ condition_type: `항목${i}`, required_value: `기준${i}`, evidence: `근거${i}` })))
  assert.match(html, /미충족 조건 <b>4<\/b>/)
  for (const i of [0, 1, 2, 3]) assert.ok(html.includes(`기준${i}`) && html.includes(`근거${i}`))
  assert.doesNotMatch(html, /class="condition-fulfillment-guide"/)
})
