import test from "node:test"
import assert from "node:assert/strict"
import { createElement as h } from "react"
import { renderToStaticMarkup } from "react-dom/server"
import { QUESTIONS, toAnswers, questionError, isAnswered, answerSummary } from "../src/features/quick/quickQuestions.ts"
import AnalysisPolicyCard, { PolicyConditionPanel } from "../src/components/policy/AnalysisPolicyCard.tsx"
import QuickFinderPage from "../src/features/quick/QuickFinderPage.tsx"

test("답하지 않은 항목은 보내지 않고 기본값을 채우지 않는다", () => {
  const ids = ["age", "region", "income", "marriage", "special_targets", "nationality"]
  assert.deepEqual(toAnswers(ids, { age: "27" }), { age: 27 })
  assert.throws(() => toAnswers(ids, {}), /만 나이/)
})

test("선택 분야 질문의 화면에 보이는 칸만 변환하고 금액은 원으로 바꾼다", () => {
  const ids = ["age", "region", "income", "marriage", "special_targets", "student"]
  const answers = toAnswers(ids, {
    age: "30", region: "서울특별시", region_district: "관악구", income_monthly_won: "215",
    marital_status: "SINGLE", marriage_years: "3", spouse_monthly_income_won: "100", // 미혼이면 숨는 칸
    special_targets: [], student_status: "NO", school_level: "COLLEGE",
    household_size: "2", // 이 분야 질문이 아님
  })
  assert.deepEqual(answers, { age: 30, region: "서울특별시 관악구", income_monthly_won: 2150000,
    marital_status: "SINGLE", special_targets: [], student_status: "NO" })
})

test("'해당 없음'과 미응답을 구분한다", () => {
  const q = QUESTIONS.special_targets
  assert.equal(isAnswered(q, {}), false)
  assert.equal(isAnswered(q, { special_targets: [] }), true)
  assert.equal(answerSummary(q, { special_targets: [] }), "해당 없음")
  assert.match(answerSummary(q, {}), /건너뛰기/)
  assert.equal("special_targets" in toAnswers(["age", "special_targets"], { age: "25" }), false)
})

test("입력 검증: 숫자 범위, 시군구, 신용점수 짝", () => {
  assert.match(questionError(QUESTIONS.household, { household_size: "0" }), /1~20/)
  assert.match(questionError(QUESTIONS.region, { region: "서울특별시" }), /시군구/)
  assert.equal(questionError(QUESTIONS.region, { region: "세종특별자치시" }), "")
  assert.match(questionError(QUESTIONS.credit, { credit_score: "700" }), /함께/)
  assert.equal(questionError(QUESTIONS.income, { income_monthly_won: "" }), "")
})

const policy = { id: "synthetic", title: "합성 정책", status: "ineligible", description: "", url: "https://example.test",
  counts: { passed: 0, failed: 2, review: 0, evaluated: 2 }, conditions: [], matchedPathId: "a",
  paths: ["a", "b"].map((id) => ({ path_id: id, label: `경로 ${id}`, kind: "기본", status: "ineligible", checks: [], rank: id === "a" ? 0 : 1,
    conditions: [{ condition_type: "본인 월소득", current_value: "프로필 보호 중", required_value: "본인 월소득 250만원 이하",
      evidence: "원문", status: "failed", difficulty: null, condition_guide: "", guide_kind: null }] })) }

test("임시 결과 카드는 관심 저장과 추천 기준 바꾸기를 보여주지 않는다", () => {
  const card = renderToStaticMarkup(h(AnalysisPolicyCard, { policy, temporary: true }))
  assert.doesNotMatch(card, /관심 저장/)
  assert.match(card, /정책 확인하러 가기/)
  const panel = renderToStaticMarkup(h(PolicyConditionPanel, { policy, tab: "failed", temporary: true }))
  assert.doesNotMatch(panel, /추천 기준 보기·바꾸기/)
  assert.match(panel, /간편 찾기 결과는 기본 순서로/)
  // 기존 진단 화면은 그대로다.
  assert.match(renderToStaticMarkup(h(PolicyConditionPanel, { policy, tab: "failed" })), /추천 기준 보기·바꾸기/)
  assert.match(renderToStaticMarkup(h(AnalysisPolicyCard, { policy, saved: false, toggle() {} })), /관심 저장/)
})

test("간편 정책 찾기 첫 화면은 버튼형 안내만 있고 자유 입력창이 없다", () => {
  const html = renderToStaticMarkup(h(QuickFinderPage, { onDiagnosis() {} }))
  assert.match(html, /어떤 분야의 정책을 찾고 있나요/)
  assert.match(html, /자유 문장 입력이나 AI 답변은 없어요/)
  assert.doesNotMatch(html, /<textarea|type="text"/)
})

// ---- 미입력 조건이 남은 '신청 가능' 표시(간편 찾기 전용) ----
import { pendingConditionsOf } from "../src/components/policy/AnalysisPolicyCard.tsx"
import { orderQuickRows, quickFilterCounts } from "../src/features/quick/QuickFinderPage.tsx"

