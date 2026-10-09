import { useState } from 'react'
import type { Page } from '../../types/page'
import type { Policy } from '../../types/policy'
import { CATEGORIES, POLICIES } from '../../data/policies'
import { ConditionRow, StatusPill } from '../../components/policy/PolicyStatus'
import PolicyCard from '../../components/policy/PolicyCard'

// ── EXPLORER PAGE ─────────────────────────────────────────────────────────────
export default function PolicyExplorerPage({ setPage, setSelectedPolicy }: { setPage: (p: Page) => void; setSelectedPolicy: (p: Policy) => void }) {
  const [search, setSearch] = useState('')
  const [activeCategory, setActiveCategory] = useState('전체')
  const [statusFilter, setStatusFilter] = useState<Policy['status'] | 'all'>('all')

  const filtered = POLICIES.filter(p => {
    const matchSearch = p.name.includes(search) || p.desc.includes(search)
    const matchCat = activeCategory === '전체' || p.category === activeCategory
    const matchStatus = statusFilter === 'all' || p.status === statusFilter
    return matchSearch && matchCat && matchStatus
  })

  return (
    <div className="pb-20 md:pb-0">
      {/* Header */}
      <div className="bg-slate-900 border-b-2 border-slate-800 py-10 px-4 sm:px-6">
        <div className="max-w-6xl mx-auto">
          <div className="text-emerald-400 text-xs font-black tracking-widest mb-2">POLICY FINDER</div>
          <h1 className="text-3xl font-black text-white mb-6">복지정책 찾기</h1>
          <div className="relative max-w-2xl">
            <input
              value={search}
              onChange={e => setSearch(e.target.value)}
              placeholder="어떤 청년복지를 찾고 있나요? (월세, 취업, 금융…)"
              className="w-full pl-12 pr-4 py-4 border-2 border-slate-700 bg-slate-800 text-white rounded-xl text-sm focus:outline-none focus:border-blue-500 placeholder-slate-500 font-medium"
            />
            <span className="absolute left-4 top-1/2 -translate-y-1/2 text-slate-400 text-lg">🔍</span>
          </div>
        </div>
      </div>

      <div className="max-w-6xl mx-auto px-4 sm:px-6 py-8">
        {/* Filters */}
        <div className="flex flex-wrap gap-2 mb-4">
          {CATEGORIES.map(c => (
            <button
              key={c}
              onClick={() => setActiveCategory(c)}
              className={`px-4 py-2 rounded-full text-sm font-black transition-all border-2 ${
                activeCategory === c
                  ? 'bg-slate-900 text-white border-slate-900'
                  : 'bg-white text-slate-700 border-slate-200 hover:border-slate-400'
              }`}
            >
              {c}
            </button>
          ))}
        </div>
        <div className="flex flex-wrap gap-2 mb-8">
          {[
            { id: 'all', label: '전체' },
            { id: 'eligible', label: '✓ 신청 가능' },
            { id: 'potential', label: '△ 확인 필요' },
            { id: 'ineligible', label: '✕ 미충족' },
          ].map(f => (
            <button
              key={f.id}
              onClick={() => setStatusFilter(f.id as typeof statusFilter)}
              className={`px-3 py-1.5 rounded-lg text-xs font-black transition-all border ${
                statusFilter === f.id
                  ? 'bg-blue-600 text-white border-blue-600'
                  : 'bg-white text-slate-600 border-slate-200 hover:border-slate-400'
              }`}
            >
              {f.label}
            </button>
          ))}
        </div>

        <div className="mb-5 flex items-center justify-between">
          <div className="text-sm font-bold text-slate-500">
            <span className="text-slate-900 text-xl font-black">{filtered.length}</span>개 정책
          </div>
        </div>

        {filtered.length === 0 ? (
          <div className="text-center py-24">
            <div className="text-6xl mb-4">🔍</div>
            <div className="font-black text-slate-900 text-lg">검색 결과가 없어요</div>
            <div className="text-slate-500 text-sm mt-1">다른 키워드로 검색해보세요</div>
          </div>
        ) : (
          <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-5">
            {filtered.map(p => (
              <PolicyCard key={p.id} policy={p} onClick={() => { setSelectedPolicy(p); setPage('detail') }} />
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
