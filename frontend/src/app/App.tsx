import { useEffect, useRef, useState } from "react"
import Navigation from "../components/layout/Navigation"
import { POLICIES } from "../data/policies"
import type { Page } from "../types/page"
import type { Policy } from "../types/policy"
import HomePage from "../features/home/HomePage"
import PolicyExplorerPage from "../features/policies/PolicyExplorerPage"
import PolicyDetailPage from "../features/policies/PolicyDetailPage"
import DiagnosisPage from "../features/diagnosis/DiagnosisPage"
import ResultPage from "../features/diagnosis/ResultPage"
import DashboardPage from "../features/dashboard/DashboardPage"
import {
  analyzeWelfareProfile,
  refreshWelfareAnalysis,
  IS_DEMO_MODE,
} from "../services/welfareApi"
import {
  emptySession,
  restoreSession,
  storageKey,
  type Snapshot,
} from "../services/analysisSession"
import type { UserProfileInput } from "../types/welfareApi"
import { profileKey, restoreSavedPolicies, type PolicyRow, type SavedPolicy } from "../services/policyResults"
import "../styles/interface.css"

const pages: Page[] = ["home", "explorer", "diagnosis", "result", "dashboard"]
function policyFromRoute(): Policy | undefined {
  return POLICIES.find(
    (p) => "#detail/" + encodeURIComponent(p.id) === window.location.hash,
  )
}
function route(): Page {
  const hash = window.location.hash.slice(1) as Page
  return policyFromRoute() ? "detail" : pages.includes(hash) ? hash : "home"
}

