import { safeOfficialUrl } from "../../services/analysisSession"
import type { PolicyRow } from "../../services/policyResults"

export const statusLabels = { eligible: "신청 가능", ineligible: "신청 불가", needs_review: "추가 확인 필요" }
const fields: Record<string, string> = { age: "나이", income_amount: "소득 금액", income_ratio: "중위소득 비율", income_level: "소득", region: "거주 지역", employment: "고용 상태", employment_status: "고용 상태", target_group: "대상 집단", other: "세부 자격", external_review: "기관 심사", informational: "안내 사항" }
export default function AnalysisPolicyCard({ policy, saved, toggle, savedAt }: { policy: PolicyRow; saved: boolean; toggle: () => void; savedAt?: string }) {
  const url = safeOfficialUrl(policy.url)
  return <article className="reverse-card" data-policy-status={policy.status}>
    <header><div><span className="reverse-tag">{statusLabels[policy.status]}</span><h3>{policy.title}</h3></div><button className="policy-save" aria-pressed={saved} aria-label={`${policy.title} 관심 정책 ${saved ? "해제" : "저장"}`} onClick={toggle}>{saved ? "★ 저장됨" : "☆ 관심 저장"}</button></header>
    {policy.description && <p className="reverse-card-note">{policy.description}</p>}
    {savedAt && <p className="policy-saved-date">저장 당시의 분석 결과 · {new Date(savedAt).toLocaleDateString("ko-KR")}</p>}
    {policy.conditions.length > 0 ? <div className="condition-table-scroll" role="region" aria-label={`${policy.title} 조건 비교`} tabIndex={0}><table className="condition-table"><caption>내 조건과 정책 기준 비교</caption><thead><tr><th scope="col">조건</th><th scope="col">내 조건</th><th scope="col">정책 기준</th><th scope="col">비교 결과</th><th scope="col">확인 안내</th></tr></thead><tbody>{policy.conditions.map((c, i) => <tr key={`${c.field}-${i}`}><th scope="row">{fields[c.field.toLowerCase()] ?? c.field}</th><td>{c.current || "미확인"}</td><td>{c.required || "미제공"}</td><td><span className="reverse-tag">{c.status}</span></td><td>{c.guide || "정책의 상세 조건을 확인해주세요."}</td></tr>)}</tbody></table></div> : <p className="reverse-card-note">서버가 제공한 조건별 비교 정보가 없습니다. 세부 기준은 정책에서 확인해주세요.</p>}
    <footer className="policy-card-actions">{url ? <a className="interface-primary" href={url} target="_blank" rel="noopener noreferrer">정책 확인하러 가기 <span aria-hidden="true">↗</span><span className="sr-only"> (새 탭)</span></a> : <span className="policy-link-missing">공식 링크 미제공</span>}<p>자동 비교에 따른 사전 안내이며 최종 자격은 담당 기관에서 확인해주세요.</p></footer>
  </article>
}
