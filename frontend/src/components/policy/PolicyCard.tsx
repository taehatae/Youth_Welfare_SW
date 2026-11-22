import { categoryLabel, type CatalogPolicy } from "../../types/policyCatalog"
import { styleOf, supportTypeOf } from "../../features/policies/categoryStyle"
import {
  resultCategoryLabels,
  type ResultCategory,
} from "./AnalysisPolicyCard"

// 첫 줄만 짧게 보여준다.
const shortLine = (text: string) =>
  (text.split("\n")[0] ?? "").replace(/\s+/g, " ").trim()

export default function PolicyCard({
  policy,
  index,
  status,
}: {
  policy: CatalogPolicy
  index: number
  /** 내 진단 결과가 있을 때만 */
  status?: ResultCategory
}) {
  const style = styleOf(policy.categories)
  const first = policy.categories[0]
  const support = supportTypeOf(policy.support_type)
  return (
    <a
      data-reveal
      data-reveal-delay={index % 4}
      className="catalog-row"
      href={"#detail/" + encodeURIComponent(policy.id)}
      aria-label={policy.title + " 상세 보기"}
    >
      <span
        className="catalog-row-icon"
        style={{ background: style.bg, color: style.ink }}
        aria-hidden="true"
      >
        {support.glyph || style.word.slice(0, 1)}
      </span>
      <span className="catalog-row-body">
        <h3>{policy.title}</h3>
        <span className="catalog-row-summary">
          {shortLine(policy.summary) || policy.support_type || "지원 내용 확인 필요"}
        </span>
        <span className="catalog-row-meta">
          {first && <span>{categoryLabel(first)}</span>}
          <span>{policy.department || "제공 기관 확인 필요"}</span>
          <span className="catalog-row-pill">{support.label}</span>
        </span>
      </span>
      <span className="catalog-row-end">
        {status && (
          <em data-result={status}>{resultCategoryLabels[status]}</em>
        )}
        <i aria-hidden="true">›</i>
      </span>
    </a>
  )
}
