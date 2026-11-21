import type { Condition, Policy } from '../../types/policy'

const STATUS_CONFIG = {
  eligible:   { label: '신청 가능',    bg: 'bg-teal-700', text: 'text-white',        light: 'bg-[var(--likely)] text-[var(--likely-ink)] border-transparent',   symbol: '✓', dot: '#22C55E' },
  potential:  { label: '확인 필요',    bg: 'bg-blue-500',   text: 'text-white',        light: 'bg-[var(--review)] text-[var(--review-ink)] border-transparent',             symbol: '△', dot: '#3B82F6' },
  ineligible: { label: '조건 미충족', bg: 'bg-amber-700', text: 'text-white',        light: 'bg-[var(--gap)] text-[var(--gap-ink)] border-transparent',       symbol: '✕', dot: '#F97316' },
  unknown:    { label: '정보 필요',    bg: 'bg-slate-400',  text: 'text-white',        light: 'bg-[var(--bg)] text-[var(--sub)] border-[var(--line)]',          symbol: '?', dot: '#94A3B8' },
}

export function StatusPill({ status }: { status: Policy['status'] }) {
  const s = STATUS_CONFIG[status]
  return (
    <span className={`inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-[12px] font-bold border ${s.light}`}>
      <span className="font-semibold">{s.symbol}</span> {s.label}
    </span>
  )
}

export function ConditionRow({ c }: { c: Condition }) {
  const colors = {
    eligible:   { bg: 'bg-[var(--likely)]', border: 'border-transparent', badge: 'bg-[var(--likely-ink)] text-white', label: 'text-[var(--likely-ink)]' },
    potential:  { bg: 'bg-[var(--review)]', border: 'border-transparent', badge: 'bg-[var(--review-ink)] text-white', label: 'text-[var(--review-ink)]' },
    ineligible: { bg: 'bg-[var(--gap)]', border: 'border-transparent', badge: 'bg-[var(--gap-ink)] text-white', label: 'text-[var(--gap-ink)]' },
  }
  const col = colors[c.result]
  return (
    <div className={`flex items-center gap-3 px-4 py-3 rounded-2xl border ${col.bg} ${col.border}`}>
      <span className={`w-6 h-6 rounded-full flex items-center justify-center text-[13px] font-semibold flex-shrink-0 ${col.badge}`}>
        {c.result === 'eligible' ? '✓' : c.result === 'ineligible' ? '✕' : '△'}
      </span>
      <div className="flex-1 min-w-0">
        <span className="font-bold text-[var(--ink)] text-sm">{c.label}</span>
        <span className="text-[var(--sub)] text-[13px] ml-2">기준: {c.requirement}</span>
      </div>
      <span className={`text-sm font-bold ${col.label}`}>{c.userValue}</span>
    </div>
  )
}
