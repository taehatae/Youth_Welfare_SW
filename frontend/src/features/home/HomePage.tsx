import { useEffect, useRef, useState, type FormEvent } from "react"

import CountUp from "../../components/motion/CountUp"
import { BrandLogo } from "../../components/brand/BrandLogo"
import {
  cardBrief,
  metCountOf,
  resultCategoryOf,
} from "../../components/policy/AnalysisPolicyCard"
import type { PolicyRow } from "../../services/policyResults"
import { loadPolicyCatalog } from "../../services/welfareApi"
import {
  CATALOG_CATEGORIES,
  type CatalogPolicy,
  type CatalogResponse,
} from "../../types/policyCatalog"
import type { Page } from "../../types/page"

import "./home.css"

/** 라이선스 사진이 생기면 경로를 넣는다. null이면 타이포그래피 히어로로 보인다. */
const HERO_IMAGE: string | null = null

const TONES: Record<string, string> = {
  housing: "blue",
  employment: "mint",
  finance: "butter",
  education: "lav",
  health: "pink",
  living: "mint",
  culture: "butter",
  safety: "lav",
  other: "gray",
}

const STEPS = [
  "나이·지역·소득 등 기본 정보를 입력해요",
  "정책마다 신청 가능 / 확인 필요 / 불가로 나눠 보여줘요",
  "안 되는 정책은 무엇이 바뀌면 되는지 알려줘요",
]

const explorerHref = (params: { category?: string; q?: string }) => {
  const search = new URLSearchParams()
  if (params.category && params.category !== "all")
    search.set("category", params.category)
  if (params.q) search.set("q", params.q)
  return "#explorer" + (search.size ? "?" + search.toString() : "")
}

// 카탈로그 목록 응답에 마감일이 없으면 null(표시 안 함)
function daysLeft(policy: CatalogPolicy) {
  const end = (policy as { application_end_date?: string }).application_end_date
  if (!end) return null
  const date = new Date(end + "T23:59:59")
  if (Number.isNaN(date.getTime())) return null
  const days = Math.ceil((date.getTime() - Date.now()) / 86_400_000)
  return days >= 0 ? days : null
}

