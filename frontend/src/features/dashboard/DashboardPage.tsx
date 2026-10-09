import type { Page } from '../../types/page'
import type { Policy } from '../../types/policy'
import { POLICIES } from '../../data/policies'
import { LogoMark } from '../../components/brand/LogoMark'
import { StatusPill } from '../../components/policy/PolicyStatus'

export default function DashboardPage({ setPage, setSelectedPolicy }: { setPage: (p: Page) => void; setSelectedPolicy: (p: Policy) => void }) {
  const eligible = POLICIES.filter(p => p.status === 'eligible')
  const potential = POLICIES.filter(p => p.status === 'potential')
  const ineligible = POLICIES.filter(p => p.status === 'ineligible')

  return (
    <div className="pb-20 md:pb-0">
      {/* Header */}
      <div className="bg-slate-900 border-b-2 border-slate-800 py-8 px-4 sm:px-6">
        <div className="max-w-6xl mx-auto flex flex-wrap items-center justify-between gap-4">
          <div>
            <div className="text-emerald-400 text-xs font-black tracking-widest mb-1">MY DASHBOARD</div>
            <h1 className="text-2xl font-black text-white">나의 복지 현황</h1>
            <p className="text-slate-400 text-xs mt-1">2026.09.23 기준 진단 결과</p>
          </div>
          <button onClick={() => setPage('diagnosis')}
            className="bg-blue-600 text-white font-black px-5 py-2.5 rounded-xl border border-blue-500 hover:bg-blue-500 transition-colors text-sm">
            재진단하기 →
          </button>
        </div>
      </div>

      <div className="max-w-6xl mx-auto px-4 sm:px-6 py-8">
        {/* Overview bar */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8">
          {[
            { label: '분석 정책', val: POLICIES.length, unit: '개', bg: 'bg-slate-100 border-slate-200', num: 'text-slate-900' },
            { label: '신청 가능', val: eligible.length, unit: '개', bg: 'bg-emerald-50 border-emerald-300', num: 'text-emerald-700' },
            { label: '추가 확인', val: potential.length, unit: '개', bg: 'bg-blue-50 border-blue-300', num: 'text-blue-700' },
            { label: '조건 미충족', val: ineligible.length, unit: '개', bg: 'bg-orange-50 border-orange-300', num: 'text-orange-700' },
          ].map((s, i) => (
            <div key={i} className={`${s.bg} border-2 rounded-2xl p-5`}>
              <div className={`text-4xl font-black ${s.num} mb-1`}>{s.val}<span className="text-lg font-black ml-1">{s.unit}</span></div>
              <div className="text-slate-500 text-xs font-bold">{s.label}</div>
            </div>
          ))}
        </div>

        <div className="grid md:grid-cols-3 gap-6">
          <div className="md:col-span-2 space-y-6">
            {/* Eligible */}
            <div className="bg-white border-2 border-slate-200 rounded-2xl overflow-hidden">
              <div className="flex items-center justify-between px-5 py-4 bg-emerald-50 border-b border-emerald-200">
                <div className="font-black text-emerald-900">지금 신청 가능한 정책</div>
                <span className="bg-emerald-500 text-white text-xs font-black px-2.5 py-1 rounded-full">{eligible.length}개</span>
              </div>
              <div className="p-4 space-y-2">
                {eligible.map(p => (
                  <div key={p.id} onClick={() => { setSelectedPolicy(p); setPage('detail') }}
                    className="flex items-center gap-4 p-3.5 border border-slate-100 rounded-xl hover:border-emerald-300 hover:bg-emerald-50/50 transition-all cursor-pointer group">
                    <div className="w-10 h-10 bg-emerald-100 rounded-xl flex items-center justify-center text-xl flex-shrink-0">{p.emoji}</div>
                    <div className="flex-1 min-w-0">
                      <div className="font-black text-slate-800 text-sm group-hover:text-emerald-700 transition-colors">{p.name}</div>
                      <div className="text-slate-500 text-xs mt-0.5">{p.benefit}</div>
                    </div>
                    <span className="text-emerald-500 font-black text-lg flex-shrink-0">✓</span>
                  </div>
                ))}
              </div>
            </div>

            {/* Potential */}
            <div className="bg-white border-2 border-slate-200 rounded-2xl overflow-hidden">
              <div className="flex items-center justify-between px-5 py-4 bg-blue-50 border-b border-blue-200">
                <div className="font-black text-blue-900">추가 확인이 필요한 정책</div>
                <span className="bg-blue-500 text-white text-xs font-black px-2.5 py-1 rounded-full">{potential.length}개</span>
              </div>
              <div className="p-4 space-y-2">
                {potential.map(p => {
                  const met = p.conditions.filter(c => c.result === 'eligible').length
                  const total = p.conditions.length
                  return (
                    <div key={p.id} onClick={() => { setSelectedPolicy(p); setPage('detail') }}
                      className="flex items-center gap-4 p-3.5 border border-slate-100 rounded-xl hover:border-blue-300 hover:bg-blue-50/50 transition-all cursor-pointer group">
                      <div className="w-10 h-10 bg-blue-100 rounded-xl flex items-center justify-center text-xl flex-shrink-0">{p.emoji}</div>
                      <div className="flex-1 min-w-0">
                        <div className="font-black text-slate-800 text-sm group-hover:text-blue-700 transition-colors">{p.name}</div>
                        <div className="flex items-center gap-2 mt-1">
                          <div className="flex-1 h-1.5 bg-slate-100 rounded-full overflow-hidden max-w-20">
                            <div className="h-full bg-blue-500 rounded-full" style={{ width: `${(met / total) * 100}%` }} />
                          </div>
                          <span className="text-xs text-slate-400 font-bold">{met}/{total}</span>
                        </div>
                      </div>
                      <button onClick={e => { e.stopPropagation(); setPage('diagnosis') }}
                        className="text-xs font-black border border-blue-200 bg-blue-50 text-blue-700 px-3 py-1.5 rounded-lg hover:bg-blue-100 transition-colors whitespace-nowrap flex-shrink-0">
                        확인 →
                      </button>
                    </div>
                  )
                })}
              </div>
            </div>
          </div>

          {/* Sidebar */}
          <div className="space-y-5">
            {/* Deadline */}
            <div className="bg-white border-2 border-slate-200 rounded-2xl overflow-hidden">
              <div className="flex items-center gap-2 px-5 py-4 bg-orange-50 border-b border-orange-200">
                <span className="text-orange-500 text-base">⏰</span>
                <div className="font-black text-orange-900 text-sm">신청기간 임박</div>
              </div>
              <div className="p-4 space-y-3">
                {POLICIES.filter(p => p.period !== '상시 모집' && p.period !== '상시 신청').slice(0, 2).map(p => (
                  <div key={p.id} className="p-3 bg-orange-50 border border-orange-200 rounded-xl cursor-pointer hover:bg-orange-100 transition-colors" onClick={() => { setSelectedPolicy(p); setPage('detail') }}>
                    <div className="font-black text-slate-900 text-sm mb-1">{p.emoji} {p.name}</div>
                    <div className="text-orange-600 text-xs font-bold">마감: {p.period.split('~')[1]?.trim() || p.period}</div>
                    <div className="mt-2"><StatusPill status={p.status} /></div>
                  </div>
                ))}
              </div>
            </div>

            {/* Quick links */}
            <div className="bg-white border-2 border-slate-200 rounded-2xl p-5">
              <div className="font-black text-slate-900 text-sm mb-4">빠른 메뉴</div>
              <div className="space-y-1">
                {[
                  { label: '정책 더 찾아보기', icon: '🔍', action: () => setPage('explorer') },
                  { label: '진단 다시 하기', icon: '📋', action: () => setPage('diagnosis') },
                  { label: 'Delta 분석 보기', icon: '△', action: () => setPage('result') },
                ].map((a, i) => (
                  <button key={i} onClick={a.action}
                    className="w-full flex items-center gap-3 px-3 py-3 rounded-xl text-left hover:bg-slate-50 transition-colors group border border-transparent hover:border-slate-200">
                    <span className="text-base w-6 text-center">{a.icon}</span>
                    <span className="text-sm font-black text-slate-700 group-hover:text-blue-600 transition-colors flex-1">{a.label}</span>
                    <span className="text-slate-300 group-hover:text-blue-400 transition-colors font-black">→</span>
                  </button>
                ))}
              </div>
            </div>

            {/* Logo card */}
            <div className="bg-slate-900 rounded-2xl border-2 border-slate-800 p-5 text-center">
              <div className="flex items-center justify-center gap-2 mb-3">
                <LogoMark size={28} />
                <div className="text-left">
                  <div className="text-white font-black text-base leading-none">자격있청</div>
                  <div className="text-blue-400 text-[8px] font-black tracking-widest">FOR YOUTH</div>
                </div>
              </div>
              <p className="text-slate-400 text-xs leading-relaxed">데이터로 더 정확하게<br/>청년의 내일을 더 가깝게</p>
              <div className="mt-3 text-[10px] text-slate-600">데이터 기준: 2026.09.23</div>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
