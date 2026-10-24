import "./dashboard.css"
import "./workspace.css"
import AnalysisChanges from "../../components/policy/AnalysisChanges"
import PageHeading from "../../components/layout/PageHeading"
import SavedPolicyWorkspace from "./SavedPolicyWorkspace"
import type { Page } from "../../types/page"
import { formatTime, type AnalysisSession } from "../../services/analysisSession"
import type { SavedPolicy, TrackingStatus } from "../../services/policyResults"

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
  if (!current) return <section className="dashboard-page">
    <PageHeading eyebrow="내 정책 관리 공간" title="나의 현황" description="관심 있는 정책을 모으고, 준비 상황과 달라진 내용을 확인하세요." />
    <div className="interface-empty"><h2>첫 진단부터 시작해볼까요?</h2><p>진단을 완료한 뒤 관심 정책을 저장하면 이곳에서 이어서 관리할 수 있어요.</p><button className="interface-primary" onClick={() => setPage("diagnosis")}>자격 진단 시작 →</button></div>
  </section>

  return <section className="dashboard-page dashboard-workspace">
    <PageHeading eyebrow="진단 다음의 할 일" title="나의 현황" description="관심 정책의 준비 상황을 기록하고, 저장한 조건으로 달라진 내용을 확인하세요."
      action={<button className="interface-primary" disabled={busy} onClick={() => void refresh()}>{busy ? "처리 중…" : "↻ 최신 정책으로 다시 확인"}</button>} />

    <section className="workspace-overview" aria-labelledby="workspace-overview-title" data-reveal>
      <div className="workspace-overview-heading"><div><p className="dashboard-eyebrow">01 / 최근 확인 상태</p><h2 id="workspace-overview-title">다음 확인을 위한 기록</h2></div><span className="workspace-account-badge">내 계정에 저장됨</span></div>
      <dl className="workspace-records">
        <div><dt>마지막 진단</dt><dd>{session.diagnosis ? <time dateTime={session.diagnosis.checkedAt}>{formatTime(session.diagnosis.checkedAt)}</time> : "진단 기록 없음"}</dd><p>진단 당시의 결과는 그대로 보관돼요.</p></div>
        <div><dt>현황 마지막 조회</dt><dd><time dateTime={current.checkedAt}>{formatTime(current.checkedAt)}</time></dd><p>서버에 수집된 정책을 다시 비교한 시각이에요.</p></div>
        <div className="workspace-next"><dt>이번에 할 일</dt><dd>{savedPolicies.length ? "저장한 정책 이어서 준비하기" : "관심 정책부터 골라보세요"}</dd><button onClick={() => setPage("result")}>{savedPolicies.length ? "진단 근거 다시 보기 →" : "진단 결과에서 관심 정책 고르기 →"}</button></div>
      </dl>
      <p className="dashboard-small">새로 확인해도 관심 정책의 관리 상태와 메모는 유지돼요. 공공데이터 수집 시각은 현황 조회 시각과 다를 수 있어요.</p>
      {error && <p className="dashboard-error" role="alert">{error} 마지막으로 조회한 결과를 유지하고 있어요.</p>}
      <p className="workspace-live" role="status">{busy ? "요청을 처리하고 있어요. 완료될 때까지 잠시 기다려주세요." : ""}</p>
    </section>

    <section className="workspace-changes" aria-labelledby="workspace-changes-title">
      <div className="workspace-section-title"><p className="dashboard-eyebrow">02 / 달라진 내용</p><h2 id="workspace-changes-title">지난 확인 이후의 변화</h2></div>
      {session.previous ? <AnalysisChanges previous={session.previous} current={current} mode="refresh" /> : <div className="workspace-first" data-reveal><span aria-hidden="true">↻</span><div><h3>비교의 기준이 되는 첫 기록을 저장했어요</h3><p>다음 현황 조회부터 추가·제외된 정책과 판정·조건 안내의 변화를 보여드려요. 첫 기록의 정책은 신규 공고로 표시하지 않아요.</p></div></div>}
    </section>

    <SavedPolicyWorkspace savedPolicies={savedPolicies} current={current} busy={busy} updateSaved={updateSaved} setPage={setPage} />

    <section className="workspace-account" aria-labelledby="workspace-account-title" data-reveal>
      <div className="workspace-section-title"><p className="dashboard-eyebrow">04 / 내 정보와 기록</p><h2 id="workspace-account-title">내 정보 관리</h2></div>
      <div className="workspace-account-grid">
        <section className="workspace-profile"><span className="workspace-mini-label">프로필 보호</span><h3>저장된 입력 정보</h3><p>아이디와 비밀번호를 다시 확인한 뒤 조회할 수 있어요.</p><div className="workspace-actions"><button disabled={busy} onClick={onViewProfile}>본인 확인 후 조회 →</button><button disabled={busy} onClick={() => onEdit()}>정보 수정 후 재진단 →</button></div></section>
        <section className="workspace-report"><span className="workspace-mini-label">진단 보고서</span><h3>정책별 판단 근거가 궁금하다면</h3><p>전체 정책의 충족·미충족·추가 확인 조건은 진단 결과에서 확인하세요.</p><button onClick={() => setPage("result")}>진단 결과 보기 →</button></section>
      </div>
    </section>
    <footer className="dashboard-footer"><details><summary>조회 및 기록 안내</summary><p>추가·제외는 직전 조회 결과와의 차이이며 새 공고 발표나 접수 종료를 뜻하지 않아요. 신청 일정은 공식 공고에서 확인해주세요.</p><p>프로필·진단 결과·관심 정책·관리 상태·메모는 로그인한 계정에 저장돼요. 작성 중인 메모는 저장 버튼을 눌러야 반영되며, 관리 상태는 사용자가 직접 기록한 내용이에요.</p></details></footer>
  </section>
}
