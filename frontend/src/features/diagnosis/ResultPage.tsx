import PageHeading from "../../components/layout/PageHeading"
import type { Page } from "../../types/page"

import {
  formatTime,
  koreaDate,
  type Snapshot,
} from "../../services/analysisSession"

import MatchedPolicyCard from "../../components/policy/MatchedPolicyCard"

export default function ResultPage({
  snapshot,
  setPage,
}: {
  snapshot: Snapshot | null
  setPage: (page: Page) => void
}) {
  const analysis = snapshot?.analysis

  if (!analysis) {
    return (
      <section className="mx-auto max-w-5xl px-4 py-8 sm:px-6">
        <PageHeading eyebrow="진단 시점의 가능성을 기록해요" title="진단 결과" description="내 조건에 맞는 정책과 아직 부족한 조건을 함께 확인하는 공간이에요." />
        <div className="interface-empty"><span className="interface-empty-icon" aria-hidden="true">✓</span><h2>아직 진단 결과가 없어요</h2><p>나이와 거주지부터 차근차근 선택해주세요. 진단을 마치면 맞춤 정책과 추가 확인이 필요한 조건을 보여드릴게요.</p><button onClick={() => setPage("diagnosis")} className="interface-primary">내 자격 진단하기 →</button></div>
      </section>
    )
  }

  const policies = analysis.matched.policies ?? []

  const recommendations = analysis.reverse.recommendations ?? []

  const conditionAnalyses = (analysis.matched.analysis_results ?? []).filter(
    (policy) =>
      policy.gap_conditions.length > 0 || policy.review_conditions.length > 0,
  )

  return (
    <div className="pb-20 md:pb-0">
      <div className="mx-auto max-w-5xl px-4 pt-8 sm:px-6">
        <PageHeading eyebrow="진단 시점의 가능성을 기록해요" title="내 프로필로 찾은 결과" description={(snapshot ? formatTime(snapshot.checkedAt) : '') + ' 진단 기록입니다. 이후 신청 기간과 정책 변화는 나의 현황에서 확인해주세요.'}>
          <div className="interface-metrics grid max-w-lg grid-cols-2 gap-3">
            <div className="p-4"><p className="text-sm text-teal-800">맞춤 정책</p><p className="mt-1 text-3xl font-bold">{policies.length}<span className="ml-1 text-sm font-normal">개</span></p></div>
            <div className="p-4"><p className="text-sm text-blue-800">역설계 추천</p><p className="mt-1 text-3xl font-bold">{recommendations.length}<span className="ml-1 text-sm font-normal">개</span></p></div>
          </div>
        </PageHeading>
      </div>

      <div className="mx-auto max-w-5xl space-y-10 px-4 py-8 sm:px-6">
        <button
          onClick={() => setPage("dashboard")}
          className="interface-primary"
        >
          나의 현황에서 최신 정책 조회 →
        </button>
        <section className="interface-result-block" aria-labelledby="matched-heading">
          <div className="mb-4 flex items-end justify-between gap-3">
            <div>
              <h2
                id="matched-heading"
                className="mt-1 text-xl font-bold text-slate-900"
              >
                진단 당시 조건에 맞는 정책
              </h2>
            </div>
          </div>
          {policies.length === 0 ? (
            <div className="rounded-2xl border border-dashed border-slate-300 p-8 text-center text-sm text-slate-500">
              조건에 맞는 정책이 아직 없어요. 아래 자격 개선 가이드도
              확인해보세요.
            </div>
          ) : (
            <ul className="grid gap-4 md:grid-cols-2">
              {policies.map((policy) => (
                <li key={policy.policy_id}>
                  <MatchedPolicyCard
                    policy={{
                      ...policy,
                      detail_url:
                        policy.detail_url ||
                        analysis.matched.analysis_results?.find(
                          (p) => p.policy_id === policy.policy_id,
                        )?.detail_url,
                    }}
                    date={koreaDate(new Date(snapshot!.checkedAt))}
                  />
                </li>
              ))}
            </ul>
          )}
        </section>

        <section className="interface-result-block" aria-labelledby="conditions-heading">
          <div className="mb-4">
            <p className="text-xs font-semibold tracking-widest text-orange-600">
              조건별 확인
            </p>
            <h2
              id="conditions-heading"
              className="mt-1 text-xl font-semibold text-slate-900"
            >
              미충족 또는 추가 확인이 필요한 조건
            </h2>
            <p className="mt-1 text-sm text-slate-500">
              자동 비교 결과는 사전 안내이며, 최종 자격은 담당 기관에
              확인하세요.
            </p>
          </div>
          {conditionAnalyses.length === 0 ? (
            <div className="rounded-2xl border border-dashed border-slate-300 p-8 text-center text-sm text-slate-500">
              표시할 미충족 또는 추가 확인 조건이 없습니다.
            </div>
          ) : (
            <ul className="space-y-4">
              {conditionAnalyses.map((policy) => (
                <li
                  key={policy.policy_id}
                  className="rounded-2xl border border-slate-200 bg-white p-5"
                >
                  <h3 className="mb-4 font-semibold text-slate-900">
                    {policy.title}
                  </h3>
                  <div className="space-y-3">
                    {[
                      ...policy.gap_conditions,
                      ...policy.review_conditions,
                    ].map((condition, index) => (
                      <div
                        key={`${condition.condition_type}-${index}`}
                        className="rounded-xl bg-slate-50 p-4"
                      >
                        <div className="text-xs font-semibold text-slate-500">
                          {condition.condition_type}
                          {condition.status === "needs_review"
                            ? " · 추가 확인"
                            : " · 미충족"}
                        </div>
                        <p className="mt-2 text-sm font-bold text-slate-800">
                          {condition.message}
                        </p>
                        <div className="mt-2 flex flex-wrap items-center gap-2 text-sm">
                          <span className="rounded-lg bg-white px-3 py-2 font-bold text-slate-600">
                            현재: {condition.current_value}
                          </span>
                          <span
                            aria-hidden="true"
                            className="font-semibold text-orange-500"
                          >
                            →
                          </span>
                          <span className="rounded-lg bg-orange-100 px-3 py-2 font-semibold text-orange-800">
                            기준: {condition.required_value}
                          </span>
                        </div>
                        <p className="mt-3 text-sm leading-relaxed text-slate-700">
                          <span className="font-semibold">확인 안내</span> ·{" "}
                          {condition.action_guide}
                        </p>
                      </div>
                    ))}
                  </div>
                </li>
              ))}
            </ul>
          )}
        </section>

        <section className="interface-result-block" aria-labelledby="reverse-heading">
          <div className="mb-4">
            <p className="text-xs font-semibold tracking-widest text-orange-600">
              조건을 바꾸면 생기는 기회
            </p>
            <h2
              id="reverse-heading"
              className="mt-1 text-xl font-semibold text-slate-900"
            >
              역설계 자격 개선 추천
            </h2>
            <p className="mt-1 text-sm text-slate-500">
              조건을 바꾸었을 때 검토할 수 있는 정책과 필요한 행동입니다.
            </p>
          </div>
          {recommendations.length === 0 ? (
            <div className="rounded-2xl border border-dashed border-slate-300 p-8 text-center text-sm text-slate-500">
              서버에서 제공된 역설계 추천이 없습니다. 추천 기능 제공 여부와 정책
              조건에 따라 달라질 수 있어요.
            </div>
          ) : (
            <ul className="space-y-4">
              {recommendations.map((recommendation, index) => (
                <li
                  key={`${recommendation.target_policy}-${index}`}
                  className="overflow-hidden rounded-2xl border border-slate-200 bg-white"
                >
                  <div className="flex flex-wrap items-center justify-between gap-2 border-b border-orange-100 bg-orange-50 px-5 py-4">
                    <h3 className="font-semibold text-slate-900">
                      {recommendation.target_policy}
                    </h3>
                    <span
                      className={`rounded-full px-3 py-1 text-xs font-semibold ${
                        recommendation.current_eligibility
                          ? "bg-emerald-100 text-teal-800"
                          : "bg-orange-100 text-orange-700"
                      }`}
                    >
                      {recommendation.current_eligibility
                        ? "현재 조건 충족"
                        : "조건 개선 필요"}
                    </span>
                  </div>
                  <div className="space-y-3 p-5">
                    {(recommendation.missing_conditions ?? []).map(
                      (condition, conditionIndex) => (
                        <div
                          key={`${({ employment_status: "고용 상태", income_level: "소득", region: "거주 지역", age: "나이" } as Record<string, string>)[condition.field] ?? condition.field}-${conditionIndex}`}
                          className="rounded-xl bg-slate-50 p-4"
                        >
                          <div className="text-xs font-semibold text-slate-500">
                            {({
                              employment_status: "고용 상태",
                              income_level: "소득",
                              region: "거주 지역",
                              age: "나이",
                            } as Record<string, string>)[condition.field] ??
                              condition.field}
                          </div>
                          <div className="mt-2 flex flex-wrap items-center gap-2 text-sm">
                            <span className="rounded-lg bg-white px-3 py-2 font-bold text-slate-600">
                              현재: {condition.current_value}
                            </span>
                            <span
                              aria-hidden="true"
                              className="font-semibold text-orange-500"
                            >
                              →
                            </span>
                            <span className="rounded-lg bg-orange-100 px-3 py-2 font-semibold text-orange-800">
                              필요: {condition.required_value}
                            </span>
                          </div>
                          <p className="mt-3 text-sm leading-relaxed text-slate-700">
                            <span className="font-semibold">다음 행동</span> ·{" "}
                            {condition.action_guide}
                          </p>
                        </div>
                      ),
                    )}
                    {recommendation.missing_conditions.length === 0 && (
                      <p className="text-sm text-slate-500">
                        추가로 충족해야 할 조건이 없습니다.
                      </p>
                    )}
                  </div>
                </li>
              ))}
            </ul>
          )}
        </section>

        <div className="flex flex-wrap gap-3 border-t border-slate-200 pt-6">
          <button
            onClick={() => setPage("diagnosis")}
            className="rounded-xl border-2 border-slate-900 px-5 py-3 text-sm font-semibold text-slate-900 hover:bg-slate-50"
          >
            내 정보 수정 후 재진단
          </button>
          <button
            onClick={() => setPage("explorer")}
            className="rounded-xl border-2 border-slate-900 bg-blue-600 px-5 py-3 text-sm font-semibold text-white shadow-[2px_2px_0px_#14213b]"
          >
            정책 더 찾아보기 →
          </button>
        </div>
      </div>
    </div>
  )
}