export default function App() {
  const [page, updatePage] = useState<Page>(route)
  const [selectedPolicy, setSelectedPolicy] = useState<Policy>(
    () => policyFromRoute() ?? POLICIES[0],
  )
  const [storageWarning, setStorageWarning] = useState("")
  const savedKey = "youth-welfare:saved:v1:" + (IS_DEMO_MODE ? "demo" : "live")
  const [savedState, setSavedState] = useState<{ items: SavedPolicy[]; warning: string }>(() => {
    try { return { items: restoreSavedPolicies(window.localStorage.getItem(savedKey)), warning: "" } }
    catch { return { items: [], warning: "관심 정책을 읽지 못했습니다. 새로 저장하면 현재 목록으로 저장됩니다." } }
  })
  const toggleSaved = (policy: PolicyRow, profile: UserProfileInput) => {
    const key = profileKey(profile)
    const exists = savedState.items.some(item => item.profileKey === key && item.policy.id === policy.id)
    const items = exists ? savedState.items.filter(item => !(item.profileKey === key && item.policy.id === policy.id)) : [...savedState.items, { profileKey: key, profile, policy, savedAt: new Date().toISOString() }]
    try { window.localStorage.setItem(savedKey, JSON.stringify(items)); setSavedState({ items, warning: exists ? "관심 정책 저장을 해제했습니다." : "이 프로필의 관심 정책으로 저장했습니다." }) }
    catch { setSavedState({ items, warning: "현재 화면에만 반영했습니다. 브라우저 저장에 실패해 새로고침하면 사라질 수 있습니다." }) }
  }
  const [session, setSession] = useState(() => {
    try {
      return restoreSession(
        window.localStorage.getItem(storageKey(IS_DEMO_MODE)),
      )
    } catch {
      return emptySession()
    }
  })
  const [busy, setBusy] = useState(false)
  const pending = useRef(false)
  const [refreshError, setRefreshError] = useState("")
  useEffect(() => {
    try {
      restoreSession(window.localStorage.getItem(storageKey(IS_DEMO_MODE)))
    } catch {
      setStorageWarning(
        "저장된 정보를 읽지 못했어요. 이번 입력부터 다시 저장합니다.",
      )
    }
    const navigate = () => {
      const policy = policyFromRoute()
      if (policy) setSelectedPolicy(policy)
      updatePage(route())
      window.scrollTo({ top: 0, behavior: "instant" })
    }
    window.addEventListener("hashchange", navigate)
    return () => window.removeEventListener("hashchange", navigate)
  }, [])
  useEffect(() => {
    try {
      window.localStorage.setItem(
        storageKey(IS_DEMO_MODE),
        JSON.stringify(session),
      )
    } catch {
      setStorageWarning(
        "브라우저에 저장하지 못했어요. 현재 화면에서는 계속 사용할 수 있지만 새로고침하면 내용이 사라질 수 있어요.",
      )
    }
  }, [session])
  const setPage = (next: Page) => {
    if (next === "diagnosis" && (page === "result" || page === "dashboard")) {
      setSession((current) => ({ ...current, step: 0 }))
    }
    updatePage(next)
    if (next !== "detail") window.location.hash = next
    window.scrollTo({ top: 0, behavior: "instant" })
  }
  const completeDiagnosis = async (profile: UserProfileInput) => {
    if (pending.current) return
    pending.current = true
    setBusy(true)
    try {
      const analysis = await analyzeWelfareProfile(profile)
      const snapshot: Snapshot = {
        profile,
        analysis,
        checkedAt: new Date().toISOString(),
      }
      setSession((current) => ({
        ...current,
        diagnosis: snapshot,
        current: snapshot,
        previous: null,
        knownPolicies: analysis.matched.policies,
      }))
      setRefreshError("")
      setPage("result")
    } finally {
      pending.current = false
      setBusy(false)
    }
  }
  const refresh = async () => {
    if (pending.current || !session.current) return
    pending.current = true
    setBusy(true)
    setRefreshError("")
    const saved = session.current
    try {
      const analysis = await refreshWelfareAnalysis(
        saved.analysis.userId,
        saved.profile,
      )
      setSession((current) => ({
        ...current,
        previous: saved,
        current: {
          profile: saved.profile,
          analysis,
          checkedAt: new Date().toISOString(),
        },
        knownPolicies: [
          ...new Map(
            [...current.knownPolicies, ...analysis.matched.policies].map(
              (p) => [p.policy_id, p],
            ),
          ).values(),
        ],
      }))
    } catch (e) {
      setRefreshError(e instanceof Error ? e.message : "조회에 실패했어요.")
    } finally {
      pending.current = false
      setBusy(false)
    }
  }
  return (
    <div className="min-h-screen bg-white">
      {IS_DEMO_MODE && (
        <div
          role="status"
          className="bg-amber-100 px-4 py-2 text-center text-sm text-amber-950"
        >
          시연 모드 · 선택한 정보와 별개로 정해진 예시 결과를 보여줍니다. 실제
          자격 판정이 아닙니다.
        </div>
      )}
      <Navigation page={page} setPage={setPage} />
      {savedState.warning && <p role="status" className="analysis-notice saved-feedback">{savedState.warning}</p>}
      {storageWarning && (
        <p
          role="alert"
          className="bg-amber-50 px-4 py-3 text-center text-sm text-amber-900"
        >
          {storageWarning}
        </p>
      )}
      <main className={page === "home" ? undefined : "interface-workspace"}>
        {page === "home" && <HomePage setPage={setPage} />}
        {page === "explorer" && (
          <PolicyExplorerPage
            setPage={setPage}
            setSelectedPolicy={(policy) => {
              setSelectedPolicy(policy)
              window.location.hash = "detail/" + encodeURIComponent(policy.id)
            }}
          />
        )}
        {page === "detail" && (
          <PolicyDetailPage policy={selectedPolicy} setPage={setPage} />
        )}
        {page === "diagnosis" && (
          <DiagnosisPage
            draft={session.draft}
            setDraft={(draft) =>
              setSession((current) => ({ ...current, draft }))
            }
            step={session.step}
            setStep={(step) => setSession((current) => ({ ...current, step }))}
            setPage={setPage}
            onComplete={completeDiagnosis}
            busy={busy}
          />
        )}
        {page === "result" && (
          <ResultPage snapshot={session.current ?? session.diagnosis} setPage={setPage} refresh={refresh} busy={busy} error={refreshError} savedPolicies={savedState.items} toggleSaved={toggleSaved} />
        )}
        {page === "dashboard" && (
          <DashboardPage
            savedPolicies={savedState.items}
            toggleSaved={toggleSaved}
            session={session}
            setPage={setPage}
            refresh={refresh}
            busy={busy}
            error={refreshError}
            clear={() => {
              try { window.localStorage.removeItem(savedKey); setSavedState({ items: [], warning: "" }) }
              catch { setSavedState({ items: [], warning: "브라우저의 관심 정책 저장 정보를 삭제하지 못했습니다." }) }
              setSession(emptySession())
              setRefreshError("")
              setPage("home")
            }}
          />
        )}
      </main>
    </div>
  )
}
