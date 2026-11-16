import test from "node:test"
import assert from "node:assert/strict"
import { createElement as h } from "react"
import { renderToStaticMarkup } from "react-dom/server"
import * as Card from "../src/components/policy/AnalysisPolicyCard.tsx"

// 합성 응답: 안내는 이미 백엔드가 생성했다. UI는 자격을 재계산하지 않는다.
const guide = "입력 연령이 하한보다 낮습니다. 만 26세가 되면 이 조건을 충족할 수 있습니다."
const condition = { field: "만 나이", current: "프로필 보호 중", required: "만 26세 이상", status: "미충족",
  guide: "공식 안내 확인", conditionGuide: guide, guideKind: "state_change", evidence: "원문 연령 기준" }
const policy = { id: "synthetic", title: "합성 정책", status: "ineligible", description: "", url: "https://example.test",
  counts: { passed: 0, failed: 1, review: 0, evaluated: 1 }, conditions: [condition], matchedPathId: "p",
  paths: [{ path_id: "p", label: "대표 신청 경로", kind: "기본", status: "ineligible", checks: [], conditions: [{
    condition_type: "만 나이", current_value: "프로필 보호 중", required_value: condition.required,
    evidence: condition.evidence, status: "failed", condition_guide: guide, guide_kind: "state_change" }] }] }

test("닫힌 정책 카드 하단에는 전체 경로 상세나 역설계 안내를 노출하지 않는다", () => {
  const html = renderToStaticMarkup(h(Card.default, { policy, saved: false, toggle() {} }))
  assert.doesNotMatch(html, /전체 신청 경로|data-path-id=|condition-fulfillment-guide/)
  for (const label of ["충족", "미충족", "추가 확인", "관심 저장", "정책 확인하러 가기"]) assert.ok(html.includes(label))
})

test("경로에서 가져온 안내도 미충족 카드에서 숨기지 않는다", () => {
  const html = renderToStaticMarkup(h(Card.ConditionChangeNotice, { condition, failed: true }))
  assert.match(html, /역설계 안내/)
  assert.ok(html.includes(guide))
  assert.equal((html.match(/condition-fulfillment-guide/g) ?? []).length, 1)
})

const panel = (p, tab = "failed") => renderToStaticMarkup(h(Card.PolicyConditionPanel, { policy: p, tab, onEdit() {} }))

test("미충족 탭에 요구 기준·역설계 안내·관련 입력 버튼을 순서대로 한 번 표시한다", () => {
  const html = panel(policy)
  assert.ok(html.indexOf(condition.required) < html.indexOf(guide))
  assert.ok(html.indexOf(guide) < html.indexOf("관련 입력 확인"))
  assert.equal((html.match(/condition-fulfillment-guide/g) ?? []).length, 1)
  assert.doesNotMatch(html, /프로필 보호 중|<dt>내 정보<\/dt>/)
  assert.match(html, /선택된 신청 경로/)
})

test("미충족 네 개를 제한 없이 각각의 안내와 함께 표시한다", () => {
  const conditions = Array.from({ length: 4 }, (_, i) => ({ ...condition, field: `조건${i}`, required: `기준${i}`,
    conditionGuide: `조건${i} 상태가 달라져 기준${i}에 도달하면 이 조건을 충족할 수 있습니다.` }))
  const html = panel({ ...policy, conditions })
  assert.equal((html.match(/condition-fulfillment-guide/g) ?? []).length, 4)
  for (const c of conditions) assert.ok(html.includes(c.conditionGuide))
})

test("충족과 추가 확인 탭에는 역설계 영역을 만들지 않고 checks를 미충족으로 바꾸지 않는다", () => {
  const p = { ...policy, confirmedConditions: [{ ...condition, field: "확인된 연령" }], conditions: [condition,
    { ...condition, field: "미입력 고용", status: "추가 확인" },
    { field: "확인 사항", current: "", required: "기관 심사 확인", status: "추가 확인", guide: "" }] }
  const passed = panel(p, "passed"), review = panel(p, "review"), failed = panel(p)
  assert.match(passed, /확인된 연령/)
  assert.match(review, /미입력 고용|기관 심사 확인/)
  assert.doesNotMatch(passed + review, /condition-fulfillment-guide/)
  assert.doesNotMatch(failed, /미입력 고용|기관 심사 확인/)
})

test("공통 조건에서 막힌 결과는 백엔드가 반환한 gap만 표시하고 생략 범위를 설명한다", () => {
  const p = { ...policy, blockedByCommon: ["만 나이"], paths: [...policy.paths, {
    ...policy.paths[0], path_id: "other", conditions: [...policy.paths[0].conditions,
      { ...policy.paths[0].conditions[0], condition_type: "다른 경로 고용", required_value: "미반환 고용 기준" }],
  }] }
  const before = JSON.stringify(p), html = panel(p)
  assert.match(html, /공통인 미충족 조건만 표시/)
  assert.match(html, /다른 미충족 조건은 생략될 수/)
  assert.doesNotMatch(html, /다른 경로 고용|미반환 고용 기준/)
  assert.equal(JSON.stringify(p), before)
})

test("원문이 기준과 같으면 중복하지 않고 안내가 없어도 기준과 입력 확인을 유지한다", () => {
  const p = { ...policy, conditions: [{ ...condition, conditionGuide: undefined, guideKind: undefined,
    evidence: condition.required }] }
  const html = panel(p)
  assert.equal((html.match(/만 26세 이상/g) ?? []).length, 1)
  assert.doesNotMatch(html, /condition-fulfillment-guide|정책 원문 근거/)
  assert.match(html, /관련 입력 확인/)
})
