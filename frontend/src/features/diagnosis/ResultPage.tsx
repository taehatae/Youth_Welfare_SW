import { useState } from "react"
import { useMediaQuery } from "../../hooks/useMediaQuery"
import CountUp from "../../components/motion/CountUp"
import PageHeading from "../../components/layout/PageHeading"
import AnalysisPolicyCard, {
  cardBrief,
  isUnverified,
  tabCounts,
  metCountOf,
  resultCategoryOf,
  resultCategoryLabels,
  resultCategoryOrder,
  type ConditionTab,
  type ResultCategory,
} from "../../components/policy/AnalysisPolicyCard"
import AnalysisChanges, {
  changedPolicyIds,
} from "../../components/policy/AnalysisChanges"
import type { Page } from "../../types/page"
import { formatTime, type Snapshot } from "../../services/analysisSession"
import {
  policyResults,
  type PolicyRow,
  type SavedPolicy,
} from "../../services/policyResults"
import Mascot from "../../components/brand/Mascot"
import "./reverse.css"
import "./result.css"

type Filter = "all" | ResultCategory | "saved" | "changed"
// 같은 분류 안에서는 입력값과 대조해 충족한 조건이 많은 정책을 먼저 보여준다.
const metCount = metCountOf
const initialOf = (title: string) => {
  const t = title.replace(/^\s*[(（\[][^)）\]]*[)）\]]\s*/, "").trim() || title.trim()
  return Array.from(t)[0] ?? "?"
}
const pillText = (
  category: ResultCategory,
  c: { passed: number; failed: number; review: number },
) =>
  category === "gap"
    ? `미충족 ${c.failed}`
    : category === "review"
      ? `추가 확인 ${c.review}`
      : `충족 ${c.passed}`
