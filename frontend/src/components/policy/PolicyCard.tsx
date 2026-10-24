import { categoryLabel, type CatalogPolicy } from "../../types/policyCatalog"

export default function PolicyCard({
  policy,
  index,
}: {
  policy: CatalogPolicy
  index: number
}) {
  return (
    <article data-reveal data-reveal-delay={index % 3} className="catalog-card">
      <div className="catalog-tags">
        {policy.categories.map((category) => (
          <span key={category}>{categoryLabel(category)}</span>
        ))}
      </div>
      <h3>
        <a href={"#detail/" + encodeURIComponent(policy.id)}>{policy.title}</a>
      </h3>
      <p className="catalog-description">
        {policy.summary || "상세 화면에서 지원 대상과 내용을 확인해주세요."}
      </p>
      <div className="catalog-card-meta">
        <span>{policy.department || "제공 기관 확인 필요"}</span>
        <span>{policy.support_type || "지원 방식 확인 필요"}</span>
      </div>
      <a
        className="catalog-detail-link"
        href={"#detail/" + encodeURIComponent(policy.id)}
        aria-label={policy.title + " 상세 보기"}
      >
        지원 내용 보기 <span aria-hidden="true">↗</span>
      </a>
    </article>
  )
}
