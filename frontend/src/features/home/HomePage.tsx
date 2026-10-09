import type { Page } from '../../types/page'
import type { Policy } from '../../types/policy'
import { POLICIES } from '../../data/policies'
import { LogoMark } from '../../components/brand/LogoMark'
import PolicyCard from '../../components/policy/PolicyCard'
import Ticker from './Ticker'

export default function HomePage({ setPage, setSelectedPolicy }: { setPage: (p: Page) => void; setSelectedPolicy: (p: Policy) => void }) {
  return (
    <div className="pb-20 md:pb-0">
      <Ticker />

      {/* ── Hero ── */}
      <section className="relative overflow-hidden">
        {/* Big bg number */}
        <div className="absolute right-0 top-0 text-[28vw] font-black text-slate-50 leading-none select-none pointer-events-none z-0 -translate-y-4">
          청
        </div>

        <div className="relative z-10 max-w-6xl mx-auto px-4 sm:px-6 pt-14 pb-10">
          <div className="grid md:grid-cols-2 gap-10 items-start">
            {/* Left */}
            <div>
              <div className="inline-flex items-center gap-2 bg-emerald-400 text-slate-900 text-xs font-black px-3 py-1.5 rounded-full mb-6">
                <span>✦</span> 청년 복지 자격 진단 플랫폼
              </div>

              <h1 className="text-5xl sm:text-6xl font-black text-slate-900 leading-[1.05] tracking-tight mb-6">
                내가 받을 수<br/>
                있는 복지,<br/>
                <span className="text-blue-600">지금 확인</span>하세요.
              </h1>

              <p className="text-slate-500 text-base leading-relaxed mb-8 max-w-md">
                복잡한 자격조건을 분석해서<br/>
                <strong className="text-slate-800">내가 부족한 조건</strong>과 <strong className="text-slate-800">필요한 행동</strong>까지 알려드립니다.
              </p>

              <div className="flex flex-wrap gap-3">
                <button
                  onClick={() => setPage('diagnosis')}
                  className="bg-blue-600 text-white font-black px-7 py-4 rounded-xl hover:bg-blue-700 transition-all text-base shadow-lg shadow-blue-200 hover:shadow-blue-300"
                >
                  내 자격 진단하기 →
                </button>
                <button
                  onClick={() => setPage('explorer')}
                  className="bg-white text-slate-900 font-black px-7 py-4 rounded-xl border-2 border-slate-900 hover:bg-slate-900 hover:text-white transition-all text-base"
                >
                  정책 찾아보기
                </button>
              </div>

              {/* Mini stats */}
              <div className="flex gap-6 mt-10 pt-8 border-t border-slate-100">
                {[['1,200+', '등록 정책'], ['47만+', '진단 건수'], ['89%', '정확도']].map(([n, l]) => (
                  <div key={l}>
                    <div className="text-2xl font-black text-slate-900">{n}</div>
                    <div className="text-xs text-slate-500 font-medium">{l}</div>
                  </div>
                ))}
              </div>
            </div>

            {/* Right: floating card cluster */}
            <div className="hidden md:block relative h-[420px]">
              {/* Center card */}
              <div className="absolute top-10 left-8 right-8 bg-white border-2 border-slate-900 rounded-2xl p-5 shadow-[4px_4px_0px_#0A0F1E]">
                <div className="flex items-center justify-between mb-4">
                  <div className="font-black text-slate-900">청년 내일채움공제</div>
                  <span className="bg-emerald-400 text-slate-900 text-xs font-black px-2 py-0.5 rounded-full">신청 가능</span>
                </div>
                <div className="space-y-2">
                  {[
                    { label: '연령', val: '27세 ✓', ok: true },
                    { label: '취업상태', val: '중소기업 재직 ✓', ok: true },
                    { label: '소득', val: '280만원 ✓', ok: true },
                  ].map(r => (
                    <div key={r.label} className="flex justify-between text-sm">
                      <span className="text-slate-500">{r.label}</span>
                      <span className={r.ok ? 'text-emerald-600 font-bold' : 'text-orange-600 font-bold'}>{r.val}</span>
                    </div>
                  ))}
                </div>
                <div className="mt-4 pt-3 border-t border-slate-100 flex items-center justify-between">
                  <span className="text-slate-500 text-xs">혜택</span>
                  <span className="font-black text-blue-600 text-lg">최대 1,200만원</span>
                </div>
              </div>

              {/* Delta badge */}
              <div className="absolute top-2 right-2 bg-orange-400 text-white font-black text-xs px-3 py-2 rounded-xl shadow-[2px_2px_0px_#0A0F1E] border border-slate-900 animate-float">
                △ 소득 조건 1개<br/>부족해요
              </div>

              {/* Bottom card */}
              <div className="absolute bottom-8 left-4 right-20 bg-slate-900 text-white rounded-2xl p-4 shadow-[4px_4px_0px_#1D4ED8]">
                <div className="text-slate-400 text-xs font-bold mb-1">나의 자격 달성도</div>
                <div className="flex items-center gap-3">
                  <div className="text-3xl font-black">3/6</div>
                  <div className="flex-1 space-y-1">
                    <div className="h-2 bg-slate-700 rounded-full overflow-hidden">
                      <div className="h-full bg-emerald-400 rounded-full" style={{ width: '50%' }} />
                    </div>
                    <div className="text-slate-400 text-xs">정책 신청 가능</div>
                  </div>
                </div>
              </div>

              {/* Sprout accent */}
              <div className="absolute bottom-4 right-4 text-4xl animate-float-delay">🌱</div>
            </div>
          </div>
        </div>
      </section>

      {/* ── How it works ── */}
      <section className="bg-slate-900 py-16 overflow-hidden">
        <div className="max-w-6xl mx-auto px-4 sm:px-6">
          <div className="flex items-end justify-between mb-10">
            <div>
              <div className="text-emerald-400 text-xs font-black tracking-widest mb-2">HOW IT WORKS</div>
              <h2 className="text-3xl font-black text-white leading-tight">진단부터 행동가이드까지,<br/>한 번에 끝납니다</h2>
            </div>
          </div>

          <div className="grid md:grid-cols-5 gap-3">
            {[
              { n: '01', icon: '📄', title: '정책 분석', desc: '자격조건 구조화', bg: 'bg-slate-800 border-slate-700' },
              { n: '02', icon: '📝', title: '내 정보 입력', desc: '5분이면 충분', bg: 'bg-slate-800 border-slate-700' },
              { n: '03', icon: '⚖️', title: '조건 비교', desc: '정확한 대조', bg: 'bg-blue-600 border-blue-500' },
              { n: '04', icon: '△', title: 'Delta 분석', desc: '부족한 조건 파악', bg: 'bg-orange-500 border-orange-400' },
              { n: '05', icon: '✓', title: '행동 가이드', desc: '다음 단계 제시', bg: 'bg-emerald-500 border-emerald-400' },
            ].map((s, i) => (
              <div key={i} className={`${s.bg} border rounded-2xl p-4 relative`}>
                <div className="text-slate-500 text-xs font-black mb-3">{s.n}</div>
                <div className="text-2xl mb-2">{s.icon}</div>
                <div className="text-white font-black text-sm">{s.title}</div>
                <div className="text-slate-300 text-xs mt-0.5">{s.desc}</div>
                {i < 4 && (
                  <div className="hidden md:block absolute -right-2 top-1/2 -translate-y-1/2 z-10 text-slate-600 font-bold text-lg">→</div>
                )}
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ── Eligible policies ── */}
      <section className="py-16">
        <div className="max-w-6xl mx-auto px-4 sm:px-6">
          <div className="flex items-end justify-between mb-8">
            <div>
              <div className="text-blue-600 text-xs font-black tracking-widest mb-2">지금 신청 가능</div>
              <h2 className="text-3xl font-black text-slate-900">바로 신청할 수<br/>있는 정책들</h2>
            </div>
            <button onClick={() => setPage('explorer')} className="text-sm font-black text-slate-600 border-2 border-slate-900 px-4 py-2 rounded-lg hover:bg-slate-900 hover:text-white transition-colors">
              전체 보기 →
            </button>
          </div>

          <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-5">
            {POLICIES.filter(p => p.status === 'eligible').map(p => (
              <PolicyCard key={p.id} policy={p} onClick={() => { setSelectedPolicy(p); setPage('detail') }} />
            ))}
          </div>
        </div>
      </section>

      {/* ── CTA ── */}
      <section className="py-12 px-4 sm:px-6">
        <div className="max-w-6xl mx-auto">
          <div className="bg-blue-600 rounded-2xl border-2 border-slate-900 shadow-[6px_6px_0px_#0A0F1E] p-8 sm:p-12 flex flex-col md:flex-row items-center justify-between gap-6">
            <div>
              <div className="text-blue-200 text-xs font-black tracking-widest mb-2">오늘의 진단이, 내일의 기회가 됩니다</div>
              <h2 className="text-2xl sm:text-3xl font-black text-white leading-tight">
                지금 내 자격을 확인하면<br/>놓치는 혜택이 없어요
              </h2>
            </div>
            <button
              onClick={() => setPage('diagnosis')}
              className="flex-shrink-0 bg-emerald-400 text-slate-900 font-black px-8 py-4 rounded-xl hover:bg-emerald-300 transition-colors text-base border-2 border-slate-900 shadow-[3px_3px_0px_#0A0F1E]"
            >
              무료 진단 시작하기 →
            </button>
          </div>
        </div>
      </section>
    </div>
  )
}
