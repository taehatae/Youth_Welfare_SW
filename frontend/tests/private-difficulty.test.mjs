import test from "node:test"
import assert from "node:assert/strict"
import { createPrivateGuideSession, createPrivateGuideLoader, pathCards, pathConditionKey } from "../src/services/conditionGuidance.ts"
import { DEFAULT_PREFS } from "../src/services/difficultyPrefs.ts"

const target = { snapshot: "current", profile_key: "a".repeat(64), checked_at: "2026-11-19T00:00:00Z", policy_id: "p" }
const response = { ...target, items: [], difficulties: [
  { path_id: "a", condition_index: 0, difficulty: 2, difficulty_group: "money" },
  { path_id: "b", condition_index: 0, difficulty: 4, difficulty_group: "life" },
] }
const paths = [
  { path_id: "a", label: "가", status: "ineligible", rank: 0, checks: [], difficulty: 99,
    conditions: [{ status: "failed", condition_type: "소득", required_value: "기준", evidence: "근거", difficulty: 99 }] },
  { path_id: "b", label: "나", status: "ineligible", rank: 1, checks: [], difficulty: 1,
    conditions: [{ status: "failed", condition_type: "고용", required_value: "기준", evidence: "근거", difficulty: 1 }] },
]

test("기본·과거 스냅샷 점수를 무시하고 전용 점수 전에는 저장 순위를 유지한다", () => {
  const cards = pathCards(paths, "failed", { ...DEFAULT_PREFS, money: 5 })
  assert.equal(cards.best[0].pathId, "a")
  assert.equal(cards.best[0].difficulty, null)
  assert.equal(cards.scored, false)
})

test("전용 메모리 점수 수신 후에만 기존 가중치로 추천 순위를 계산한다", () => {
  const session = createPrivateGuideSession()
  assert.equal(session.accept(target, session.begin(target), response), true)
  const privateScores = session.readDifficulties(target), before = JSON.stringify(paths)
  assert.equal(privateScores.get(pathConditionKey("a", 0)).difficulty, 2)
  assert.equal(pathCards(paths, "failed", DEFAULT_PREFS, privateScores).best[0].pathId, "a")
  assert.equal(pathCards(paths, "failed", { ...DEFAULT_PREFS, money: 5 }, privateScores).best[0].pathId, "b")
  assert.equal(JSON.stringify(paths), before)
})

test("계정·화면 이탈·진단 전환 후 점수를 폐기하고 늦은 응답도 거절한다", async () => {
  let complete
  const loader = createPrivateGuideLoader(() => new Promise(resolve => { complete = resolve }), () => {})
  let pending = loader.load(target)
  complete(response); await pending
  assert.equal(loader.read(target).difficulties.size, 2)
  pending = loader.load(target)
  loader.clear()
  complete(response); await pending
  assert.equal(loader.read(target).difficulties.size, 0)
  pending = loader.load(target)
  complete(response); await pending
  assert.equal(loader.read({ ...target, checked_at: "different" }).difficulties.size, 0)
  assert.equal(loader.read(target).difficulties.size, 0)
})

test("비정상·중복 전용 점수를 수락하지 않고 일부 점수를 0점으로 대체하지 않는다", () => {
  for (const difficulty of [NaN, Infinity, -1]) {
    const session = createPrivateGuideSession()
    assert.equal(session.accept(target, session.begin(target), { ...response,
      difficulties: [{ ...response.difficulties[0], difficulty }] }), false)
  }
  const partial = new Map([[pathConditionKey("a", 0), response.difficulties[0]]])
  const cards = pathCards(paths, "failed", DEFAULT_PREFS, partial)
  assert.equal(cards.scored, false)
  assert.equal(cards.best[0].pathId, "a")
  const session = createPrivateGuideSession()
  assert.equal(session.accept(target, session.begin(target), { ...response,
    difficulties: [response.difficulties[0], response.difficulties[0]] }), false)
})

test("폐기 시 이전 렌더가 잡고 있던 안내·점수 맵도 비운다", () => {
  const session = createPrivateGuideSession()
  session.accept(target, session.begin(target), { ...response, items: [
    { gap_index: 0, guide_kind: "state_change", condition_guide: "합성 개인화 안내" }] })
  const oldGuides = session.read(target), oldScores = session.readDifficulties(target)
  assert.equal(oldScores.size, 2)
  session.accept(target, session.begin(target), response)
  assert.equal(oldGuides.size, 0)
  assert.equal(oldScores.size, 0)
  const refreshed = session.readDifficulties(target)
  session.clear()
  assert.equal(refreshed.size, 0)
})
