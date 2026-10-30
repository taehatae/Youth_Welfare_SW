import { useEffect, useRef, useState } from "react"
import Navigation from "../components/layout/Navigation"
import LoginDialog from "../components/layout/LoginDialog"
import ProfileDialog from "../components/layout/ProfileDialog"
import type { Page } from "../types/page"
import HomePage from "../features/home/HomePage"
import PolicyExplorerPage from "../features/policies/PolicyExplorerPage"
import PolicyDetailPage from "../features/policies/PolicyDetailPage"
import DiagnosisPage from "../features/diagnosis/DiagnosisPage"
import ResultPage from "../features/diagnosis/ResultPage"
import DashboardPage from "../features/dashboard/DashboardPage"
import { currentAccount, diagnoseAccount, refreshAccount, loadAccountState, signOut, setApiAccount, toggleAccountPolicy, ApiError, type Account, type AccountState } from "../services/welfareApi"
import { emptySession } from "../services/analysisSession"
import type { UserProfileInput } from "../types/welfareApi"
import { type PolicyRow, type SavedPolicy, type TrackingStatus } from "../services/policyResults"
import { updateAccountPolicy } from "../services/welfareApi"
import { profileToDraft } from "../services/profileSummary"
import { usePageMotion } from "../hooks/usePageMotion"
import "../styles/interface.css"
import "../styles/motion.css"
import "../styles/improvements.css"
import "../styles/auth.css"
import "../styles/actions.css"

const pages: Page[] = ["home", "explorer", "diagnosis", "result", "dashboard"]
function policyFromRoute(): string {
  if (!window.location.hash.startsWith("#detail/")) return ""
  try { return decodeURIComponent(window.location.hash.slice(8)) } catch { return "invalid-policy" }
}
function route(): Page {
  const hash = window.location.hash.slice(1).split("?")[0] as Page
  return policyFromRoute() ? "detail" : pages.includes(hash) ? hash : "home"
}
function accountSession(state: AccountState) {
  return { ...emptySession(), ...state,
    draft: state.profile ? profileToDraft(state.profile) : emptySession().draft,
    step: 0,
  }
}

