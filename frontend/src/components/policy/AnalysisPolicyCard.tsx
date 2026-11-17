import { useId, useState } from "react"
import { safeOfficialUrl } from "../../services/analysisSession"
import { conditionStep } from "../../services/profileSummary"
import type { PolicyRow } from "../../services/policyResults"
import { samePolicyText, stateChangeGuide, guideTargetKey, gapKey, otherPathDetails, pathCards, type GuideLine, type PathCard, type PathTab } from "../../services/conditionGuidance"
import PersonalizedGuideAccess from "./PersonalizedGuideAccess"
import DifficultySettings from "./DifficultySettings"
import { useDifficultyPrefs } from "../../services/difficultyPrefs"
import type { ConditionGuideTarget } from "../../types/welfareApi"

export const statusLabels = {
  eligible: "자동 비교상 충족",
  ineligible: "미충족 조건 있음",
  needs_review: "추가 확인 필요",
}
// 신청 가능 여부는 사용자가 입력한 값과 비교한 조건만으로 판단한다.
// 입력값으로 비교할 수 없는 조건은 판정에 쓰지 않고 '추가 확인'으로만 안내한다.
export const resultCategoryLabels = {
  likely: "신청 가능",
  review: "확인 필요",
  gap: "신청 불가",
} as const
export type ResultCategory = keyof typeof resultCategoryLabels
export const resultCategoryOrder: ResultCategory[] = ["likely", "review", "gap"]
const pathStatusCategory = (
  status: "eligible" | "needs_review" | "ineligible",
): ResultCategory =>
  status === "eligible" ? "likely" : status === "needs_review" ? "review" : "gap"
// 자격 경로 데이터가 있으면 경로 기준 3분류를, 없는 예전 저장 결과는 기존 2분류 규칙을 쓴다.
export const resultCategoryOf = (policy: PolicyRow): ResultCategory =>
  policy.paths?.length
    ? pathStatusCategory(policy.status)
    : policy.conditions.some((c) => c.status === "미충족")
      ? "gap"
      : "likely"
// 신청 가능이지만 입력값으로 비교한 조건이 하나도 없는 정책. 자격을 확인했다는 뜻이 아니라서 따로 표시한다.
export const metCountOf = (policy: PolicyRow) =>
  policy.counts?.passed ?? policy.confirmedConditions?.length ?? 0
export const isUnverified = (policy: PolicyRow) =>
  !policy.paths?.length &&
  resultCategoryOf(policy) === "likely" &&
  metCountOf(policy) === 0