export default function ResultPage({
  snapshot,
  previous,
  setPage,
  busy = false,
  savedPolicies,
  toggleSaved,
  onEdit,
  onViewProfile,
}: {
  snapshot: Snapshot | null
  previous: Snapshot | null
  setPage: (page: Page) => void
  busy?: boolean
  savedPolicies: SavedPolicy[]
  toggleSaved: (policy: PolicyRow, profileKey: string) => void
  onViewProfile: () => void
  onEdit: (step: number) => void
}) {
  const [filter, setFilter] = useState<Filter>("all")
  const [search, setSearch] = useState("")
  const [query, setQuery] = useState("")
  // 지금은 원문 기준으로 자격 경로를 검수한 정책만 기본으로 보여준다(체크를 끄면 전체).
  const [reviewedOnly, setReviewedOnly] = useState(true)
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const wide = useMediaQuery("(min-width: 1100px)")
  if (!snapshot)
    return (
      <section className="reverse-page">
        <PageHeading
          eyebrow="내 조건에서 시작하는 복지 역설계"
          title="내 조건으로 정책 조회"
          description="내 정보를 입력하면 정책별 부족한 조건과 충족에 필요한 기준을 살펴볼 수 있어요."
        />
        <div className="interface-empty">
          <h2>먼저 내 조건을 알려주세요</h2>
          <p>자격 진단을 완료하면 분석 결과와 정책 링크가 표시됩니다.</p>
          <button
            className="interface-primary"
            onClick={() => setPage("diagnosis")}
          >
            내 조건 입력하기 →
          </button>
        </div>
      </section>
    )
  const { analysis } = snapshot
  const allRows = policyResults(snapshot)
  const reviewedCount = allRows.filter((p) => p.pathReview === "reviewed").length
  // 검수 정보가 없는 이전 결과는 필터 없이 전체를 보여준다.
  const onlyReviewed = reviewedOnly && reviewedCount > 0
  const rows = allRows.filter((p) => !onlyReviewed || p.pathReview === "reviewed").sort(
    (a, b) =>
      resultCategoryOrder.indexOf(resultCategoryOf(a)) -
        resultCategoryOrder.indexOf(resultCategoryOf(b)) ||
      metCount(b) - metCount(a),
  )
  const key = snapshot.profileKey ?? ""
  const savedIds = new Set(
    savedPolicies.filter((p) => p.profileKey === key).map((p) => p.policy.id),
  )
  const changedIds = changedPolicyIds(previous, snapshot)
  const counts = Object.fromEntries(
    resultCategoryOrder.map((category) => [
      category,
      rows.filter((p) => resultCategoryOf(p) === category).length,
    ]),
  ) as Record<ResultCategory, number>
  const unverifiedCount = rows.filter(isUnverified).length
  const filtered = rows.filter(
    (p) =>
      (filter === "all" ||
        (filter === "saved"
          ? savedIds.has(p.id)
          : filter === "changed"
            ? changedIds.has(p.id)
            : resultCategoryOf(p) === filter)) &&
      p.title.toLocaleLowerCase().includes(query.trim().toLocaleLowerCase()),
  )
  const filters: {
    id: Filter
    label: string
    count: number
  }[] = [
    { id: "all", label: "전체", count: rows.length },
    ...resultCategoryOrder.map((category) => ({
      id: category,
      label: resultCategoryLabels[category],
      count: counts[category],
    })),
    {
      id: "saved",
      label: "관심 정책",
      count: rows.filter((p) => savedIds.has(p.id)).length,
    },
    ...(previous
      ? [
          {
            id: "changed" as const,
            label: "추가·변경 정책",
            count: rows.filter((p) => changedIds.has(p.id)).length,
          },
        ]
      : []),
  ]
  const title =
    filter === "all"
      ? "전체 정책"
      : filter === "saved"
        ? "이번 진단의 관심 정책"
        : filter === "changed"
          ? "추가·변경 정책"
          : resultCategoryLabels[filter]
  const selected =
    filtered.find((p) => p.id === selectedId) ?? filtered[0] ?? null
  const total = onlyReviewed
    ? rows.length
    : (analysis.matched.evaluated_count ?? rows.length)
  const pct = (n: number) => (rows.length ? Math.round((n / rows.length) * 100) : 0)
  const resetAll = () => {
    setSearch("")
    setQuery("")
    setFilter("all")
  }
  const guideOf = (policy: PolicyRow) =>
    key.length === 64 && policy.pathReview === "reviewed" && policy.paths?.length
      ? {
          snapshot: "diagnosis" as const,
          profile_key: key,
          checked_at: snapshot.checkedAt,
          policy_id: policy.id,
        }
      : undefined
  const firstTab = (policy: PolicyRow): ConditionTab | null => {
    const c = tabCounts(policy)
    return c.failed > 0 ? "failed" : c.review > 0 ? "review" : c.passed > 0 ? "passed" : null
  }
  const sectionTitle = (
    <header className="reverse-section-title">
      <p className="reverse-kicker">나의 분석 결과</p>
      <h2>
        {title} <small>{filtered.length}개</small>
      </h2>
      <p role="status">
        {query
          ? `‘${query}’ 검색 결과입니다.`
          : filter === "changed"
            ? "직전 진단에 비해 추가되거나 판정·조건 안내가 바뀐 정책입니다. 제외된 정책은 위 비교에서 확인하세요."
            : "조건별 집계와 핵심 사유를 먼저 확인하고, 필요한 내용을 펼쳐보세요."}
      </p>
    </header>
  )
  const footnote = (
    <p className="reverse-footnote">
      이 결과는 입력 정보와 서버의 정책 조건을 바탕으로 한 사전
      안내입니다. 최종 수급 자격과 신청 가능 여부는 담당 기관에서
      확인해주세요.
    </p>
  )
  const empty = (
    <div className="reverse-empty">
      <Mascot pose="think" size={110} className="mascot-center" />
      <h3>
        {rows.length === 0
          ? "서버에서 제공된 정책 결과가 없어요"
          : "조건에 맞는 정책이 없어요"}
      </h3>
      <p>
        {rows.length === 0
          ? "정책 데이터가 없거나 분석 결과가 제공되지 않았을 수 있습니다. 결과가 없다고 자격이 없다는 뜻은 아닙니다."
          : filter === "changed"
            ? "이번 결과에 추가되거나 변경된 정책이 없어요."
            : filter === "saved"
              ? "관심 있는 정책의 ‘관심 저장’을 눌러보세요."
              : "검색어 또는 분류를 바꾸어 확인해주세요."}
      </p>
      {rows.length > 0 && (
        <button className="interface-primary" onClick={resetAll}>
          전체 결과 보기
        </button>
      )}
    </div>
  )
  return (
    <section className="reverse-page result-page" aria-busy={busy}>
      <div className="result-hero" data-reveal>
        <div className="result-hero-title">
          <p className="result-eyebrow">내 조건으로 살펴본 정책</p>
          <h1>진단 결과</h1>
          <p className="result-hero-desc">
            입력한 정보로 {total}개 정책을 비교했어요.
            <br />
            신청할 수 있는 정책과, 무엇이 바뀌면 되는지 확인해 보세요.
          </p>
          <p className="result-meta">
            <span>진단 시각</span>
            <time dateTime={snapshot.checkedAt}>{formatTime(snapshot.checkedAt)}</time>
            <button type="button" className="result-link" disabled={busy} onClick={onViewProfile}>
              본인 확인 후 프로필 조회 →
            </button>
          </p>
        </div>
        <div className="result-hero-actions">
          <Mascot pose="thumbs" size={150} className="result-m-thumbs" delay={0.4} />
          <button className="result-btn-ghost" disabled={busy} onClick={() => onEdit(0)}>
            내 정보 수정
          </button>
          <button className="result-btn-primary" onClick={() => setPage("dashboard")}>
            최신 현황 보기 →
          </button>
        </div>
      </div>
      <div className="result-stats" aria-label="전체 분석 요약">
        <div className="result-stat result-stat-total" data-reveal>
          <span className="result-stat-label">
            총 분석
            {onlyReviewed && <span className="result-chip">검수 완료 {reviewedCount}</span>}
          </span>
          <p className="result-stat-num">
            <CountUp value={total} />
            <small>건</small>
          </p>
          <div className="result-ratio" aria-hidden="true">
            {resultCategoryOrder.map((category) => (
              <i key={category} data-category={category} style={{ flexGrow: counts[category] }} />
            ))}
          </div>
          <p className="result-stat-foot">
            가능 {pct(counts.likely)}% · 확인 필요 {pct(counts.review)}% · 불가 {pct(counts.gap)}%
          </p>
        </div>
        {resultCategoryOrder.map((category) => (
          <button
            key={category}
            type="button"
            className="result-stat result-stat-cat"
            data-reveal
            data-category={category}
            aria-pressed={filter === category}
            onClick={() => setFilter(filter === category ? "all" : category)}
          >
            <span className="result-stat-label">
              {resultCategoryLabels[category]}
              <span className="result-chip">{pct(counts[category])}%</span>
            </span>
            <span className="result-stat-num">
              <CountUp value={counts[category]} />
              <small>건</small>
            </span>
            <span className="result-bar" aria-hidden="true">
              <i style={{ width: `${pct(counts[category])}%` }} />
            </span>
          </button>
        ))}
      </div>
      {unverifiedCount > 0 && (
        <p className="analysis-unverified result-unverified">
          신청 가능 {counts.likely}건 중 <strong>{unverifiedCount}건</strong>은
          입력한 정보로 비교할 수 있는 조건이 없어 ‘비교 조건 없음’으로 표시했어요.
          이 정책들은 공식 안내에서 세부 자격을 꼭 확인해주세요.
        </p>
      )}
      <AnalysisChanges
        key={snapshot.checkedAt}
        previous={previous}
        current={snapshot}
        mode="diagnosis"
      />
      <div className="result-toolbar" data-reveal>
        <div className="result-toolbar-row">
          <div className="analysis-filters" aria-label="분석 결과 필터">
            {filters.map((item) => (
              <button
                key={item.id}
                data-category={item.id}
                aria-pressed={filter === item.id}
                onClick={() => setFilter(item.id)}
              >
                {item.label} <strong>{item.count}</strong>
              </button>
            ))}
          </div>
          <form
            className="reverse-search result-search"
            onSubmit={(event) => {
              event.preventDefault()
              setQuery(search)
            }}
          >
            <label htmlFor="reverse-policy-search" className="result-sr">정책명 조회</label>
            <div>
              <span className="result-input-wrap">
                <svg aria-hidden="true" viewBox="0 0 20 20" width="16" height="16" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round">
                  <circle cx="9" cy="9" r="5.5" />
                  <path d="m13.5 13.5 3.5 3.5" />
                </svg>
                <input
                  id="reverse-policy-search"
                  value={search}
                  onChange={(event) => setSearch(event.target.value)}
                  placeholder="조회할 정책명을 입력하세요"
                />
              </span>
              <button className="interface-primary" type="submit">
                조회
              </button>
              <button className="search-reset" type="button" onClick={resetAll}>
                초기화
              </button>
            </div>
          </form>
        </div>
        <p className="result-helper">
          이번 진단 결과 안에서 검색합니다. 이전 관심 정책은 ‘나의 현황’에서
          확인할 수 있어요.
        </p>
        <div className="result-toolbar-row2">
          {reviewedCount > 0 && (
            <label className="reviewed-only-toggle">
              <input
                type="checkbox"
                checked={reviewedOnly}
                onChange={(event) => setReviewedOnly(event.target.checked)}
              />
              <span className="result-switch" aria-hidden="true" />
              원문 기준으로 자격 경로를 검수한 정책만 보기 ({reviewedCount}개)
            </label>
          )}
          <details className="result-legend">
            <summary>판정 기준 보기</summary>
            <div className="result-legend-body">
              <h2>결과는 이렇게 나눠요</h2>
              <p>
                판정은 내가 입력한 정보와 비교할 수 있는 조건만으로 해요.
              </p>
              <p>
                정책마다 자격 경로(대상·유형별 조건)가 여러 개일 수 있고, 그중
                하나만 맞으면 돼요.
              </p>
              <p>
                <strong>신청 가능</strong> 입력한 정보로 비교한 조건을 모두
                충족하는 경로가 있어요. 입력값으로 비교할 수 없는 조건은 카드의
                확인 사항을 봐주세요.
              </p>
              <p>
                <strong>확인 필요</strong> 입력하지 않은 정보가 있거나, 입력값으로
                비교할 수 없는 경로가 있어요. 카드에서 무엇을 입력하면 되는지
                확인하세요.
              </p>
              <p>
                <strong>신청 불가</strong> 모든 경로에서 부족한 조건이 있어요.
                카드에서 현재 진단이 선택한 미충족 조건과 충족 기준을 확인하세요.
              </p>
            </div>
          </details>
        </div>
      </div>
      {wide && selected ? (
        <div className="result-master-detail">
          <div className="result-list-panel">
            {sectionTitle}
            <ul className="result-list">
              {filtered.map((policy) => {
                const c = tabCounts(policy)
                return (
                  <li key={policy.id} data-reveal>
                    <button
                      type="button"
                      data-category={resultCategoryOf(policy)}
                      aria-pressed={policy.id === selected.id}
                      aria-controls="result-detail"
                      onClick={() => setSelectedId(policy.id)}
                    >
                      <i className="result-ico" aria-hidden="true">{initialOf(policy.title)}</i>
                      <span className="result-row-main">
                        <strong>{policy.title}</strong>
                        <small>{cardBrief(policy)}</small>
                      </span>
                      <span className="result-row-side">
                        {savedIds.has(policy.id) && <b aria-label="관심 정책">★</b>}
                        <em className="result-pill">{pillText(resultCategoryOf(policy), c)}</em>
                      </span>
                    </button>
                  </li>
                )
              })}
            </ul>
          </div>
          <div id="result-detail" className="result-detail" role="region" aria-label="선택한 정책 상세">
            <AnalysisPolicyCard
              key={selected.id}
              index={0}
              policy={selected}
              guideTarget={guideOf(selected)}
              saved={savedIds.has(selected.id)}
              toggle={() => toggleSaved(selected, key)}
              onEdit={onEdit}
              busy={busy}
              defaultTab={firstTab(selected)}
            />
            {footnote}
          </div>
        </div>
      ) : (
        <div className="result-stacked">
          {sectionTitle}
          {filtered.length > 0 ? (
            <div className="reverse-list">
              {filtered.map((policy, index) => (
                <AnalysisPolicyCard
                  key={policy.id}
                  index={index}
                  policy={policy}
                  guideTarget={guideOf(policy)}
                  saved={savedIds.has(policy.id)}
                  toggle={() => toggleSaved(policy, key)}
                  onEdit={onEdit}
                  busy={busy}
                />
              ))}
            </div>
          ) : (
            empty
          )}
          {footnote}
        </div>
      )}
    </section>
  )
}
