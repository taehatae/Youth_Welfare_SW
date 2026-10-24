import { useEffect, useRef, useState } from "react"

import PageHeading from "../../components/layout/PageHeading"

import PolicyCard from "../../components/policy/PolicyCard"

import { loadPolicyCatalog } from "../../services/welfareApi"

import {
  CATALOG_CATEGORIES,
  categoryLabel,
  type CatalogResponse,
} from "../../types/policyCatalog"

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

export default function PolicyExplorerPage() {
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

  return (
    <section className="catalog-page">
      <PageHeading
        eyebrow="내 생활과 가까운 지원"
        title="필요한 정책을 찾아보세요"
        description="주거부터 일자리까지, 분야별 지원 내용과 신청 대상을 살펴보세요."
      >
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
          <input
            id="catalog-search"
            type="search"
            maxLength={100}
            value={search}
            onChange={(event) => setSearch(event.target.value)}
            placeholder="정책명 또는 지원 내용 검색"
          />
          <button className="interface-primary" type="submit">
            검색
          </button>
        </form>
      </PageHeading>
      <nav className="catalog-categories" aria-label="정책 분야">
        {CATALOG_CATEGORIES.map(([id, label]) => (
          <button
            key={id}
            aria-pressed={filter.category === id}
            onClick={() => navigate({ category: id, page: 1 })}
          >
            {label}
            <span>
              {data?.categories.find((c) => c.id === id)?.count ?? "–"}
            </span>
          </button>
        ))}
      </nav>
      <div className="catalog-results-heading">
        <div>
          <h2 ref={heading} tabIndex={-1}>
            {categoryLabel(filter.category)} 정책{" "}
            {data && <span>{data.total}개</span>}
          </h2>
          <p role="status" aria-live="polite">
            {error
              ? "목록 조회에 실패했어요."
              : !data
                ? "정책을 불러오고 있어요…"
                : filter.query
                  ? `‘${filter.query}’ 검색 결과예요.`
                  : `공공 API에서 수집한 ${data.collected_count}개 정책을 살펴볼 수 있어요.`}
          </p>
        </div>
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
        <div className="catalog-grid" aria-hidden="true">
          {Array.from({ length: 6 }, (_, i) => (
            <div key={i} className="catalog-skeleton">
              <span />
              <span />
              <span />
            </div>
          ))}
        </div>
      ) : data.items.length === 0 ? (
        <div className="catalog-state">
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
      ) : (
        <div key={key} className="catalog-grid">
          {data.items.map((policy, index) => (
            <PolicyCard key={policy.id} policy={policy} index={index} />
          ))}
        </div>
      )}
      {data && data.total > 0 && filter.page <= pages && (
        <nav className="catalog-pagination" aria-label="정책 목록 페이지">
          <button
            disabled={filter.page <= 1}
            onClick={() => navigate({ page: filter.page - 1 }, true)}
          >
            ← 이전
          </button>
          <span aria-live="polite">
            {filter.page} / {pages}
          </span>
          <button
            disabled={filter.page >= pages}
            onClick={() => navigate({ page: filter.page + 1 }, true)}
          >
            다음 →
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
