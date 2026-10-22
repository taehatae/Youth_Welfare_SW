import { useState } from "react"
import type { UserProfileInput } from "../../types/welfareApi"
import { profileKey, type PolicyRow, type SavedPolicy } from "../../services/policyResults"
import AnalysisPolicyCard from "./AnalysisPolicyCard"

export default function SavedPoliciesPanel({ profile, savedPolicies, toggleSaved }: { profile: UserProfileInput; savedPolicies: SavedPolicy[]; toggleSaved: (policy: PolicyRow, profile: UserProfileInput) => void }) {
  const [scope, setScope] = useState("current")
  const currentKey = profileKey(profile)
  const groups = new Map<string, SavedPolicy[]>()
  for (const item of savedPolicies) {
    if (scope === "current" && item.profileKey !== currentKey) continue
    groups.set(item.profileKey, [...(groups.get(item.profileKey) ?? []), item])
  }
  return <section className="saved-policies-panel" aria-labelledby="saved-policy-heading"><header><div><p className="reverse-kicker">프로필과 함께 보관한 정책</p><h2 id="saved-policy-heading">관심 정책</h2></div><label>표시할 프로필 <select value={scope} onChange={event => setScope(event.target.value)}><option value="current">현재 진단 프로필</option><option value="all">이전에 저장한 프로필 포함</option></select></label></header><p className="reverse-small">관심 정책은 저장 당시의 프로필과 함께 이 브라우저에 보관됩니다. 재진단해도 이전 프로필의 저장 목록은 유지되며, 계정·다른 기기와 자동 공유되지 않습니다.</p>
    {groups.size === 0 ? <p className="saved-empty">이 프로필에 저장한 관심 정책이 없어요. 진단 결과에서 ‘관심 저장’을 눌러주세요.</p> : [...groups].map(([key, items]) => <section className="saved-profile-group" key={key}><h3>{key === currentKey ? "현재 진단 프로필" : "이전 진단 프로필"} · 만 {items[0].profile.age}세 · {items[0].profile.region}</h3><p className="reverse-small">월 소득 {items[0].profile.income_level.toLocaleString("ko-KR")}원 · {items.length}개 저장</p><div className="reverse-list">{items.map(item => <AnalysisPolicyCard key={item.policy.id} policy={item.policy} saved savedAt={item.savedAt} toggle={() => toggleSaved(item.policy, item.profile)} />)}</div></section>)}
  </section>
}
