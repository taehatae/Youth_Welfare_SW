import type { Page } from '../../types/page'
import type { WelfareAnalysis } from '../../types/welfareApi'

export default function ResultPage({ analysis, setPage }: { analysis: WelfareAnalysis | null; setPage: (page: Page) => void }) {
  if (!analysis) {
    return (
      <section className="mx-auto max-w-3xl px-4 py-20 text-center">
        <div className="text-5xl mb-5">🧭</div>
        <h1 className="text-2xl font-black text-slate-900">아직 진단 결과가 없어요</h1>
        <p className="mt-3 text-sm text-slate-500">프로필을 입력하면 받을 수 있는 복지와 자격을 갖추는 방법을 함께 찾아드려요.</p>
        <button onClick={() => setPage('diagnosis')} className="mt-7 rounded-xl border-2 border-slate-900 bg-blue-600 px-6 py-3 font-black text-white shadow-[3px_3px_0px_#0A0F1E]">내 자격 진단하기 →</button>
      </section>
    )
  }

  const policies = analysis.matched.policies ?? []
  const recommendations = analysis.reverse.recommendations ?? []
  const conditionAnalyses = (analysis.matched.analysis_results ?? []).filter(
    policy => policy.gap_conditions.length > 0 || policy.review_conditions.length > 0,
  )

  return (
    <div className="pb-20 md:pb-0">
      <header className="border-b-2 border-slate-800 bg-slate-900 px-4 py-10 text-white sm:px-6">
        <div className="mx-auto max-w-5xl">
          <div className="mb-2 text-xs font-black tracking-widest text-emerald-400">맞춤 복지 분석 완료</div>
          <h1 className="text-3xl font-black">내 프로필로 찾은 결과</h1>
          <p className="mt-2 text-sm text-slate-400">프로필과 비교한 조건 및 추가 확인 항목을 살펴보세요.</p>
          <div className="mt-7 grid max-w-lg grid-cols-2 gap-3">
            <div className="rounded-xl bg-emerald-500 p-4"><div className="text-xs font-bold text-white/80">맞춤 정책</div><div className="mt-1 text-3xl font-black">{analysis.matched.matched_count ?? policies.length}<span className="ml-1 text-base">개</span></div></div>
            <div className="rounded-xl bg-orange-500 p-4"><div className="text-xs font-bold text-white/80">역설계 추천</div><div className="mt-1 text-2xl font-black">{recommendations.length > 0 ? `${recommendations.length}개` : '미구현'}</div></div>
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-5xl space-y-10 px-4 py-8 sm:px-6">
        <section aria-labelledby="matched-heading">
          <div className="mb-4 flex items-end justify-between gap-3">
            <div><p className="text-xs font-black tracking-widest text-blue-600">MATCHED BENEFITS</p><h2 id="matched-heading" className="mt-1 text-xl font-black text-slate-900">지금 신청 가능성이 있는 정책</h2></div>
            <span className="text-xs font-bold text-slate-500">점수는 참고용이에요</span>
          </div>
          {policies.length === 0 ? (
            <div className="rounded-2xl border-2 border-dashed border-slate-300 p-8 text-center text-sm text-slate-500">조건에 맞는 정책이 아직 없어요. 아래 자격 개선 가이드도 확인해보세요.</div>
          ) : (
            <ul className="grid gap-4 md:grid-cols-2">
              {policies.map(policy => (
                <li key={policy.policy_id} className="rounded-2xl border-2 border-slate-200 bg-white p-5">
                  <div className="flex items-start justify-between gap-3">
                    <div><span className="rounded-full bg-blue-50 px-2.5 py-1 text-[11px] font-black text-blue-700">{policy.category}</span><h3 className="mt-3 text-lg font-black text-slate-900">{policy.title}</h3></div>
                    <div className="shrink-0 rounded-xl bg-emerald-50 px-3 py-2 text-center"><div className="text-xl font-black text-emerald-700">{policy.match_score}<span className="text-xs">점</span></div><div className="text-[10px] font-bold text-emerald-700">매칭</div></div>
                  </div>
                  <p className="mt-4 border-t border-slate-100 pt-3 text-sm font-bold text-slate-600">지원 내용 <span className="ml-2 text-slate-900">{policy.support_amount}</span></p>
                </li>
              ))}
            </ul>
          )}
        </section>

        <section aria-labelledby="conditions-heading">
          <div className="mb-4">
            <p className="text-xs font-black tracking-widest text-orange-600">ELIGIBILITY REVIEW</p>
            <h2 id="conditions-heading" className="mt-1 text-xl font-black text-slate-900">미충족 또는 추가 확인이 필요한 조건</h2>
            <p className="mt-1 text-sm text-slate-500">자동 비교 결과는 사전 안내이며, 최종 자격은 담당 기관에 확인하세요.</p>
          </div>
          {conditionAnalyses.length === 0 ? (
            <div className="rounded-2xl border-2 border-dashed border-slate-300 p-8 text-center text-sm text-slate-500">표시할 미충족 또는 추가 확인 조건이 없습니다.</div>
          ) : (
            <ul className="space-y-4">
              {conditionAnalyses.map(policy => (
                <li key={policy.policy_id} className="rounded-2xl border-2 border-slate-200 bg-white p-5">
                  <h3 className="mb-4 font-black text-slate-900">{policy.title}</h3>
                  <div className="space-y-3">
                    {[...policy.gap_conditions, ...policy.review_conditions].map((condition, index) => (
                      <div key={`${condition.condition_type}-${index}`} className="rounded-xl bg-slate-50 p-4">
                        <div className="text-xs font-black text-slate-500">{condition.condition_type}{condition.status === 'needs_review' ? ' · 추가 확인' : ' · 미충족'}</div>
                        <p className="mt-2 text-sm font-bold text-slate-800">{condition.message}</p>
                        <div className="mt-2 flex flex-wrap items-center gap-2 text-sm">
                          <span className="rounded-lg bg-white px-3 py-2 font-bold text-slate-600">현재: {condition.current_value}</span>
                          <span aria-hidden="true" className="font-black text-orange-500">→</span>
                          <span className="rounded-lg bg-orange-100 px-3 py-2 font-black text-orange-800">기준: {condition.required_value}</span>
                        </div>
                        <p className="mt-3 text-sm leading-relaxed text-slate-700"><span className="font-black">확인 안내</span> · {condition.action_guide}</p>
                      </div>
                    ))}
                  </div>
                </li>
              ))}
            </ul>
          )}
        </section>

        <section aria-labelledby="reverse-heading">
          <div className="mb-4"><p className="text-xs font-black tracking-widest text-orange-600">QUALIFICATION PATH</p><h2 id="reverse-heading" className="mt-1 text-xl font-black text-slate-900">역설계 자격 개선 추천</h2><p className="mt-1 text-sm text-slate-500">추천 계산 기능은 현재 준비 중입니다.</p></div>
          {recommendations.length === 0 ? (
            <div className="rounded-2xl border-2 border-dashed border-slate-300 p-8 text-center text-sm text-slate-500">역설계 추천 로직은 아직 구현되지 않았습니다. 현재는 조건 개선 추천을 제공하지 않습니다.</div>
          ) : (
            <ul className="space-y-4">
              {recommendations.map((recommendation, index) => (
                <li key={`${recommendation.target_policy}-${index}`} className="overflow-hidden rounded-2xl border-2 border-slate-200 bg-white">
                  <div className="flex flex-wrap items-center justify-between gap-2 border-b border-orange-100 bg-orange-50 px-5 py-4">
                    <h3 className="font-black text-slate-900">{recommendation.target_policy}</h3>
                    <span className={`rounded-full px-3 py-1 text-xs font-black ${recommendation.current_eligibility ? 'bg-emerald-100 text-emerald-700' : 'bg-orange-100 text-orange-700'}`}>{recommendation.current_eligibility ? '현재 신청 가능' : '조건 개선 필요'}</span>
                  </div>
                  <div className="space-y-3 p-5">
                    {(recommendation.missing_conditions ?? []).map((condition, conditionIndex) => (
                      <div key={`${condition.field}-${conditionIndex}`} className="rounded-xl bg-slate-50 p-4">
                        <div className="text-xs font-black text-slate-500">{condition.field}</div>
                        <div className="mt-2 flex flex-wrap items-center gap-2 text-sm"><span className="rounded-lg bg-white px-3 py-2 font-bold text-slate-600">현재: {condition.current_value}</span><span aria-hidden="true" className="font-black text-orange-500">→</span><span className="rounded-lg bg-orange-100 px-3 py-2 font-black text-orange-800">필요: {condition.required_value}</span></div>
                        <p className="mt-3 text-sm leading-relaxed text-slate-700"><span className="font-black">다음 행동</span> · {condition.action_guide}</p>
                      </div>
                    ))}
                    {recommendation.missing_conditions.length === 0 && <p className="text-sm text-slate-500">추가로 충족해야 할 조건이 없습니다.</p>}
                  </div>
                </li>
              ))}
            </ul>
          )}
        </section>

        <div className="flex flex-wrap gap-3 border-t border-slate-200 pt-6">
          <button onClick={() => setPage('diagnosis')} className="rounded-xl border-2 border-slate-900 px-5 py-3 text-sm font-black text-slate-900 hover:bg-slate-50">프로필 다시 입력</button>
          <button onClick={() => setPage('explorer')} className="rounded-xl border-2 border-slate-900 bg-blue-600 px-5 py-3 text-sm font-black text-white shadow-[3px_3px_0px_#0A0F1E]">정책 더 찾아보기 →</button>
        </div>
      </main>
    </div>
  )
}
