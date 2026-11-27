export const CATALOG_CATEGORIES = [
  ["all", "전체"],
  ["housing", "주거"],
  ["employment", "취업·일자리"],

  ["finance", "금융·자산"],
  ["education", "교육"],
  ["health", "건강"],

  ["living", "생활·돌봄"],
  ["culture", "문화·여가"],
  ["safety", "안전·법률"],
  ["other", "기타·미분류"],
] as const

export const categoryLabel = (id: string) =>
  CATALOG_CATEGORIES.find(([key]) => key === id)?.[1] ?? id

export interface CatalogPolicy {
  id: string
  title: string
  summary: string
  categories: string[]
  source_categories: string[]

  department: string
  organization: string
  support_type: string
  detail_url: string
  synced_at: string
}

export interface CatalogDetail extends CatalogPolicy {
  target_details: string
  selection_criteria: string
  support_content: string

  support_cycle: string
  reference_year: string
  application_methods: string[]
}

export interface CatalogResponse {
  items: CatalogPolicy[]
  total: number
  page: number
  page_size: number
  collected_count: number

  categories: {
    id: string
    label: string
    count: number
  }[]
}
