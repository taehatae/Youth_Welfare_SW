import type { Page } from '../../types/page'
import type { Policy } from '../../types/policy'
import { ConditionRow, StatusPill } from '../../components/policy/PolicyStatus'

export default function PolicyDetailPage({ policy, setPage }: { policy: Policy; setPage: (p: Page) => void }) {
  const eligible = policy.conditions.filter(c => c.result === 'eligible').length
  const total = policy.conditions.length
  const missing = policy.conditions.filter(c => c.result === 'ineligible')

  const statusHero: Record<Policy['status'], string> = {
    eligible: 'bg-emerald-500',
    potential: 'bg-blue-600',
    ineligible: 'bg-orange-500',
    unknown: 'bg-slate-500',
  }

  return (
    <div className="pb-20 md:pb-0">
      {/* Top band */}
      <div className={`${statusHero[policy.status]} border-b-2 border-slate-900 py-8 px-4 sm:px-6`}>
        <div className="max-w-4xl mx-auto">
          <button onClick={() => setPage('explorer')} className="text-white/70 text-xs font-bold mb-4 hover:text-white flex items-center gap-1">
            ← 정책 목록으로
          </button>
          <div className="flex flex-wrap items-center gap-3 mb-3">
            <span className="bg-white/20 text-white text-xs font-black px-3 py-1 rounded-full">{policy.category}</span>
            <StatusPill status={policy.status} />
          </div>
          <div className="flex items-start gap-4">
            <span className="text-5xl">{policy.emoji}</span>
            <div>
              <h1 className="text-2xl sm:text-3xl font-black text-white mb-1">{policy.name}</h1>
              <p className="text-white/80 text-sm">{policy.desc}</p>
            </div>
          </div>
        </div>
      </div>

      <div className="max-w-4xl mx-auto px-4 sm:px-6 py-8 space-y-5">
        {/* Benefit + info */}
        <div className="grid sm:grid-cols-3 gap-4">
          <div className="sm:col-span-1 bg-slate-900 text-white rounded-xl border-2 border-slate-900 shadow-[4px_4px_0px_#2563EB] p-5">
            <div className="text-slate-400 text-xs font-black mb-1">혜택</div>
            <div className="text-2xl font-black">{policy.benefit}</div>
          </div>
          <div className="bg-white border-2 border-slate-200 rounded-xl p-5">
            <div className="text-slate-500 text-xs font-black mb-1">신청기간</div>
            <div className="font-black text-slate-900 text-sm">{policy.period}</div>
          </div>
          <div className="bg-white border-2 border-slate-200 rounded-xl p-5">
            <div className="text-slate-500 text-xs font-black mb-1">지역 · 대상</div>
            <div className="font-black text-slate-900 text-sm">{policy.region} · {policy.target}</div>
          </div>
        </div>

        {/* Eligibility */}
        <div className="bg-white border-2 border-slate-200 rounded-xl p-6">
          <div className="flex items-center justify-between mb-5">
            <h2 className="font-black text-slate-900 text-lg">자격조건 분석</h2>
            <div className="flex items-center gap-2">
              <div className="text-sm font-black text-slate-700">{eligible}/{total} 충족</div>
              <div className="w-24 h-2.5 bg-slate-100 rounded-full overflow-hidden border border-slate-200">
                <div
                  className={`h-full rounded-full ${policy.status === 'eligible' ? 'bg-emerald-500' : policy.status === 'ineligible' ? 'bg-orange-500' : 'bg-blue-500'}`}
                  style={{ width: `${(eligible / total) * 100}%` }}
                />
              </div>
            </div>
          </div>
          <div className="space-y-2.5">
            {policy.conditions.map((c, i) => <ConditionRow key={i} c={c} />)}
          </div>
        </div>

        {/* Delta / action guide if missing */}
        {missing.length > 0 && (
          <div className="bg-orange-50 border-2 border-orange-300 rounded-xl p-6">
            <div className="flex items-center gap-2 mb-4">
              <span className="text-orange-600 text-xl font-black">△</span>
              <h2 className="font-black text-orange-900">지금 딱 {missing.length}가지 조건이 부족해요</h2>
            </div>
            {missing.map((c, i) => (
              <div key={i} className="mb-4">
                <div className="font-black text-orange-800 text-sm mb-1">{c.label} 조건</div>
                <div className="flex items-center gap-4 text-sm">
                  <div className="flex-1 bg-white rounded-lg border border-orange-200 px-3 py-2">
                    <div className="text-[10px] text-orange-500 font-black">정책 기준</div>
                    <div className="font-bold text-slate-800">{c.requirement}</div>
                  </div>
                  <span className="text-orange-400 font-black">vs</span>
                  <div className="flex-1 bg-orange-100 rounded-lg border border-orange-200 px-3 py-2">
                    <div className="text-[10px] text-orange-500 font-black">나의 상태</div>
                    <div className="font-bold text-orange-800">{c.userValue}</div>
                  </div>
                </div>
              </div>
            ))}
            <div className="mt-4 border-t border-orange-200 pt-4">
              <div className="text-xs font-black text-orange-800 mb-2">다음에 확인할 것</div>
              <ul className="text-xs text-orange-700 space-y-1">
                <li>• 소득 산정 방식 및 기준 확인</li>
                <li>• 가구원 기준 재확인</li>
                <li>• 최근 소득 변동 여부 확인</li>
                <li>• 공식 신청기관 기준 재확인</li>
              </ul>
            </div>
          </div>
        )}

        {/* CTAs */}
        <div className="flex flex-col sm:flex-row gap-3">
          <button
            onClick={() => setPage('diagnosis')}
            className="flex-1 bg-blue-600 text-white font-black py-4 px-6 rounded-xl hover:bg-blue-700 transition-colors border-2 border-slate-900 shadow-[3px_3px_0px_#0A0F1E] text-center"
          >
            내 조건으로 정밀 진단하기
          </button>
          <button className="sm:w-auto text-slate-900 border-2 border-slate-900 font-black py-4 px-6 rounded-xl hover:bg-slate-900 hover:text-white transition-colors text-center">
            공식 신청 →
          </button>
        </div>

        {/* Source */}
        <div className="bg-slate-50 border border-slate-200 rounded-xl p-4 text-xs text-slate-500">
          <div className="font-black text-slate-700 mb-1">📌 데이터 출처</div>
          <div className="grid sm:grid-cols-3 gap-1">
            <span>제공: {policy.source}</span>
            <span>기준일: 2026.09</span>
            <span>업데이트: {policy.updated}</span>
          </div>
        </div>
      </div>
    </div>
  )
}
