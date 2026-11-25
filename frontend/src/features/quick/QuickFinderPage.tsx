import mascotAvatar from "../../assets/brand/mascot-avatar.webp"
import { useEffect, useRef, useState, type ReactNode } from "react"
import PageHeading from "../../components/layout/PageHeading"
import AnalysisPolicyCard, {
  cardBrief, isUnverified, metCountOf, pendingConditionsOf, resultCategoryLabels, resultCategoryOf, resultCategoryOrder, type ResultCategory,
} from "../../components/policy/AnalysisPolicyCard"
import { policyResults, type PolicyRow } from "../../services/policyResults"
import { evaluateQuick, interpretQuick, loadQuickCategories, loadQuickCategory } from "../../services/welfareApi"
import { REGIONS } from "../../data/regions"
import type { QuickCategory, QuickCategoryDetail, QuickEvaluateResponse, QuickInterpretResponse } from "../../types/quickFinder"
import {
  AGE_OPTIONS, answerSummary, isAnswered, questionError, questionsFor, toAnswers, visibleInputs,
  type QuickDraft, type QuickInput, type QuickQuestion,
} from "./quickQuestions"
import Mascot from "../../components/brand/Mascot"
import "../diagnosis/reverse.css"
import "./quick.css"

// 버튼으로 묻고 답하는 간편 정책 찾기. 첫 단계에서만 문장을 받아 분야를 고른다(판정은 버튼 답으로 한다).
// 입력값과 결과는 이 화면의 메모리에만 있고 서버·브라우저 저장소에 남기지 않는다.

function Bot({ children }: { children: ReactNode }) {
  return <div className="quick-row" data-from="bot" data-reveal><span className="quick-avatar" aria-hidden="true"><img src={mascotAvatar} alt="" /></span><div className="quick-bubble">{children}</div></div>
}
function Me({ children }: { children: ReactNode }) {
  return <div className="quick-row" data-from="me" data-reveal><div className="quick-bubble">{children}</div></div>
}

function Field({ input, draft, set }: { input: QuickInput; draft: QuickDraft; set: (patch: QuickDraft) => void }) {
  const value = draft[input.key]
  const name = "quick-" + input.key
  if (input.kind === "age")
    return <label className="quick-field"><span>{input.label}</span>
      <select value={typeof value === "string" ? value : ""} onChange={(e) => set({ age: e.target.value })}>
        <option value="">선택해 주세요</option>
        {AGE_OPTIONS.map(([v, label]) => <option key={v} value={v}>만 {label}</option>)}
      </select></label>
  if (input.kind === "region") {
    const sido = typeof draft.region === "string" ? draft.region : ""
    return <div className="quick-field quick-region">
      <label><span>시도</span>
        <select value={sido} onChange={(e) => set({ region: e.target.value, region_district: "" })}>
          <option value="">모름 · 건너뛰기</option>
          {Object.keys(REGIONS).map((r) => <option key={r} value={r}>{r}</option>)}
        </select></label>
      {sido && sido !== "세종특별자치시" && <label><span>시군구</span>
        <select value={typeof draft.region_district === "string" ? draft.region_district : ""}
          onChange={(e) => set({ region_district: e.target.value })}>
          <option value="">선택해 주세요</option>
          {(REGIONS[sido] ?? []).map((r) => <option key={r} value={r}>{r}</option>)}
        </select></label>}
    </div>
  }
  if (input.kind === "number")
    return <label className="quick-field"><span>{input.label}</span>
      <span className="unit-input">
        <input inputMode="numeric" pattern="[0-9]*" placeholder="모르면 비워 두세요" value={typeof value === "string" ? value : ""}
          onChange={(e) => set({ [input.key]: e.target.value.replace(/[^\d]/g, "") })} />
        <b>{input.unit}</b>
      </span></label>
  if (input.kind === "multi") {
    const chosen = Array.isArray(value) ? value : undefined
    const toggle = (id: string) => {
      const next = new Set(chosen ?? [])
      if (next.has(id)) next.delete(id); else next.add(id)
      set({ [input.key]: next.size || input.allowNone ? [...next] : undefined })
    }
    return <fieldset className="choice-field quick-field"><legend>{input.label}</legend>
      <div className="choice-group">
        {input.options.map(([id, label]) => <label key={id} className="choice-option">
          <input type="checkbox" checked={!!chosen?.includes(id)} onChange={() => toggle(id)} /><span>{label}</span></label>)}
        {input.allowNone && <label className="choice-option">
          <input type="checkbox" checked={chosen?.length === 0} onChange={() => set({ [input.key]: chosen?.length === 0 ? undefined : [] })} />
          <span>해당 없음</span></label>}
      </div></fieldset>
  }
  return <fieldset className="choice-field quick-field"><legend>{input.label}</legend>
    <div className="choice-group">
      {[...input.options, ["", "모름"] as const].map(([id, label]) => <label key={id || "unknown"} className="choice-option">
        <input type="radio" name={name} checked={(typeof value === "string" ? value : "") === id} onChange={() => set({ [input.key]: id })} />
        <span>{label}</span></label>)}
    </div></fieldset>
}

