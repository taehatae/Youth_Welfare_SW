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
  gap: "신청 불가",
} as const
export type ResultCategory = keyof typeof resultCategoryLabels
export const resultCategoryOrder: ResultCategory[] = ["likely", "gap"]
export const resultCategoryOf = (policy: PolicyRow): ResultCategory =>
  policy.conditions.some((c) => c.status === "미충족") ? "gap" : "likely"
const resultReason = (policy: PolicyRow): string => {
  if (resultCategoryOf(policy) === "gap")
    return "입력한 정보로 비교한 결과 부족한 조건이 있어요. 아래 ‘확인된 미충족 조건’을 확인하세요."
  const passed =
    policy.counts?.passed ?? policy.confirmedConditions?.length ?? 0
  return passed > 0
    ? "입력한 정보로 비교한 조건을 모두 충족했어요. 나머지 조건은 아래 추가 확인 항목을 공식 안내에서 확인하세요."
    : "입력한 정보와 맞지 않는 조건이 없어요. 세부 자격 요건은 아래 추가 확인 항목을 공식 안내에서 확인하세요."
}

const fields: Record<string, string> = {
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
  return (
    <article
      className="reverse-card"
      data-reveal
      data-reveal-delay={index % 3}
      data-result={resultCategoryOf(policy)}
    >
      <header>
        <div>
          <span className="reverse-tag" data-result={resultCategoryOf(policy)}>
            {resultCategoryLabels[resultCategoryOf(policy)]}
          </span>
          <h3>{policy.title}</h3>
        </div>
        <button
          className="policy-save"
          aria-pressed={saved}
          aria-label={`${policy.title} 관심 정책 ${saved ? "해제" : "저장"}`}
          onClick={toggle}
        >
          {saved ? "★ 저장됨" : "☆ 관심 저장"}
        </button>
      </header>
      <div className="policy-overview">
        <p className="policy-key-reason">
          <strong>판정 이유</strong>
          <span>{resultReason(policy)}</span>
        </p>
        {policy.recommendationUncertainty && (
          <p className="reverse-alert">{policy.recommendationUncertainty}</p>
        )}
        {!!policy.confirmedConditions?.length && (
          <div className="policy-key-reason" aria-label="확인된 조건">
            <strong>자동 비교로 확인된 조건</strong>
            <ul>
              {policy.confirmedConditions.map((condition, index) => (
                <li key={`${condition.field}-${index}`}>
                  {fields[condition.field.toLowerCase()] ?? condition.field}: {condition.current}
                  {condition.required ? ` · 기준 ${condition.required}` : ""}
                </li>
              ))}
            </ul>
          </div>
        )}
        {counts ? (
          <>
            <div className="condition-counts" aria-label="조건 비교 요약">
              <span data-kind="passed">
                충족 <b>{counts.passed}</b>
              </span>
              <span data-kind="failed">
                미충족 <b>{counts.failed}</b>
              </span>
              <span data-kind="review">
                추가 확인 <b>{counts.review}</b>
              </span>
            </div>
            <p className="policy-evaluation-note">
              {counts.evaluated === 0
                ? "판정 정보 부족 · 자동 비교할 수 있는 조건이 없어요."
                : `자동 비교한 조건 ${counts.evaluated}개 중 ${counts.passed}개를 충족했어요. 전체 수급 자격의 확정을 뜻하지 않아요.`}
            </p>
          </>
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
              {fields[first.field] ?? first.field} ·{" "}
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
                        {fields[c.field.toLowerCase()] ?? c.field}
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
