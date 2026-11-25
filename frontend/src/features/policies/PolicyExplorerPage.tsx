import type { PolicyRow } from "../../services/policyResults"
import { useEffect, useRef, useState } from "react"

import PolicyCard from "../../components/policy/PolicyCard"

import { resultCategoryOf } from "../../components/policy/AnalysisPolicyCard"

import { CATEGORY_TONE, deadlineOf } from "./categoryStyle"
import CategoryIcon from "../../components/policy/CategoryIcon"

import { loadPolicyCatalog } from "../../services/welfareApi"

import {
  CATALOG_CATEGORIES,
  categoryLabel,
  type CatalogResponse,
} from "../../types/policyCatalog"

import Mascot from "../../components/brand/Mascot"
import "./catalog.css"

function filters() {
  const params = new URLSearchParams(window.location.hash.split("?")[1] ?? "")

  const category = params.get("category") ?? "all"

  const page = Number(params.get("page") ?? 1)

  return {
    category: CATALOG_CATEGORIES.some(([id]) => id === category)
      ? category
      : "all",

    query: (params.get("q") ?? "").slice(0, 100),
    page: Number.isSafeInteger(page) && page > 0 ? page : 1,
  }
}

// 페이지 번호: 처음·끝과 현재 앞뒤 1쪽을 보이고, 나머지는 …(null)로 줄인다.
function pageNumbers(current: number, total: number): (number | null)[] {
  const keep = new Set([1, total, current - 1, current, current + 1])
  const out: (number | null)[] = []
  for (let n = 1; n <= total; n++) {
    if (keep.has(n)) out.push(n)
    else if (out[out.length - 1] !== null) out.push(null)
  }
  return out
}

