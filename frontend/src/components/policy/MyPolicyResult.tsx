import type { PolicyRow } from "../../services/policyResults"
import { formatTime } from "../../services/analysisSession"
import {
  conditionFields,
  isUnverified,
  resultCategoryLabels,
  resultCategoryOf,
  resultReason,
} from "./AnalysisPolicyCard"

const label = (field: string) => conditionFields[field.toLowerCase()] ?? field

// 정책 상세 화면 위쪽에 보여주는 '이 정책에 대한 내 진단 결과' 요약.
export default function MyPolicyResult({
  policy,
  checkedAt,
  onOpenResults,
}: {
  policy: PolicyRow
  checkedAt: string
  onOpenResults: () => void
}) {
  const category = resultCategoryOf(policy)
  const failed = policy.conditions.filter((c) => c.status === "미충족")
  const review = policy.conditions.filter((c) => c.status === "추가 확인")
  const met = policy.confirmedConditions ?? []
  return (
    <section className="my-policy-result" data-result={category} aria-label="이 정책에 대한 내 진단 결과">
      <header>
        <div>
          <p className="my-policy-kicker">내 진단 결과 · {formatTime(checkedAt)}</p>
          <h2>
            <span className="reverse-tag" data-result={category}>
              {resultCategoryLabels[category]}
            </span>
            {isUnverified(policy) && (
              <span className="reverse-tag" data-result="unverified">
                비교 조건 없음
              </span>
            )}
          </h2>
          <p>{resultReason(policy)}</p>
        </div>
        <button type="button" className="text-action" onClick={onOpenResults}>
          전체 진단 결과 보기 →
        </button>
      </header>
      <div className="my-policy-columns">
        <div data-kind="failed">
          <h3>미충족 <b>{failed.length}</b></h3>
          {failed.length ? (
            <ul>
              {failed.map((c, i) => (
                <li key={i}>
                  <strong>{label(c.field)}</strong> 기준 {c.required || "공식 기준 확인"} · 내 정보 {c.current || "미입력"}
                </li>
              ))}
            </ul>
          ) : (
            <p>입력한 정보와 맞지 않는 조건이 없어요.</p>
          )}
        </div>
        <div data-kind="passed">
          <h3>충족 <b>{policy.counts?.passed ?? met.length}</b></h3>
          {met.length ? (
            <ul>
              {met.map((c, i) => (
                <li key={i}>
                  <strong>{label(c.field)}</strong> {c.current}
                  {c.required ? ` · 기준 ${c.required}` : ""}
                </li>
              ))}
            </ul>
          ) : (
            <p>입력값으로 비교해 충족을 확인한 조건이 없어요.</p>
          )}
        </div>
        <div data-kind="review">
          <h3>추가 확인 <b>{review.length}</b></h3>
          {review.length ? (
            <ul>
              {review.slice(0, 4).map((c, i) => (
                <li key={i}>
                  <strong>{label(c.field)}</strong> {c.required || "공식 기준 확인 필요"}
                </li>
              ))}
              {review.length > 4 && <li>외 {review.length - 4}개는 아래 원문에서 확인하세요.</li>}
            </ul>
          ) : (
            <p>추가로 확인할 조건이 없어요.</p>
          )}
        </div>
      </div>
    </section>
  )
}
