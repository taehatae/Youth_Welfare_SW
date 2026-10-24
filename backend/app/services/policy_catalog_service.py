import re
from datetime import timezone
from fastapi import HTTPException
from app.repositories.policy_catalog_repository import PolicyCatalogRepository
from app.schemas.policy_catalog import CatalogPolicy, CatalogDetail, CatalogResponse, CategoryCount

# 복지로의 관심분야 원문을 기준으로 묶는다. 정책명 키워드로 자격이나 분야를 추측하지 않는다.
CATEGORIES = {
    "housing": ("주거", {"주거"}),
    "employment": ("취업·일자리", {"일자리"}),
    "finance": ("금융·자산", {"서민금융"}),
    "education": ("교육", {"교육"}),
    "health": ("건강", {"신체건강", "정신건강"}),
    "living": ("생활·돌봄", {"생활지원", "보호·돌봄", "임신·출산", "입양·위탁"}),
    "culture": ("문화·여가", {"문화·여가"}),
    "safety": ("안전·법률", {"안전·위기", "법률"}),
    "other": ("기타·미분류", set()),
}


class PolicyCatalogService:
    repository = PolicyCatalogRepository()

    def item(self, row):
        source = [part.strip() for part in re.split(r"[,|]", row.interest_categories or "") if part.strip()]
        categories = [key for key, (_, fields) in CATEGORIES.items() if fields.intersection(source)]
        known = set().union(*(fields for _, fields in CATEGORIES.values()))
        if not categories or set(source) - known:
            categories.append("other")
        return CatalogPolicy(id=row.serv_id, title=row.serv_name, summary=row.summary,
            categories=categories, source_categories=source, department=row.department,
            organization=row.organization, support_type=row.support_type, detail_url=row.detail_url,
            synced_at=row.synced_at.replace(tzinfo=timezone.utc).isoformat())

    def search(self, db, query, category, page, page_size):
        if category != "all" and category not in CATEGORIES:
            raise HTTPException(422, "지원하지 않는 정책 분야예요.")
        items = [self.item(row) for row in self.repository.search(db, query.strip())]
        counts = [CategoryCount(id="all", label="전체", count=len(items))]
        counts += [CategoryCount(id=key, label=label, count=sum(key in item.categories for item in items))
                   for key, (label, _) in CATEGORIES.items()]
        filtered = [item for item in items if category == "all" or category in item.categories]
        return CatalogResponse(items=filtered[(page-1)*page_size:page*page_size], total=len(filtered),
            page=page, page_size=page_size, categories=counts, collected_count=self.repository.count(db))

    def detail(self, db, policy_id):
        row = self.repository.get(db, policy_id)
        if row is None:
            raise HTTPException(404, "정책을 찾지 못했어요. 목록에서 다시 선택해주세요.")
        # 신청방법은 API에서 제공한 텍스트만 사용하고 지원 주기를 신청기간으로 표시하지 않는다.
        methods = []
        for item in row.application_methods:
            if not isinstance(item, dict):
                continue
            content = str(item.get("link_or_content") or item.get("applMtdCn") or item.get("applMtdNm") or "").strip()
            if not content:
                continue
            label = str(item.get("name") or "").replace("연락처목록", "").replace("목록", "")
            methods.append(f"{label}: {content}" if label else content)
        return CatalogDetail(**self.item(row).model_dump(), target_details=row.target_details,
            selection_criteria=row.selection_criteria, support_content=row.support_content,
            support_cycle=row.support_cycle, reference_year=row.reference_year,
            application_methods=list(dict.fromkeys(methods)))
