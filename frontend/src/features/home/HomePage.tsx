import { useEffect, useRef, useState, type FormEvent } from "react"

import CountUp from "../../components/motion/CountUp"
import { BrandLogo } from "../../components/brand/BrandLogo"
import Mascot from "../../components/brand/Mascot"
import {
  cardBrief,
  metCountOf,
  resultCategoryOf,
} from "../../components/policy/AnalysisPolicyCard"
import type { PolicyRow } from "../../services/policyResults"
import { loadPolicyCatalog } from "../../services/welfareApi"
import { supportTypeOf } from "../policies/categoryStyle"
import {
  CATALOG_CATEGORIES,
  categoryLabel,
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

const FAQ: [string, string][] = [
  ["정책 정보는 어디서 가져오나요?", "공공 API에서 수집한 정책을 보여줘요."],
  ["결과가 나오면 바로 신청할 수 있나요?", "결과는 미리 보는 안내예요. 최종 신청 가능 여부는 해당 기관에서 확인해요."],
  ["로그인 없이도 쓸 수 있나요?", "간편 정책 찾기는 로그인 없이 쓸 수 있고, 입력값과 결과는 저장하지 않아요."],
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

  // 전체 정책(지원 형태 집계·대표 정책용). 서버 한 번에 최대 48개라 순서대로 받고, 실패하면 해당 구역만 숨긴다.
  const [all, setAll] = useState<CatalogPolicy[] | null>(null)
  const scroller = useRef<HTMLUListElement>(null)
  useEffect(() => {
    let alive = true
    ;(async () => {
      const base = new URL(import.meta.env?.VITE_API_BASE_URL || "/api/v1", window.location.origin).href.replace(/\/$/, "")
      const items: CatalogPolicy[] = []
      let total = Infinity
      for (let page = 1; page <= 10 && items.length < total; page++) {
        const res = await fetch(`${base}/policies?` + new URLSearchParams({ q: "", category: "all", page: String(page), page_size: "48" }), { credentials: "include" })
        if (!res.ok) return
        const data = (await res.json()) as CatalogResponse
        total = data.total
        if (!data.items.length) break
        items.push(...data.items)
      }
      if (alive && items.length === total) setAll(items)
    })().catch(() => undefined)
    return () => {
      alive = false
    }
  }, [])

  const deadlines = (all ?? catalog?.items ?? [])
    .map((policy) => ({ policy, days: daysLeft(policy) }))
    .filter((x): x is { policy: CatalogPolicy; days: number } => x.days !== null)
    .sort((a, b) => a.days - b.days)
    .slice(0, 5)

  const categoryCount = (catalog?.categories ?? []).filter((c) => c.id !== "all" && c.count > 0).length
  const supportCounts = new Map<string, { glyph: string; count: number }>()
  for (const policy of all ?? []) {
    const { glyph, label } = supportTypeOf(policy.support_type)
    supportCounts.set(label, { glyph, count: (supportCounts.get(label)?.count ?? 0) + 1 })
  }
  const supportList = [...supportCounts.entries()].sort((a, b) => b[1].count - a[1].count)
  const supportKinds = supportList.filter(([label]) => label !== "기타").length

  // 분야별 대표 정책: 정책이 있는 앞쪽 분야 4개에서 3개씩
  const featured: { policy: CatalogPolicy; category: string }[] = []
  {
    const seen = new Set<string>()
    const pool = all ?? catalog?.items ?? []
    let used = 0
    for (const [id] of CATALOG_CATEGORIES) {
      if (id === "all" || id === "other" || used >= 4) continue
      const picks = pool.filter((p) => p.categories.includes(id) && !seen.has(p.id)).slice(0, 3)
      if (!picks.length) continue
      used++
      picks.forEach((p) => seen.add(p.id))
      featured.push(...picks.map((policy) => ({ policy, category: id })))
    }
  }
  const slide = (dir: 1 | -1) => {
    const el = scroller.current
    if (!el) return
    const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches
    el.scrollBy({ left: dir * el.clientWidth * 0.8, behavior: reduce ? "auto" : "smooth" })
  }
  const openChat = () => (onOpenChat ? onOpenChat() : setPage("quick"))

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
            <div className="home-collage" aria-hidden="true">
              <span className="home-collage-tag">예시 화면</span>
              <div className="hc hc-pill"><span className="hc-in"><b>✓ 신청 가능</b></span></div>
              <div className="hc hc-chip"><span className="hc-in"><i>주거</i><span>청년 월세 지원</span></span></div>
              <div className="hc hc-gauge">
                <span className="hc-in">
                  <small>본인 월소득</small>
                  <span className="hc-bar"><span className="hc-fill" /><span className="hc-mark" /></span>
                  <em>기준까지 30만원</em>
                </span>
              </div>
              <div className="hc hc-count">
                <span className="hc-in">
                  <small>판정 결과</small>
                  <span className="hc-row"><u className="hc-l1" /><s>가능</s></span>
                  <span className="hc-row"><u className="hc-l2" /><s>확인 필요</s></span>
                  <span className="hc-row"><u className="hc-l3" /><s>불가</s></span>
                </span>
              </div>
              <div className="hc hc-chat"><span className="hc-in">궁금한 정책, 여기서 물어보세요!</span></div>
            </div>
          )}
          <Mascot pose="wave" size={200} eager className="home-m-hero" delay={0.4} />
          <Mascot pose="wave" size={120} eager className="home-m-hero-sm" delay={0.4} />
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
              onClick={openChat}
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

      {state !== "error" && (
        <section className="home-stats" aria-labelledby="home-stats-t" data-reveal="repeat">
          <div className="home-wrap">
            <h2 id="home-stats-t" className="home-sr">숫자로 보는 자격있청</h2>
            <dl className="home-stat-list">
              {state === "loading" ? (
                Array.from({ length: 3 }, (_, i) => (
                  <div key={i} className="home-stat home-skeleton" aria-hidden="true" />
                ))
              ) : (
                <>
                  {total ? <div className="home-stat"><dd><CountUp value={total} /><small>개</small></dd><dt>살펴볼 수 있는 정책</dt></div> : null}
                  {categoryCount ? <div className="home-stat"><dd><CountUp value={categoryCount} /><small>개</small></dd><dt>정책 분야</dt></div> : null}
                  {supportKinds ? <div className="home-stat"><dd><CountUp value={supportKinds} /><small>가지</small></dd><dt>지원 형태</dt></div> : null}
                </>
              )}
            </dl>
          </div>
        </section>
      )}

      <section className="home-wrap home-block" aria-labelledby="home-cats">
        <Mascot pose="fly" size={150} float={false} className="home-m-fly" />
        <h2 id="home-cats" className="home-sec" data-reveal="repeat">
          분야별로 보기
          {total ? <small>전체 <CountUp value={total} />개</small> : null}
        </h2>
        <ul className="home-tiles">
          {state === "loading" ? (
            Array.from({ length: 8 }, (_, i) => (
              <li key={i} className="home-tile home-skeleton" aria-hidden="true" />
            ))
          ) : (
            <>
              {CATALOG_CATEGORIES.filter(([id]) => id !== "all").map(([id, label]) => {
                const count = counts.get(id)
                if (state === "ready" && !count) return null
                return (
                  <li key={id} data-reveal="repeat" data-reveal-style="pop">
                    <a className="home-tile" href={explorerHref({ category: id })}>
                      <i className={`tone-${TONES[id] ?? "gray"}`} aria-hidden="true">{label[0]}</i>
                      <span>
                        <b>{label}</b>
                        {state === "ready" && <small><CountUp value={count ?? 0} />개</small>}
                      </span>
                    </a>
                  </li>
                )
              })}
              <li data-reveal="repeat" data-reveal-style="pop">
                <a className="home-tile" href={explorerHref({})}>
                  <i className="tone-gray" aria-hidden="true">+</i>
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

      <section className="home-band" aria-labelledby="home-rev">
        <div className="home-wrap home-split">
          <div className="home-rev-copy" data-reveal="repeat" data-reveal-style="slide">
            <h2 id="home-rev">안 되는 정책도, 무엇이 바뀌면 되는지 알려줘요</h2>
            <p>정책마다 신청 가능 / 확인 필요 / 불가로 나눠 보여줘요.</p>
            <p>불가인 정책은 어떤 조건이 어떻게 바뀌면 되는지 함께 안내해요.</p>
            <button type="button" className="home-btn" onClick={() => setPage("diagnosis")}>
              내 자격 확인하기 <span aria-hidden="true">→</span>
            </button>
          </div>
          <figure className="home-demo" data-reveal="repeat" data-reveal-style="pop">
            <Mascot pose="search" size={150} className="home-m-search" delay={0.8} />
            <figcaption><span className="home-badge">예시 화면</span> 실제 정책이 아닌 설명용 예시예요</figcaption>
            <div className="home-demo-row">
              <b>본인 월소득</b>
              <span>내 정보 300만원 → 기준 270만원 미만</span>
            </div>
            <div className="home-gauge" aria-hidden="true">
              <i className="home-gauge-ok" />
              <i className="home-gauge-over" />
              <em className="home-gauge-mark home-gauge-limit">기준 270</em>
              <em className="home-gauge-mark home-gauge-mine">내 정보 300</em>
            </div>
            <p className="home-demo-tip">월소득이 30만원 이상 낮아지면 이 조건을 충족해요</p>
          </figure>
        </div>
      </section>

      {state === "ready" && all && supportList.length > 0 && (
        <section className="home-wrap home-block" aria-labelledby="home-support">
          <h2 id="home-support" className="home-sec" data-reveal="repeat">지원 형태로 찾기</h2>
          <ul className="home-chips">
            {supportList.map(([label, { glyph, count }]) => (
              <li key={label} data-reveal="repeat" data-reveal-style="pop">
                <span className="home-chip">
                  <i aria-hidden="true">{glyph || "·"}</i>
                  <b>{label}</b>
                  <small><CountUp value={count} />개</small>
                </span>
              </li>
            ))}
          </ul>
          <a className="home-more" href={explorerHref({})}>전체 정책 목록에서 살펴보기 →</a>
        </section>
      )}

      <section className="home-wrap home-block" aria-labelledby="home-mine">
        <h2 id="home-mine" className="home-sec" data-reveal="repeat">내 조건에 맞는 정책</h2>
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
            <button type="button" onClick={() => setPage("diagnosis")}>진단하러 가기</button>
          </div>
        )}
      </section>

      {featured.length > 0 && (
        <section className="home-wrap home-block" aria-labelledby="home-feat">
          <div className="home-feat-head">
            <h2 id="home-feat" className="home-sec" data-reveal="repeat">분야별 정책 살펴보기</h2>
            <div className="home-arrows">
              <button type="button" aria-label="이전 정책" onClick={() => slide(-1)}>←</button>
              <button type="button" aria-label="다음 정책" onClick={() => slide(1)}>→</button>
            </div>
          </div>
          <ul ref={scroller} className="home-scroller" tabIndex={0} aria-label="분야별 정책 목록, 좌우로 넘겨 보세요">
            {featured.map(({ policy, category }) => (
              <li key={policy.id}>
                <a className="home-pcard" href={`#detail/${encodeURIComponent(policy.id)}`}>
                  <span className={`home-pcat tone-${TONES[category] ?? "gray"}`}>{categoryLabel(category)}</span>
                  <b>{policy.title}</b>
                  <small>{policy.summary}</small>
                </a>
              </li>
            ))}
          </ul>
        </section>
      )}

      {deadlines.length > 0 && (
        <section className="home-wrap home-block" aria-labelledby="home-dday">
          <h2 id="home-dday" className="home-sec" data-reveal="repeat">마감이 가까운 정책</h2>
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
        </section>
      )}

      <section className="home-wrap home-block" aria-labelledby="home-how">
        <h2 id="home-how" className="home-sec" data-reveal="repeat">이렇게 확인해요</h2>
        <Mascot pose="thumbs" size={150} className="home-m-thumbs" delay={0.5} />
        <ol className="home-bigsteps">
          {STEPS.map((text, i) => (
            <li key={text} data-reveal="repeat" data-reveal-style="slide">
              <b aria-hidden="true">{i + 1}</b>
              <span>{text}</span>
            </li>
          ))}
        </ol>
      </section>

      <section className="home-wrap home-block" aria-labelledby="home-quick">
        <div className="home-quick" data-reveal="repeat">
          <Mascot pose="chat" size={140} className="home-m-chat" delay={0.3} />
          <div>
            <h2 id="home-quick">로그인 없이 버튼으로 빠르게</h2>
            <p>관심 분야를 고르고 몇 가지만 답하면 돼요. 입력값과 결과는 저장하지 않아요.</p>
          </div>
          <button type="button" className="home-btn" onClick={openChat}>
            간편 정책 찾기 <span aria-hidden="true">→</span>
          </button>
        </div>
      </section>

      <section className="home-wrap home-block" aria-labelledby="home-faq">
        <h2 id="home-faq" className="home-sec" data-reveal="repeat">자주 묻는 질문</h2>
        <Mascot pose="think" size={130} className="home-m-think" delay={1} />
        <div className="home-faq" data-reveal="repeat">
          {FAQ.map(([q, a]) => (
            <details key={q}>
              <summary>{q}</summary>
              <p>{a}</p>
            </details>
          ))}
        </div>
      </section>

      <section className="home-cta-band" aria-labelledby="home-final">
        <div className="home-wrap" data-reveal="repeat" data-reveal-style="pop">
          <Mascot pose="jump" size={170} className="home-m-jump" />
          <h2 id="home-final">받을 수 있는 지원, 지금 확인해 보세요</h2>
          <button type="button" className="home-cta" onClick={() => setPage("diagnosis")}>
            지금 내 자격 확인하기 <span aria-hidden="true">→</span>
          </button>
        </div>
      </section>

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
