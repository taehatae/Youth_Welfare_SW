import { useId, useState } from "react"
import { safeOfficialUrl } from "../../services/analysisSession"
import { conditionStep } from "../../services/profileSummary"
import type { PolicyRow } from "../../services/policyResults"

export const statusLabels = {
  eligible: "자동 비교상 충족",
  ineligible: "미충족 조건 있음",
  needs_review: "추가 확인 필요",
}
// 신청 가능 여부는 사용자가 입력한 값과 비교한 조건만으로 판단한다.
// 입력값으로 비교할 수 없는 조건은 판정에 쓰지 않고 '추가 확인'으로만 안내한다.
export const resultCategoryLabels = {
  likely: "신청 가능",
  review: "확인 필요",
  gap: "신청 불가",
} as const
export type ResultCategory = keyof typeof resultCategoryLabels
export const resultCategoryOrder: ResultCategory[] = ["likely", "review", "gap"]
const pathStatusCategory = (
  status: "eligible" | "needs_review" | "ineligible",
): ResultCategory =>
  status === "eligible" ? "likely" : status === "needs_review" ? "review" : "gap"
// 자격 경로 데이터가 있으면 경로 기준 3분류를, 없는 예전 저장 결과는 기존 2분류 규칙을 쓴다.
export const resultCategoryOf = (policy: PolicyRow): ResultCategory =>
  policy.paths?.length
    ? pathStatusCategory(policy.status)
    : policy.conditions.some((c) => c.status === "미충족")
      ? "gap"
      : "likely"
// 신청 가능이지만 입력값으로 비교한 조건이 하나도 없는 정책. 자격을 확인했다는 뜻이 아니라서 따로 표시한다.
export const metCountOf = (policy: PolicyRow) =>
  policy.counts?.passed ?? policy.confirmedConditions?.length ?? 0
export const isUnverified = (policy: PolicyRow) =>
  !policy.paths?.length &&
  resultCategoryOf(policy) === "likely" &&
  metCountOf(policy) === 0
const pathBrief = (policy: PolicyRow): string | null => {
  const paths = policy.paths ?? []
  if (paths.length < 2) return null
  const path = paths.find((p) => p.path_id === policy.matchedPathId) ?? paths[0]
  if (policy.status === "eligible") return `'${path.label}' 경로로 신청 가능`
  if (policy.status === "needs_review") {
    const items = path.conditions
      .filter((c) => c.status === "needs_review")
      .map((c) => c.condition_type)
    return `'${path.label}' 경로 확인 필요 · ${items.length ? items.join(", ") : "공식 안내 확인"}`
  }
  if (policy.blockedByCommon?.length)
    return `공통 조건 미충족: ${policy.blockedByCommon.join(", ")}`
  const failedTypes = path.conditions
    .filter((c) => c.status === "failed")
    .map((c) => c.condition_type)
  return `가장 가까운 경로 '${path.label}': ${failedTypes.join(", ")} 부족`
}
export const resultReason = (policy: PolicyRow): string => {
  if (policy.paths?.length && policy.recommendationReason)
    return policy.recommendationReason
  if (resultCategoryOf(policy) === "gap")
    return "입력한 정보로 비교한 결과 부족한 조건이 있어요. 아래 ‘확인된 미충족 조건’을 확인하세요."
  const passed =
    policy.counts?.passed ?? policy.confirmedConditions?.length ?? 0
  return passed > 0
    ? "입력한 정보로 비교한 조건을 모두 충족했어요. 나머지 조건은 아래 추가 확인 항목을 공식 안내에서 확인하세요."
    : "입력한 정보와 맞지 않는 조건이 없어요. 세부 자격 요건은 아래 추가 확인 항목을 공식 안내에서 확인하세요."
}

const isOrGroup = (field: string) => field.includes(" 또는 ")
const fieldName = (field: string) =>
  isOrGroup(field) ? field : (conditionFields[field.toLowerCase()] ?? field)
const OrNote = ({ field }: { field: string }) =>
  isOrGroup(field) ? (
    <small className="text-slate-500"> (이 중 하나만 해당하면 돼요)</small>
  ) : null

export const conditionFields: Record<string, string> = {
  age: "나이",
  income_amount: "소득 금액",
  income_ratio: "중위소득 비율",
  income_level: "소득",
  region: "거주 지역",
  employment: "고용 상태",
  employment_status: "고용 상태",
  target_group: "대상 집단",
  nationality: "국적",
  education: "학력·재학",
  household: "가구",
  other: "세부 자격",
  external_review: "기관 심사",
  informational: "안내 사항",
}
type ConditionTab = "passed" | "failed" | "review"
const conditionTabs: [ConditionTab, string][] = [
  ["passed", "충족"],
  ["failed", "미충족"],
  ["review", "추가 확인"],
]
type ConditionItem = { field: string; current: string; required: string; guide?: string }
const isCheck = (c: ConditionItem) => c.field === "확인 사항"
// 추가 확인은 '입력하면 비교할 수 있는 조건'과 '공식 안내에서 확인할 사항'을 나눠 보여준다.
const groupsOf = (tab: ConditionTab, rows: ConditionItem[]): [string, ConditionItem[]][] =>
  tab === "review"
    ? ([
        ["정보를 입력하면 비교할 수 있어요", rows.filter((c) => !isCheck(c))],
        ["공식 안내에서 확인해야 해요", rows.filter(isCheck)],
      ] as [string, ConditionItem[]][]).filter(([, group]) => group.length > 0)
    : [["", rows]]
