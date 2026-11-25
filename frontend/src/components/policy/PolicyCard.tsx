import { categoryLabel, type CatalogPolicy } from "../../types/policyCatalog"
import { CATEGORY_TONE, supportTypeOf } from "../../features/policies/categoryStyle"
import CategoryIcon from "./CategoryIcon"
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
  const first = policy.categories.find((c) => c in CATEGORY_TONE) ?? policy.categories[0]
  const tone = (first && CATEGORY_TONE[first]) || "gray"
  const support = supportTypeOf(policy.support_type)
  return (
    <a
      data-reveal
      data-reveal-delay={index % 4}
      className="catalog-row"
      href={"#detail/" + encodeURIComponent(policy.id)}
      aria-label={policy.title + " 상세 보기"}
    >
      <span className="catalog-row-icon" data-tone={tone} aria-hidden="true">
        <CategoryIcon id={first ?? "other"} size={26} />
      </span>
      <span className="catalog-row-body">
        <h3>{policy.title}</h3>
        <span className="catalog-row-summary">
          {shortLine(policy.summary) || policy.support_type || "지원 내용 확인 필요"}
        </span>
        <span className="catalog-row-meta">
          {first && <span className="catalog-row-pill" data-tone={tone}>{categoryLabel(first)}</span>}
          <span className="catalog-row-pill">{support.label}</span>
          <span className="catalog-row-dept">{policy.department || "제공 기관 확인 필요"}</span>
        </span>
      </span>
      <span className="catalog-row-end">
        {status && (
          <em data-result={status}>{resultCategoryLabels[status]}</em>
        )}
        <i aria-hidden="true">→</i>
      </span>
    </a>
  )
}
