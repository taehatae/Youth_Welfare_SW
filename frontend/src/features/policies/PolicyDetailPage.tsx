import { useEffect, useState } from "react"

import PageHeading from "../../components/layout/PageHeading"

import { safeOfficialUrl, formatTime } from "../../services/analysisSession"

import { loadPolicyDetail } from "../../services/welfareApi"

import { categoryLabel, type CatalogDetail } from "../../types/policyCatalog"

import type { Page } from "../../types/page"

import "./catalog.css"

export default function PolicyDetailPage({
  policyId,
  setPage,
}: {
  policyId: string
  setPage: (page: Page) => void
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
        <>
          <PageHeading
            eyebrow={policy.categories.map(categoryLabel).join(" · ")}
            title={policy.title}
            description={policy.summary}
          />
          <div className="catalog-detail-meta">
            <span>
              {policy.department || "제공 기관 미확인"}
              {policy.organization &&
                !policy.department.includes(policy.organization) &&
                " · " + policy.organization}
            </span>
            <span>수집일 {formatTime(policy.synced_at)}</span>
          </div>
          <div className="catalog-detail-layout">
            <div>
              {[
                ["지원 내용", policy.support_content],
                ["지원 대상", policy.target_details],
                ["선정 기준", policy.selection_criteria],
              ].map(([title, content], index) => (
                <section
                  key={title}
                  data-reveal
                  className="catalog-detail-section"
                >
                  <span className="catalog-section-number">0{index + 1}</span>
                  <h2>{title}</h2>
                  <p>
                    {content ||
                      "제공된 정보가 없어요. 공식 공고에서 확인해주세요."}
                  </p>
                </section>
              ))}
              {policy.application_methods.length > 0 && (
                <section data-reveal className="catalog-detail-section">
                  <h2>신청 및 담당 기관 안내</h2>
                  <ul className="catalog-process">
                    {policy.application_methods.map((method, index) => (
                      <li key={index}>{method}</li>
                    ))}
                  </ul>
                </section>
              )}
            </div>
            <aside className="catalog-apply-panel">
              <h2>신청 전 확인해주세요</h2>
              <p>
                정책에 안내된 대상과 내 조건을 비교하고, 접수 일정은 공식
                공고에서 확인하세요.
              </p>
              <dl>
                <div>
                  <dt>지원 방식</dt>
                  <dd>{policy.support_type || "공고 확인 필요"}</dd>
                </div>
                <div>
                  <dt>지원 주기</dt>
                  <dd>{policy.support_cycle || "공고 확인 필요"}</dd>
                </div>
                <div>
                  <dt>신청 기간</dt>
                  <dd>공식 공고 확인 필요</dd>
                </div>
              </dl>
              {url ? (
                <a
                  className="interface-primary"
                  href={url}
                  target="_blank"
                  rel="noopener noreferrer"
                >
                  공식 공고 보기 ↗<small>새 탭에서 열림</small>
                </a>
              ) : (
                <p>공식 링크가 제공되지 않았어요.</p>
              )}
              <button
                className="catalog-diagnose"
                onClick={() => setPage("diagnosis")}
              >
                내 조건으로 자격 진단
              </button>
              <p className="catalog-help">
                이 페이지는 정책 안내이며, 개인별 자격 판정 결과가 아니에요.
              </p>
            </aside>
          </div>
        </>
      )}
    </section>
  )
}
