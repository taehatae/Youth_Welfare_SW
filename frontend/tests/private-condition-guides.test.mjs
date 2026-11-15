import test from "node:test"
import assert from "node:assert/strict"
import { createElement as h } from "react"
import { renderToStaticMarkup } from "react-dom/server"
import * as Guidance from "../src/services/conditionGuidance.ts"
import { PolicyConditionPanel } from "../src/components/policy/AnalysisPolicyCard.tsx"
import { setApiAccount, subscribeApiIdentityChange, viewConditionGuides, signOut } from "../src/services/welfareApi.ts"

const target = { snapshot: "diagnosis", profile_key: "a".repeat(64), checked_at: "2026-11-16T10:00:00Z", policy_id: "p" }
const response = { profile_key: target.profile_key, checked_at: target.checked_at, policy_id: "p", items: [
  { gap_index: 0, guide_kind: "state_change", condition_guide: "입력한 월소득 3,000,000원은 2,500,000원 이하여야 합니다." }] }

test("기본 카드에 개인값을 미리 노출하거나 재인증 입력을 요구하지 않는다", () => {
  const html = renderToStaticMarkup(h(PolicyConditionPanel, { tab: "failed", guideTarget: target, policy: {
    id: "p", title: "합성 정책", status: "ineligible", description: "", conditions: [{ field: "본인 월소득",
      current: "프로필 보호 중", required: "2,500,000원 이하", status: "미충족", guide: "" }],
  } }))
  assert.doesNotMatch(html, /본인 확인 후 맞춤 안내|비밀번호|<dialog|<input/)
  assert.doesNotMatch(html, /3,000,000원/)
})

test("로그인 전용 응답은 메모리에만 두며 기본 응답 객체를 변경하지 않는다", () => {
  assert.equal(typeof Guidance.createPrivateGuideSession, "function")
  const session = Guidance.createPrivateGuideSession(), before = JSON.stringify(response)
  assert.equal(session.read(target).size, 0)
  const ticket = session.begin(target)
  assert.equal(session.read(target).size, 0) // 요청 중 재렌더가 응답 수락을 취소하지 않아야 한다.
  assert.equal(session.accept(target, ticket, response), true)
  assert.match(session.read(target).get(0), /3,000,000원/)
  assert.equal(JSON.stringify(response), before)
})

test("화면 이탈·계정 변경·진단 변경 시 폐기하며 늦은 응답도 버린다", () => {
  assert.equal(typeof Guidance.createPrivateGuideSession, "function")
  const session = Guidance.createPrivateGuideSession()
  let ticket = session.begin(target)
  session.accept(target, ticket, response)
  assert.equal(session.read(target).size, 1)
  ticket = session.begin(target)
  session.clear() // 실제 컴포넌트의 blur/visibilitychange/해제와 같은 경로
  assert.equal(session.accept(target, ticket, response), false)
  ticket = session.begin(target)
  assert.equal(session.accept({ ...target, checked_at: "different" }, ticket, response), false)
  assert.equal(session.read(target).size, 0)
  ticket = session.begin(target)
  session.accept(target, ticket, response)
  assert.equal(session.read({ ...target, profile_key: "b".repeat(64) }).size, 0)
  assert.equal(session.read(target).size, 0)
})

test("다른 정책·진단 응답과 유효하지 않은 항목은 표시하지 않는다", () => {
  assert.equal(typeof Guidance.createPrivateGuideSession, "function")
  const session = Guidance.createPrivateGuideSession()
  assert.equal(session.accept(target, session.begin(target), { ...response, policy_id: "other" }), false)
  const ticket = session.begin(target)
  assert.equal(session.accept(target, ticket, { ...response, items: [{ gap_index: -1, guide_kind: "state_change", condition_guide: "invalid" }] }), false)
})

test("자동 조회는 진단 식별자만 전달하고 실패·세션 만료 시 개인화 내용을 폐기한다", async () => {
  let fail = false, calls = []
  const loader = Guidance.createPrivateGuideLoader(async (...args) => {
    calls.push(args)
    if (fail) throw Object.assign(new Error("private server text must not leak"), { status: 401 })
    return response
  }, () => {})
  await loader.load(target)
  assert.deepEqual(calls, [[target]])
  assert.equal(loader.read(target).guides.size, 1)
  fail = true
  await loader.load(target)
  assert.equal(loader.read(target).guides.size, 0)
  assert.match(loader.read(target).error, /로그인/)
  assert.doesNotMatch(loader.read(target).error, /private server text/)
})

