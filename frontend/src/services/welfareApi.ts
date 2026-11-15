import type { CatalogResponse, CatalogDetail } from "../types/policyCatalog"
import type { UserProfileInput, MatchedPolicy, ConditionGuideTarget, PrivateConditionGuides } from "../types/welfareApi"
import { isSnapshot, type Snapshot } from "./analysisSession"
import { restoreSavedPolicies, type SavedPolicy, type TrackingStatus } from "./policyResults"

export interface Account {
  account_id: string
  username: string
  display_name: string
}
export interface AccountState {
  profile: UserProfileInput | null
  diagnosis: Snapshot | null
  previousDiagnosis: Snapshot | null
  current: Snapshot | null
  previous: Snapshot | null
  knownPolicies: MatchedPolicy[]
  savedPolicies: SavedPolicy[]
}
function apiBaseUrl() {
  // 브라우저 전용 값은 요청 시 읽는다. 표시 컴포넌트의 서버 렌더링에는 필요하지 않다.
  const apiUrl = new URL(import.meta.env?.VITE_API_BASE_URL || "/api/v1", window.location.origin)
  const loopback = new Set(["localhost", "127.0.0.1"])
  if (loopback.has(apiUrl.hostname) && loopback.has(window.location.hostname)) apiUrl.hostname = window.location.hostname
  return apiUrl.href.replace(/\/$/, "")
}
let expectedAccountId: string | null = null
const identityListeners = new Set<() => void>()
const identityChannel = "youth-welfare:auth-change"
const notifyIdentityChange = () => { for (const listener of identityListeners) listener() }
function openIdentityChannel(): BroadcastChannel | null {
  try {
    return typeof window !== "undefined" && window.BroadcastChannel
      ? new window.BroadcastChannel(identityChannel) : null
  } catch { return null } // 브라우저 제한 시 초점 복귀·주기적 인증으로 확인한다.
}
export const setApiAccount = (id: string | null) => {
  if (expectedAccountId !== id) { expectedAccountId = id; notifyIdentityChange() }
}
// 계정 정보나 안내 내용은 탭 간 전송하지 않는다. 다른 탭에서도 일시 메모리를 폐기한다.
export function subscribeApiIdentityChange(listener: () => void) {
  identityListeners.add(listener)
  const channel = openIdentityChannel()
  if (channel) channel.onmessage = () => listener()
  return () => { identityListeners.delete(listener); channel?.close() }
}
function announceIdentityChange() {
  notifyIdentityChange()
  const channel = openIdentityChannel()
  try { channel?.postMessage("changed") }
  catch { /* 탭 간 알림 실패가 이미 성공한 인증 요청을 실패로 바꾸지 않는다. */ }
  finally { channel?.close() }
}
export class ApiError extends Error {
  constructor(message: string, public status: number) { super(message) }
}
// LLM이 정책을 하나씩 비교하는 진단은 수 분이 걸릴 수 있어 진단 요청만 대기 시간을 늘린다.
const LONG_TIMEOUT_MS = 30 * 60 * 1000
async function request<T>(path: string, init?: RequestInit, timeoutMs = 20000): Promise<T> {
  const controller = new AbortController()
  const timeout = window.setTimeout(() => controller.abort(), timeoutMs)
  const headers: Record<string, string> = { "Content-Type": "application/json" }
  if (expectedAccountId && !["/auth/login", "/auth/signup", "/auth/me"].includes(path)) headers["X-Account-ID"] = expectedAccountId
  try {
    const response = await fetch(`${apiBaseUrl()}${path}`, {
      ...init, signal: controller.signal, credentials: "include", headers: { ...headers, ...init?.headers },
    })
    if (!response.ok) {
      if (response.status === 401) notifyIdentityChange()
      const data = await response.json().catch(() => null)
      const message = typeof data?.detail === "string" ? data.detail
        : response.status === 422 ? "입력 형식을 확인해주세요. 아이디는 영문·숫자·밑줄 3~30자, 비밀번호는 10~128자예요."
        : "요청을 처리하지 못했어요. 잠시 후 다시 시도해주세요."
      throw new ApiError(message, response.status)
    }
    return response.status === 204 ? undefined as T : await response.json() as T
  } catch (error) {
    if (controller.signal.aborted) throw new Error("응답이 지연되고 있어요. 다시 시도하기 전에 저장 상태를 확인해주세요.")
    if (error instanceof TypeError) throw new Error("서버에 연결하지 못했어요. 잠시 후 다시 시도해주세요.")
    throw error
  } finally { window.clearTimeout(timeout) }
}
export const currentAccount = () => request<Account>("/auth/me")
export const signIn = async (username: string, password: string) => {
  const account = await request<Account>("/auth/login", {
    method: "POST", body: JSON.stringify({ username, password }),
  })
  announceIdentityChange(); return account
}
export const signUp = async (username: string, password: string, display_name: string) => {
  const account = await request<Account>("/auth/signup", {
    method: "POST", body: JSON.stringify({ username, password, display_name }),
  })
  announceIdentityChange(); return account
}
export const signOut = async () => {
  await request<void>("/auth/logout", { method: "POST" })
  announceIdentityChange()
}
function validateState(state: AccountState): AccountState {
  if (!state || ![state.diagnosis, state.previousDiagnosis, state.current, state.previous]
    .every(s => s === null || isSnapshot(s)) || !Array.isArray(state.knownPolicies)) {
    throw new Error("계정의 저장 정보를 읽지 못했어요. 다시 불러와주세요.")
  }
  state.savedPolicies = restoreSavedPolicies(JSON.stringify(state.savedPolicies ?? []))
  return state
}
export const loadAccountState = async () => validateState(await request<AccountState>("/users/state"))
export const diagnoseAccount = async (profile: UserProfileInput) => validateState(await request<AccountState>("/welfare/diagnose", {
  method: "POST", body: JSON.stringify({ ...profile,
    employment_status: profile.employment_status === "PART_TIME" ? "OTHER" : profile.employment_status,
  }),
}, LONG_TIMEOUT_MS))
export const refreshAccount = async () => validateState(await request<AccountState>("/welfare/refresh", { method: "POST" }, LONG_TIMEOUT_MS))
export const toggleAccountPolicy = (profileKey: string, policyId: string) => request<{ items: SavedPolicy[] }>("/users/saved/toggle", { method: "POST", body: JSON.stringify({ profileKey, policyId }) })
export const updateAccountPolicy = (profileKey: string, policyId: string, trackingStatus: TrackingStatus, note: string) =>
  request<{ items: SavedPolicy[] }>("/users/saved", { method: "PATCH", body: JSON.stringify({ profileKey, policyId, trackingStatus, note }) })
export const viewAccountProfile = (username: string, password: string, snapshot: "current" | "diagnosis") => request<UserProfileInput | null>("/users/profile/view", { method: "POST", body: JSON.stringify({ username, password, snapshot }) })
export const viewConditionGuides = (target: ConditionGuideTarget) =>
  request<PrivateConditionGuides>("/users/condition-guides/view", { method: "POST", cache: "no-store", body: JSON.stringify(target) })

export const loadPolicyCatalog = (query: string, category: string, page: number) =>
  request<CatalogResponse>("/policies?" + new URLSearchParams({ q: query, category, page: String(page), page_size: "12" }))
export const loadPolicyDetail = (id: string) => request<CatalogDetail>("/policies/" + encodeURIComponent(id))