const row = (type, status, required = `${type} 해당`, common = false) =>
  ({ condition_type: type, status, current_value: "프로필 보호 중", required_value: required, evidence: "원문",
     common, difficulty: null, condition_guide: "", guide_kind: null })
const pendingPolicy = {
  id: "pending", title: "미입력 정책", status: "eligible", description: "", url: "https://example.test",
  counts: { passed: 1, failed: 0, review: 3, evaluated: 1 }, conditions: [], matchedPathId: "a",
  paths: [
    { path_id: "a", label: "등록 장애인", kind: "기본", status: "eligible", rank: 0, checks: ["서류 A", "서류 B"],
      conditions: [row("만 나이", "passed", "만 19세 ~ 34세", true), row("등록 장애인", "needs_review", "등록 장애인 해당", true),
        row("등록 장애인", "needs_review", "등록 장애인 해당"), row("고용 상태", "needs_review", "고용 상태: 미취업")] },
    { path_id: "b", label: "보훈", kind: "기본", status: "needs_review", rank: 1, checks: ["보훈 서류"],
      conditions: [row("등록 장애인", "needs_review", "등록 장애인 해당", true), row("국적", "needs_review", "국적: 대한민국")] },
  ],
}
const brief = (html) => (html.match(/<p class="card-brief">([^<]*)<\/p>/) ?? [])[1] ?? ""

test("미입력 조건은 대표 경로 기준으로 중복 없이 세고 다른 경로·확인 사항은 섞지 않는다", () => {
  assert.deepEqual(pendingConditionsOf(pendingPolicy),
    { pathLabel: "등록 장애인", multiplePaths: true, fields: ["등록 장애인", "고용 상태"], count: 2, checks: 2 })
  // 판정이 '신청 가능'이 아니면 미입력 표시 대상이 아니다(불가·확인 필요 표시와 섞지 않는다).
  assert.equal(pendingConditionsOf({ ...pendingPolicy, status: "needs_review" }), null)
  assert.equal(pendingConditionsOf({ ...pendingPolicy, status: "ineligible" }), null)
})

test("간편 찾기 카드는 접힌 상태에서도 미입력 조건을 보여주고 단정 문구를 쓰지 않는다", () => {
  const html = renderToStaticMarkup(h(AnalysisPolicyCard, { policy: pendingPolicy, temporary: true }))
  assert.match(html, /미입력 조건 2개/)
  assert.equal(brief(html).replace(/&#x27;/g, "'"),
    "'등록 장애인' 경로 기준 · 입력한 조건은 충족했지만, 입력하지 않은 조건 확인이 필요해요: 등록 장애인, 고용 상태")
  assert.match(html, /기관 확인 사항 2개는 공식 안내에서 확인하세요/)
  assert.doesNotMatch(html, /경로로 신청 가능|국적|보훈 서류/)
  assert.doesNotMatch(brief(html), /미충족|불가/)
  assert.match(html, /data-pending="true"/)
  // 엔진 판정 분류는 그대로 '신청 가능'이다.
  assert.match(html, /<span class="reverse-tag" data-result="likely">신청 가능<\/span>/)
})

test("일반 진단 카드는 기존 문구 그대로다", () => {
  const html = renderToStaticMarkup(h(AnalysisPolicyCard, { policy: pendingPolicy, saved: false, toggle() {} }))
  assert.equal(brief(html).replace(/&#x27;/g, "'"), "'등록 장애인' 경로로 신청 가능")
  assert.doesNotMatch(html, /미입력 조건|기관 확인 사항|data-pending/)
})

test("미입력 조건이 없는 신청 가능 카드는 구분되어 표시된다", () => {
  const complete = { ...pendingPolicy, paths: [{ ...pendingPolicy.paths[0], checks: [],
    conditions: [row("만 나이", "passed", "만 19세 ~ 34세", true)] }, pendingPolicy.paths[1]] }
  const html = renderToStaticMarkup(h(AnalysisPolicyCard, { policy: complete, temporary: true }))
  assert.doesNotMatch(html, /미입력 조건|data-pending/)
  assert.equal(brief(html).replace(/&#x27;/g, "'"), "'등록 장애인' 경로로 신청 가능")
})

test("간편 찾기 결과는 미입력 조건이 남은 신청 가능 정책을 뒤로 두고 개수를 따로 센다", () => {
  const complete = { ...pendingPolicy, id: "complete", counts: { passed: 1, failed: 0, review: 0, evaluated: 1 },
    paths: [{ ...pendingPolicy.paths[0], conditions: [row("만 나이", "passed")] }] }
  const review = { ...pendingPolicy, id: "review", status: "needs_review" }
  const gap = { ...pendingPolicy, id: "gap", status: "ineligible" }
  assert.deepEqual(orderQuickRows([gap, review, pendingPolicy, complete]).map((p) => p.id), ["complete", "pending", "review", "gap"])
  assert.deepEqual(quickFilterCounts([gap, review, pendingPolicy, complete]),
    { all: 4, likely: 2, pending: 1, review: 1, gap: 1 })
})
