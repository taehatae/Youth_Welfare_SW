import { useEffect, useMemo, useState } from "react"
import Mascot from "../../components/brand/Mascot"
import "./dashboard.css"
import "./workspace.css"
import CountUp from "../../components/motion/CountUp"
import PageHeading from "../../components/layout/PageHeading"
import SavedPolicyWorkspace from "./SavedPolicyWorkspace"
import { changedPolicyIds } from "../../components/policy/AnalysisChanges"
import { resultCategoryLabels, resultCategoryOf, resultCategoryOrder, type ResultCategory } from "../../components/policy/AnalysisPolicyCard"
import type { Page } from "../../types/page"
import { formatTime, safeOfficialUrl, type AnalysisSession, type Snapshot } from "../../services/analysisSession"
import { policyResults, type PolicyRow, type SavedPolicy, type TrackingStatus } from "../../services/policyResults"

const statusText = { eligible: "자동 비교상 충족", ineligible: "미충족", needs_review: "추가 확인" } as const

function counts(snapshot: Snapshot) {
  const result: Record<ResultCategory, number> = { likely: 0, review: 0, gap: 0 }
  for (const row of policyResults(snapshot)) result[resultCategoryOf(row)]++
  return result
}

type Change = { id: string; kind: string; row: PolicyRow; tag: string }
function changesOf(previous: Snapshot, current: Snapshot): Change[] {
  const before = new Map(policyResults(previous).map(p => [p.id, p]))
  const after = policyResults(current)
  const afterIds = new Set(after.map(p => p.id))
  const changedIds = changedPolicyIds(previous, current)
  const list: Change[] = []
  for (const p of after) {
    const old = before.get(p.id)
    if (!old) list.push({ id: p.id, kind: p.status === "eligible" ? "새로 가능" : "추가", row: p, tag: statusText[p.status] })
    else if (changedIds.has(p.id)) {
      if (old.status === p.status) list.push({ id: p.id, kind: "조건 변경", row: p, tag: statusText[p.status] })
      else list.push({ id: p.id, kind: p.status === "eligible" ? "새로 가능" : "판정 변경", row: p, tag: `${statusText[old.status]} → ${statusText[p.status]}` })
    }
  }
  for (const p of before.values()) if (!afterIds.has(p.id)) list.push({ id: p.id, kind: "제외", row: p, tag: statusText[p.status] })
  return list
}

function Delta({ now, before }: { now: number; before?: number }) {
  if (before === undefined) return null
  const d = now - before
  if (d === 0) return <span className="kpi-delta">변화 없음</span>
  return <span className="kpi-delta" data-dir={d > 0 ? "up" : "down"}>{d > 0 ? "↑" : "↓"} {Math.abs(d)} 지난 확인보다</span>
}

// 내 정보 카드 아이콘(선 그림)
const ACCOUNT_ICONS = {
  lock: ["M6 11h12v9H6z", "M8.5 11V8a3.5 3.5 0 0 1 7 0v3", "M12 15v2"],
  edit: ["M4 20h4L19 9l-4-4L4 16z", "M13.5 6.5l4 4"],
  result: ["M4 20V10", "M10 20V4", "M16 20v-7", "M3 20h18"],
} as const
function AccountIcon({ kind }: { kind: keyof typeof ACCOUNT_ICONS }) {
  return <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.9} strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" focusable="false">
    {ACCOUNT_ICONS[kind].map(d => <path key={d} d={d} />)}
  </svg>
}

