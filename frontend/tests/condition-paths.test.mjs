import test from "node:test"
import assert from "node:assert/strict"
import { readFileSync } from "node:fs"
import { createElement as h } from "react"
import { renderToStaticMarkup } from "react-dom/server"
import AnalysisPolicyCard, { PolicyConditionPanel, resultCategoryOf } from "../src/components/policy/AnalysisPolicyCard.tsx"
import ResultPage from "../src/features/diagnosis/ResultPage.tsx"
import { changedPolicyIds } from "../src/components/policy/AnalysisChanges.tsx"
import { policyResults, restoreSavedPolicies } from "../src/services/policyResults.ts"

// 원문/경로 구조는 검수본, 비교 결과와 안내는 UI 테스트용 합성 응답이다.
const row = (field, status, extra = {}) => ({
  condition_type: field, status, current_value: "프로필 보호 중", required_value: field + " 정책 기준",
  evidence: field + " 원문 근거", ...extra,
})
const path = (id, conditions = [], checks = []) => ({
  path_id: id, label: id, kind: "기본", priority: null, status: "ineligible", conditions, checks,
})
const summary = (c) => ({ condition_type: c.condition_type, status: c.status, current_value: c.current_value,
  required_value: c.required_value, source_text: c.evidence || c.required_value,
  source_field: "eligibility_path", message: "기존 판정 설명", action_guide: "기존 일반 안내" })
const snapshot = (extra = {}) => ({
  profile: null, profileKey: "synthetic", checkedAt: "2026-11-15T10:00:00+09:00",
  analysis: { userId: "synthetic", reverse: { recommendations: [] }, matched: {
    matched_count: 0, policies: [], evaluated_count: 1, analysis_results: [{
      policy_id: "synthetic", title: "합성 정책", status: "ineligible", match_score: 25,
      evaluated_conditions: 4, passed_conditions: 1, gap_conditions: [], review_conditions: [],
      notes: [], detail_url: "https://example.test", path_review: "reviewed", ...extra,
    }],
  } },
})
const panel = (s, tab = "failed") => renderToStaticMarkup(h(PolicyConditionPanel, {
  policy: policyResults(s)[0], tab, onEdit() {},
}))
const card = (s) => renderToStaticMarkup(h(AnalysisPolicyCard, {
  policy: policyResults(s)[0], saved: false, toggle() {},
}))

test("대표 경로의 정확히 일치하는 안내만 미충족 카드로 연결하며 금액·제외 방향을 계산하지 않는다", () => {
  const failed = row("본인 월소득", "failed", { required_value: "본인 월소득 2,699,999원 이하",
    condition_guide: "입력된 본인 월소득이 상한보다 높습니다. 2,699,999원 이하로 낮아지면 이 조건을 충족합니다.",
    guide_kind: "state_change" })
  const exclusion = row("재학 여부", "failed", { condition_guide: "재학 상태에 해당하면 제외됩니다. 재학하지 않는 상태로 변경되면 이 조건의 제외 기준을 벗어납니다.",
    guide_kind: "state_change" })
  const s = snapshot({ eligibility_paths: [path("대표", [failed, exclusion])], matched_path_id: "대표",
    gap_conditions: [summary(failed), summary(exclusion)] })
  const before = JSON.stringify(s), html = panel(s)
  assert.match(html, /2,699,999원 이하로 낮아지면/)
  assert.match(html, /재학 상태에 해당하면 제외됩니다/)
  assert.equal((html.match(/condition-fulfillment-guide/g) ?? []).length, 2)
  assert.equal(JSON.stringify(s), before)
})

