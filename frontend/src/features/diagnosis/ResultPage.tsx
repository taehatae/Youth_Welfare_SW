import { useState } from "react"
import PageHeading from "../../components/layout/PageHeading"
import AnalysisPolicyCard, { statusLabels } from "../../components/policy/AnalysisPolicyCard"
import type { Page } from "../../types/page"
import type { UserProfileInput } from "../../types/welfareApi"
import { formatTime, type Snapshot } from "../../services/analysisSession"
import { policyResults, profileKey, type PolicyRow, type PolicyStatus, type SavedPolicy } from "../../services/policyResults"
import { EMPLOYMENT } from "../../data/profileOptions"
import "./reverse.css"

type Filter = "all" | PolicyStatus | "saved"
export default function ResultPage({ snapshot, setPage, refresh, busy = false, error = "", savedPolicies, toggleSaved }: {
  snapshot: Snapshot | null
  setPage: (page: Page) => void
  refresh?: () => Promise<void>
  busy?: boolean
  error?: string
  savedPolicies: SavedPolicy[]
  toggleSaved: (policy: PolicyRow, profile: UserProfileInput) => void
}) {
  const [filter, setFilter] = useState<Filter>("all")
  const [search, setSearch] = useState("")
  const [query, setQuery] = useState("")
  if (!snapshot) return <section className="reverse-page"><PageHeading eyebrow="내 조건에서 시작하는 복지 역설계" title="내 조건으로 정책 조회" description="내 정보를 입력하면 정책별 부족한 조건과 확인할 행동을 살펴볼 수 있어요." /><div className="interface-empty"><h2>먼저 내 조건을 알려주세요</h2><p>자격 진단을 완료하면 분석 결과와 정책 링크가 표시됩니다.</p><button className="interface-primary" onClick={() => setPage("diagnosis")}>내 조건 입력하기 →</button></div></section>
  const { profile, analysis } = snapshot
  const rows = policyResults(snapshot)
  const key = profileKey(profile)
  const savedIds = new Set(savedPolicies.filter(p => p.profileKey === key).map(p => p.policy.id))
  const counts = { eligible: rows.filter(p => p.status === "eligible").length, ineligible: rows.filter(p => p.status === "ineligible").length, needs_review: rows.filter(p => p.status === "needs_review").length }
  const filtered = rows.filter(p => (filter === "all" || (filter === "saved" ? savedIds.has(p.id) : p.status === filter)) && p.title.toLocaleLowerCase().includes(query.trim().toLocaleLowerCase()))
  const filters: { id: Filter; label: string; count: number }[] = [ { id: "all", label: "전체", count: rows.length }, { id: "eligible", label: "신청 가능", count: counts.eligible }, { id: "ineligible", label: "신청 불가", count: counts.ineligible }, { id: "needs_review", label: "추가 확인 필요", count: counts.needs_review }, { id: "saved", label: "관심 정책", count: rows.filter(p => savedIds.has(p.id)).length } ]
  return <section className="reverse-page" aria-busy={busy}>
    <PageHeading eyebrow="WELFARE REVERSE DESIGN / 복지 역설계" title="내 조건으로 정책 조회" description="신청 가능한 정책을 찾고, 부족한 조건과 확인할 행동을 살펴보세요. 분류는 서버의 자동 비교 기준입니다." action={refresh && <button className="interface-primary" disabled={busy} onClick={() => void refresh()}>{busy ? "정책 조회 중…" : "↻ 최신 결과 조회"}</button>}>
      <div className="analysis-summary" aria-label="전체 분석 요약"><strong>총 {analysis.matched.evaluated_count ?? rows.length}건 분석</strong><span>신청 가능 {counts.eligible}건</span><span>신청 불가 {counts.ineligible}건</span><span>추가 확인 {counts.needs_review}건</span></div>
    </PageHeading>
    {busy && <p className="analysis-notice" role="status">저장된 프로필로 최신 분석을 조회하고 있어요. 완료 전까지 이전 결과를 표시합니다.</p>}
    {error && <p className="reverse-alert" role="alert">{error} 마지막 조회 결과를 유지합니다. ‘최신 결과 조회’로 다시 시도해주세요.</p>}
    <div className="reverse-layout"><aside className="reverse-sidebar"><section className="reverse-profile"><p className="reverse-kicker">분석에 사용한 프로필</p><h2>이번 진단의 내 조건</h2><dl><div><dt>나이</dt><dd>만 {profile.age}세</dd></div><div><dt>거주지</dt><dd>{profile.region}</dd></div><div><dt>고용 상태</dt><dd>{EMPLOYMENT.find(([id]) => id === profile.employment_status)?.[1] ?? profile.employment_status}</dd></div><div><dt>월 소득</dt><dd>{profile.income_level.toLocaleString("ko-KR")}원</dd></div></dl>
      <p className="reverse-small">마지막 조회<br /><time dateTime={snapshot.checkedAt}>{formatTime(snapshot.checkedAt)}</time><br />정책 데이터 수집 시각과 다를 수 있어요.</p><button className="reverse-edit" disabled={busy} onClick={() => setPage("diagnosis")}>내 정보 수정 후 재진단 →</button><button className="reverse-edit" onClick={() => setPage("dashboard")}>이 프로필의 관심 정책 보기 →</button>
    </section><section className="reverse-note"><h2>추가 확인은 무슨 뜻인가요?</h2><p>자동으로 비교하지 못한 조건이 남은 정책입니다. 신청 불가를 의미하지 않아요.</p><p>조건 비교표를 읽고 ‘정책 확인하러 가기’로 공식 안내를 확인해주세요.</p></section></aside>
    <div className="reverse-content"><form className="reverse-search" onSubmit={event => { event.preventDefault(); setQuery(search) }}><label htmlFor="reverse-policy-search">정책명 조회</label><div><input id="reverse-policy-search" value={search} onChange={event => setSearch(event.target.value)} placeholder="조회할 정책명을 입력하세요" /><button className="interface-primary" type="submit">조회</button><button className="search-reset" type="button" onClick={() => { setSearch(""); setQuery(""); setFilter("all") }}>초기화</button></div><p>현재 분석 결과 안에서 검색합니다. 관심 정책 전체 목록은 ‘나의 현황’에서 확인할 수 있어요.</p></form>
      <div className="analysis-filters" aria-label="분석 결과 필터">{filters.map(item => <button key={item.id} aria-pressed={filter === item.id} onClick={() => setFilter(item.id)}>{item.label} <strong>{item.count}</strong></button>)}</div>
      <header className="reverse-section-title"><p className="reverse-kicker">나의 분석 결과</p><h2>{filter === "all" ? "전체 정책" : filter === "saved" ? "이번 조회의 관심 정책" : statusLabels[filter]} <small>{filtered.length}개</small></h2><p role="status">{query ? `‘${query}’ 검색 결과입니다.` : "정책별 비교 결과와 확인 안내를 살펴보세요."}</p></header>
      {filtered.length > 0 ? <div className="reverse-list">{filtered.map(policy => <AnalysisPolicyCard key={policy.id} policy={policy} saved={savedIds.has(policy.id)} toggle={() => toggleSaved(policy, profile)} />)}</div> : <div className="reverse-empty"><h3>{rows.length === 0 ? "서버에서 제공된 정책 결과가 없어요" : "조건에 맞는 정책이 없어요"}</h3><p>{rows.length === 0 ? "정책 데이터가 없거나 분석 결과가 제공되지 않았을 수 있습니다. 결과가 없다고 자격이 없다는 뜻은 아닙니다." : filter === "saved" ? "관심 있는 정책의 ‘관심 저장’을 눌러보세요. 이전에 저장한 정책은 나의 현황에서 확인할 수 있어요." : "검색어 또는 분류를 바꾸어 확인해주세요."}</p>{rows.length > 0 && <button className="interface-primary" onClick={() => { setSearch(""); setQuery(""); setFilter("all") }}>전체 결과 보기</button>}</div>}
      <p className="reverse-footnote">이 결과는 입력 정보와 서버의 정책 조건을 바탕으로 한 사전 안내입니다. 최종 수급 자격과 신청 가능 여부는 담당 기관에서 확인해주세요.</p>
    </div></div>
  </section>
}