const STATUS_OF_TAB = { passed: "passed", failed: "failed", review: "needs_review" } as const
// 탭 숫자: 대표 경로 결과 + 다른 경로에서 합친 조건(+ 다른 경로의 확인 사항).
// 미충족·추가 확인 숫자는 가장 가까운 경로 기준이다(카드에 크게 보이는 경로와 같게).
const tabCounts = (policy: PolicyRow) => {
  const base = policy.counts ?? { passed: 0, failed: 0, review: 0 }
  const other = otherPathDetails(policy.paths, policy.matchedPathId)
  const best = pathCards(policy.paths).best[0]
  if (!best) return { ...base, passed: base.passed + other.conditions.filter((c) => c.status === STATUS_OF_TAB.passed).length }
  return { passed: best.passedLines.length, failed: best.failed.length, review: best.review.length + best.checks.length }
}
const pathBrief = (policy: PolicyRow): string | null => {
  const paths = policy.paths ?? []
  if (paths.length < 2) return null
  const path = paths.find((p) => p.path_id === policy.matchedPathId) ?? paths[0]
  if (policy.status === "eligible") return `'${path.label}' 경로로 신청 가능`
  if (policy.status === "needs_review") {
    const items = path.conditions
      .filter((c) => c.status === "needs_review")
      .map((c) => c.condition_type)
    return `'${path.label}' 경로 확인 필요 · ${items.length ? items.join(", ") : "공식 안내 확인"}`
  }
  if (policy.blockedByCommon?.length)
    return `공통 조건 미충족: ${policy.blockedByCommon.join(", ")}`
  const { best } = pathCards(paths)
  if (best[0]?.failed.length) {
    const fields = [...new Set(best[0].failed.map((l) => l.field))].join(", ")
    return `추천 경로 '${best[0].label}': ${fields} 미충족 · 경로 ${paths.length}개`
  }
  const failedTypes = path.conditions
    .filter((c) => c.status === "failed")
    .map((c) => c.condition_type)
  return `${policy.matchedPathId === path.path_id ? "대표 경로" : "경로"} '${path.label}': ${failedTypes.join(", ")} 미충족`
}
export const resultReason = (policy: PolicyRow): string => {
  if (policy.paths?.length && policy.recommendationReason)
    return policy.recommendationReason
  if (resultCategoryOf(policy) === "gap")
    return "입력한 정보로 비교한 결과 부족한 조건이 있어요. 아래 ‘확인된 미충족 조건’을 확인하세요."
  const passed =
    policy.counts?.passed ?? policy.confirmedConditions?.length ?? 0
  return passed > 0
    ? "입력한 정보로 비교한 조건을 모두 충족했어요. 나머지 조건은 아래 추가 확인 항목을 공식 안내에서 확인하세요."
    : "입력한 정보와 맞지 않는 조건이 없어요. 세부 자격 요건은 아래 추가 확인 항목을 공식 안내에서 확인하세요."
}

const isOrGroup = (field: string) => field.includes(" 또는 ")
const fieldName = (field: string) =>
  isOrGroup(field) ? field : (conditionFields[field.toLowerCase()] ?? field)
const OrNote = ({ field }: { field: string }) =>
  isOrGroup(field) ? (
    <small className="text-slate-500"> (이 중 하나만 해당하면 돼요)</small>
  ) : null

export const conditionFields: Record<string, string> = {
  age: "나이",
  income_amount: "소득 금액",
  income_ratio: "중위소득 비율",
  income_level: "소득",
  region: "거주 지역",
  employment: "고용 상태",
  employment_status: "고용 상태",
  target_group: "대상 집단",
  nationality: "국적",
  education: "학력·재학",
  household: "가구",
  other: "세부 자격",
  external_review: "기관 심사",
  informational: "안내 사항",
}
type ConditionTab = "passed" | "failed" | "review"
const conditionTabs: [ConditionTab, string][] = [
  ["passed", "충족"],
  ["failed", "미충족"],
  ["review", "추가 확인"],
]
type ConditionItem = { field: string; current: string; required: string; guide?: string; conditionGuide?: string;
  guideKind?: "state_change" | null; evidence?: string }
export function ConditionChangeNotice({ condition, failed }: {
  condition: ConditionItem; failed: boolean
}) {
  const guide = stateChangeGuide(condition.conditionGuide, condition.guideKind,
    condition.required, condition.evidence, failed)
  return guide ? (
    <div className="condition-fulfillment-guide"><strong>역설계 안내</strong><p>{guide}</p></div>
  ) : null
}
const isCheck = (c: ConditionItem) => c.field === "확인 사항"
// 추가 확인은 '입력하면 비교할 수 있는 조건'과 '공식 안내에서 확인할 사항'을 나눠 보여준다.
const groupsOf = (tab: ConditionTab, rows: ConditionItem[]): [string, ConditionItem[]][] =>
  tab === "review"
    ? ([
        ["정보를 입력하면 비교할 수 있어요", rows.filter((c) => !isCheck(c))],
        ["공식 안내에서 확인해야 해요", rows.filter(isCheck)],
      ] as [string, ConditionItem[]][]).filter(([, group]) => group.length > 0)
    : [["", rows]]