function QuestionCard({ question, draft, setDraft, onDone, editing }: {
  question: QuickQuestion; draft: QuickDraft; setDraft: (d: QuickDraft) => void; onDone: () => void; editing: boolean
}) {
  const [error, setError] = useState("")
  const set = (patch: QuickDraft) => { setError(""); setDraft({ ...draft, ...patch }) }
  const next = () => {
    const message = questionError(question, draft)
    if (message) { setError(message); return }
    onDone()
  }
  const skip = () => {
    const cleared: QuickDraft = { ...draft }
    for (const input of question.inputs) cleared[input.key] = undefined
    if (question.id === "region") cleared.region_district = undefined
    setDraft(cleared); setError(""); onDone()
  }
  return <div className="quick-card" data-reveal>
    {visibleInputs(question, draft).map((input) => <Field key={input.key} input={input} draft={draft} set={set} />)}
    {error && <p role="alert" className="quick-error">{error}</p>}
    <div className="quick-card-actions">
      <button type="button" className="interface-primary" onClick={next}>{editing ? "수정 완료" : "다음"}</button>
      {!question.required && <button type="button" className="quick-ghost" onClick={skip}>모름 · 건너뛰기</button>}
    </div>
  </div>
}

// 판정(status)과 대표 경로는 엔진 결과 그대로 둔다. 표시 순서와 필터만 정한다.
export type QuickFilter = "all" | ResultCategory | "pending"
type Filter = QuickFilter
export const isPendingRow = (p: PolicyRow) => !!pendingConditionsOf(p)?.count
// 신청 가능 안에서는 미입력 조건이 없는 정책을 먼저, 미입력 조건이 남은 정책을 뒤에 둔다.
export const orderQuickRows = (rows: PolicyRow[]) => [...rows].sort((a, b) =>
  resultCategoryOrder.indexOf(resultCategoryOf(a)) - resultCategoryOrder.indexOf(resultCategoryOf(b))
  || Number(isPendingRow(a)) - Number(isPendingRow(b)) || metCountOf(b) - metCountOf(a))
export const inQuickFilter = (p: PolicyRow, f: QuickFilter) =>
  f === "all" || (f === "pending" ? isPendingRow(p) : resultCategoryOf(p) === f)
export const quickFilterCounts = (rows: PolicyRow[]) => Object.fromEntries(
  (["all", ...resultCategoryOrder, "pending"] as QuickFilter[]).map((f) => [f, rows.filter((p) => inQuickFilter(p, f)).length]),
) as Record<QuickFilter, number>

function scrollReveal(el: HTMLElement | null, widget: boolean) {
  if (!el) return
  const scroller = widget ? el.closest<HTMLElement>(".quick-widget-scroll") : null
  if (!scroller) { el.scrollIntoView({ behavior: "smooth", block: "start" }); return }
  const top = el.getBoundingClientRect().top - scroller.getBoundingClientRect().top + scroller.scrollTop - 8
  scroller.scrollTo({ top: Math.max(0, top), behavior: "smooth" })
}