export default function HomePage({
  setPage,
  onOpenChat,
  myResults,
}: {
  setPage: (page: Page) => void
  /** 간편 정책 찾기 채팅 위젯 열기(없으면 전체 화면 페이지로 이동) */
  onOpenChat?: () => void
  /** 로그인 후 최근 진단 결과(없으면 undefined) */
  myResults?: PolicyRow[]
}) {
  const [catalog, setCatalog] = useState<CatalogResponse | null>(null)
  const [state, setState] = useState<"loading" | "ready" | "error">("loading")
  const [query, setQuery] = useState("")
  const hero = useRef<HTMLElement>(null)

  // 히어로 스크롤 효과: 히어로가 화면 근처에 있을 때만 스크롤을 듣고 --hero-p(0~1)를 갱신한다.
  useEffect(() => {
    const el = hero.current
    if (
      !el ||
      !("IntersectionObserver" in window) ||
      window.matchMedia("(prefers-reduced-motion: reduce)").matches
    )
      return
    let frame = 0
    const update = () => {
      frame = 0
      const p = Math.min(1, Math.max(0, window.scrollY / Math.max(1, el.offsetHeight)))
      el.style.setProperty("--hero-p", p.toFixed(3))
    }
    const onScroll = () => {
      if (!frame) frame = requestAnimationFrame(update)
    }
    const io = new IntersectionObserver(
      ([entry]) => {
        window.removeEventListener("scroll", onScroll)
        if (entry.isIntersecting) {
          window.addEventListener("scroll", onScroll, { passive: true })
          onScroll()
        }
      },
      { rootMargin: "200px 0px" },
    )
    io.observe(el)
    return () => {
      io.disconnect()
      window.removeEventListener("scroll", onScroll)
      if (frame) cancelAnimationFrame(frame)
    }
  }, [])

  useEffect(() => {
    let alive = true
    loadPolicyCatalog("", "all", 1)
      .then((data) => {
        if (!alive) return
        setCatalog(data)
        setState("ready")
      })
      .catch(() => alive && setState("error"))
    return () => {
      alive = false
    }
  }, [])

  const total = catalog?.total
  const counts = new Map(catalog?.categories.map((c) => [c.id, c.count]))

  // App의 hashchange 핸들러가 탐색 화면으로 바꾸고 주소를 기억한다.
  const submit = (event: FormEvent) => {
    event.preventDefault()
    window.location.hash = explorerHref({ q: query.trim().slice(0, 100) })
  }

  const deadlines = (catalog?.items ?? [])
    .map((policy) => ({ policy, days: daysLeft(policy) }))
    .filter((x): x is { policy: CatalogPolicy; days: number } => x.days !== null)
    .sort((a, b) => a.days - b.days)
    .slice(0, 5)

  const mine = (myResults ?? [])
    .filter((row) => resultCategoryOf(row) === "likely")
    .sort((a, b) => metCountOf(b) - metCountOf(a))
    .slice(0, 5)

  return (
    <div className="home">
      <section ref={hero} className="home-wrap home-hero-wrap" aria-labelledby="home-title">
        <div
          className="home-hero-media"
          style={
            HERO_IMAGE ? { backgroundImage: `url(${HERO_IMAGE})` } : undefined
          }
          data-photo={HERO_IMAGE ? "true" : "false"}
        >
          {!HERO_IMAGE && (
            <span className="home-hero-mark" aria-hidden="true">
              자격
            </span>
          )}
          <div className="home-hero-copy">
            <h1 id="home-title" data-reveal>
              받을 수 있는 지원,
              <br />
              3분이면 알 수 있어요
            </h1>
            <p data-reveal>
              {total ? `${total}개 ` : ""}청년 정책을 내 조건으로 한 번에
              비교해요.
            </p>
            <button
              type="button"
              className="home-cta"
              data-reveal
              onClick={() => setPage("diagnosis")}
            >
              내 자격 확인하기 <span aria-hidden="true">→</span>
            </button>
            <button
              type="button"
              className="home-cta home-cta-ghost"
              data-reveal
              onClick={() => (onOpenChat ? onOpenChat() : setPage("quick"))}
            >
              로그인 없이 간편 정책 찾기 <span aria-hidden="true">→</span>
            </button>
          </div>
        </div>
        <form className="home-search" role="search" onSubmit={submit}>
          <label className="home-sr" htmlFor="home-q">
            정책 검색
          </label>
          <span aria-hidden="true" className="home-search-icon">
            ⌕
          </span>
          <input
            id="home-q"
            type="search"
            maxLength={100}
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="월세 지원, 취업 수당, 전세 대출… 찾는 정책을 검색해 보세요"
          />
          <button type="submit">검색</button>
        </form>
      </section>

      <div className="home-wrap home-grid">
        <div className="home-main">
          <section aria-labelledby="home-cats">
            <h2 id="home-cats" className="home-sec" data-reveal="repeat">
              분야별로 보기
              {total ? <small>전체 <CountUp value={total} />개</small> : null}
            </h2>
            <ul className="home-tiles">
              {state === "loading" ? (
                Array.from({ length: 8 }, (_, i) => (
                  <li
                    key={i}
                    className="home-tile home-skeleton"
                    aria-hidden="true"
                  />
                ))
              ) : (
                <>
                  {CATALOG_CATEGORIES.filter(([id]) => id !== "all").map(
                    ([id, label]) => {
                      const count = counts.get(id)
                      if (state === "ready" && !count) return null
                      return (
                        <li key={id} data-reveal="repeat" data-reveal-style="pop">
                          <a
                            className="home-tile"
                            href={explorerHref({ category: id })}
                          >
                            <i
                              className={`tone-${TONES[id] ?? "gray"}`}
                              aria-hidden="true"
                            >
                              {label[0]}
                            </i>
                            <span>
                              <b>{label}</b>
                              {state === "ready" && <small><CountUp value={count ?? 0} />개</small>}
                            </span>
                          </a>
                        </li>
                      )
                    },
                  )}
                  <li data-reveal="repeat" data-reveal-style="pop">
                    <a className="home-tile" href={explorerHref({})}>
                      <i className="tone-gray" aria-hidden="true">
                        +
                      </i>
                      <span>
                        <b>전체 보기</b>
                        {total ? <small><CountUp value={total} />개</small> : null}
                      </span>
                    </a>
                  </li>
                </>
              )}
            </ul>
          </section>

          <section aria-labelledby="home-mine">
            <h2 id="home-mine" className="home-sec" data-reveal="repeat">
              내 조건에 맞는 정책
            </h2>
            {mine.length ? (
              <ol className="home-rank">
                {mine.map((row, i) => (
                  <li key={row.id} data-reveal="repeat" data-reveal-style="slide">
                    <a href={`#detail/${encodeURIComponent(row.id)}`}>
                      <em>{i + 1}</em>
                      <span>
                        <b>{row.title}</b>
                        <small>{cardBrief(row)}</small>
                      </span>
                    </a>
                  </li>
                ))}
              </ol>
            ) : (
              <div className="home-prompt" data-reveal="repeat" data-reveal-style="slide">
                <p>진단하면 내 조건에 맞는 정책을 여기서 바로 보여드려요</p>
                <button type="button" onClick={() => setPage("diagnosis")}>
                  진단하러 가기
                </button>
              </div>
            )}
          </section>
        </div>

        <aside className="home-side">
          {/* 마감일 데이터가 들어오기 전에는 카드 자체를 숨긴다 */}
          {deadlines.length > 0 && <section className="home-card" data-reveal="repeat" aria-labelledby="home-dday">
            <h3 id="home-dday">마감이 가까운 정책</h3>
            {deadlines.length ? (
              <ul className="home-dday">
                {deadlines.map(({ policy, days }) => (
                  <li key={policy.id}>
                    <a href={`#detail/${encodeURIComponent(policy.id)}`}>
                      <span>{policy.title}</span>
                      <b>{days === 0 ? "D-Day" : `D-${days}`}</b>
                    </a>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="home-empty">지금 마감이 가까운 정책이 없어요</p>
            )}
          </section>}
          <section className="home-card" data-reveal="repeat" aria-labelledby="home-how">
            <h3 id="home-how">이렇게 확인해요</h3>
            <ol className="home-steps">
              {STEPS.map((text, i) => (
                <li key={text}>
                  <b>{i + 1}</b>
                  {text}
                </li>
              ))}
            </ol>
          </section>
        </aside>
      </div>

      <footer className="home-wrap home-footer" data-reveal="repeat">
        <BrandLogo width={112} />
        <p>내 조건을 이해하고, 다음 가능성을 발견하는 곳.</p>
        <button type="button" onClick={() => setPage("diagnosis")}>
          내 자격 확인하기 →
        </button>
      </footer>
    </div>
  )
}
