import "./dashboard.css"
import PageHeading from "../../components/layout/PageHeading"
import { useState } from "react"
import type { Page } from "../../types/page"
import type {
  AnalysisSession,
  ApplicationState,
} from "../../services/analysisSession"
import {
  applicationLabels,
  applicationState,
  formatTime,
  koreaDate,
} from "../../services/analysisSession"
import { EMPLOYMENT } from "../../data/profileOptions"
import MatchedPolicyCard from "../../components/policy/MatchedPolicyCard"
import SavedPoliciesPanel from "../../components/policy/SavedPoliciesPanel"
import type { PolicyRow, SavedPolicy } from "../../services/policyResults"
import type { UserProfileInput } from "../../types/welfareApi"

export default function DashboardPage({
  session,
  setPage,
  refresh,
  busy,
  error,
  clear,
  savedPolicies,
  toggleSaved,
}: {
  session: AnalysisSession
  setPage: (page: Page) => void
  refresh: () => Promise<void>
  busy: boolean
  error: string
  clear: () => void
  savedPolicies: SavedPolicy[]
  toggleSaved: (policy: PolicyRow, profile: UserProfileInput) => void
}) {
  const [confirmClear, setConfirmClear] = useState(false)
  const [filter, setFilter] = useState<ApplicationState | "all">("all")
  const current = session.current
  if (!current)
    return (
      <section className="mx-auto max-w-5xl px-4 py-8 sm:px-6">
        <PageHeading eyebrow="저장한 조건으로 이어가는 확인" title="나의 현황" description="내 정보는 저장하고, 정책의 변화는 다시 조회하세요. 진단 당시 결과와 최신 현황을 각각 확인할 수 있어요." />
        <div className="interface-empty"><span className="interface-empty-icon" aria-hidden="true">↻</span><h2>내 정보가 있으면, 다음 기회도 찾을 수 있어요</h2><p>먼저 자격 진단을 완료해주세요. 이후 현황 새로고침으로 추가된 정책과 신청 기간 변화를 살펴볼 수 있어요.</p><button onClick={() => setPage("diagnosis")} className="interface-primary">내 정보 입력하기 →</button></div>
      </section>
    )
  const date = koreaDate(new Date(current.checkedAt))
  const currentIds = new Set(
    current.analysis.matched.policies.map((p) => p.policy_id),
  )
  const previousIds = new Set(
    session.previous?.analysis.matched.policies.map((p) => p.policy_id),
  )
  const added = session.previous
    ? current.analysis.matched.policies.filter(
        (p) => !previousIds.has(p.policy_id),
      )
    : []
  const oldPolicies = session.knownPolicies
  const disappeared = [
    ...new Map(
      oldPolicies
        .filter((p) => !currentIds.has(p.policy_id))
        .map((p) => [p.policy_id, p]),
    ).values(),
  ]
  const ended = disappeared.filter(
    (p) => applicationState(p, date) === "expired",
  )
  const unavailable = disappeared.filter(
    (p) => applicationState(p, date) !== "expired",
  )
  const policies = [...current.analysis.matched.policies, ...ended]
  const states: ApplicationState[] = ["open", "upcoming", "unknown", "expired"]
  const profile = current.profile
  const counts = Object.fromEntries(states.map(state => [state, policies.filter(p => applicationState(p, date) === state).length])) as Record<ApplicationState, number>
  const descriptions: Record<ApplicationState, string> = {
    open: '공식 공고에서 세부 자격과 마감 시간을 확인해주세요.',
    upcoming: '접수 시작일을 확인하고 필요한 서류를 준비하세요.',
    unknown: '날짜가 제공되지 않아 공식 공고 확인이 필요해요.',
    expired: '조회 기준일에 신청 기한이 지난 정책이에요.',
  }
  const renderCards = (state: ApplicationState) => {
    const list = policies.filter(policy => applicationState(policy, date) === state)
    return list.length ? <div className={list.length > 1 ? 'dashboard-policy-grid' : 'dashboard-policy-single'}>
      {list.map(policy => <MatchedPolicyCard key={policy.policy_id} policy={policy} date={date} isNew={added.some(item => item.policy_id === policy.policy_id)} />)}
    </div> : <p className="dashboard-no-policies">이 상태에 해당하는 정책이 없어요.</p>
  }
  return <section className="dashboard-page">
    <SavedPoliciesPanel profile={profile} savedPolicies={savedPolicies} toggleSaved={toggleSaved} />
    <PageHeading eyebrow="내 조건은 저장하고, 기회는 다시 찾고" title="나의 현황" description="마지막 조회 결과를 한눈에 확인하세요. 새로고침하면 저장된 프로필로 정책을 다시 찾아요."
      action={<button onClick={() => void refresh()} disabled={busy} className="interface-primary">{busy ? '조회 중…' : '↻ 현황 새로고침'}</button>} />

    <section className="dashboard-summary" aria-labelledby="dashboard-summary-title">
      <div className="dashboard-section-heading"><div><p className="dashboard-eyebrow">01 / 한눈에 보기</p><h2 id="dashboard-summary-title">내 정책 현황</h2></div><p className="dashboard-date">조회 기준 {date} · 한국시간</p></div>
      <div className="dashboard-stat-grid">
        {states.map(state => <button key={state} type="button" data-status={state} aria-pressed={filter === state} className="dashboard-stat" onClick={() => setFilter(filter === state ? 'all' : state)}>
          <span className="dashboard-stat-label">{applicationLabels[state]}<span aria-hidden="true">{state === 'open' ? '↗' : state === 'upcoming' ? '◷' : state === 'unknown' ? '?' : '✓'}</span></span>
          <strong>{counts[state]}<small>개</small></strong><span className="dashboard-stat-hint">{filter === state ? '전체 목록으로 돌아가기' : '해당 정책 모아보기 →'}</span>
        </button>)}
      </div>
      <div className="dashboard-update" aria-live="polite"><div><span className="dashboard-update-icon" aria-hidden="true">↻</span><div><strong>{session.previous ? `직전 조회보다 ${added.length}개 정책이 추가됐어요` : '첫 조회 결과를 저장했어요'}</strong><p>{session.previous ? '추가 표시는 이번에 새로 조회된 정책을 뜻하며, 새 공고 발표와는 다릅니다.' : '다음 새로고침부터 직전 조회와 비교해 추가된 정책을 알려드려요.'}</p></div></div><time dateTime={current.checkedAt}>마지막 조회<br />{formatTime(current.checkedAt)}</time></div>
      {error && <p role="alert" className="dashboard-error">{error} 마지막으로 조회한 결과를 유지하고 있어요.</p>}
    </section>

    <div className="dashboard-body">
      <aside className="dashboard-sidebar" aria-labelledby="saved-profile-title">
        <section className="dashboard-profile-card">
          <p className="dashboard-eyebrow">02 / 저장된 내 정보</p><h2 id="saved-profile-title">조회에 사용하는 프로필</h2>
          <div className="dashboard-profile-badge"><span aria-hidden="true">✓</span><div><strong>진단 완료 프로필</strong><p>재진단을 완료하면 갱신돼요</p></div></div>
          <dl className="dashboard-profile-facts"><div><dt>나이</dt><dd>만 {profile.age}세</dd></div><div><dt>거주지</dt><dd>{profile.region}</dd></div><div><dt>고용 상태</dt><dd>{EMPLOYMENT.find(([id]) => id === profile.employment_status)?.[1] ?? profile.employment_status}</dd></div></dl>
          <details className="dashboard-income"><summary>저장된 소득 확인</summary><p>월 {profile.income_level.toLocaleString('ko-KR')}원</p></details>
          <button disabled={busy} onClick={() => setPage('diagnosis')} className="dashboard-edit">내 정보 수정 후 재진단 →</button>
          <p className="dashboard-small">수정 중인 정보는 재진단을 완료한 뒤 현황에 반영됩니다.</p>
        </section>
        <section className="dashboard-record-card"><span className="dashboard-eyebrow">진단 당시의 기록</span><h2>이전 진단도 그대로</h2><p>현황을 새로 조회해도 진단 시점의 결과는 유지돼요.</p><button onClick={() => setPage('result')}>진단 결과 보기 →</button></section>
      </aside>

      <section className="dashboard-policy-section" aria-labelledby="dashboard-policies-title">
        <div className="dashboard-section-heading"><div><p className="dashboard-eyebrow">03 / 정책 살펴보기</p><h2 id="dashboard-policies-title">상태별 정책 목록</h2></div><span className="dashboard-total">총 {policies.length}개</span></div>
        <div className="dashboard-filters" aria-label="정책 상태 필터">
          {(['all', ...states] as const).map(state => <button key={state} aria-pressed={filter === state} onClick={() => setFilter(state)}>{state === 'all' ? '전체' : applicationLabels[state]} <span>{state === 'all' ? policies.length : counts[state]}</span></button>)}
        </div>
        <p className="dashboard-small dashboard-policy-note">접수 기간 내 정책도 추가 자격 확인이 필요할 수 있어요.</p>
        {states.filter(state => filter === 'all' || filter === state).map(state => {
          if (filter === 'all' && counts[state] === 0) return null
          return state === 'expired' ? <details key={state} className="dashboard-policy-group dashboard-ended" open={filter === 'expired'}>
            <summary><span>신청 종료 <b>{counts[state]}</b></span><span className="dashboard-small">목록 펼치기 / 접기</span></summary><p className="dashboard-group-description">{descriptions[state]}</p>{renderCards(state)}
          </details> : <section key={state} className="dashboard-policy-group" data-status={state} aria-labelledby={'dashboard-' + state}>
            <h3 id={'dashboard-' + state}>{applicationLabels[state]} <b>{counts[state]}</b></h3><p className="dashboard-group-description">{descriptions[state]}</p>{renderCards(state)}
          </section>
        })}
        {policies.length === 0 && filter === 'all' && <p className="dashboard-no-policies">현재 조회된 맞춤 정책이 없어요. 내 정보를 수정하거나 나중에 다시 조회해주세요.</p>}
        {unavailable.length > 0 && <details className="dashboard-policy-group dashboard-ended"><summary>이번 조회에서 제외된 정책 <b>{unavailable.length}</b></summary><p className="dashboard-group-description">종료일이 확인되지 않아 신청 종료로 단정하지 않았어요.</p><ul className="list-inside list-disc text-sm">{unavailable.map(policy => <li key={policy.policy_id}>{policy.title}</li>)}</ul></details>}
      </section>
    </div>
    <footer className="dashboard-footer">
      <details><summary>조회 기준 및 저장 정보 관리</summary><p>새로고침은 서버에 등록된 정책을 재조회합니다. 공공데이터 자체의 수집 시각과는 다를 수 있어요.</p><p>입력 정보와 기록은 이 브라우저에 저장되며, 다른 기기와 자동으로 공유되지 않아요.</p>
        {!confirmClear ? <button onClick={() => setConfirmClear(true)} className="dashboard-delete">이 브라우저의 저장 정보 삭제</button> : <div className="dashboard-delete-confirm"><span>입력 정보와 조회 기록, 모든 프로필의 관심 정책을 삭제할까요? 서버 기록은 유지됩니다.</span><button disabled={busy} onClick={clear}>삭제</button><button onClick={() => setConfirmClear(false)}>취소</button></div>}
      </details>
    </footer>
  </section>
}