test("다른 원문·다른 OR 경로·모호한 중복 일치의 안내를 잘못 연결하지 않는다", () => {
  const first = row("만 나이", "failed", { condition_guide: "다른 경로의 안내", guide_kind: "state_change" })
  const selected = { ...first, condition_guide: "선택된 경로의 상태 변화 안내" }
  const s = snapshot({ eligibility_paths: [path("A", [first]), path("B", [selected])], matched_path_id: "B",
    gap_conditions: [summary(selected)] })
  assert.match(panel(s), /선택된 경로의 상태 변화 안내/)
  assert.doesNotMatch(panel(s), /다른 경로의 안내/)
  s.analysis.matched.analysis_results[0].gap_conditions[0].source_text = "다른 원문"
  assert.doesNotMatch(panel(s), /condition-fulfillment-guide/)
  s.analysis.matched.analysis_results[0].gap_conditions[0] = summary(selected)
  s.analysis.matched.analysis_results[0].eligibility_paths[1].conditions.push({ ...selected })
  assert.doesNotMatch(panel(s), /condition-fulfillment-guide/)
})

test("경로 상세 UI는 없어져도 모든 OR 데이터·대표 경로·판정·점수·공통 차단 정보는 유지한다", () => {
  const paths = Array.from({ length: 12 }, (_, i) => path("경로-" + i, [row("조건-" + i, "failed")]))
  const s = snapshot({ eligibility_paths: paths, matched_path_id: "경로-7", blocked_by_common: ["공통 연령"] })
  const before = JSON.stringify(s), policy = policyResults(s)[0], html = card(s)
  assert.equal(policy.paths.length, 12)
  assert.equal(policy.matchedPathId, "경로-7")
  assert.equal(policy.status, "ineligible")
  assert.deepEqual(policy.blockedByCommon, ["공통 연령"])
  assert.equal(s.analysis.matched.analysis_results[0].match_score, 25)
  assert.match(html, /공통 조건 미충족/)
  assert.doesNotMatch(html, /전체 신청 경로|data-path-id=/)
  assert.equal(JSON.stringify(s), before)
})

test("공통 조건 표시가 없는 이전 경로에서도 gap 목록을 임의로 합치거나 확장하지 않는다", () => {
  const c = row("연령", "failed", { condition_guide: "현재 상태가 달라지면 연령 요건을 충족합니다.", guide_kind: "state_change" })
  const s = snapshot({ eligibility_paths: [path("A", [c]), path("B", [c])], gap_conditions: [summary(c)] })
  assert.equal(policyResults(s)[0].conditions.length, 1)
  assert.equal((panel(s).match(/condition-fulfillment-guide/g) ?? []).length, 1)
})

test("checks만 있는 경로는 확인 사항 탭에 유지하고 미충족으로 세지 않는다", () => {
  const check = { condition_type: "확인 사항", status: "needs_review", current_value: "", required_value: "별도 기관 심사",
    source_field: "eligibility_path_check", source_text: "별도 기관 심사", action_guide: "", message: "" }
  const s = snapshot({ status: "needs_review", eligibility_paths: [path("기관 확인", [], ["별도 기관 심사"])],
    gap_conditions: [], review_conditions: [check] })
  const policy = policyResults(s)[0]
  assert.equal(resultCategoryOf(policy), "review")
  assert.equal(policy.counts.failed, 0)
  assert.match(panel(s, "review"), /별도 기관 심사/)
  assert.doesNotMatch(panel(s), /별도 기관 심사|condition-fulfillment-guide/)
})

test("이전 스냅샷은 경로·대표 경로·안내·common 필드 없이 기준과 저장 기능을 유지한다", () => {
  const s = snapshot({ gap_conditions: [{ ...summary(row("만 나이", "failed")), source_field: "selection_criteria" }] })
  const before = JSON.stringify(s), policy = policyResults(s)[0]
  assert.equal(resultCategoryOf(policy), "gap")
  assert.match(panel(s), /만 나이 정책 기준/)
  assert.doesNotMatch(panel(s), /condition-fulfillment-guide/)
  const saved = [{ profileKey: "synthetic", profile: null, policy, savedAt: s.checkedAt }]
  assert.equal(restoreSavedPolicies(JSON.stringify(saved))[0].policy.id, "synthetic")
  assert.equal(JSON.stringify(s), before)
})

