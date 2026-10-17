import PageHeading from "../../components/layout/PageHeading"
import { useState } from "react"

import type { Page } from "../../types/page"

import type { Policy } from "../../types/policy"

import { CATEGORIES, POLICIES } from "../../data/policies"

import PolicyCard from "../../components/policy/PolicyCard"

// ── EXPLORER PAGE ─────────────────────────────────────────────────────────────

export default function PolicyExplorerPage({
  setPage,
  setSelectedPolicy,
}: {
  setPage: (p: Page) => void
  setSelectedPolicy: (p: Policy) => void
}) {
  const [search, setSearch] = useState("")

  const [activeCategory, setActiveCategory] = useState("전체")

  const [statusFilter, setStatusFilter] = useState<Policy["status"] | "all">(
    "all",
  )

  const filtered = POLICIES.filter((p) => {
    const matchSearch = p.name.includes(search) || p.desc.includes(search)

    const matchCat = activeCategory === "전체" || p.category === activeCategory

    const matchStatus = statusFilter === "all" || p.status === statusFilter

    return matchSearch && matchCat && matchStatus
  })

  return (
    <div className="pb-20 md:pb-0">
      <div className="max-w-6xl mx-auto px-4 sm:px-6 pt-8">
        <PageHeading eyebrow="내 생활과 가까운 지원" title="복지정책 둘러보기" description="주거부터 취업까지, 분야별 정책을 살펴보세요. 현재 목록과 조건 표시는 설명용 예시이며 본인의 진단 결과가 아닙니다.">
          <div className="relative max-w-2xl">
            <input
              aria-label="예시 정책 검색"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="어떤 청년복지를 찾고 있나요? (월세, 취업, 금융…)"
              className="interface-search w-full pl-12 pr-4 py-4 rounded-xl text-sm placeholder-slate-500 font-medium"
            />
            <span className="absolute left-4 top-1/2 -translate-y-1/2 text-slate-400 text-lg">
              🔍
            </span>
          </div>
        </PageHeading>
      </div>

      <div className="max-w-6xl mx-auto px-4 sm:px-6 py-8">
        {/* Filters */}
        <div className="flex flex-wrap gap-2 mb-4">
          {CATEGORIES.map((c) => (
            <button
              key={c}
              aria-pressed={activeCategory === c}
              onClick={() => setActiveCategory(c)}
              className={`px-4 py-2 rounded-full text-sm font-semibold transition-all border ${
                activeCategory === c
                  ? "bg-blue-700 text-white border-blue-800"
                  : "bg-white text-slate-700 border-slate-200 hover:border-slate-400"
              }`}
            >
              {c}
            </button>
          ))}
        </div>
        <div className="flex flex-wrap gap-2 mb-8">
          {[
            { id: "all", label: "전체" },

            { id: "eligible", label: "✓ 예시 조건 충족" },

            { id: "potential", label: "△ 예시 확인 필요" },

            { id: "ineligible", label: "✕ 예시 미충족" },
          ].map((f) => (
            <button
              key={f.id}
              aria-pressed={statusFilter === f.id}
              onClick={() => setStatusFilter(f.id as typeof statusFilter)}
              className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition-all border ${
                statusFilter === f.id
                  ? "bg-blue-600 text-white border-blue-600"
                  : "bg-white text-slate-600 border-slate-200 hover:border-slate-400"
              }`}
            >
              {f.label}
            </button>
          ))}
        </div>

        <div className="mb-5 flex items-center justify-between">
          <div className="text-sm font-bold text-slate-500">
            <span className="text-slate-900 text-xl font-semibold">
              {filtered.length}
            </span>
            개 정책
          </div>
        </div>

        {filtered.length === 0 ? (
          <div className="text-center py-24">
            <div className="text-6xl mb-4">🔍</div>
            <div className="font-semibold text-slate-900 text-lg">
              검색 결과가 없어요
            </div>
            <div className="text-slate-500 text-sm mt-1">
              다른 키워드로 검색해보세요
            </div>
          </div>
        ) : (
          <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-5">
            {filtered.map((p) => (
              <PolicyCard
                key={p.id}
                policy={p}
                onClick={() => {
                  setSelectedPolicy({ ...p, isExample: true })
                  setPage("detail")
                }}
              />
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