// 역설계 문장 하나. 맞춤 안내(로그인) → 공개 안내 → 기준 문장 순으로 쓴다.
function GuideItem({ line, text, personal, onEdit, busy, showCommon = false }: {
  line: GuideLine; text?: string; personal: ReadonlyMap<string, string>; onEdit?: (step: number) => void; busy: boolean
  showCommon?: boolean
}) {
  const sentence = text ?? personal.get(line.key)
    ?? (line.guideKind === "state_change" && line.guide ? line.guide : `${line.required} 기준을 충족해야 합니다.`)
  return (
    <li className="path-guide-line">
      <p>{showCommon && line.common && <span className="path-guide-common">모든 경로 공통</span>}{sentence}</p>
      <span className="path-guide-actions">
        {line.evidence && !samePolicyText(line.evidence, line.required) && (
          <details><summary>원문</summary><p>{line.evidence}</p></details>
        )}
        {onEdit && (
          <button type="button" disabled={busy} onClick={() => onEdit(conditionStep(line.field))}>입력 확인</button>
        )}
      </span>
    </li>
  )
}
// 경로 카드 하나. 미충족 탭은 고칠 조건 전부를, 추가 확인 탭은 입력할 정보와 확인 사항을 보여준다.
function PathCardView({ card, tab, single, best, personal, onEdit, busy }: {
  card: PathCard; tab: PathTab; single: boolean; best: boolean
  personal: ReadonlyMap<string, string>; onEdit?: (step: number) => void; busy: boolean
}) {
  const reviewCount = card.review.length + card.checks.length
  return (
    <section className="path-guide" data-best={best || undefined}>
      {!single && (
        <h4>
          {best && <span className="path-guide-badge">{card.failed.length ? "추천 · 개선 난이도가 가장 낮아요" : "가장 가까운 경로"}</span>}
          {card.labels.join(' · ')} 경로
          <small>{card.labels.length > 1 ? `경로 ${card.labels.length}개 · ` : ''}미충족 {card.failed.length}개{card.labels.length > 1 ? '' : ` · 추가 확인 ${reviewCount}개`}{tab === "failed" && card.difficulty ? ` · 난이도 ${card.difficulty}점` : ""}</small>
        </h4>
      )}
      {tab === "failed" ? (
        card.failed.length ? (
          <>
            <ol>{card.failed.map((l) => <GuideItem key={l.key} line={l} personal={personal} onEdit={onEdit} busy={busy} showCommon={!single} />)}</ol>
            <p className="path-guide-conclusion">
              {card.failed.length > 1 ? `위 ${card.failed.length}개를 모두 충족하면` : "이 조건을 충족하면"} 이 경로의 비교 조건을 모두 충족해요.
              {reviewCount > 0 && card.labels.length === 1 && ` 추가 확인 ${reviewCount}개는 '추가 확인' 탭에서 볼 수 있어요.`}
            </p>
          </>
        ) : (
          <p className="path-guide-conclusion">
            이 경로는 미충족 조건이 없어요.{reviewCount > 0 && ` 추가 확인 ${reviewCount}개를 확인하세요.`}
          </p>
        )
      ) : tab === "passed" ? (
        card.passedLines.length ? (
          <ul className="path-guide-passed">
            {card.passedLines.map((l) => <li key={l.key}>✓ {l.required}</li>)}
          </ul>
        ) : <p className="path-guide-conclusion">입력값으로 충족을 확인한 조건이 없어요.</p>
      ) : reviewCount ? (
        <>
          {!!card.review.length && (
            <>
              <p className="path-guide-sub">정보를 입력하면 비교할 수 있어요</p>
              <ol>
                {card.review.map((l) => (
                  <GuideItem key={l.key} line={l} personal={personal} onEdit={onEdit} busy={busy} showCommon={!single}
                    text={l.required} />
                ))}
              </ol>
            </>
          )}
          {!!card.checks.length && (
            <>
              <p className="path-guide-sub">공식 안내에서 확인할 사항</p>
              <ul className="path-guide-checks">{card.checks.map((text) => <li key={text}>{text}</li>)}</ul>
            </>
          )}
          {card.failed.length > 0 && <p className="path-guide-conclusion">이 경로는 미충족 조건 {card.failed.length}개도 있어요.</p>}
        </>
      ) : (
        <p className="path-guide-conclusion">이 경로는 추가로 확인할 사항이 없어요.</p>
      )}
      {tab === "failed" && !!card.passed.length && <p className="path-guide-note">✓ 충족한 조건: {card.passed.join(", ")}</p>}
    </section>
  )
}
// 경로가 있는 정책의 미충족·추가 확인 탭: 가장 가까운 경로만 크게, 나머지는 '다른 경로 확인하기'에 접어 둔다.
function PathCards({ policy, tab, personal, onEdit, busy = false }: {
  policy: PolicyRow; tab: PathTab; personal: ReadonlyMap<string, string>
  onEdit?: (step: number) => void; busy?: boolean
}) {
  const { best, others, hidden, allImpossible } = pathCards(policy.paths, tab)
  const single = (policy.paths?.length ?? 0) < 2
  const view = (card: PathCard, isBest: boolean) => (
    <PathCardView key={card.pathId} card={card} tab={tab} single={single} best={isBest && !single}
      personal={personal} onEdit={onEdit} busy={busy} />
  )
  return (
    <div className="path-guides">
      {allImpossible && <p className="condition-scope-note">시간이 지나도 다시 충족할 수 없는 조건 때문에 이 정책에는 해당하지 않아요.</p>}
      {best.map((c) => view(c, true))}
      {tab === "failed" && !single && best[0]?.failed.length > 0 && (
        <DifficultySettings />
      )}
      {!!others.length && (
        <details className="other-path-cards">
          <summary>다른 경로 확인하기 ({others.length})</summary>
          {others.map((c) => view(c, false))}
        </details>
      )}
      {hidden > 0 && <p className="path-guide-note">나이 상한 초과처럼 시간이 지나도 충족할 수 없는 경로 {hidden}개는 표시하지 않았어요.</p>}
    </div>
  )
}
// 선택된 탭의 조건만 표시한다. 판정과 조건 선택은 백엔드 결과를 그대로 사용한다.
export function PolicyConditionPanel({ policy, tab, onEdit, busy = false, savedAt, guideTarget }: {
  policy: PolicyRow; tab: ConditionTab; onEdit?: (step: number) => void; busy?: boolean; savedAt?: string
  guideTarget?: ConditionGuideTarget
}) {
  useDifficultyPrefs() // 사용자 가중치가 바뀌면 다시 그린다
  const items: Record<ConditionTab, ConditionItem[]> = {
    passed: policy.confirmedConditions ?? [],
    failed: policy.conditions.filter((c) => c.status === "미충족"),
    review: policy.conditions.filter((c) => c.status === "추가 확인"),
  }
  const shown = items[tab]
  // 경로가 있는 정책의 미충족 탭은 경로별 역설계 문장으로 보여준다.
  const pathMode = !!policy.paths?.length
  const other = otherPathDetails(policy.paths, policy.matchedPathId)
  const otherRows = pathMode ? [] : other.conditions.filter((c) => c.status === STATUS_OF_TAB[tab])
  const mainLabel = policy.paths?.find((p) => p.path_id === policy.matchedPathId)?.label
  return (
    <PersonalizedGuideAccess key={tab === "failed" && guideTarget ? guideTargetKey(guideTarget) : tab}
      target={tab === "failed" ? guideTarget : undefined}>{(personalGuides) => <>
      <p className="condition-panel-title">
        {conditionTabs.find(([kind]) => kind === tab)![1]} 조건{" "}
        <b>{pathMode ? tabCounts(policy)[tab] : shown.length + otherRows.length + (tab === "review" ? other.checks.length : 0)}</b>
      </p>
      {pathMode && (
        <PathCards policy={policy} tab={tab} personal={personalGuides} onEdit={onEdit} busy={busy} />
      )}
      {pathMode ? null : shown.length ? (
        groupsOf(tab, shown).map(([title, rows]) => (
          <section key={title || "all"} className="condition-group">
            {title && (
              <p className="condition-group-title">
                {title} <b>{rows.length}</b>
              </p>
            )}
            <ul>
              {rows.map((c, i) => {
                return isCheck(c) ? (
                  // 입력값으로 비교할 수 없는 확인 사항은 기준 문장만 한 칸에 보여준다.
                  <li key={`check-${i}`} className="condition-item" data-check>
                    <span className="condition-no" aria-hidden="true">{i + 1}</span>
                    <p>{c.required || c.guide || "공식 안내에서 확인해주세요."}</p>
                  </li>
                ) : (
                  <li key={`${c.field}-${i}`} className="condition-item">
                    <strong>
                      {fieldName(c.field)}
                      <OrNote field={c.field} />
                    </strong>
                    <dl>
                      {/* 저장된 결과는 내 정보가 '프로필 보호 중'으로 가려져 있어 기준만 보여준다. */}
                      {c.current && c.current !== "프로필 보호 중" && (
                        <div>
                          <dt>내 정보</dt>
                          <dd>{c.current}</dd>
                        </div>
                      )}
                      <div>
                        <dt>정책 요구 기준</dt>
                        <dd>{c.required || c.evidence || "공식 안내에서 확인해주세요."}</dd>
                      </div>
                    </dl>
                    <ConditionChangeNotice condition={personalGuides.has(gapKey(i))
                      ? { ...c, conditionGuide: personalGuides.get(gapKey(i)), guideKind: "state_change" } : c} failed={tab === "failed"} />
                    {c.evidence && !samePolicyText(c.evidence, c.required || c.evidence) && (
                      <details className="condition-evidence">
                        <summary>정책 원문 근거</summary>
                        <p>{c.evidence}</p>
                      </details>
                    )}
                    {tab !== "passed" && onEdit && c.field !== "external_review" && (
                      <button
                        className="condition-edit"
                        type="button"
                        disabled={busy}
                        onClick={() => onEdit(conditionStep(c.field))}
                      >
                        관련 입력 확인 →
                      </button>
                    )}
                  </li>
                )
              })}
            </ul>
          </section>
        ))
      ) : !otherRows.length && (
        <p className="reverse-card-note">이 결과에는 조건별 상세 내역이 없어요.</p>
      )}
      {!!otherRows.length && (
        <section className="condition-group other-paths">
          <p className="condition-group-title">
            {mainLabel ? `'${mainLabel}' 외 ` : ""}다른 경로의 조건 <b>{otherRows.length}</b>
          </p>
          <ul>
            {otherRows.map((c) => (
              <li key={`${c.field}|${c.required}`} className="condition-item">
                <strong>{fieldName(c.field)}</strong>
                <dl>
                  <div>
                    <dt>정책 요구 기준</dt>
                    <dd>{c.required || c.evidence}</dd>
                  </div>
                  <div>
                    <dt>해당 경로</dt>
                    <dd>{c.labels.join(", ")}</dd>
                  </div>
                </dl>
                <ConditionChangeNotice condition={{ field: c.field, current: "", required: c.required,
                  evidence: c.evidence, conditionGuide: c.conditionGuide, guideKind: c.guideKind }} failed={tab === "failed"} />
              </li>
            ))}
          </ul>
        </section>
      )}
      {!pathMode && tab === "review" && !!other.checks.length && (
        <details className="condition-evidence other-checks">
          <summary>다른 경로의 확인 사항 {other.checks.length}개</summary>
          <ul>
            {other.checks.map((c) => (
              <li key={c.text}><p>{c.text}</p><small>{c.labels.join(", ")}</small></li>
            ))}
          </ul>
        </details>
      )}
      {savedAt && (
        <p className="comparison-time">
          저장 당시 결과 · {new Date(savedAt).toLocaleDateString("ko-KR")}
        </p>
      )}
    </>}</PersonalizedGuideAccess>
  )
}
export default function AnalysisPolicyCard({
  policy,
  saved,
  toggle,
  savedAt,
  onEdit,
  guideTarget,
  busy = false,
  index = 0,
}: {
  policy: PolicyRow
  saved: boolean
  toggle: () => void
  savedAt?: string
  onEdit?: (step: number) => void
  guideTarget?: ConditionGuideTarget
  busy?: boolean
  index?: number
}) {
  useDifficultyPrefs() // 사용자 가중치가 바뀌면 요약·숫자도 다시 계산한다
  const url = safeOfficialUrl(policy.url)
  const counts = policy.counts
  const failed = policy.conditions.filter((c) => c.status === "미충족")
  const [tab, setTab] = useState<ConditionTab | null>(null)
  const panelId = useId()
  const passed = metCountOf(policy)
  return (
    <article
      className="reverse-card"
      data-reveal
      data-reveal-delay={index % 3}
      data-result={resultCategoryOf(policy)}
      data-open={tab !== null}
    >
      <header>
        <div className="card-heading">
          <span className="reverse-tag" data-result={resultCategoryOf(policy)}>
            {resultCategoryLabels[resultCategoryOf(policy)]}
          </span>
          {isUnverified(policy) && (
            <span className="reverse-tag" data-result="unverified">
              비교 조건 없음
            </span>
          )}
          <h3>
            <a href={"#detail/" + encodeURIComponent(policy.id)}>{policy.title}</a>
          </h3>
          <p className="card-brief">
            {pathBrief(policy) ??
              (failed.length
              ? `${fieldName(failed[0].field)}${isOrGroup(failed[0].field) ? " (이 중 하나만 해당하면 돼요)" : ""} 조건 미충족${failed.length > 1 ? ` 외 ${failed.length - 1}개` : ""}`
              : passed > 0
                ? `입력값으로 비교한 조건 ${passed}개 충족`
                : "입력값으로 비교할 조건 없음 · 공식 안내 확인 필요")}
          </p>
          {counts && (
            <div className="condition-counts compact" role="group" aria-label="조건 비교 요약">
              {conditionTabs.map(([kind, label]) => {
                const count = tabCounts(policy)[kind]
                return (
                  <button
                    key={kind}
                    type="button"
                    data-kind={kind}
                    aria-pressed={tab === kind}
                    aria-controls={panelId}
                    disabled={count === 0}
                    onClick={() => setTab(tab === kind ? null : kind)}
                  >
                    {label} <b>{count}</b>
                  </button>
                )
              })}
            </div>
          )}
        </div>
        <div className="card-header-actions">
          <button
            className="policy-save"
            aria-pressed={saved}
            aria-label={`${policy.title} 관심 정책 ${saved ? "해제" : "저장"}`}
            onClick={toggle}
          >
            {saved ? "★ 저장됨" : "☆ 관심 저장"}
          </button>
        </div>
      </header>
      <div id={panelId} hidden={tab === null} className="condition-panel" data-kind={tab ?? undefined}>
        {tab && <PolicyConditionPanel policy={policy} tab={tab} onEdit={onEdit} busy={busy} savedAt={savedAt} guideTarget={guideTarget} />}
      </div>
      <footer className="policy-card-actions">
        {url ? (
          <a
            className="interface-primary"
            href={url}
            target="_blank"
            rel="noopener noreferrer"
          >
            정책 확인하러 가기 <span aria-hidden="true">↗</span>
            <span className="sr-only"> (새 탭)</span>
          </a>
        ) : (
          <span className="policy-link-missing">공식 링크 미제공</span>
        )}
        <p>
          자동 비교에 따른 사전 안내이며 최종 자격은 담당 기관에서 확인해주세요.
        </p>
      </footer>
    </article>
  )
}
