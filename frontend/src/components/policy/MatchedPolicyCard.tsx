import type { MatchedPolicy } from "../../types/welfareApi"
import {
  applicationLabels,
  applicationState,
  safeOfficialUrl,
} from "../../services/analysisSession"
export default function MatchedPolicyCard({
  policy,
  date,
  isNew = false,
}: {
  policy: MatchedPolicy
  date: string
  isNew?: boolean
}) {
  const status = applicationState(policy, date)
  const url = safeOfficialUrl(policy.detail_url)
  return (
    <article data-status={status} className="interface-policy-card bg-white p-5">
      <div className="flex flex-wrap items-center gap-2 text-xs font-semibold">
        <span className="text-blue-700">{policy.category}</span>
        <span
          className={
            status === "expired"
              ? "rounded bg-slate-100 px-2 py-1 text-slate-600"
              : "rounded bg-blue-50 px-2 py-1 text-blue-800"
          }
        >
          {applicationLabels[status]}
        </span>
        {isNew && (
          <span className="rounded bg-teal-50 px-2 py-1 text-emerald-800">
            이번 조회에 추가
          </span>
        )}
      </div>
      <h3 className="mt-3 text-lg font-semibold text-slate-900">
        {policy.title}
      </h3>
      <p className="mt-3 text-sm text-slate-700">
        {policy.support_amount || "지원 내용 확인 필요"}
      </p>
      <p className="mt-3 text-sm text-slate-500">
        {policy.application_period_type === "ALWAYS"
          ? "상시 접수"
          : (policy.application_start_date || "시작일 미제공") +
            " ~ " +
            (policy.application_end_date || "마감일 미제공")}
      </p>
      {url ? (
        <a
          href={url}
          target="_blank"
          rel="noopener noreferrer"
          className="mt-4 inline-block text-sm font-semibold text-blue-700 underline underline-offset-4"
        >
          공식 공고 확인 ↗<span className="sr-only"> (새 탭)</span>
        </a>
      ) : (
        <p className="mt-4 text-sm text-slate-500">
          공식 공고 링크가 아직 제공되지 않았어요.
        </p>
      )}
    </article>
  )
}
