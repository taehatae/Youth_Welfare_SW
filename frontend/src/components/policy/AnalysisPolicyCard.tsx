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
const pathMarks = { passed: "✓", failed: "✕", needs_review: "?" } as const
type PathCondition = NonNullable<PolicyRow["paths"]>[number]["conditions"][number]
// 기준 문구(required_value)에 조건 이름이 이미 들어 있어 이름을 따로 쓰지 않는다.
const PathConditionLine = ({ c }: { c: PathCondition }) => (
  <li data-status={c.status}>
    <span aria-label={pathMarkLabels[c.status]}>{pathMarks[c.status]}</span>{" "}
    {c.required_value || c.condition_type}
    <small> · 내 정보 {c.current_value || "미입력"}</small>
  </li>
)
const pathMarkLabels = { passed: "충족", failed: "미충족", needs_review: "확인 필요" } as const
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
  const first = failed[0] ?? review[0] ?? policy.conditions[0]
  const [open, setOpen] = useState(false)
  const bodyId = useId()
  const passed = metCountOf(policy)
  const allPaths = policy.paths ?? []
  // 이전 결과에는 common 표시가 없어 모든 경로에 같은 조건이 있어도 공통으로 묶지 않는다.
  const commonConditions = allPaths[0]?.conditions.filter((c) => c.common) ?? []
  const commonChecks = (allPaths[0]?.checks ?? []).filter((check) =>
    allPaths.every((p) => p.checks.includes(check)),
  )
  return (
    <article
      className="reverse-card"
      data-reveal
      data-reveal-delay={index % 3}
      data-result={resultCategoryOf(policy)}
      data-open={open}
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
            <div className="condition-counts compact" aria-label="조건 비교 요약">
              <span data-kind="passed">충족 <b>{counts.passed}</b></span>
              <span data-kind="failed">미충족 <b>{counts.failed}</b></span>
              <span data-kind="review">추가 확인 <b>{counts.review}</b></span>
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
          <button
            className="card-toggle"
            type="button"
            aria-expanded={open}
            aria-controls={bodyId}
            onClick={() => setOpen(!open)}
          >
            {open ? "접기" : "자세히"} <span aria-hidden="true">{open ? "▴" : "▾"}</span>
          </button>
        </div>
      </header>
      <div id={bodyId} hidden={!open}>
      <div className="policy-overview">
        <p className="policy-key-reason">
          <strong>판정 이유</strong>
          <span>{resultReason(policy)}</span>
        </p>
        {(policy.paths?.length ?? 0) > 1 && (
          <div className="policy-key-reason policy-paths" aria-label="자격 경로">
            <strong>자격 경로</strong>
            <p className="policy-path-note">아래 경로 중 하나만 맞으면 신청할 수 있어요.</p>
            {commonConditions.length > 0 && (
              <div className="policy-path-checks">
                <small>모든 경로 공통 조건</small>
                <ul className="policy-path-conditions">
                  {commonConditions.map((c, i) => (
                    <PathConditionLine key={i} c={c} />
                  ))}
                </ul>
              </div>
            )}
            {commonChecks.length > 0 && (
              <div className="policy-path-checks">
                <small>모든 경로 공통 확인 사항</small>
                <ul>
                  {commonChecks.map((check, i) => (
                    <li key={i}>{check}</li>
                  ))}
                </ul>
              </div>
            )}
            <ul className="policy-path-list">
              {policy.paths!.map((path) => {
                const own = path.conditions.filter((c) => !c.common)
                const checks = path.checks.filter((check) => !commonChecks.includes(check))
                return (
                <li key={path.path_id}>
                  <p className="policy-path-head">
                    <span>{path.label}</span>
                    <span
                      className="reverse-tag"
                      data-result={pathStatusCategory(path.status)}
                    >
                      {resultCategoryLabels[pathStatusCategory(path.status)]}
                    </span>
                    {path.path_id === policy.matchedPathId && (
                      <small className="policy-path-main">대표</small>
                    )}
                  </p>
                  {own.length > 0 && (
                    <ul className="policy-path-conditions">
                      {own.map((c, i) => (
                        <PathConditionLine key={i} c={c} />
                      ))}
                    </ul>
                  )}
                  {checks.length > 0 && (
                    <div className="policy-path-checks">
                      <small>확인 사항</small>
                      <ul>
                        {checks.map((check, i) => (
                          <li key={i}>{check}</li>
                        ))}
                      </ul>
                    </div>
                  )}
                </li>
                )
              })}
            </ul>
          </div>
        )}
        {!!policy.preferences?.length && (
          <p className="policy-path-preferences">
            <strong>우대 사항</strong> {policy.preferences.join(", ")}
          </p>
        )}
        {policy.recommendationUncertainty && (
          <p className="reverse-alert">{policy.recommendationUncertainty}</p>
        )}
        {!!policy.confirmedConditions?.length && (
          <div className="policy-key-reason" aria-label="확인된 조건">
            <strong>자동 비교로 확인된 조건</strong>
            <ul>
              {policy.confirmedConditions.map((condition, index) => (
                <li key={`${condition.field}-${index}`}>
                  {fieldName(condition.field)}<OrNote field={condition.field} />: {condition.current}
                  {condition.required ? ` · 기준 ${condition.required}` : ""}
                </li>
              ))}
            </ul>
          </div>
        )}
        {counts ? (
          <p className="policy-evaluation-note">
            {counts.evaluated === 0
              ? "판정 정보 부족 · 자동 비교할 수 있는 조건이 없어요."
              : `자동 비교한 조건 ${counts.evaluated}개 중 ${counts.passed}개를 충족했어요. 전체 수급 자격의 확정을 뜻하지 않아요.`}
          </p>
        ) : (
          <p className="policy-evaluation-note">
            조건별 집계가 제공되지 않은 결과예요.
          </p>
        )}
        {first && (
          <p className="policy-key-reason">
            <strong>
              {failed.length ? "확인된 미충족 조건" : "먼저 확인할 조건"}
            </strong>
            <span>
              {isOrGroup(first.field) ? first.field : (conditionFields[first.field] ?? first.field)}
              <OrNote field={first.field} /> ·{" "}
              {first.required || "공식 기준 확인 필요"}
            </span>
          </p>
        )}
        {policy.description && (
          <p className="policy-description">{policy.description}</p>
        )}
        {savedAt && (
          <p className="comparison-time">
            저장 당시 결과 · {new Date(savedAt).toLocaleDateString("ko-KR")}
          </p>
        )}
      </div>
      {policy.conditions.length > 0 ? (
        <details className="motion-details policy-condition-details">
          <summary>
            조건과 확인 방법 자세히 보기 <span aria-hidden="true">＋</span>
          </summary>
          <div className="details-body">
            <div
              className="condition-table-scroll"
              role="region"
              aria-label={`${policy.title} 조건 비교`}
              tabIndex={0}
            >
              <table className="condition-table">
                <caption>
                  미충족·추가 확인 조건 — 충족한 조건의 상세 내역은 서버에서
                  제공되지 않습니다.
                </caption>
                <thead>
                  <tr>
                    <th scope="col">조건</th>
                    <th scope="col">내 조건</th>
                    <th scope="col">정책 기준</th>
                    <th scope="col">비교 결과</th>
                    <th scope="col">확인 안내</th>
                  </tr>
                </thead>
                <tbody>
                  {policy.conditions.map((c, i) => (
                    <tr key={`${c.field}-${i}`}>
                      <th scope="row">
                        {fieldName(c.field)}
                        <OrNote field={c.field} />
                      </th>
                      <td>{c.current || "미확인"}</td>
                      <td>{c.required || "미제공"}</td>
                      <td>
                        <span className="reverse-tag">{c.status}</span>
                      </td>
                      <td>
                        {c.guide || "정책의 상세 조건을 확인해주세요."}
                        {onEdit && c.field !== "external_review" && (
                          <button
                            className="condition-edit"
                            type="button"
                            disabled={busy}
                            onClick={() => onEdit(conditionStep(c.field))}
                          >
                            관련 입력 확인 →
                          </button>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </details>
      ) : (
        <p className="reverse-card-note">
          {counts?.evaluated
            ? "충족한 조건의 상세 내역은 제공되지 않아요. 세부 기준은 공식 공고에서 확인해주세요."
            : "서버가 제공한 조건별 비교 정보가 없습니다."}
        </p>
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