export default function QuickFinderPage({ onDiagnosis, variant = "page" }: { onDiagnosis: () => void; variant?: "page" | "widget" }) {
  const widget = variant === "widget"
  const [categories, setCategories] = useState<QuickCategory[] | null>(null)
  const [loadError, setLoadError] = useState("")
  const [detail, setDetail] = useState<QuickCategoryDetail | null>(null)
  const [detailLoading, setDetailLoading] = useState(false)
  const [draft, setDraft] = useState<QuickDraft>({})
  const [progress, setProgress] = useState(0)
  const [editing, setEditing] = useState<string | null>(null)
  const [result, setResult] = useState<QuickEvaluateResponse | null>(null)
  const [stale, setStale] = useState(false)
  const [evaluating, setEvaluating] = useState(false)
  const [evalError, setEvalError] = useState("")
  const [filter, setFilter] = useState<Filter>("all")
  const [skippedAtEval, setSkippedAtEval] = useState(0)
  // 문장으로 묻기: 보낸 문장은 화면에만 남고 서버에 저장되지 않는다.
  const [ask, setAsk] = useState("")
  const [asked, setAsked] = useState("")
  const [asking, setAsking] = useState(false)
  const [intent, setIntent] = useState<QuickInterpretResponse | null>(null)
  const [askError, setAskError] = useState("")
  const askGeneration = useRef(0)
  const generation = useRef(0)
  const chatTop = useRef<HTMLDivElement>(null)
  const resultTop = useRef<HTMLDivElement>(null)

  const loadCategories = () => {
    setLoadError(""); setCategories(null)
    loadQuickCategories().then((r) => setCategories(r.categories))
      .catch((e) => setLoadError(e instanceof Error ? e.message : "분야 목록을 불러오지 못했어요."))
  }
  useEffect(loadCategories, [])

  const chooseCategory = async (id: string) => {
    clearAsk()
    const version = ++generation.current
    setDetailLoading(true); setLoadError(""); setResult(null); setEvalError(""); setStale(false)
    setProgress(0); setEditing(null); setFilter("all")
    try {
      const found = await loadQuickCategory(id)
      if (version === generation.current) setDetail(found)
    } catch (e) {
      if (version === generation.current) setLoadError(e instanceof Error ? e.message : "분야 정보를 불러오지 못했어요.")
    } finally { if (version === generation.current) setDetailLoading(false) }
  }
  const submitAsk = async () => {
    const text = ask.trim()
    if (!text || asking) return
    const version = ++askGeneration.current
    setAsked(text); setAsk(""); setIntent(null); setAskError(""); setAsking(true)
    try {
      const found = await interpretQuick(text)
      if (version === askGeneration.current) setIntent(found)
    } catch (e) {
      if (version === askGeneration.current) setAskError(e instanceof Error ? e.message : "문장을 이해하지 못했어요. 위 버튼에서 분야를 골라주세요.")
    } finally { if (version === askGeneration.current) setAsking(false) }
  }
  function clearAsk() { askGeneration.current++; setAsked(""); setIntent(null); setAskError(""); setAsking(false) }
  // 해석된 분야가 간편 찾기 분야 목록에 있고 정책이 있을 때만 바로 시작할 수 있다.
  const suggested = intent?.category ? categories?.find((c) => c.id === intent.category && c.policy_count > 0) : undefined
  const resetCategory = () => {
    generation.current++
    setDetail(null); setResult(null); setProgress(0); setEditing(null); setEvalError(""); setStale(false); setEvaluating(false)
    scrollReveal(chatTop.current, widget)
  }
  const evaluate = async () => {
    if (!detail || evaluating) return
    const version = ++generation.current
    setEvaluating(true); setEvalError("")
    try {
      const response = await evaluateQuick(detail.id, toAnswers(detail.questions, draft))
      if (version !== generation.current) return
      setResult(response); setStale(false); setFilter("all")
      setSkippedAtEval(questions.length - questions.filter((q) => isAnswered(q, draft)).length)
      window.setTimeout(() => scrollReveal(resultTop.current, widget), 0)
    } catch (e) {
      if (version === generation.current) setEvalError(e instanceof Error ? e.message : "결과를 불러오지 못했어요.")
    } finally { if (version === generation.current) setEvaluating(false) }
  }

  const questions = detail ? questionsFor(detail.questions) : []
  const finished = !!detail && progress >= questions.length
  const answeredCount = questions.slice(0, progress).filter((q) => isAnswered(q, draft)).length
  const updateDraft = (next: QuickDraft) => { setDraft(next); if (result) setStale(true) }

  const rows = result ? orderQuickRows(policyResults({ profile: null, checkedAt: result.evaluated_at,
    analysis: { userId: "quick-finder", matched: result.matched, reverse: { recommendations: [] } } })) : []
  const counts = quickFilterCounts(rows)
  const shown = rows.filter((p) => inQuickFilter(p, filter))
  const unverified = rows.filter(isUnverified).length

  return <section className={widget ? "quick-widget-body" : "reverse-page quick-page"}>
    {!widget && <PageHeading eyebrow="버튼으로 답하는 간편 탐색" title="간편 정책 찾기"
      description="관심 분야를 고르고, 그 분야 정책이 실제로 비교하는 조건만 답해 보세요. 로그인 없이 쓸 수 있고 입력값과 결과는 저장하지 않아요." />}
    <div className="quick-chat" ref={chatTop} aria-label="간편 정책 찾기 대화">
      <Bot>
        <p>안녕하세요. 관심 분야의 정책을 간단히 찾아 드릴게요.</p>
        <p className="quick-muted">분야 버튼을 누르거나, 찾는 정책을 문장으로 적어 보세요. 문장은 분야를 고르는 데만 쓰고 저장하지 않아요. 모르는 질문은 건너뛰면 그 조건은 ‘확인 필요’로 남아요. 전체 자격 진단을 대신하지는 않아요.</p>
      </Bot>
      <Bot><p>어떤 분야의 정책을 찾고 있나요?</p></Bot>
      {!detail && <div className="quick-options" data-reveal aria-busy={!categories || detailLoading}>
        {loadError && <div role="alert" className="quick-error">{loadError}
          <button type="button" className="quick-ghost" onClick={categories ? () => setLoadError("") : loadCategories}>다시 시도</button></div>}
        {!categories && !loadError && <p role="status" className="quick-muted">분야 목록을 불러오는 중이에요.</p>}
        {categories?.map((c) => <button key={c.id} type="button" className="quick-option" disabled={detailLoading || c.policy_count === 0}
          onClick={() => void chooseCategory(c.id)}>{c.label} <small>{c.policy_count}개</small></button>)}
        {detailLoading && <p role="status" className="quick-muted">분야의 비교 조건을 확인하고 있어요.</p>}
      </div>}
      {!detail && <>
        {asked && <Me>{asked}</Me>}
        {asking && <Bot><p role="status">무엇을 찾는지 생각하고 있어요…</p></Bot>}
        {askError && <Bot><p role="alert">{askError}</p></Bot>}
        {intent && !asking && (suggested
          ? <Bot>
              <p><strong>{suggested.label}</strong> 분야 정책을 찾으시는 것 같아요. {suggested.label} 정책 {suggested.policy_count}개 중에서 찾아볼까요?</p>
              {intent.keywords.length > 0 && <p className="quick-muted">관련된 말: {intent.keywords.join(" · ")}</p>}
              <div className="quick-intent-actions">
                <button type="button" className="quick-intent-yes" disabled={detailLoading} onClick={() => void chooseCategory(suggested.id)}>네, {suggested.label} 정책 찾기</button>
                <button type="button" className="quick-ghost" onClick={clearAsk}>다른 분야 고를게요</button>
              </div>
            </Bot>
          : <Bot><p>말씀하신 내용에 맞는 분야를 찾지 못했어요. 위 버튼에서 분야를 골라 주시거나, 다른 말로 다시 적어 주세요.</p></Bot>)}
        <form className="quick-ask" onSubmit={(e) => { e.preventDefault(); void submitAsk() }}>
          <label className="sr-only" htmlFor={widget ? "quick-ask-widget" : "quick-ask-page"}>찾는 정책을 문장으로 적기</label>
          <input id={widget ? "quick-ask-widget" : "quick-ask-page"} type="text" maxLength={200} value={ask} disabled={asking}
            onChange={(e) => setAsk(e.target.value)} placeholder="예: 자취 관련 정책 없어?" autoComplete="off" />
          <button type="submit" disabled={asking || !ask.trim()}>보내기</button>
        </form>
      </>}
      {detail && <>
        <Me>{detail.label} <button type="button" className="quick-link" onClick={resetCategory}>다른 분야 선택</button></Me>
        <Bot>
          <p>{detail.label} 분야 정책 {detail.policy_count}개가 입력값으로 비교하는 조건을 질문 {questions.length}개로 물어볼게요.</p>
          {detail.unsupported_fields.length > 0 && <p className="quick-muted">
            입력으로 비교할 수 없는 조건({detail.unsupported_fields.join(", ")})은 결과에서 ‘확인 필요’로 안내해요.</p>}
          {detail.check_count > 0 && <p className="quick-muted">서류·심사처럼 입력으로 비교할 수 없는 확인 사항은 결과 카드의 ‘추가 확인’에 따로 보여 드려요.</p>}
        </Bot>
        {questions.slice(0, progress + 1).map((q, i) => <div key={q.id} className="quick-step">
          <Bot>
            <p>{q.prompt}</p>
            {q.help && <p className="quick-muted">{q.help}</p>}
            {q.id !== "age" && detail.question_policy_counts[q.id] > 0 &&
              <p className="quick-muted">이 분야 정책 {detail.question_policy_counts[q.id]}개가 이 조건을 봐요.</p>}
          </Bot>
          {i < progress && editing !== q.id
            ? <Me>{answerSummary(q, draft)} <button type="button" className="quick-link" disabled={evaluating}
                onClick={() => setEditing(q.id)}>수정</button></Me>
            : (i === progress || editing === q.id) && <QuestionCard key={q.id + (editing === q.id ? ":edit" : "")} question={q} draft={draft}
                setDraft={updateDraft} editing={editing === q.id}
                onDone={() => { if (editing === q.id) setEditing(null); else setProgress(progress + 1) }} />}
        </div>)}
        {progress >= 1 && <Bot>
          <p>{finished ? "질문을 모두 마쳤어요." : "남은 질문은 건너뛰고 지금까지 답한 내용으로 볼 수도 있어요."}
            {" "}답한 질문 {answeredCount}개 · 건너뛴 질문 {progress - answeredCount}개{finished ? "" : ` · 남은 질문 ${questions.length - progress}개`}</p>
          <div className="quick-card-actions">
            <button type="button" className="interface-primary" disabled={evaluating || editing !== null} onClick={() => void evaluate()}>
              {evaluating ? "확인하는 중…" : result ? "바뀐 입력으로 다시 조회" : "결과 보기"}
            </button>
            {editing && <span className="quick-muted">수정 중인 질문을 먼저 마쳐 주세요.</span>}
          </div>
          {evalError && <p role="alert" className="quick-error">{evalError}</p>}
        </Bot>}
      </>}
    </div>

    {detail && result && <div className="quick-results" ref={resultTop} aria-busy={evaluating}>
      <header className="reverse-section-title">
        <p className="reverse-kicker">간편 찾기 결과 · 저장되지 않아요</p>
        <h2>{result.category_label} 분야 <small>{rows.length}개</small></h2>
        <p>입력한 값과 비교할 수 있는 조건만으로 판정한 사전 안내예요. ‘신청 가능’도 실제 자격이 확정됐다는 뜻은 아니에요. 최종 자격은 담당 기관에서 확인해 주세요.</p>
      </header>
      {(skippedAtEval > 0 || counts.pending > 0) && <p className="analysis-unverified">
        {skippedAtEval > 0 && <>답하지 않은 질문 {skippedAtEval}개의 조건은 비교하지 않았어요.</>}
        {counts.pending > 0 && <> 신청 가능 {counts.likely}건 중 <strong>{counts.pending}건</strong>은 입력한 조건만 충족했고
        입력하지 않은 조건이 남아 있어 ‘미입력 조건’으로 표시하고 뒤쪽에 두었어요. 해당하는지 꼭 확인해 주세요.</>}</p>}
      {stale &&<p role="status" className="quick-stale">입력이 바뀌었어요. ‘바뀐 입력으로 다시 조회’를 누르면 결과가 갱신돼요.
        <button type="button" className="interface-primary" disabled={evaluating || editing !== null} onClick={() => void evaluate()}>다시 조회</button></p>}
      <div className="analysis-filters" aria-label="간편 찾기 결과 필터">
        {(["all", "likely", ...(counts.pending ? ["pending"] : []), "review", "gap"] as Filter[]).map((id) =>
          <button key={id} type="button" aria-pressed={filter === id} data-category={id} onClick={() => setFilter(id)}>
            {id === "all" ? "전체" : id === "pending" ? "└ 그중 미입력 조건 있음" : resultCategoryLabels[id]} <strong>{counts[id]}</strong></button>)}
      </div>
      {unverified > 0 && <p className="analysis-unverified">신청 가능 중 {unverified}건은 비교할 수 있는 조건이 없어 ‘비교 조건 없음’으로 표시했어요.</p>}
      {shown.length ? widget ? <ul className="quick-mini-list">
        {shown.map((policy) => { const cat = resultCategoryOf(policy)
          // 큰 화면 카드(temporary)와 같게, 입력하지 않은 조건이 남은 '신청 가능'은 따로 표시한다.
          const pending = pendingConditionsOf(policy)
          return <li key={policy.id}><a className="quick-mini" href={"#detail/" + encodeURIComponent(policy.id)}>
            <span className="quick-mini-tags">
              <span className="quick-mini-pill" data-category={cat}>{resultCategoryLabels[cat]}</span>
              {!!pending?.count && <span className="quick-mini-pill" data-category="pending">미입력 조건 {pending.count}개</span>}
            </span>
            <strong>{policy.title}</strong>
            <span className="quick-mini-brief">{pending?.count
              ? `입력한 조건은 충족했지만, 입력하지 않은 조건 확인이 필요해요: ${pending.fields.join(", ")}`
              : cardBrief(policy)}</span>
          </a></li> })}
      </ul> : <div className="reverse-list quick-list">
        {shown.map((policy, index) => <AnalysisPolicyCard key={policy.id} policy={policy} index={index} temporary />)}
      </div> : <div className="reverse-empty">
        <Mascot pose="think" size={110} className="mascot-center" />
        <h3>{rows.length ? "이 분류에 해당하는 정책이 없어요" : "이 분야에서 분석된 정책이 없어요"}</h3>
        <p>{rows.length ? "다른 분류를 눌러 보세요." : "결과가 없다고 자격이 없다는 뜻은 아니에요. 다른 분야를 선택하거나 전체 자격 진단을 이용해 보세요."}</p>
      </div>}
      <div className="quick-next">
        <button type="button" className="quick-ghost" onClick={() => scrollReveal(chatTop.current, widget)}>답변 수정하기</button>
        <button type="button" className="quick-ghost" onClick={resetCategory}>다른 분야 찾기</button>
        <button type="button" className="interface-primary" onClick={onDiagnosis}>전체 자격 진단 하기 →</button>
      </div>
      <p className="reverse-footnote">간편 찾기 결과는 이 화면을 떠나면 사라지고, 계정의 진단 기록이나 관심 정책에 저장되지 않아요.</p>
    </div>}
  </section>
}