export default function PolicyExplorerPage({
  myResults,
}: {
  /** 로그인 후 최근 진단 결과(없으면 undefined) */
  myResults?: PolicyRow[]
} = {}) {
  const [sort, setSort] = useState<"default" | "deadline">("default")
  const [mineOnly, setMineOnly] = useState(false)
  const mine = new Map((myResults ?? []).map((row) => [row.id, resultCategoryOf(row)]))
  const [filter, setFilter] = useState(filters)

  const [search, setSearch] = useState(filter.query)

  const [result, setResult] = useState<{
    key: string
    data: CatalogResponse
  } | null>(null)

  const [failure, setFailure] = useState<{
    key: string
    message: string
  } | null>(null)

  const [retry, setRetry] = useState(0)

  const key = JSON.stringify(filter) + retry

  const heading = useRef<HTMLHeadingElement>(null)

  const focusResults = useRef(false)

  const data = result?.key === key ? result.data : null

  const error = failure?.key === key ? failure.message : ""

  useEffect(() => {
    const change = () => {
      const next = filters()
      setFilter(next)
      setSearch(next.query)
    }

    window.addEventListener("hashchange", change)

    return () => window.removeEventListener("hashchange", change)
  }, [])

  useEffect(() => {
    let active = true

    loadPolicyCatalog(filter.query, filter.category, filter.page)
      .then((data) => {
        if (active) setResult({ key, data })
      })
      .catch((error) => {
        if (active)
          setFailure({
            key,
            message:
              error instanceof Error
                ? error.message
                : "목록을 불러오지 못했어요.",
          })
      })

    return () => {
      active = false
    }
  }, [key])

  useEffect(() => {
    if (data && focusResults.current) {
      focusResults.current = false
      heading.current?.focus({ preventScroll: true })
      heading.current?.scrollIntoView({ block: "start", behavior: "smooth" })
    }
  }, [data])

  const navigate = (next: Partial<typeof filter>, focus = false) => {
    const value = { ...filter, ...next }
    const params = new URLSearchParams()

    if (value.category !== "all") params.set("category", value.category)

    if (value.query) params.set("q", value.query)

    if (value.page > 1) params.set("page", String(value.page))

    focusResults.current = focus

    window.location.hash =
      "explorer" + (params.size ? "?" + params.toString() : "")

    setSearch(value.query)
  }

  const pages = data ? Math.max(1, Math.ceil(data.total / data.page_size)) : 1

  const hasDeadline = !!data?.items.some((p) => deadlineOf(p) !== null)
  const shown = (data?.items ?? [])
    .filter((p) => !mineOnly || mine.get(p.id) === "likely")
    .map((p, i) => ({ p, i }))
    .sort((a, b) => {
      if (sort !== "deadline") return a.i - b.i
      const x = deadlineOf(a.p) ?? Infinity
      const y = deadlineOf(b.p) ?? Infinity
      return x === y ? a.i - b.i : x - y
    })
    .map(({ p }) => p)

  return (
    <section className="catalog-page">
      <div className="catalog-hero" data-reveal>
        <div className="catalog-top">
          <h1 ref={heading} tabIndex={-1} className="catalog-title">
            {filter.category === "all" ? "정책 찾기" : categoryLabel(filter.category) + " 정책"}
            {data && <span className="catalog-total">{data.total}개</span>}
          </h1>
          {/* 마감일 데이터가 있을 때만 정렬을 보여 준다 */}
          {hasDeadline && <div className="catalog-sort" role="group" aria-label="정렬">
            <button
              aria-pressed={sort === "default"}
              onClick={() => setSort("default")}
            >
              기본순
            </button>
            <button
              aria-pressed={sort === "deadline"}
              disabled={!hasDeadline}
              title={hasDeadline ? undefined : "신청 마감일 정보가 있는 정책에서만 쓸 수 있어요"}
              onClick={() => setSort("deadline")}
            >
              마감임박순
            </button>
          </div>}
        </div>
        <p className="catalog-lead">분야를 고르거나 검색해서 청년 정책을 찾아보세요.</p>
        <form
          className="catalog-search"
          role="search"
          onSubmit={(event) => {
            event.preventDefault()
            navigate({ query: search.trim(), page: 1 })
          }}
        >
          <label className="sr-only" htmlFor="catalog-search">
            정책명 또는 지원 내용
          </label>
          <span className="catalog-search-icon" aria-hidden="true">⌕</span>
          <input
            id="catalog-search"
            type="search"
            maxLength={100}
            value={search}
            onChange={(event) => setSearch(event.target.value)}
            placeholder="정책명 또는 지원 내용으로 검색 (예: 월세, 취업 수당)"
          />
          <button type="submit">검색</button>
        </form>
        <Mascot pose="search" size={130} className="catalog-m-search" delay={0.3} />
      </div>
      <nav className="catalog-categories" aria-label="정책 분야">
        {CATALOG_CATEGORIES.map(([id, label]) => (
          <button
            key={id}
            data-reveal
            data-tone={id === "all" ? "all" : CATEGORY_TONE[id] ?? "gray"}
            aria-pressed={filter.category === id}
            onClick={() => navigate({ category: id, page: 1 })}
          >
            <i aria-hidden="true"><CategoryIcon id={id} size={22} /></i>
            <b>{label}</b>
            <span>
              {data?.categories.find((c) => c.id === id)?.count ?? "–"}
            </span>
          </button>
        ))}
      </nav>
      {myResults && myResults.length > 0 && (
        <button
          className="catalog-mine"
          aria-pressed={mineOnly}
          onClick={() => setMineOnly((v) => !v)}
        >
          {mineOnly ? "✓ " : ""}내 조건에 맞는 것만
        </button>
      )}
      <div className="catalog-results-heading" data-reveal>
        <p role="status" aria-live="polite">
          {error
            ? "목록 조회에 실패했어요."
            : !data
              ? "정책을 불러오고 있어요…"
              : filter.query
                ? `‘${filter.query}’ 검색 결과예요.`
                : `공공 API에서 수집한 ${data.collected_count}개 정책을 살펴볼 수 있어요.`}
        </p>
        {(filter.query || filter.category !== "all") && (
          <button
            className="catalog-reset"
            onClick={() => navigate({ category: "all", query: "", page: 1 })}
          >
            조건 초기화
          </button>
        )}
      </div>
      <p className="catalog-help">
        제공 기관의 분야 분류를 기준으로 묶었어요. 여러 분야에 속한 정책은 중복
        표시되며, 개인별 자격은 자격 진단에서 확인할 수 있어요.
      </p>
      {error ? (
        <div className="catalog-state" role="alert">
          <h3>정책을 불러오지 못했어요</h3>
          <p>{error}</p>
          <button
            className="interface-primary"
            onClick={() => setRetry((n) => n + 1)}
          >
            다시 불러오기
          </button>
        </div>
      ) : !data ? (
        <div className="catalog-list" aria-hidden="true">
          {Array.from({ length: 8 }, (_, i) => (
            <div key={i} className="catalog-skeleton">
              <span />
              <span />
              <span />
            </div>
          ))}
        </div>
      ) : data.items.length === 0 ? (
        <div className="catalog-state">
          <Mascot pose="think" size={110} className="mascot-center" />
          <h3>
            {data.collected_count === 0
              ? "아직 등록된 정책이 없어요"
              : filter.page > pages
                ? "이 페이지에는 정책이 없어요"
                : "이 조건에 맞는 정책이 없어요"}
          </h3>
          <p>다른 분야를 선택하거나 검색어를 줄여보세요.</p>
          <button
            className="interface-primary"
            onClick={() => navigate({ category: "all", query: "", page: 1 })}
          >
            전체 정책 보기
          </button>
        </div>
      ) : shown.length === 0 ? (
        <div className="catalog-state">
          <Mascot pose="think" size={110} className="mascot-center" />
          <h3>이 페이지에는 내 조건에 맞는 정책이 없어요</h3>
          <p>다른 페이지나 분야를 보거나 필터를 꺼보세요.</p>
          <button className="interface-primary" onClick={() => setMineOnly(false)}>
            전체 보기
          </button>
        </div>
      ) : (
        <div key={key} className="catalog-list">
          {shown.map((policy, index) => (
            <PolicyCard
              key={policy.id}
              policy={policy}
              index={index}
              status={mine.get(policy.id)}
            />
          ))}
        </div>
      )}
      {data && data.total > 0 && filter.page <= pages && (
        <nav className="catalog-pagination" aria-label="정책 목록 페이지">
          <button
            className="catalog-page-step"
            disabled={filter.page <= 1}
            onClick={() => navigate({ page: filter.page - 1 }, true)}
          >
            <span aria-hidden="true">←</span> 이전
          </button>
          <ol className="catalog-page-numbers">
            {pageNumbers(filter.page, pages).map((n, i) =>
              n === null ? (
                <li key={"gap" + i} className="catalog-page-gap" aria-hidden="true">…</li>
              ) : (
                <li key={n}>
                  <button
                    aria-current={n === filter.page ? "page" : undefined}
                    aria-label={`${n}페이지`}
                    onClick={() => navigate({ page: n }, true)}
                  >
                    {n}
                  </button>
                </li>
              ),
            )}
          </ol>
          <span className="sr-only" aria-live="polite">
            {pages}페이지 중 {filter.page}페이지
          </span>
          <button
            className="catalog-page-step"
            disabled={filter.page >= pages}
            onClick={() => navigate({ page: filter.page + 1 }, true)}
          >
            다음 <span aria-hidden="true">→</span>
          </button>
        </nav>
      )}
      <aside className="catalog-bottom-note">
        신청 가능 여부와 접수 일정은 공식 공고를 확인해주세요. 목록은 서버에
        수집된 정책 기준이며, 실시간 공고 전체를 의미하지 않아요.
      </aside>
    </section>
  )
}