export default function DashboardPage({ session, setPage, refresh, busy, error, savedPolicies, updateSaved, onEdit, onViewProfile }: {
  session: AnalysisSession
  setPage: (page: Page) => void
  refresh: () => Promise<void>
  busy: boolean
  error: string
  savedPolicies: SavedPolicy[]
  updateSaved: (item: SavedPolicy, status: TrackingStatus, note: string) => Promise<void>
  onEdit: (step?: number) => void
  onViewProfile: () => void
}) {
  const current = session.current
  const previous = session.previous
  const nowCounts = useMemo(() => current ? counts(current) : null, [current])
  const prevCounts = useMemo(() => previous ? counts(previous) : null, [previous])
  const changes = useMemo(() => current && previous ? changesOf(previous, current) : [], [current, previous])
  const [active, setActive] = useState("summary")

  useEffect(() => {
    if (!current || typeof IntersectionObserver === "undefined") return
    const ids = ["summary", "saved", "changes", "profile"]
    const io = new IntersectionObserver(entries => {
      const hit = entries.filter(e => e.isIntersecting).sort((a, b) => a.boundingClientRect.top - b.boundingClientRect.top)[0]
      if (hit) setActive(hit.target.id)
    }, { rootMargin: "-20% 0px -65% 0px" })
    ids.forEach(id => { const el = document.getElementById(id); if (el) io.observe(el) })
    return () => io.disconnect()
  }, [current])

  if (!current || !nowCounts) return <section className="dashboard-page">
    <PageHeading eyebrow="내 정책 관리 공간" title="나의 현황" description="관심 있는 정책을 모으고, 준비 상황과 달라진 내용을 확인하세요." />
    <div className="interface-empty"><h2>첫 진단부터 시작해볼까요?</h2><p>진단을 완료한 뒤 관심 정책을 저장하면 이곳에서 이어서 관리할 수 있어요.</p><button className="interface-primary" onClick={() => setPage("diagnosis")}>자격 진단 시작 →</button></div>
  </section>

  const menu = [["summary", "요약", null], ["saved", "관심 정책", savedPolicies.length], ["changes", "바뀐 정책", previous ? changes.length : null], ["profile", "내 정보", null]] as const
  const maxBar = Math.max(1, ...resultCategoryOrder.flatMap(k => [nowCounts[k], prevCounts?.[k] ?? 0]))
  const applied = savedPolicies.filter(s => s.trackingStatus === "applied").length
  const headline = previous && changes.length > 0 ? `지난 확인 이후 ${changes.length}개 정책이 바뀌었어요` : "내 정책 현황이에요"
  const go = (id: string) => (e: React.MouseEvent) => {
    e.preventDefault(); setActive(id)
    document.getElementById(id)?.scrollIntoView({ behavior: window.matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth", block: "start" })
  }

  return <section className="dashboard-page dashboard-workspace">
    <nav className="dash-side" aria-label="나의 현황 구역">
      <ul>{menu.map(([id, label, n]) => <li key={id}><a href={`#${id}`} onClick={go(id)} aria-current={active === id ? "true" : undefined}>{label}{n !== null && <b>{n}</b>}</a></li>)}</ul>
    </nav>
    <div className="dash-main">
      <header className="dash-head" id="summary" data-reveal>
        <Mascot pose="water" size={120} className="dash-m-water" />
        <h1>{headline}</h1>
        <p className="dash-sub">마지막 확인 <time dateTime={current.checkedAt}>{formatTime(current.checkedAt)}</time>
          <button className="dash-refresh" disabled={busy} onClick={() => void refresh()}>{busy ? "처리 중…" : "↻ 최신 정책으로 다시 확인"}</button></p>
        {error && <p className="dashboard-error" role="alert">{error} 마지막으로 조회한 결과를 유지하고 있어요.</p>}
        <p className="workspace-live" role="status">{busy ? "요청을 처리하고 있어요. 완료될 때까지 잠시 기다려주세요." : ""}</p>
      </header>

      <div className="kpi-row">
        {resultCategoryOrder.map(k => <div className="kpi" key={k} data-cat={k} data-reveal><span className="kpi-label">{resultCategoryLabels[k]}</span><strong><CountUp value={nowCounts[k]} /></strong><Delta now={nowCounts[k]} before={prevCounts?.[k]} /></div>)}
        <div className="kpi" data-cat="saved" data-reveal><span className="kpi-label">관심 정책</span><strong><CountUp value={savedPolicies.length} /></strong><span className="kpi-delta">신청 완료 {applied}</span></div>
      </div>

      <div className="dash-two">
        <section className="dash-panel" data-reveal aria-labelledby="cmp-title">
          <div className="dash-panel-head"><h2 id="cmp-title">지난 확인 vs 이번 확인</h2></div>
          <ul className="cmp-bars">{resultCategoryOrder.map(k => <li key={k} data-cat={k}>
            <span className="cmp-name">{resultCategoryLabels[k]}</span>
            <div className="cmp-track">
              {prevCounts && <div className="cmp-line"><i className="is-prev" style={{ width: `${(prevCounts[k] / maxBar) * 100}%` }} /><span>지난 {prevCounts[k]}</span></div>}
              <div className="cmp-line"><i style={{ width: `${(nowCounts[k] / maxBar) * 100}%` }} /><span>이번 {nowCounts[k]}</span></div>
            </div></li>)}</ul>
          {!prevCounts && <p className="dashboard-small">다음 확인부터 변화를 비교해요. 첫 기록의 정책은 신규 공고로 표시하지 않아요.</p>}
        </section>
        <section className="dash-panel" id="changes" data-reveal aria-labelledby="chg-title">
          <div className="dash-panel-head"><h2 id="chg-title">바뀐 정책 {previous && <span>{changes.length}</span>}</h2></div>
          {!previous ? <p className="dashboard-small">비교의 기준이 되는 첫 기록을 저장했어요. 다음 현황 조회부터 추가·제외된 정책과 판정·조건 안내의 변화를 보여드려요.</p>
            : changes.length === 0 ? <p className="dashboard-small">정책 분류와 조건 안내에 변화가 없어요.</p>
            : <ul className="chg-list">{changes.map(c => { const url = c.kind === "제외" ? null : safeOfficialUrl(c.row.url); return <li key={`${c.kind}:${c.id}`}>
              <span className="chg-kind" data-kind={c.kind}>{c.kind}</span>
              {url ? <a href={url} target="_blank" rel="noopener noreferrer">{c.row.title}<span className="sr-only"> (새 탭)</span></a> : <strong>{c.row.title}</strong>}
              <span className="chg-tag">{c.tag}</span></li> })}</ul>}
          <p className="dashboard-small">추가·제외는 직전 조회 결과와의 차이이며 새 공고 발표나 접수 종료를 뜻하지 않아요.</p>
        </section>
      </div>

      <SavedPolicyWorkspace savedPolicies={savedPolicies} current={current} busy={busy} updateSaved={updateSaved} setPage={setPage} />

      <section className="dash-panel workspace-account" id="profile" data-reveal aria-labelledby="workspace-account-title">
        <div className="account-head">
          <Mascot pose="thumbs" size={92} className="account-mascot" />
          <div>
            <h2 id="workspace-account-title">내 정보</h2>
            <p>진단에 쓴 입력 정보를 확인하거나 고쳐서 다시 진단할 수 있어요.</p>
            {session.diagnosis && <span className="account-chip">마지막 진단 · <time dateTime={session.diagnosis.checkedAt}>{formatTime(session.diagnosis.checkedAt)}</time></span>}
          </div>
        </div>
        <div className="account-actions">
          <button className="account-action" data-tone="blue" disabled={busy} onClick={onViewProfile}>
            <i aria-hidden="true"><AccountIcon kind="lock" /></i>
            <b>내 입력 정보 보기</b>
            <small>아이디·비밀번호를 다시 확인한 뒤 보여줘요</small>
            <em aria-hidden="true">→</em>
          </button>
          <button className="account-action" data-tone="mint" disabled={busy} onClick={() => onEdit()}>
            <i aria-hidden="true"><AccountIcon kind="edit" /></i>
            <b>정보 수정하고 다시 진단</b>
            <small>바뀐 소득·주거 상황을 넣고 결과를 새로 받아요</small>
            <em aria-hidden="true">→</em>
          </button>
          <button className="account-action" data-tone="lav" onClick={() => setPage("result")}>
            <i aria-hidden="true"><AccountIcon kind="result" /></i>
            <b>진단 결과 보기</b>
            <small>신청 가능·확인 필요·불가 정책을 다시 봐요</small>
            <em aria-hidden="true">→</em>
          </button>
        </div>
        <p className="account-note">진단 당시의 결과는 그대로 보관돼요. 다시 진단하면 새 결과가 추가돼요.</p>
      </section>
      <footer className="dashboard-footer"><details><summary>조회 및 기록 안내</summary><p>프로필·진단 결과·관심 정책·관리 상태·메모는 로그인한 계정에 저장돼요. 작성 중인 메모는 저장 버튼을 눌러야 반영되며, 관리 상태는 사용자가 직접 기록한 내용이에요. 신청 일정은 공식 공고에서 확인해주세요.</p></details></footer>
    </div>
  </section>
}
