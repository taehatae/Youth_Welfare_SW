import type { Condition, Policy } from '../../types/policy'

const STATUS_CONFIG = {
  eligible:   { label: '신청 가능',    bg: 'bg-emerald-500', text: 'text-white',        light: 'bg-emerald-50 text-emerald-700 border-emerald-200',   symbol: '✓', dot: '#22C55E' },
  potential:  { label: '확인 필요',    bg: 'bg-blue-500',   text: 'text-white',        light: 'bg-blue-50 text-blue-700 border-blue-200',             symbol: '△', dot: '#3B82F6' },
  ineligible: { label: '조건 미충족', bg: 'bg-orange-500', text: 'text-white',        light: 'bg-orange-50 text-orange-700 border-orange-200',       symbol: '✕', dot: '#F97316' },
  unknown:    { label: '정보 필요',    bg: 'bg-slate-400',  text: 'text-white',        light: 'bg-slate-50 text-slate-600 border-slate-200',          symbol: '?', dot: '#94A3B8' },
}

export function StatusPill({ status }: { status: Policy['status'] }) {
  const s = STATUS_CONFIG[status]
  return (
    <span className={`inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-[11px] font-bold border ${s.light}`}>
      <span className="font-black">{s.symbol}</span> {s.label}
    </span>
  )
}

export function ConditionRow({ c }: { c: Condition }) {
  const colors = {
    eligible:   { bg: 'bg-emerald-50', border: 'border-emerald-200', badge: 'bg-emerald-500 text-white', label: 'text-emerald-700' },
    potential:  { bg: 'bg-blue-50',    border: 'border-blue-200',    badge: 'bg-blue-500 text-white',    label: 'text-blue-700' },
    ineligible: { bg: 'bg-orange-50',  border: 'border-orange-200',  badge: 'bg-orange-500 text-white',  label: 'text-orange-700' },
  }
  const col = colors[c.result]
  return (
    <div className={`flex items-center gap-3 px-4 py-3 rounded-xl border ${col.bg} ${col.border}`}>
      <span className={`w-6 h-6 rounded-full flex items-center justify-center text-xs font-black flex-shrink-0 ${col.badge}`}>
        {c.result === 'eligible' ? '✓' : c.result === 'ineligible' ? '✕' : '△'}
      </span>
      <div className="flex-1 min-w-0">
        <span className="font-bold text-slate-800 text-sm">{c.label}</span>
        <span className="text-slate-400 text-xs ml-2">기준: {c.requirement}</span>
      </div>
      <span className={`text-sm font-bold ${col.label}`}>{c.userValue}</span>
    </div>
  )
}
