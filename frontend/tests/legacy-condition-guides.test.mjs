import test from "node:test"
import assert from "node:assert/strict"
import { readFileSync } from "node:fs"
import { createElement as h } from "react"
import { renderToStaticMarkup } from "react-dom/server"
import * as Card from "../src/components/policy/AnalysisPolicyCard.tsx"
import { policyResults } from "../src/services/policyResults.ts"

// 정책 문구는 실제 스냅샷, 판정/안내는 격리 백엔드 회귀 테스트와 같은 형태의 합성 응답이다.
const raw = JSON.parse(readFileSync(new URL("../../backend/data/welfare-policies.json", import.meta.url), "utf8"))
  .data.welfare_services.find((p) => p.serv_id === "WLF00000781")
const source = raw.selection_criteria.split("\n")[0]
const guide = "입력된 성별이 허용 대상과 다릅니다. 성별이 정책이 요구하는 여성 상태로 변경되면 이 조건을 충족할 수 있습니다. 이 안내는 실제 비교한 성별 항목에 한정되며, 같은 원문의 다른 요건까지 충족한다는 뜻은 아닙니다."
const snapshot = (metadata = {}) => ({
  profile: null, checkedAt: "2026-11-15T10:00:00+09:00",
  analysis: { userId: "synthetic", reverse: { recommendations: [] }, matched: {
    matched_count: 0, policies: [], analysis_results: [{
      policy_id: raw.serv_id, title: raw.serv_name, status: "needs_review", evaluated_conditions: 3, passed_conditions: 2,
      match_score: 66.7, notes: [], detail_url: raw.detail_url, eligibility_paths: [],
      review_conditions: [], gap_conditions: [{ condition_type: "target_group", status: "failed", current_value: "프로필 보호 중",
        required_value: source, source_text: source, source_field: "selection_criteria", message: "기존 비교 결과",
        action_guide: "공식 안내 확인", ...metadata }],
    }],
  } },
})

test("자격 경로가 없는 기존 gap의 안내·인증 정보를 프런트 모델에 전달한다", () => {
  const s = snapshot({ condition_guide: guide, guide_kind: "state_change", reason_code: "requirement_not_met" })
  const before = JSON.stringify(s)
  const policy = policyResults(s)[0]
  assert.deepEqual(policy.paths, [])
  assert.equal(policy.conditions[0].conditionGuide, guide)
  assert.equal(policy.conditions[0].guideKind, "state_change")
  assert.equal(policy.status, "needs_review")
  assert.equal(Card.resultCategoryOf(policy), "gap")  // 기존 화면 분류는 변경하지 않는다.
  assert.equal(JSON.stringify(s), before)
})

test("기존 미충족 탭에서 사용하는 실제 표시 컴포넌트가 성별 변화 안내를 렌더링한다", () => {
  const policy = policyResults(snapshot({ condition_guide: guide, guide_kind: "state_change" }))[0]
  const html = renderToStaticMarkup(h(Card.ConditionChangeNotice, { condition: policy.conditions[0], failed: true }))
  assert.match(html, /역설계 안내/)
  assert.match(html, /실제 비교한 성별 항목에 한정/)
  assert.doesNotMatch(html, /남성|프로필 보호 중/)
})

test("원문만 있는 이전 저장 결과에는 변화 안내를 새로 만들지 않는다", () => {
  const policy = policyResults(snapshot())[0]
  const html = renderToStaticMarkup(h(Card.ConditionChangeNotice, { condition: policy.conditions[0], failed: true }))
  assert.equal(html, "")
  assert.equal(policy.conditions[0].required, source)
})

test("미충족 탭의 안내는 경로 상세에 의존하지 않고 한 번 표시한다", () => {
  const policy = policyResults(snapshot({ condition_guide: guide, guide_kind: "state_change" }))[0]
  const html = renderToStaticMarkup(h(Card.ConditionChangeNotice, { condition: policy.conditions[0], failed: true }))
  assert.equal((html.match(/condition-fulfillment-guide/g) ?? []).length, 1)
  assert.match(html, /실제 비교한 성별 항목에 한정/)
})
