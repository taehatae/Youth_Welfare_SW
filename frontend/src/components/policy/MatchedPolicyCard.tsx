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
    <article
      data-reveal
      data-status={status}
      className="interface-policy-card bg-white p-5"
    >
      <div className="flex flex-wrap items-center gap-2 text-xs font-semibold">
        <span className="text-[var(--accent-ink)]">{policy.category}</span>
        <span
          className={
            status === "expired"
              ? "rounded-full bg-[var(--bg)] px-2.5 py-1 text-[var(--sub)]"
              : "rounded-full bg-[var(--accent-soft)] px-2.5 py-1 text-[var(--accent-ink)]"
          }
        >
          {applicationLabels[status]}
        </span>
        {isNew && (
          <span className="rounded-full bg-[var(--likely)] px-2.5 py-1 text-[var(--likely-ink)]">
            이번 조회에 추가
          </span>
        )}
      </div>
      <h3 className="mt-3 text-lg font-semibold text-[var(--ink)]">
        {policy.title}
      </h3>
      <p className="mt-3 text-xs leading-relaxed text-[var(--sub)]">
        자동 비교 가능한 조건을 충족한 사전 안내입니다. 최종 수급 여부는 담당
        기관에 확인해 주세요.
      </p>
      <p className="mt-3 text-sm text-[var(--ink)]">
        {policy.support_amount || "지원 내용 확인 필요"}
      </p>
      <p className="mt-3 text-sm text-[var(--sub)]">
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
          className="mt-4 inline-block text-sm font-semibold text-[var(--accent-ink)] underline underline-offset-4"
        >
          정책 확인하러 가기 ↗<span className="sr-only"> (새 탭)</span>
        </a>
      ) : (
        <p className="mt-4 text-sm text-[var(--sub)]">
          공식 공고 링크가 아직 제공되지 않았어요.
        </p>
      )}
    </article>
  )
}
