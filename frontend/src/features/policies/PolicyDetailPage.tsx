import PageHeading from "../../components/layout/PageHeading"
import { safeOfficialUrl } from "../../services/analysisSession"

import type { Page } from "../../types/page"

import type { Policy } from "../../types/policy"

import { ConditionRow } from "../../components/policy/PolicyStatus"

export default function PolicyDetailPage({
  policy,
  setPage,
}: {
  policy: Policy
  setPage: (p: Page) => void
}) {
  const officialUrl = safeOfficialUrl(policy.detailUrl)

  const eligible = policy.conditions.filter(
    (c) => c.result === "eligible",
  ).length

  const total = policy.conditions.length

  const missing = policy.conditions.filter((c) => c.result === "ineligible")

  return (
    <div className="pb-20 md:pb-0">
      <div className="max-w-4xl mx-auto px-4 sm:px-6 pt-8">
        <button onClick={() => setPage("explorer")} className="mb-4 text-sm font-semibold text-blue-700">← 정책 목록으로</button>
        <PageHeading eyebrow={policy.category + ' · 정책 상세'} title={policy.name} description={policy.desc}>
          <span className="inline-block rounded-md border border-blue-200 bg-white px-3 py-2 text-xs text-slate-600">설명용 예시 · 내 진단 결과 아님</span>
        </PageHeading>
      </div>

      <div className="max-w-4xl mx-auto px-4 sm:px-6 py-8 space-y-5">
        {/* Benefit + info */}
        <div className="grid sm:grid-cols-3 gap-4">
          <div className="sm:col-span-1 bg-[#14213b] text-white rounded-xl border border-slate-900 shadow-[3px_3px_0px_#cfddf4] p-5">
            <div className="text-slate-400 text-xs font-semibold mb-1">혜택</div>
            <div className="text-2xl font-semibold">{policy.benefit}</div>
          </div>
          <div className="interface-panel p-5">
            <div className="text-slate-500 text-xs font-semibold mb-1">
              신청기간
            </div>
            <div className="font-semibold text-slate-900 text-sm">
              {policy.period}
            </div>
          </div>
          <div className="interface-panel p-5">
            <div className="text-slate-500 text-xs font-semibold mb-1">
              지역 · 대상
            </div>
            <div className="font-semibold text-slate-900 text-sm">
              {policy.region} · {policy.target}
            </div>
          </div>
        </div>

        {/* Eligibility */}
        <div className="interface-panel p-6">
          <div className="flex items-center justify-between mb-5">
            <h2 className="font-semibold text-slate-900 text-lg">자격조건 분석</h2>
            <div className="flex items-center gap-2">
              <div className="text-sm font-semibold text-slate-700">
                {eligible}/{total} 충족
              </div>
              <div className="w-24 h-2.5 bg-slate-100 rounded-full overflow-hidden border border-slate-200">
                <div
                  className={`h-full rounded-full ${
                    policy.status === "eligible"
                      ? "bg-teal-700"
                      : policy.status === "ineligible"
                        ? "bg-amber-700"
                        : "bg-blue-500"
                  }`}
                  style={{ width: `${total ? (eligible / total) * 100 : 0}%` }}
                />
              </div>
            </div>
          </div>
          <div className="space-y-2.5">
            {policy.conditions.map((c, i) => (
              <ConditionRow key={i} c={c} />
            ))}
          </div>
        </div>

        {/* Delta / action guide if missing */}
        {missing.length > 0 && (
          <div className="bg-amber-50 border border-amber-200 rounded-xl p-6">
            <div className="flex items-center gap-2 mb-4">
              <span className="text-orange-600 text-xl font-semibold">△</span>
              <h2 className="font-semibold text-orange-900">
                지금 딱 {missing.length}가지 조건이 부족해요
              </h2>
            </div>
            {missing.map((c, i) => (
              <div key={i} className="mb-4">
                <div className="font-semibold text-orange-800 text-sm mb-1">
                  {c.label} 조건
                </div>
                <div className="flex items-center gap-4 text-sm">
                  <div className="flex-1 bg-white rounded-lg border border-orange-200 px-3 py-2">
                    <div className="text-[10px] text-orange-500 font-semibold">
                      정책 기준
                    </div>
                    <div className="font-bold text-slate-800">
                      {c.requirement}
                    </div>
                  </div>
                  <span className="text-orange-400 font-semibold">vs</span>
                  <div className="flex-1 bg-orange-100 rounded-lg border border-orange-200 px-3 py-2">
                    <div className="text-[10px] text-orange-500 font-semibold">
                      나의 상태
                    </div>
                    <div className="font-bold text-orange-800">
                      {c.userValue}
                    </div>
                  </div>
                </div>
              </div>
            ))}
            <div className="mt-4 border-t border-orange-200 pt-4">
              <div className="text-xs font-semibold text-orange-800 mb-2">
                다음에 확인할 것
              </div>
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
            onClick={() => setPage("diagnosis")}
            className="flex-1 bg-blue-600 text-white font-semibold py-4 px-6 rounded-xl hover:bg-blue-700 transition-colors border-2 border-slate-900 shadow-[2px_2px_0px_#14213b] text-center"
          >
            내 조건으로 정밀 진단하기
          </button>
          {officialUrl ? (
            <a
              href={officialUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="rounded-xl border border-slate-300 px-6 py-4 text-center font-semibold text-blue-700"
            >
              공식 공고 확인 ↗ (새 탭)
            </a>
          ) : (
            <p className="rounded-xl bg-slate-50 px-5 py-4 text-sm text-slate-600">
              공식 공고 링크가 없는 예시 정책입니다.
            </p>
          )}
        </div>

        {/* Source */}
        <div className="bg-slate-50 border border-slate-200 rounded-xl p-4 text-xs text-slate-500">
          <div className="font-semibold text-slate-700 mb-1">📌 데이터 출처</div>
          <div className="grid sm:grid-cols-3 gap-1">
            <span>제공: {policy.source}</span>
            <span>설명용 예시 자료</span>
            <span>업데이트: {policy.updated}</span>
          </div>
        </div>
      </div>
    </div>
  )
}
