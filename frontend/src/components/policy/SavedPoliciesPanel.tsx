import { useState } from "react"
import { type PolicyRow, type SavedPolicy } from "../../services/policyResults"
import AnalysisPolicyCard from "./AnalysisPolicyCard"

export default function SavedPoliciesPanel({ currentKey, savedPolicies, toggleSaved }: { currentKey: string; savedPolicies: SavedPolicy[]; toggleSaved: (policy: PolicyRow, profileKey: string) => void }) {
  const [scope, setScope] = useState("current")
  const groups = new Map<string, SavedPolicy[]>()
  for (const item of savedPolicies) {
    if (scope === "current" && item.profileKey !== currentKey) continue
    groups.set(item.profileKey, [...(groups.get(item.profileKey) ?? []), item])
  }
  return <section className="saved-policies-panel" aria-labelledby="saved-policy-heading"><header><div><p className="reverse-kicker">프로필과 함께 보관한 정책</p><h2 id="saved-policy-heading">관심 정책</h2></div><label>표시할 프로필 <select value={scope} onChange={event => setScope(event.target.value)}><option value="current">현재 진단 프로필</option><option value="all">이전에 저장한 프로필 포함</option></select></label></header><p className="reverse-small">관심 정책은 저장 당시의 프로필과 함께 내 계정에 보관됩니다. 다시 로그인해도 저장한 목록을 확인할 수 있어요.</p>
    {groups.size === 0 ? <p className="saved-empty">이 프로필에 저장한 관심 정책이 없어요. 진단 결과에서 ‘관심 저장’을 눌러주세요.</p> : [...groups].map(([key, items]) => <section className="saved-profile-group" key={key}><h3>{key === currentKey ? "현재 진단 프로필" : "이전 진단 프로필"}</h3><p className="reverse-small">{items.length}개 저장</p><div className="reverse-list">{items.map(item => <AnalysisPolicyCard key={item.policy.id} policy={item.policy} saved savedAt={item.savedAt} toggle={() => toggleSaved(item.policy, item.profileKey)} />)}</div></section>)}
  </section>
}