export default function App() {
  const [page, updatePage] = useState<Page>(route)
  const [selectedPolicy, setSelectedPolicy] = useState<string>(policyFromRoute)
  const explorerRoute = useRef(window.location.hash.startsWith("#explorer") ? window.location.hash : "#explorer")
  const motionRoot = usePageMotion(page + (page === "detail" ? selectedPolicy : ""))
  const [account, setAccount] = useState<Account | null>(null)
  const [ready, setReady] = useState(false)
  const [authLoading, setAuthLoading] = useState(true)
  const [authError, setAuthError] = useState("")
  const [loginOpen, setLoginOpen] = useState(false)
  const [profileRequest, setProfileRequest] = useState<{ snapshot: "current" | "diagnosis"; step?: number } | null>(null)
  const [session, setSession] = useState(emptySession)
  const [savedPolicies, setSavedPolicies] = useState<SavedPolicy[]>([])
  const [busy, setBusy] = useState(false)
  const [refreshError, setRefreshError] = useState("")
  const pending = useRef(false)
  const generation = useRef(0)

  const setPage = (next: Page) => {
    if (next === "diagnosis" && (page === "result" || page === "dashboard")) setSession(s => ({ ...s, step: 0 }))
    updatePage(next)
    if (next !== "detail") window.location.hash = next === "explorer" ? explorerRoute.current : next
    window.scrollTo({ top: 0, behavior: "instant" })
  }
  const clearIdentity = () => {
    generation.current++
    setApiAccount(null)
    setProfileRequest(null)
    setAccount(null)
    setSession(emptySession())
    setSavedPolicies([])
    setRefreshError("")
    setReady(true)
    pending.current = false
    setBusy(false)
    setAuthLoading(false)
  }
  const restoreAccount = async () => {
    const version = ++generation.current
    setAuthLoading(true)
    setReady(false)
    setAuthError("")
    // 재연결 중에는 이전 계정의 정보를 표시하지 않는다.
    setAccount(null); setSession(emptySession()); setSavedPolicies([]); setApiAccount(null)
    try {
      const found = await currentAccount()
      if (version !== generation.current) return
      setApiAccount(found.account_id)
      setAccount(found)
      const state = await loadAccountState()
      if (version !== generation.current) return
      setSession(accountSession(state)); setSavedPolicies(state.savedPolicies)
      setReady(true)
    } catch (error) {
      if (version !== generation.current) return
      if (error instanceof ApiError && error.status === 401) clearIdentity()
      else setAuthError(error instanceof Error ? error.message : "계정을 불러오지 못했어요.")
    } finally { if (version === generation.current) setAuthLoading(false) }
  }
  useEffect(() => {
    // 이전 익명 버전이 남긴 입력값 캐시도 계정 조회를 우회하는 경로가 되지 않게 제거한다.
    try {
      for (const mode of ["live", "demo"]) {
        window.localStorage.removeItem(`youth-welfare:session:v2:${mode}`)
        window.localStorage.removeItem(`youth-welfare:saved:v1:${mode}`)
      }
    } catch { setAuthError("이전 브라우저 저장 정보를 정리하지 못했어요. 공유 기기라면 사이트 데이터를 삭제해주세요.") }
    void restoreAccount()
    let previousRoute = route()
    const navigate = () => {
      if (window.location.hash.startsWith("#explorer")) explorerRoute.current = window.location.hash
      const policy = policyFromRoute()
      if (policy) setSelectedPolicy(policy)
      const nextRoute = route()
      updatePage(nextRoute)
      if (nextRoute !== previousRoute) window.scrollTo({ top: 0, behavior: "instant" })
      previousRoute = nextRoute
    }
    window.addEventListener("hashchange", navigate)
    return () => { generation.current++; window.removeEventListener("hashchange", navigate) }
  }, [])

  useEffect(() => {
    setProfileRequest(null)
    if (page !== "diagnosis") setSession(s => ({ ...s, draft: emptySession().draft, step: 0 }))
  }, [page])

  const acceptAccount = async (next: Account) => {
    const version = ++generation.current
    setAuthLoading(true); setReady(false); setAuthError("")
    setSession(emptySession()); setSavedPolicies([]); setRefreshError("")
    setAccount(next); setApiAccount(next.account_id)
    try {
      const state = await loadAccountState()
      if (version !== generation.current) return
      setSession(accountSession(state)); setSavedPolicies(state.savedPolicies); setReady(true)
      if (page === "home") setPage("dashboard")
    } catch (error) {
      setAuthError(error instanceof Error ? error.message : "계정 정보를 불러오지 못했어요.")
      throw error
    } finally { if (version === generation.current) setAuthLoading(false) }
  }
  const logout = async () => {
    if (pending.current || authLoading) return
    setAuthLoading(true)
    try { await signOut(); clearIdentity(); setAuthError(""); setPage("home") }
    catch (error) { authFailure(error); setAuthError(error instanceof Error ? error.message : "로그아웃하지 못했어요.") }
    finally { setAuthLoading(false) }
  }
  const authFailure = (error: unknown) => {
    if (error instanceof ApiError && error.status === 401) {
      clearIdentity(); setAuthError("로그인이 만료되었거나 계정이 변경됐어요. 다시 로그인해주세요.")
    }
  }
  const completeDiagnosis = async (profile: UserProfileInput) => {
    if (!account || !ready) throw new Error("로그인 후 진단해주세요.")
    if (pending.current) return
    pending.current = true; setBusy(true)
    const version = generation.current
    try {
      const state = await diagnoseAccount(profile)
      if (version !== generation.current) return
      setSession(accountSession(state)); setSavedPolicies(state.savedPolicies); setRefreshError(""); setPage("result")
    } catch (error) { authFailure(error); throw error }
    finally { if (version === generation.current) { pending.current = false; setBusy(false) } }
  }
  const refresh = async () => {
    if (pending.current || !account || !session.current) return
    pending.current = true; setBusy(true); setRefreshError("")
    const version = generation.current
    try {
      const state = await refreshAccount()
      if (version !== generation.current) return
      setSession(current => ({ ...current, ...state }))
      setSavedPolicies(state.savedPolicies)
    } catch (error) {
      authFailure(error)
      if (version === generation.current) setRefreshError(error instanceof Error ? error.message : "조회하지 못했어요.")
    } finally { if (version === generation.current) { pending.current = false; setBusy(false) } }
  }
  const editProfile = (profile: UserProfileInput, step = 0) => {
    if (pending.current) return
    setPage("diagnosis"); setSession(s => ({ ...s, draft: profileToDraft(profile), step }))
  }
  const toggleSaved = async (policy: PolicyRow, key: string) => {
    if (pending.current || !account) return
    const version = generation.current
    pending.current = true; setBusy(true)
    try {
      const saved = await toggleAccountPolicy(key, policy.id)
      if (version === generation.current) { setSavedPolicies(saved.items); setAuthError("") }
    } catch (error) {
      authFailure(error)
      if (version === generation.current) setAuthError(error instanceof Error ? error.message : "관심 정책을 저장하지 못했어요.")
    } finally { if (version === generation.current) { pending.current = false; setBusy(false) } }
  }
  const privatePage = ["diagnosis", "result", "dashboard"].includes(page)
  const updateSaved = async (item: SavedPolicy, status: TrackingStatus, note: string) => {
    if (pending.current || !account) throw new Error("진행 중인 작업이 끝난 뒤 다시 저장해주세요.")
    const version = generation.current
    pending.current = true; setBusy(true)
    try {
      const saved = await updateAccountPolicy(item.profileKey, item.policy.id, status, note)
      if (version !== generation.current) throw new Error("계정이 변경되었어요. 다시 로그인해주세요.")
      setSavedPolicies(saved.items)
    } catch (error) { authFailure(error); throw error }
    finally { if (version === generation.current) { pending.current = false; setBusy(false) } }
  }
  return <div className="min-h-screen bg-white">
    <Navigation page={page} setPage={setPage} account={account} busy={busy || authLoading} onLogin={() => setLoginOpen(true)} onLogout={() => void logout()} />
    <LoginDialog open={loginOpen} onClose={() => setLoginOpen(false)} onSuccess={acceptAccount} />
    {profileRequest && account && <ProfileDialog snapshot={profileRequest.snapshot} editStep={profileRequest.step} onClose={() => setProfileRequest(null)} onEdit={editProfile} onAuthFailure={authFailure} />}
    {authError && <div role="alert" className="auth-notice">{authError} <button disabled={authLoading} onClick={() => void restoreAccount()}>다시 연결</button></div>}
    <main ref={motionRoot} key={page + (page === "detail" ? selectedPolicy : "")} className={page === "home" ? undefined : "interface-workspace page-arrive"}>
      {privatePage && (!account || !ready || authLoading) ? <section className="auth-gate interface-empty">
        <span className="interface-login-status">내 계정에 이어서 저장</span>
        <h1>{authLoading ? "계정 정보를 불러오고 있어요" : account ? "저장 정보를 다시 불러와주세요" : "로그인하고 내 자격을 확인하세요"}</h1>
        <p>입력한 프로필과 진단 결과를 계정에 저장하고, 나의 현황에서 다시 확인할 수 있어요.</p>
        {!authLoading && <button className="interface-primary" onClick={() => account ? void restoreAccount() : setLoginOpen(true)}>{account ? "다시 불러오기" : "로그인 · 회원가입"}</button>}
      </section> : <>
        {page === "home" && <HomePage setPage={setPage} />}
        {page === "explorer" && <PolicyExplorerPage />}
        {page === "detail" && <PolicyDetailPage policyId={selectedPolicy} setPage={setPage} />}
        {page === "diagnosis" && <DiagnosisPage draft={session.draft} setDraft={draft => setSession(s => ({ ...s, draft }))} step={session.step} setStep={step => setSession(s => ({ ...s, step }))} setPage={setPage} onComplete={completeDiagnosis} busy={busy} />}
        {page === "result" && <ResultPage snapshot={session.diagnosis} previous={session.previousDiagnosis} setPage={setPage} busy={busy} savedPolicies={savedPolicies} toggleSaved={toggleSaved} onViewProfile={() => setProfileRequest({ snapshot: "diagnosis" })} onEdit={step => setProfileRequest({ snapshot: "diagnosis", step })} />}
        {page === "dashboard" && <DashboardPage onViewProfile={() => setProfileRequest({ snapshot: "current" })} onEdit={step => setProfileRequest({ snapshot: "current", step: step ?? 0 })} savedPolicies={savedPolicies} updateSaved={updateSaved} session={session} setPage={setPage} refresh={refresh} busy={busy} error={refreshError} />}
      </>}
    </main>
  </div>
}
