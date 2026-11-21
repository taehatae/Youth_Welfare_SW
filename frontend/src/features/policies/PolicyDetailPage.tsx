import { useEffect, useState } from "react"

import { safeOfficialUrl, formatTime } from "../../services/analysisSession"

import { loadPolicyDetail } from "../../services/welfareApi"

import { categoryLabel, type CatalogDetail } from "../../types/policyCatalog"

import type { Page } from "../../types/page"

import type { PolicyRow } from "../../services/policyResults"

import MyPolicyResult from "../../components/policy/MyPolicyResult"

import {
  resultCategoryLabels,
  resultCategoryOf,
} from "../../components/policy/AnalysisPolicyCard"

import PolicyText from "./PolicyText"

import { styleOf } from "./categoryStyle"

import "./catalog.css"

export default function PolicyDetailPage({
  policyId,
  setPage,
  myResult,
  checkedAt,
  saved = false,
  onToggleSaved,
  busy = false,
}: {
  policyId: string
  setPage: (page: Page) => void
  myResult?: PolicyRow
  checkedAt?: string
  saved?: boolean
  /** 로그인·진단이 있을 때만 전달된다 */
  onToggleSaved?: (row: PolicyRow) => void
  busy?: boolean
}) {
  const [result, setResult] = useState<{
    id: string
    data: CatalogDetail
  } | null>(null)

  const [error, setError] = useState("")

  const [retry, setRetry] = useState(0)

  const policy = result?.id === policyId ? result.data : null

  useEffect(() => {
    let active = true
    setError("")
    setResult(null)

    loadPolicyDetail(policyId)
      .then((data) => {
        if (active) setResult({ id: policyId, data })
      })
      .catch((e) => {
        if (active)
          setError(e instanceof Error ? e.message : "정책을 불러오지 못했어요.")
      })

    return () => {
      active = false
    }
  }, [policyId, retry])

  const url = safeOfficialUrl(policy?.detail_url)

  return (
    <section className="catalog-page catalog-detail">
      <button className="catalog-back" onClick={() => setPage("explorer")}>
        ← 정책 목록으로
      </button>
      {error ? (
        <div className="catalog-state" role="alert">
          <h1>정책을 불러오지 못했어요</h1>
          <p>{error}</p>
          <button
            className="interface-primary"
            onClick={() => setRetry((n) => n + 1)}
          >
            다시 불러오기
          </button>
        </div>
      ) : !policy ? (
        <p role="status" className="catalog-state">
          지원 내용을 불러오고 있어요…
        </p>
      ) : (
        <PolicyBody
          policy={policy}
          url={url}
          setPage={setPage}
          myResult={myResult}
          checkedAt={checkedAt}
          saved={saved}
          onToggleSaved={onToggleSaved}
          busy={busy}
        />
      )}
    </section>
  )
}

const firstLine = (text: string) =>
  (text.split(/\n/).find((l) => l.trim()) ?? "").replace(/\s+/g, " ").trim()

