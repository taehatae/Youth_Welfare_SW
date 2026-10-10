import type { Policy } from '../../types/policy'
import { StatusPill } from './PolicyStatus'

export default function PolicyCard({ policy, onClick }: { policy: Policy; onClick: () => void }) {
  const eligible = policy.conditions.filter(c => c.result === 'eligible').length
  const total = policy.conditions.length
  const borderColors: Record<Policy['status'], string> = {
    eligible: 'border-t-emerald-500',
    potential: 'border-t-blue-500',
    ineligible: 'border-t-orange-500',
    unknown: 'border-t-slate-400',
  }

  return (
    <div
      onClick={onClick}
      className={`bg-white border border-slate-200 border-t-4 ${borderColors[policy.status]} rounded-xl p-5 hover:shadow-lg hover:-translate-y-0.5 transition-all cursor-pointer group`}
    >
      <div className="flex items-start justify-between mb-3">
        <div className="text-3xl">{policy.emoji}</div>
        <StatusPill status={policy.status} />
      </div>
      <h3 className="font-black text-slate-900 text-base mb-1 group-hover:text-blue-600 transition-colors">{policy.name}</h3>
      <p className="text-slate-500 text-xs leading-relaxed mb-4 line-clamp-2">{policy.desc}</p>

      <div className="flex items-center justify-between mb-4">
        <div className="bg-blue-50 rounded-lg px-3 py-2">
          <div className="text-[10px] text-blue-500 font-black mb-0.5">혜택</div>
          <div className="text-blue-800 font-black text-sm">{policy.benefit}</div>
        </div>
        <div className="text-right">
          <div className="text-[10px] text-slate-400 font-bold">지역</div>
          <div className="font-bold text-slate-700 text-sm">{policy.region}</div>
        </div>
      </div>

      <div className="flex items-center gap-2">
        <div className="flex-1 h-1.5 bg-slate-100 rounded-full overflow-hidden">
          <div
            className={`h-full rounded-full ${policy.status === 'eligible' ? 'bg-emerald-500' : policy.status === 'potential' ? 'bg-blue-500' : 'bg-orange-500'}`}
            style={{ width: `${(eligible / total) * 100}%` }}
          />
        </div>
        <span className="text-xs text-slate-500 font-bold whitespace-nowrap">{eligible}/{total} 충족</span>
      </div>
    </div>
  )
}
