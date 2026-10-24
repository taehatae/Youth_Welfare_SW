import { useState } from "react"
import { formatTime, type Snapshot } from "../../services/analysisSession"
import { policyResults } from "../../services/policyResults"
import { profileSummary } from "../../services/profileSummary"

const labels = {
  eligible: "자동 비교상 충족",
  ineligible: "미충족",
  needs_review: "추가 확인",
}
export function changedPolicyIds(previous: Snapshot | null, current: Snapshot) {
  if (!previous) return new Set<string>()
  const old = new Map(policyResults(previous).map((p) => [p.id, p]))
  return new Set(
    policyResults(current)
      .filter((p) => {
        const before = old.get(p.id)
        return (
          !before ||
          before.status !== p.status ||
          JSON.stringify(before.conditions) !== JSON.stringify(p.conditions) ||
          JSON.stringify(before.counts) !== JSON.stringify(p.counts)
        )
      })
      .map((p) => p.id),
  )
}
export default function AnalysisChanges({
  previous,
  current,
  mode,
}: {
  previous: Snapshot | null
  current: Snapshot
  mode: "diagnosis" | "refresh"
}) {
  const [expanded, setExpanded] = useState(false)
  if (!previous) return null
  const before = new Map(policyResults(previous).map((p) => [p.id, p]))
  const after = new Map(policyResults(current).map((p) => [p.id, p]))
  const added = [...after.values()].filter((p) => !before.has(p.id))
  const removed = [...before.values()].filter((p) => !after.has(p.id))
  const changedIds = changedPolicyIds(previous, current)
  const changed = [...after.values()].filter(
    (p) => before.has(p.id) && changedIds.has(p.id),
  )
  const oldProfile = new Map(
    profileSummary(previous.profile)
      .flatMap((group) => group.items)
      .map(([key, value]) => [key, value]),
  )
  const profileChanges = profileSummary(current.profile)
    .flatMap((group) => group.items)
    .filter(([key, value]) => oldProfile.get(key) !== value)
  const total = added.length + removed.length + changed.length
  return (
    <section
      className="changes-panel"
      data-reveal
      aria-label={
        mode === "diagnosis" ? "재진단 전후 비교" : "현황 조회 전후 비교"
      }
    >
      <div className="changes-heading">
        <div>
          <p className="reverse-kicker">
            {mode === "diagnosis" ? "이전 진단과 비교" : "직전 조회와 비교"}
          </p>
          <h2>
            {total
              ? `${total}개 정책의 결과가 달라졌어요`
              : "정책 분류와 조건 안내에 변화가 없어요"}
          </h2>
        </div>
        <button
          type="button"
          className="comparison-toggle"
          aria-expanded={expanded}
          onClick={() => setExpanded(!expanded)}
        >
          {expanded ? "비교 접기 −" : "비교 자세히 +"}
        </button>
      </div>
      <div className="change-counts">
        <span>
          이번에 추가 <b>{added.length}</b>
        </span>
        <span>
          판정·조건 안내 변경 <b>{changed.length}</b>
        </span>
        <span>
          이번에 제외 <b>{removed.length}</b>
        </span>
      </div>
      {expanded && (
        <div className="details-body step-arrive">
          <p className="comparison-time">
            {formatTime(previous.checkedAt)} → {formatTime(current.checkedAt)}
          </p>
          {mode === "diagnosis" && (
            <>
              <h3>입력 정보 변화</h3>
              {profileChanges.length ? (
                <ul className="profile-differences">
                  {profileChanges.map(([key, value]) => (
                    <li key={key}>
                      <strong>{key}</strong>
                      <span>
                        {oldProfile.get(key) ?? "미확인"} → {value}
                      </span>
                    </li>
                  ))}
                </ul>
              ) : (
                <p>입력 정보는 재인증 후 프로필 조회에서 확인할 수 있어요.</p>
              )}
            </>
          )}
          <ul className="policy-differences">
            {added.map((p) => (
              <li key={p.id}>
                <span className="change-label">추가</span>
                <strong>{p.title}</strong>
                <span>{labels[p.status]}</span>
              </li>
            ))}
            {changed.map((p) => (
              <li key={p.id}>
                <span className="change-label">변경</span>
                <strong>{p.title}</strong>
                <span>
                  {before.get(p.id)!.status === p.status
                    ? "조건 안내 변경"
                    : `${labels[before.get(p.id)!.status]} → ${labels[p.status]}`}
                </span>
              </li>
            ))}
            {removed.map((p) => (
              <li key={p.id}>
                <span className="change-label">제외</span>
                <strong>{p.title}</strong>
                <span>이번 응답에 없음</span>
              </li>
            ))}
          </ul>
          <p className="comparison-note">
            정책 데이터도 변경될 수 있어 입력 변화만의 효과로 단정할 수 없어요.
            추가·제외는 조회 결과의 차이이며, 새 공고나 신청 종료를 뜻하지
            않아요.
          </p>
        </div>
      )}
    </section>
  )
}