function PolicyBody({
  policy,
  url,
  setPage,
  myResult,
  checkedAt,
  saved,
  onToggleSaved,
  busy,
}: {
  policy: CatalogDetail
  url: string | null | undefined
  setPage: (page: Page) => void
  myResult?: PolicyRow
  checkedAt?: string
  saved: boolean
  onToggleSaved?: (row: PolicyRow) => void
  busy: boolean
}) {
  const style = styleOf(policy.categories)
  const category = myResult ? resultCategoryOf(myResult) : null
  const counts = myResult && {
    passed: myResult.counts?.passed ?? myResult.confirmedConditions?.length ?? 0,
    failed: myResult.conditions.filter((c) => c.status === "미충족").length,
    review: myResult.conditions.filter((c) => c.status === "추가 확인").length,
  }
  const facts = [
    ["지원 내용", firstLine(policy.support_content) || policy.support_type],
    ["대상", firstLine(policy.target_details)],
    ["신청 방법", policy.application_methods[0] ?? ""],
    [
      "문의",
      [policy.department, policy.organization]
        .filter((v, i, a) => v && a.indexOf(v) === i)
        .join(" · "),
    ],
  ].filter(([, v]) => v)
  const sections = [
    ["지원 내용", policy.support_content],
    ["지원 대상", policy.target_details],
    ["선정 기준", policy.selection_criteria],
  ]
  const nav = [
    ...sections.map(([t], i) => [t, "sec-" + i]),
    ...(policy.application_methods.length ? [["신청 및 담당 기관", "sec-apply"]] : []),
    ...(myResult && checkedAt ? [["내 진단 결과 자세히", "sec-mine"]] : []),
  ]
  return (
    <>
      <div
        className="catalog-banner"
        data-reveal
        style={{ background: style.bg, color: style.ink }}
        aria-hidden="true"
      >
        <span>{style.word}</span>
      </div>
      <div className="catalog-detail-layout">
        <div className="catalog-detail-head" data-reveal>
          <p className="catalog-detail-meta">
            {policy.department || "제공 기관 미확인"}
            {policy.organization &&
              !policy.department.includes(policy.organization) &&
              " · " + policy.organization}
            {policy.categories.length > 0 &&
              " · " + policy.categories.map(categoryLabel).join(" · ")}
            <span> · 수집일 {formatTime(policy.synced_at)}</span>
          </p>
          <h1>{policy.title}</h1>
          {policy.summary && <p className="catalog-detail-summary">{policy.summary}</p>}
          {facts.length > 0 && (
            <dl className="catalog-facts">
              {facts.map(([k, v]) => (
                <div key={k}>
                  <dt>{k}</dt>
                  <dd>{v}</dd>
                </div>
              ))}
            </dl>
          )}
          <nav className="catalog-sectionnav" aria-label="정책 상세 목차">
            {nav.map(([t, id]) => (
              <a key={id} href={"#detail-" + id} onClick={(e) => {
                e.preventDefault()
                document.getElementById(id)?.scrollIntoView({ behavior: "smooth", block: "start" })
              }}>
                {t}
              </a>
            ))}
          </nav>
        </div>
        <aside className="catalog-apply-panel" data-reveal aria-label="신청과 내 자격">
          {url ? (
            <a
              className="catalog-apply-cta"
              href={url}
              target="_blank"
              rel="noopener noreferrer"
            >
              신청하러 가기 ↗<small className="sr-only">새 탭에서 열림</small>
            </a>
          ) : (
            <p className="catalog-no-link">공식 링크가 제공되지 않았어요.</p>
          )}
          {onToggleSaved && myResult && (
            <button
              type="button"
              className="catalog-save"
              aria-pressed={saved}
              disabled={busy}
              onClick={() => onToggleSaved(myResult)}
            >
              {saved ? "★ 저장됨" : "☆ 관심 저장"}
            </button>
          )}
          {myResult && category && counts ? (
            <div className="catalog-mybox" data-result={category}>
              <p className="catalog-mybox-title">내 자격 결과</p>
              <span className="catalog-pill" data-result={category}>
                {resultCategoryLabels[category]}
              </span>
              <ul>
                <li>충족 <b>{counts.passed}</b></li>
                <li>미충족 <b>{counts.failed}</b></li>
                <li>추가 확인 <b>{counts.review}</b></li>
              </ul>
              <button type="button" className="catalog-link" onClick={() => setPage("result")}>
                전체 진단 결과에서 보기 →
              </button>
            </div>
          ) : (
            <div className="catalog-mybox">
              <p className="catalog-mybox-title">
                진단하면 이 정책을 받을 수 있는지 바로 알려드려요
              </p>
              <button type="button" className="catalog-diagnose" onClick={() => setPage("diagnosis")}>
                내 조건으로 자격 진단
              </button>
            </div>
          )}
          <p className="catalog-help">
            이 페이지는 정책 안내이며, 개인별 자격 판정 결과가 아니에요. 접수
            일정은 공식 공고에서 확인하세요.
          </p>
        </aside>
        <div className="catalog-detail-body">
          {sections.map(([title, content], index) => (
            <section
              key={title}
              id={"sec-" + index}
              data-reveal
              className="catalog-detail-section"
            >
              <h2>{title}</h2>
              <PolicyText text={content} />
            </section>
          ))}
          {policy.application_methods.length > 0 && (
            <section id="sec-apply" data-reveal className="catalog-detail-section">
              <h2>신청 및 담당 기관 안내</h2>
              <ul className="catalog-process">
                {policy.application_methods.map((method, index) => (
                  <li key={index}>{method}</li>
                ))}
              </ul>
            </section>
          )}
          {myResult && checkedAt && (
            <div id="sec-mine">
              <MyPolicyResult
                policy={myResult}
                checkedAt={checkedAt}
                onOpenResults={() => setPage("result")}
              />
            </div>
          )}
        </div>
      </div>
    </>
  )
}
