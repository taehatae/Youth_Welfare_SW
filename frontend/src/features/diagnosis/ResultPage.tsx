import { useState } from "react"
import PageHeading from "../../components/layout/PageHeading"
import AnalysisPolicyCard, {
  resultCategoryOf,
  resultCategoryLabels,
  resultCategoryOrder,
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
import "./reverse.css"

type Filter = "all" | ResultCategory | "saved" | "changed"
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
  if (!snapshot)
    return (
      <section className="reverse-page">
        <PageHeading
          eyebrow="내 조건에서 시작하는 복지 역설계"
          title="내 조건으로 정책 조회"
          description="내 정보를 입력하면 정책별 부족한 조건과 확인할 행동을 살펴볼 수 있어요."
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
  const rows = [...policyResults(snapshot)].sort(
    (a, b) =>
      resultCategoryOrder.indexOf(resultCategoryOf(a)) -
      resultCategoryOrder.indexOf(resultCategoryOf(b)),
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
            count: changedIds.size,
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
  return (
    <section className="reverse-page" aria-busy={busy}>
      <PageHeading
        eyebrow="내 조건으로 살펴본 정책"
        title="진단 결과"
        description="진단 당시 입력 정보와 결과를 보관한 기록이에요. 최신 정책 현황은 ‘나의 현황’에서 다시 조회할 수 있어요."
        action={
          <button
            className="interface-primary"
            onClick={() => setPage("dashboard")}
          >
            최신 현황 확인 →
          </button>
        }
      >
        <div className="analysis-summary" aria-label="전체 분석 요약">
          <strong>
            총 {analysis.matched.evaluated_count ?? rows.length}건 분석
          </strong>
          {resultCategoryOrder.map((category) => (
            <span key={category} data-category={category}>
              {resultCategoryLabels[category]} {counts[category]}건
            </span>
          ))}
        </div>
      </PageHeading>
      <AnalysisChanges
        key={snapshot.checkedAt}
        previous={previous}
        current={snapshot}
        mode="diagnosis"
      />
      <div className="reverse-layout">
        <aside className="reverse-sidebar">
          <section data-reveal className="reverse-profile">
            <p className="reverse-kicker">분석에 사용한 프로필</p>
            <h2>이번 진단의 내 조건</h2>
            <p className="reverse-small">저장된 입력값은 본인 확인 후 조회할 수 있어요.</p>
            <button className="reverse-edit" disabled={busy} onClick={onViewProfile}>본인 확인 후 프로필 조회 →</button>
            <p className="reverse-small">
              진단 시각
              <br />
              <time dateTime={snapshot.checkedAt}>
                {formatTime(snapshot.checkedAt)}
              </time>
              <br />
              정책 데이터 수집 시각과 다를 수 있어요.
            </p>
            <button
              className="reverse-edit"
              disabled={busy}
              onClick={() => onEdit(0)}
            >
              내 정보 수정 후 재진단 →
            </button>
            <button
              className="reverse-edit"
              onClick={() => setPage("dashboard")}
            >
              이 프로필의 관심 정책 보기 →
            </button>
          </section>
          <section data-reveal className="reverse-note">
            <h2>결과는 이렇게 나눠요</h2>
            <p>
              판정은 내가 입력한 정보와 비교할 수 있는 조건만으로 해요.
            </p>
            <p>
              <strong>신청 가능</strong> 입력한 정보와 맞지 않는 조건이 없어요.
              입력값으로 비교할 수 없는 조건은 카드의 추가 확인 항목을
              봐주세요.
            </p>
            <p>
              <strong>신청 불가</strong> 입력한 정보로 비교한 조건 중 부족한
              조건이 있어요. 카드에서 어떤 조건인지 확인하세요.
            </p>
          </section>
        </aside>
        <div className="reverse-content">
          <form
            className="reverse-search"
            onSubmit={(event) => {
              event.preventDefault()
              setQuery(search)
            }}
          >
            <label htmlFor="reverse-policy-search">정책명 조회</label>
            <div>
              <input
                id="reverse-policy-search"
                value={search}
                onChange={(event) => setSearch(event.target.value)}
                placeholder="조회할 정책명을 입력하세요"
              />
              <button className="interface-primary" type="submit">
                조회
              </button>
              <button
                className="search-reset"
                type="button"
                onClick={() => {
                  setSearch("")
                  setQuery("")
                  setFilter("all")
                }}
              >
                초기화
              </button>
            </div>
            <p>
              이번 진단 결과 안에서 검색합니다. 이전 관심 정책은 ‘나의 현황’에서
              확인할 수 있어요.
            </p>
          </form>
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
          {filtered.length > 0 ? (
            <div className="reverse-list">
              {filtered.map((policy, index) => (
                <AnalysisPolicyCard
                  key={policy.id}
                  index={index}
                  policy={policy}
                  saved={savedIds.has(policy.id)}
                  toggle={() => toggleSaved(policy, key)}
                  onEdit={onEdit}
                  busy={busy}
                />
              ))}
            </div>
          ) : (
            <div className="reverse-empty">
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
                <button
                  className="interface-primary"
                  onClick={() => {
                    setSearch("")
                    setQuery("")
                    setFilter("all")
                  }}
                >
                  전체 결과 보기
                </button>
              )}
            </div>
          )}
          <p className="reverse-footnote">
            이 결과는 입력 정보와 서버의 정책 조건을 바탕으로 한 사전
            안내입니다. 최종 수급 자격과 신청 가능 여부는 담당 기관에서
            확인해주세요.
          </p>
        </div>
      </div>
    </section>
  )
}
