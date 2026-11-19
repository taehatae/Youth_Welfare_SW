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

test("미확인 비교 조건과 공식 확인 사항을 각각 안내하고 비교 조건 전체 충족을 단정하지 않는다", () => {
  const main = policy.paths[0]
  const missing = { ...main.conditions[0], condition_type: "혼인 상태", status: "needs_review" }
  const html = panel({ ...policy, paths: [{ ...main, conditions: [...main.conditions, missing], checks: ["서류 심사"] }] })
  assert.match(html, /이 조건을 충족해도 아직 확인하지 못한 비교 조건이 있어요/)
  assert.match(html, /별도 확인 사항은 공식 안내에서 확인하세요/)
  assert.doesNotMatch(html, /비교 조건을 모두 충족해요/)
})

test("합쳐 보이는 경로 중 하나에 미확인 비교 조건이 있으면 전체 충족을 단정하지 않는다", () => {
  const main = policy.paths[0], same = main.conditions[0]
  const missing = { ...same, condition_type: "혼인 상태", status: "needs_review" }
  const html = panel({ ...policy, paths: [
    { ...main, rank: 0 },
    { ...main, path_id: "a", label: "가", rank: 1, conditions: [same] },
    { ...main, path_id: "b", label: "나", rank: 2, conditions: [same, missing] },
  ] })
  const others = html.slice(html.indexOf("가 · 나 경로"))
  assert.match(others, /경로별로 추가 확인이 필요해요/)
  assert.doesNotMatch(others, /비교 조건을 모두 충족해요/)
})

test("전용 점수가 없으면 이전 응답에 점수가 있어도 대표 경로만 표시한다", () => {
  const main = policy.paths[0], failed = { ...main.conditions[0], difficulty: 5 }
  const html = panel({ ...policy, paths: [
    { ...main, rank: 0, conditions: [failed], difficulty: 5 },
    { ...main, path_id: "alt", label: "대안", rank: 1, conditions: [failed], difficulty: 1 },
  ] })
  assert.match(html, /class="path-guide-badge">대표 경로</)
  assert.doesNotMatch(html, /난이도가 가장 낮아요|현재 설정 기준 추천 경로|난이도 [0-9.]+점/)
})

test("미충족 탭은 조건 카드 대신 역설계 문장과 입력 확인만 한 번 표시한다", () => {
  const html = panel(policy)
  assert.equal((html.match(new RegExp(guide, "g")) ?? []).length, 1)
  assert.ok(html.indexOf(guide) < html.indexOf("입력 확인"))
  assert.doesNotMatch(html, /정책 요구 기준|프로필 보호 중|<dt>내 정보<\/dt>|다음 중 하나만/)
})

test("한 경로의 미충족 네 개를 각각의 역설계 문장으로 모두 표시한다", () => {
  const rows = Array.from({ length: 4 }, (_, i) => ({ ...policy.paths[0].conditions[0], condition_type: `조건${i}`,
    required_value: `기준${i}`, condition_guide: `조건${i} 상태가 달라져 기준${i}에 도달하면 이 조건을 충족할 수 있습니다.` }))
  const html = panel({ ...policy, paths: [{ ...policy.paths[0], conditions: rows }] })
  assert.equal((html.match(/class="path-guide-line"/g) ?? []).length, 4)
  for (const r of rows) assert.ok(html.includes(r.condition_guide))
})

test("충족·추가 확인 탭도 경로 카드로: 충족은 기준 목록, 추가 확인은 입력할 정보와 공식 확인 사항을 나눠 보여준다", () => {
  const passedRow = { ...policy.paths[0].conditions[0], condition_type: "만 나이", required_value: "만 나이 19세 이상", status: "passed" }
  const missing = { ...policy.paths[0].conditions[0], condition_type: "미입력 고용", required_value: "고용 상태: 재직", status: "needs_review" }
  const p = { ...policy, paths: [{ ...policy.paths[0], conditions: [passedRow, missing], checks: ["기관 심사 확인"], status: "needs_review" }] }
  const passed = panel(p, "passed"), review = panel(p, "review"), failed = panel(p)
  assert.match(passed, /✓ 만 나이 19세 이상/)
  assert.ok(review.indexOf("정보를 입력하면 비교할 수 있어요") < review.indexOf("고용 상태: 재직"))
  assert.ok(review.indexOf("공식 안내에서 확인할 사항") < review.indexOf("기관 심사 확인"))
  assert.equal((review.match(/공식 안내에서 확인/g) ?? []).length, 1)
  assert.doesNotMatch(passed + review, /condition-fulfillment-guide|정책 요구 기준/)
  assert.doesNotMatch(failed, /기관 심사 확인|고용 상태: 재직/)
  assert.match(failed, /미충족 조건이 없어요/)
})

test("가장 가까운 경로 카드에 공통 미충족까지 번호로 모두 보여주고 나머지 경로는 '다른 경로 확인하기'에 접는다", () => {
  const common = { ...policy.paths[0].conditions[0], common: true }
  const own = (type, required) => ({ ...policy.paths[0].conditions[0], condition_type: type, required_value: required,
    condition_guide: `${type} 안내`, guide_kind: "state_change" })
  const p = { ...policy, matchedPathId: "b", paths: [
    { ...policy.paths[0], path_id: "a", label: "가", rank: 1, conditions: [common, own("고용", "고용 기준"), own("재산", "재산 기준")] },
    { ...policy.paths[0], path_id: "b", label: "나", rank: 0, conditions: [common, own("소득", "소득 기준")], checks: ["서류 심사"] },
  ] }
  const before = JSON.stringify(p), html = panel(p)
  const best = html.indexOf('class="path-guide-badge">대표 경로'), more = html.indexOf("다른 경로 확인하기 (1)")
  assert.ok(best > -1 && more > best && html.indexOf("가 경로") > more)
  assert.ok(html.indexOf("공통</span>") > best && html.indexOf("공통</span>") < more)
  assert.ok(html.indexOf("소득 안내") < more)
  assert.match(html, /위 2개를 모두 충족하면 이 경로의 비교 조건을 모두 충족해요/)
  assert.match(html, /별도 확인 사항은 공식 안내에서 확인하세요/)
  for (const t of ["고용 안내", "재산 안내"]) assert.ok(html.indexOf(t) > more)
  assert.equal(JSON.stringify(p), before)
})

test("안내가 없고 원문이 기준과 같으면 기준 문장을 한 번만 쓰고 원문 버튼을 만들지 않는다", () => {
  const r = { ...policy.paths[0].conditions[0], condition_guide: "", guide_kind: null, evidence: condition.required }
  const html = panel({ ...policy, paths: [{ ...policy.paths[0], conditions: [r] }] })
  assert.equal((html.match(/만 26세 이상/g) ?? []).length, 1)
  assert.doesNotMatch(html, /<summary>원문<\/summary>/)
  assert.match(html, /입력 확인/)
})
