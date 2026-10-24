from pydantic import BaseModel


class CategoryCount(BaseModel):
    id: str
    label: str
    count: int


class CatalogPolicy(BaseModel):
    id: str
    title: str
    summary: str
    categories: list[str]
    source_categories: list[str]
    department: str
    organization: str
    support_type: str
    detail_url: str
    synced_at: str


class CatalogDetail(CatalogPolicy):
    target_details: str
    selection_criteria: str
    support_content: str
    support_cycle: str
    reference_year: str
    application_methods: list[str]


class CatalogResponse(BaseModel):
    items: list[CatalogPolicy]
    total: int
    page: int
    page_size: int
    categories: list[CategoryCount]
    collected_count: int
