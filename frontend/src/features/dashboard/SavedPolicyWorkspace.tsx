import { useId, useState } from "react"
import { formatTime, safeOfficialUrl, type Snapshot } from "../../services/analysisSession"
import { policyResults, trackingLabels, type PolicyRow, type SavedPolicy, type TrackingStatus } from "../../services/policyResults"
import type { Page } from "../../types/page"
import { resultCategoryLabels, resultCategoryOf } from "../../components/policy/AnalysisPolicyCard"

type UpdateSaved = (item: SavedPolicy, status: TrackingStatus, note: string) => Promise<void>

function SavedCard({ item, latest, currentProfile, busy, updateSaved }: {
  item: SavedPolicy; latest?: PolicyRow; currentProfile: boolean; busy: boolean; updateSaved: UpdateSaved
}) {
  const id = useId()
  const [editing, setEditing] = useState(false)
  const [status, setStatus] = useState<TrackingStatus>(item.trackingStatus ?? "interested")
  const [note, setNote] = useState(item.note ?? "")
  const [message, setMessage] = useState("")
  const [error, setError] = useState("")
  const row = latest ?? item.policy
  const url = safeOfficialUrl(row.url)
  const save = async () => {
    setError(""); setMessage("")
    try { await updateSaved(item, status, note); setEditing(false); setMessage("계정에 저장했어요.") }
    catch (e) { setError(e instanceof Error ? e.message : "저장하지 못했어요. 다시 시도해주세요.") }
  }
  return <article className="workspace-saved-card">
    <div className="workspace-saved-top"><span className="workspace-tracking" data-tracking={item.trackingStatus ?? "interested"}>{trackingLabels[item.trackingStatus ?? "interested"]}</span><span className="dashboard-small">{currentProfile ? "현재 진단 프로필" : "이전 진단 프로필"}</span></div>
    <h4>{row.title}</h4>
    <p className="workspace-saved-verdict">{latest ? "최근 조회 결과" : "저장 당시 결과"} ·<strong data-result={resultCategoryOf(row)}>{resultCategoryLabels[resultCategoryOf(row)]}</strong></p>
    {currentProfile && !latest && <p className="dashboard-small">이번 조회에 없는 정책이에요. 종료 여부는 공식 공고에서 확인해주세요.</p>}
    <p className="workspace-saved-time">관심 저장 · {formatTime(item.savedAt)}</p>
    {!editing && <>
      <p className={`workspace-note${item.note ? "" : " is-empty"}`}>{item.note || "준비할 일이나 확인할 내용을 메모해보세요."}</p>
      <div className="workspace-actions"><button disabled={busy} onClick={() => { setStatus(item.trackingStatus ?? "interested"); setNote(item.note ?? ""); setError(""); setMessage(""); setEditing(true) }}>상태·메모 수정</button>{url && <a href={url} target="_blank" rel="noopener noreferrer">공식 공고 ↗<span className="sr-only"> (새 탭)</span></a>}</div>
    </>}
    {editing && <form className="workspace-editor step-arrive" onSubmit={e => { e.preventDefault(); void save() }}>
      <label htmlFor={`${id}-status`}>내가 기록한 관리 상태</label><select id={`${id}-status`} value={status} disabled={busy} onChange={e => setStatus(e.target.value as TrackingStatus)}>{Object.entries(trackingLabels).map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select>
      <label htmlFor={`${id}-note`}>준비 메모 <small>{note.length}/500</small></label><textarea autoFocus id={`${id}-note`} rows={3} maxLength={500} value={note} disabled={busy} onChange={e => setNote(e.target.value)} placeholder="예: 공고에서 제출 서류 확인하기" aria-describedby={`${id}-help`} />
      <p id={`${id}-help`} className="dashboard-small">비밀번호·주민등록번호 등 민감한 정보는 적지 마세요.</p>
      <div className="workspace-actions"><button type="submit" disabled={busy}>{busy ? "처리 중…" : "변경 저장"}</button><button type="button" disabled={busy} onClick={() => { setEditing(false); setError("") }}>취소</button></div>
    </form>}
    {error && <p className="dashboard-error" role="alert">{error}</p>}
    <p className="workspace-save-message" role="status">{message}</p>
  </article>
}

const columns = ["interested", "preparing", "applied"] as const

export default function SavedPolicyWorkspace({ savedPolicies, current, busy, updateSaved, setPage }: {
  savedPolicies: SavedPolicy[]; current: Snapshot; busy: boolean; updateSaved: UpdateSaved; setPage: (page: Page) => void
}) {
  const [scope, setScope] = useState("all")
  const latest = new Map(policyResults(current).map(row => [row.id, row]))
  const scoped = savedPolicies.filter(item => scope === "all" || item.profileKey === current.profileKey)
    .slice().sort((a, b) => b.savedAt.localeCompare(a.savedAt))
  const by = (value: TrackingStatus) => scoped.filter(item => (item.trackingStatus ?? "interested") === value)
  const card = (item: SavedPolicy) => <SavedCard key={`${item.profileKey}:${item.policy.id}`} item={item} currentProfile={item.profileKey === current.profileKey} latest={item.profileKey === current.profileKey ? latest.get(item.policy.id) : undefined} busy={busy} updateSaved={updateSaved} />
  const archived = by("archived")
  return <section className="workspace-saved" id="saved" aria-labelledby="workspace-saved-title">
    <div className="dash-panel-head"><h2 id="workspace-saved-title">관심 정책 <span>{savedPolicies.length}</span></h2><label className="workspace-scope">프로필 범위<select value={scope} onChange={e => setScope(e.target.value)} disabled={busy}><option value="all">이전 프로필 포함</option><option value="current">현재 진단 프로필만</option></select></label></div>
    <p className="dashboard-small">관리 상태는 직접 기록한 내용이며 실제 접수·선정 결과와 연동되지 않아요. 보관한 정책은 ‘보관’에서 다시 꺼낼 수 있어요.</p>
    {savedPolicies.length === 0 ? <div className="workspace-empty">
      <span className="workspace-empty-mark" aria-hidden="true">☆</span><h3>관심 정책을 저장하면 준비가 쉬워져요</h3><p>진단 결과에서 관심 정책을 고르고, 이곳에서 준비할 일과 진행 상황을 기록하세요.</p><button className="interface-primary" onClick={() => setPage("result")}>진단 결과에서 정책 고르기 →</button>
    </div> : <>
      <div className="kanban">
        {columns.map(col => { const items = by(col); return <section key={col} className="kanban-col" data-tracking={col} aria-label={trackingLabels[col]}>
          <h3>{trackingLabels[col]}<b>{items.length}</b></h3>
          {items.length ? items.map(card) : <p className="kanban-empty">이 단계의 정책이 없어요</p>}
        </section> })}
      </div>
      <details className="kanban-archive"><summary>{trackingLabels.archived} <b>{archived.length}</b></summary>
        {archived.length ? <div className="kanban-archive-list">{archived.map(card)}</div> : <p className="kanban-empty">보관한 정책이 없어요</p>}
      </details>
    </>}
  </section>
}
