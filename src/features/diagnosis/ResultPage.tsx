import { useState } from 'react'
import type { Page } from '../../types/page'
import type { Policy } from '../../types/policy'
import { POLICIES } from '../../data/policies'
import { StatusPill } from '../../components/policy/PolicyStatus'

export default function ResultPage({ setPage, setSelectedPolicy }: { setPage: (p: Page) => void; setSelectedPolicy: (p: Policy) => void }) {
  const [activeTab, setActiveTab] = useState<'all' | 'eligible' | 'potential' | 'ineligible'>('all')
  const [expandedId, setExpandedId] = useState<string | null>('3')

  const eligible = POLICIES.filter(p => p.status === 'eligible')
  const potential = POLICIES.filter(p => p.status === 'potential')
  const ineligible = POLICIES.filter(p => p.status === 'ineligible')

  const displayPolicies = activeTab === 'all' ? POLICIES : activeTab === 'eligible' ? eligible : activeTab === 'potential' ? potential : ineligible

  return (
    <div className="pb-20 md:pb-0">
      {/* Result hero */}
      <div className="bg-slate-900 border-b-2 border-slate-800 py-10 px-4 sm:px-6">
        <div className="max-w-4xl mx-auto">
          <div className="text-emerald-400 text-xs font-black tracking-widest mb-3">진단 완료</div>
          <div className="flex flex-wrap items-end gap-6 mb-8">
            <div>
              <div className="text-slate-400 text-sm font-bold mb-1">신청 가능한 정책</div>
              <div className="text-7xl font-black text-white leading-none">{eligible.length}<span className="text-3xl text-slate-500 ml-1">/{POLICIES.length}</span></div>
            </div>
            <div className="flex-1 min-w-48">
              <div className="text-slate-400 text-xs font-bold mb-2">전체 자격 달성도</div>
              <div className="h-4 bg-slate-800 rounded-full overflow-hidden flex border border-slate-700">
                <div className="h-full bg-emerald-500" style={{ width: `${(eligible.length / POLICIES.length) * 100}%` }} />
                <div className="h-full bg-blue-500" style={{ width: `${(potential.length / POLICIES.length) * 100}%` }} />
                <div className="h-full bg-orange-500" style={{ width: `${(ineligible.length / POLICIES.length) * 100}%` }} />
              </div>
              <div className="flex gap-4 mt-2 text-xs text-slate-400 font-bold">
                <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-sm bg-emerald-500 inline-block" />{eligible.length} 가능</span>
                <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-sm bg-blue-500 inline-block" />{potential.length} 확인</span>
                <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-sm bg-orange-500 inline-block" />{ineligible.length} 미충족</span>
              </div>
            </div>
          </div>

          {/* Mini stat cards */}
          <div className="grid grid-cols-3 gap-3">
            {[
              { label: '신청 가능', count: eligible.length, bg: 'bg-emerald-500', text: '바로 신청하세요' },
              { label: '추가 확인 필요', count: potential.length, bg: 'bg-blue-500', text: '조건을 확인해보세요' },
              { label: '조건 미충족', count: ineligible.length, bg: 'bg-orange-500', text: 'Delta 분석을 확인해요' },
            ].map((s, i) => (
              <div key={i} className={`${s.bg} rounded-xl p-4 border border-white/10`}>
                <div className="text-white/80 text-[10px] font-black mb-1">{s.label}</div>
                <div className="text-3xl font-black text-white">{s.count}</div>
                <div className="text-white/60 text-[10px] mt-1">{s.text}</div>
              </div>
            ))}
          </div>
        </div>
      </div>

      <div className="max-w-4xl mx-auto px-4 sm:px-6 py-8 space-y-6">
        {/* Delta Analysis */}
        <div className="bg-white border-2 border-slate-200 rounded-2xl overflow-hidden">
          <div className="flex items-center gap-3 px-6 py-4 bg-orange-50 border-b border-orange-200">
            <span className="text-xl font-black text-orange-600">△</span>
            <div>
              <div className="font-black text-orange-900">미충족 조건 Delta 분석</div>
              <div className="text-orange-600 text-xs">이 조건들만 충족하면 신청 가능성이 생겨요</div>
            </div>
          </div>

          {POLICIES.filter(p => p.status === 'ineligible' || p.status === 'potential').map(policy => {
            const missing = policy.conditions.filter(c => c.result === 'ineligible')
            const isOpen = expandedId === policy.id
            return (
              <div key={policy.id} className="border-b border-slate-100 last:border-0">
                <button
                  onClick={() => setExpandedId(isOpen ? null : policy.id)}
                  className="w-full flex items-center justify-between px-6 py-4 hover:bg-slate-50 transition-colors text-left"
                >
                  <div className="flex items-center gap-3">
                    <span className="text-xl">{policy.emoji}</span>
                    <div>
                      <div className="font-black text-slate-900 text-sm">{policy.name}</div>
                      <div className="text-slate-400 text-xs">{policy.benefit}</div>
                    </div>
                  </div>
                  <div className="flex items-center gap-2 flex-shrink-0">
                    <span className="text-xs font-black bg-orange-100 text-orange-700 px-2 py-1 rounded-lg">{missing.length}개 미충족</span>
                    <span className="text-slate-400 text-sm">{isOpen ? '▲' : '▼'}</span>
                  </div>
                </button>

                {isOpen && (
                  <div className="px-6 pb-5">
                    {/* Condition table */}
                    <div className="border border-slate-200 rounded-xl overflow-hidden mb-4">
                      <table className="w-full text-sm">
                        <thead className="bg-slate-50">
                          <tr>
                            {['조건', '정책 기준', '나의 상태', '결과'].map(h => (
                              <th key={h} className="text-left px-3 py-2 text-xs font-black text-slate-500">{h}</th>
                            ))}
                          </tr>
                        </thead>
                        <tbody className="divide-y divide-slate-100">
                          {policy.conditions.map((c, i) => (
                            <tr key={i} className={c.result === 'ineligible' ? 'bg-orange-50' : ''}>
                              <td className="px-3 py-3 font-black text-slate-800">{c.label}</td>
                              <td className="px-3 py-3 text-slate-600 text-xs">{c.requirement}</td>
                              <td className={`px-3 py-3 font-bold text-xs ${c.result === 'eligible' ? 'text-emerald-700' : c.result === 'ineligible' ? 'text-orange-700' : 'text-blue-700'}`}>{c.userValue}</td>
                              <td className="px-3 py-3">
                                <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-black ${c.result === 'eligible' ? 'bg-emerald-100 text-emerald-700' : c.result === 'ineligible' ? 'bg-orange-100 text-orange-700' : 'bg-blue-100 text-blue-700'}`}>
                                  {c.result === 'eligible' ? '✓ 충족' : c.result === 'ineligible' ? '✕ 미충족' : '△ 확인'}
                                </span>
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>

                    {missing.length > 0 && (
                      <div className="bg-orange-50 border border-orange-200 rounded-xl p-4 text-sm">
                        <div className="font-black text-orange-800 mb-2">📌 다음에 확인할 것</div>
                        <ul className="text-orange-700 space-y-1 text-xs">
                          <li>• 소득 산정 방식 및 공식 기준 확인</li>
                          <li>• 가구원 수 및 가구 소득 기준 재확인</li>
                          <li>• 최근 소득 변동 여부 점검</li>
                          <li>• 해당 기관 공식 신청 기준 재확인</li>
                        </ul>
                        <button className="mt-3 text-xs font-black text-orange-700 border border-orange-300 bg-white px-3 py-1.5 rounded-lg hover:bg-orange-50 transition-colors">
                          공식 기준 자세히 보기 →
                        </button>
                      </div>
                    )}
                  </div>
                )}
              </div>
            )
          })}
        </div>

        {/* Policy list */}
        <div className="bg-white border-2 border-slate-200 rounded-2xl overflow-hidden">
          <div className="flex border-b-2 border-slate-200">
            {[
              { id: 'all', label: '전체', count: POLICIES.length },
              { id: 'eligible', label: '✓ 가능', count: eligible.length },
              { id: 'potential', label: '△ 확인', count: potential.length },
              { id: 'ineligible', label: '✕ 미충족', count: ineligible.length },
            ].map(t => (
              <button key={t.id} onClick={() => setActiveTab(t.id as typeof activeTab)}
                className={`flex-1 px-2 py-3.5 text-xs font-black transition-colors ${activeTab === t.id ? 'bg-slate-900 text-white' : 'text-slate-500 hover:text-slate-700 hover:bg-slate-50'}`}>
                {t.label} <span className="ml-0.5 opacity-70">{t.count}</span>
              </button>
            ))}
          </div>
          <div className="p-4 space-y-2">
            {displayPolicies.map(p => (
              <div key={p.id} onClick={() => { setSelectedPolicy(p); setPage('detail') }}
                className="flex items-center justify-between p-4 border border-slate-100 rounded-xl hover:border-blue-200 hover:bg-blue-50/30 transition-all cursor-pointer group">
                <div className="flex items-center gap-3 flex-1 min-w-0 mr-4">
                  <span className="text-xl flex-shrink-0">{p.emoji}</span>
                  <div>
                    <div className="font-black text-slate-800 text-sm group-hover:text-blue-700 transition-colors">{p.name}</div>
                    <div className="text-slate-500 text-xs">{p.benefit} · {p.region}</div>
                  </div>
                </div>
                <StatusPill status={p.status} />
              </div>
            ))}
          </div>
        </div>

        <div className="flex gap-3">
          <button onClick={() => setPage('diagnosis')} className="flex-1 border-2 border-slate-900 text-slate-900 font-black py-4 rounded-xl hover:bg-slate-900 hover:text-white transition-colors">다시 진단하기</button>
          <button onClick={() => setPage('dashboard')} className="flex-1 bg-blue-600 text-white font-black py-4 rounded-xl hover:bg-blue-700 transition-colors border-2 border-slate-900 shadow-[3px_3px_0px_#0A0F1E]">나의 현황 보기 →</button>
        </div>
      </div>
    </div>
  )
}
