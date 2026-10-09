export default function Ticker() {
  const items = ['청년 월세 지원 — 월 최대 20만원', '청년 도약 계좌 — 최대 5,000만원', '청년 내일채움공제 — 최대 1,200만원', '청년 마음건강 지원 — 100만원 상담권', '청년 전세임대 — 보증금 최대 1.2억', '국민취업지원제도 — 월 50만원×6개월']
  const doubled = [...items, ...items]
  return (
    <div className="bg-slate-900 py-2.5 overflow-hidden border-b border-slate-800">
      <div className="flex items-center gap-8 animate-marquee whitespace-nowrap">
        {doubled.map((item, i) => (
          <span key={i} className="flex items-center gap-3 text-xs font-bold text-slate-300 flex-shrink-0">
            <span className="text-emerald-400">✦</span>
            {item}
          </span>
        ))}
      </div>
    </div>
  )
}