test("대표 경로가 없어도 새 판정을 만들지 않고 반환된 gap과 기준만 표시한다", () => {
  const c = row("연령", "failed")
  for (const matched_path_id of [undefined, "unknown"]) {
    const s = snapshot({ status: "needs_review", eligibility_paths: [path("첫 경로", [c])],
      matched_path_id, gap_conditions: [summary(c)] })
    assert.equal(policyResults(s)[0].status, "needs_review")
    assert.match(panel(s), /연령 정책 기준/)
  }
})

test("안내와 요구값이 비어 있으면 원문을 표시하며 새 기준을 만들지 않는다", () => {
  const c = row("별도 자격", "failed", { required_value: "", evidence: "원문 그대로의 별도 요건" })
  const html = panel(snapshot({ gap_conditions: [summary(c)] }))
  assert.doesNotMatch(html, /condition-fulfillment-guide/)
  assert.match(html, /원문 그대로의 별도 요건/)
  assert.doesNotMatch(html, /퇴사하세요|이사하세요|소득을 줄이세요/)
})

test("보호된 입력을 재노출하지 않고 안내와 근거를 HTML로 실행하지 않는다", () => {
  const c = row("고용", "failed", { guide_kind: "state_change", condition_guide: "<script>안내</script>",
    evidence: "<img src=x onerror=alert(1)>" })
  const html = panel(snapshot({ eligibility_paths: [path("p", [c])], gap_conditions: [summary(c)] }))
  assert.match(html, /&lt;script&gt;안내&lt;\/script&gt;/)
  assert.doesNotMatch(html, /<script>|<img src=x|<dt>내 정보<\/dt>/)
})

test("진단 결과의 검수 필터·검색·관심·비교·본인 확인 기능과 상태 분류를 유지한다", () => {
  const s = snapshot({ eligibility_paths: [path("p", [row("만 나이", "failed")])] })
  const html = renderToStaticMarkup(h(ResultPage, { snapshot: s, previous: snapshot({ status: "eligible" }), savedPolicies: [],
    setPage() {}, toggleSaved() {}, onEdit() {}, onViewProfile() {} }))
  for (const text of ["정책명 조회", "관심 정책", "추가·변경 정책", "본인 확인 후 프로필 조회", "자격 경로를 검수한 정책만 보기"]) assert.ok(html.includes(text))
  assert.equal(changedPolicyIds(snapshot({ status: "eligible" }), s).has("synthetic"), true)
})

const reviewed = JSON.parse(readFileSync(new URL("../../backend/data/eligibility_paths_reviewed.json", import.meta.url), "utf8")).policies
const escapeText = (text) => text.replaceAll("&", "&amp;").replaceAll("<", "&lt;").replaceAll(">", "&gt;").replaceAll('"', "&quot;").replaceAll("'", "&#x27;")
for (const term of ["청소년특별지원", "행복주택", "평생교육이용권", "미소금융"]) {
  test("실제 검수 정책 " + term + "의 대표 경로 기준을 유지하고 다른 OR 경로를 gap에 추가하지 않는다", () => {
    const policy = reviewed.find((p) => p.name.includes(term))
    assert.ok(policy)
    const common = (policy.common ?? []).map((c) => row(c.field, "failed", { common: true, required_value: c.evidence, evidence: c.evidence }))
    const paths = policy.paths.map((p) => path(p.id, [...common, ...p.conditions.map((c) =>
      row(c.field, "failed", { required_value: c.evidence, evidence: c.evidence }))], p.checks ?? []))
    const returned = paths[0].conditions
    const s = snapshot({ title: policy.name, eligibility_paths: paths, matched_path_id: paths[0].path_id,
      gap_conditions: returned.map(summary) })
    const before = JSON.stringify(s), mapped = policyResults(s)[0], html = panel(s)
    assert.equal(mapped.paths.length, policy.paths.length)
    assert.equal(mapped.conditions.length, returned.length)
    for (const c of returned) assert.ok(html.includes(escapeText(c.evidence)))
    assert.doesNotMatch(card(s), /data-path-id=/)
    assert.equal(JSON.stringify(s), before)
  })
}