export default function AnalysisPolicyCard({
  policy,
  saved,
  toggle,
  savedAt,
  onEdit,
  busy = false,
  index = 0,
}: {
  policy: PolicyRow
  saved: boolean
  toggle: () => void
  savedAt?: string
  onEdit?: (step: number) => void
  busy?: boolean
  index?: number
}) {
  const url = safeOfficialUrl(policy.url)
  const counts = policy.counts
  const failed = policy.conditions.filter((c) => c.status === "미충족")
  const review = policy.conditions.filter((c) => c.status === "추가 확인")
  const confirmed = policy.confirmedConditions ?? []
  const [tab, setTab] = useState<ConditionTab | null>(null)
  const panelId = useId()
  const passed = metCountOf(policy)
  const items: Record<ConditionTab, ConditionItem[]> = {
    passed: confirmed,
    failed,
    review,
  }
  const shown = tab ? items[tab] : []
  return (
    <article
      className="reverse-card"
      data-reveal
      data-reveal-delay={index % 3}
      data-result={resultCategoryOf(policy)}
      data-open={tab !== null}
    >
      <header>
        <div className="card-heading">
          <span className="reverse-tag" data-result={resultCategoryOf(policy)}>
            {resultCategoryLabels[resultCategoryOf(policy)]}
          </span>
          {isUnverified(policy) && (
            <span className="reverse-tag" data-result="unverified">
              비교 조건 없음
            </span>
          )}
          <h3>
            <a href={"#detail/" + encodeURIComponent(policy.id)}>{policy.title}</a>
          </h3>
          <p className="card-brief">
            {pathBrief(policy) ??
              (failed.length
              ? `${fieldName(failed[0].field)}${isOrGroup(failed[0].field) ? " (이 중 하나만 해당하면 돼요)" : ""} 조건 미충족${failed.length > 1 ? ` 외 ${failed.length - 1}개` : ""}`
              : passed > 0
                ? `입력값으로 비교한 조건 ${passed}개 충족`
                : "입력값으로 비교할 조건 없음 · 공식 안내 확인 필요")}
          </p>
          {counts && (
            <div className="condition-counts compact" role="group" aria-label="조건 비교 요약">
              {conditionTabs.map(([kind, label]) => {
                const count = kind === "passed" ? counts.passed : kind === "failed" ? counts.failed : counts.review
                return (
                  <button
                    key={kind}
                    type="button"
                    data-kind={kind}
                    aria-pressed={tab === kind}
                    aria-controls={panelId}
                    disabled={count === 0}
                    onClick={() => setTab(tab === kind ? null : kind)}
                  >
                    {label} <b>{count}</b>
                  </button>
                )
              })}
            </div>
          )}
        </div>
        <div className="card-header-actions">
          <button
            className="policy-save"
            aria-pressed={saved}
            aria-label={`${policy.title} 관심 정책 ${saved ? "해제" : "저장"}`}
            onClick={toggle}
          >
            {saved ? "★ 저장됨" : "☆ 관심 저장"}
          </button>
        </div>
      </header>
      <div id={panelId} hidden={tab === null} className="condition-panel" data-kind={tab ?? undefined}>
        {tab && (
          <>
            <p className="condition-panel-title">
              {conditionTabs.find(([kind]) => kind === tab)![1]} 조건 <b>{shown.length}</b>
            </p>
            {shown.length ? (
              groupsOf(tab, shown).map(([title, rows]) => (
                <section key={title || "all"} className="condition-group">
                  {title && (
                    <p className="condition-group-title">
                      {title} <b>{rows.length}</b>
                    </p>
                  )}
                  <ul>
                    {rows.map((c, i) =>
                      isCheck(c) ? (
                        // 입력값으로 비교할 수 없는 확인 사항은 기준 문장만 한 칸에 보여준다.
                        <li key={`check-${i}`} className="condition-item" data-check>
                          <span className="condition-no" aria-hidden="true">{i + 1}</span>
                          <p>{c.required || c.guide || "공식 안내에서 확인해주세요."}</p>
                        </li>
                      ) : (
                        <li key={`${c.field}-${i}`} className="condition-item">
                          <strong>
                            {fieldName(c.field)}
                            <OrNote field={c.field} />
                          </strong>
                          <dl>
                            {/* 저장된 결과는 내 정보가 '프로필 보호 중'으로 가려져 있어 기준만 보여준다. */}
                            {c.current && c.current !== "프로필 보호 중" && (
                              <div>
                                <dt>내 정보</dt>
                                <dd>{c.current}</dd>
                              </div>
                            )}
                            <div>
                              <dt>기준</dt>
                              <dd>{c.required || "공식 안내에서 확인해주세요."}</dd>
                            </div>
                          </dl>
                          {tab !== "passed" && onEdit && c.field !== "external_review" && (
                            <button
                              className="condition-edit"
                              type="button"
                              disabled={busy}
                              onClick={() => onEdit(conditionStep(c.field))}
                            >
                              관련 입력 확인 →
                            </button>
                          )}
                        </li>
                      ),
                    )}
                  </ul>
                </section>
              ))
            ) : (
              <p className="reverse-card-note">이 결과에는 조건별 상세 내역이 없어요.</p>
            )}
            {savedAt && (
              <p className="comparison-time">
                저장 당시 결과 · {new Date(savedAt).toLocaleDateString("ko-KR")}
              </p>
            )}
          </>
        )}
      </div>
      <footer className="policy-card-actions">
        {url ? (
          <a
            className="interface-primary"
            href={url}
            target="_blank"
            rel="noopener noreferrer"
          >
            정책 확인하러 가기 <span aria-hidden="true">↗</span>
            <span className="sr-only"> (새 탭)</span>
          </a>
        ) : (
          <span className="policy-link-missing">공식 링크 미제공</span>
        )}
        <p>
          자동 비교에 따른 사전 안내이며 최종 자격은 담당 기관에서 확인해주세요.
        </p>
      </footer>
    </article>
  )
}