test("자동 조회 중 화면 종료·진단 전환 시 이전 응답과 오류가 복구되지 않는다", async () => {
  let complete
  const loader = Guidance.createPrivateGuideLoader(() => new Promise(resolve => { complete = resolve }), () => {})
  const loading = loader.load(target)
  loader.clear()
  complete(response)
  await loading
  assert.equal(loader.read(target).guides.size, 0)
  const other = { ...target, policy_id: "other" }
  const next = loader.load(other)
  complete(response)
  await next
  assert.equal(loader.read(other).guides.size, 0)
})

test("계정 전환·로그아웃 알림은 메모리와 진행 중 응답을 무효화한다", async () => {
  let complete
  const loader = Guidance.createPrivateGuideLoader(() => new Promise(resolve => { complete = resolve }), () => {})
  setApiAccount("a")
  const stop = subscribeApiIdentityChange(() => loader.clear())
  try {
    let loading = loader.load(target)
    setApiAccount("b")
    complete(response); await loading
    assert.equal(loader.read(target).guides.size, 0)
    loading = loader.load(target)
    complete(response); await loading
    assert.equal(loader.read(target).guides.size, 1)
    setApiAccount(null)
    assert.equal(loader.read(target).guides.size, 0)
  } finally { stop(); setApiAccount(null) }
})

test("실제 API 클라이언트는 로그인 쿠키와 계정 식별자로 조회하며 자격증명·캐시를 사용하지 않는다", async () => {
  const previousWindow = globalThis.window, previousFetch = globalThis.fetch
  const calls = []
  globalThis.window = { location: { origin: "http://localhost:5173", hostname: "localhost" }, setTimeout, clearTimeout }
  globalThis.fetch = async (url, init) => {
    calls.push({ url, init })
    return { ok: true, status: 200, json: async () => response }
  }
  try {
    setApiAccount("signed-in-a")
    await viewConditionGuides(target)
    assert.match(calls[0].url, /\/api\/v1\/users\/condition-guides\/view$/)
    assert.deepEqual(JSON.parse(calls[0].init.body), target)
    assert.equal(calls[0].init.credentials, "include")
    assert.equal(calls[0].init.cache, "no-store")
    assert.equal(calls[0].init.headers["X-Account-ID"], "signed-in-a")
  } finally { setApiAccount(null); globalThis.window = previousWindow; globalThis.fetch = previousFetch }
})

test("401 응답 및 다른 탭의 계정 변경은 안내를 즉시 폐기하고 구독을 정리한다", async () => {
  const previousWindow = globalThis.window, previousFetch = globalThis.fetch
  const channels = []
  class TestChannel {
    constructor(name) { this.name = name; channels.push(this) }
    postMessage(value) { this.sent = value }
    close() { this.closed = true }
  }
  globalThis.window = { BroadcastChannel: TestChannel,
    location: { origin: "http://localhost:5173", hostname: "localhost" }, setTimeout, clearTimeout }
  globalThis.fetch = async () => ({ ok: false, status: 401, json: async () => ({ detail: "login required" }) })
  const loader = Guidance.createPrivateGuideLoader(async () => response, () => {})
  const stop = subscribeApiIdentityChange(() => loader.clear())
  try {
    await loader.load(target)
    assert.equal(loader.read(target).guides.size, 1)
    await assert.rejects(viewConditionGuides(target), e => e.status === 401)
    assert.equal(loader.read(target).guides.size, 0)
    await loader.load(target)
    channels[0].onmessage({ data: "changed" })
    assert.equal(loader.read(target).guides.size, 0)
    globalThis.fetch = async () => ({ ok: true, status: 204 })
    await signOut()
    assert.equal(channels.at(-1).sent, "changed")
    assert.equal(channels.at(-1).closed, true)
    assert.deepEqual(Object.keys(channels.at(-1)).sort(), ["closed", "name", "sent"])
  } finally {
    stop(); assert.equal(channels[0].closed, true)
    globalThis.window = previousWindow; globalThis.fetch = previousFetch
  }
})

test("브라우저가 탭 간 알림을 차단해도 기존 로그인·로그아웃 API 흐름을 중단하지 않는다", async () => {
  const previousWindow = globalThis.window, previousFetch = globalThis.fetch
  globalThis.window = { BroadcastChannel: class { constructor() { throw new Error("channel unavailable") } },
    location: { origin: "http://localhost:5173", hostname: "localhost" }, setTimeout, clearTimeout }
  globalThis.fetch = async () => ({ ok: true, status: 204 })
  let cleared = 0, stop
  try {
    stop = subscribeApiIdentityChange(() => cleared++)
    await signOut()
    assert.equal(cleared, 1)
  } finally { stop?.(); globalThis.window = previousWindow; globalThis.fetch = previousFetch }
})
