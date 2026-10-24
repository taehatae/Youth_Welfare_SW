import type { CatalogResponse, CatalogDetail } from "../types/policyCatalog"
import type { UserProfileInput, MatchedPolicy } from "../types/welfareApi"
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
const apiUrl = new URL(import.meta.env.VITE_API_BASE_URL || "/api/v1", window.location.origin)
const loopback = new Set(["localhost", "127.0.0.1"])
if (loopback.has(apiUrl.hostname) && loopback.has(window.location.hostname)) apiUrl.hostname = window.location.hostname
const API_BASE_URL = apiUrl.href.replace(/\/$/, "")
let expectedAccountId: string | null = null
export const setApiAccount = (id: string | null) => { expectedAccountId = id }
export class ApiError extends Error {
  constructor(message: string, public status: number) { super(message) }
}
async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const controller = new AbortController()
  const timeout = window.setTimeout(() => controller.abort(), 20000)
  const headers: Record<string, string> = { "Content-Type": "application/json" }
  if (expectedAccountId && !["/auth/login", "/auth/signup", "/auth/me"].includes(path)) headers["X-Account-ID"] = expectedAccountId
  try {
    const response = await fetch(`${API_BASE_URL}${path}`, {
      ...init, signal: controller.signal, credentials: "include", headers: { ...headers, ...init?.headers },
    })
    if (!response.ok) {
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
export const signIn = (username: string, password: string) => request<Account>("/auth/login", {
  method: "POST", body: JSON.stringify({ username, password }),
})
export const signUp = (username: string, password: string, display_name: string) => request<Account>("/auth/signup", {
  method: "POST", body: JSON.stringify({ username, password, display_name }),
})
export const signOut = () => request<void>("/auth/logout", { method: "POST" })
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
}))
export const refreshAccount = async () => validateState(await request<AccountState>("/welfare/refresh", { method: "POST" }))
export const toggleAccountPolicy = (profileKey: string, policyId: string) => request<{ items: SavedPolicy[] }>("/users/saved/toggle", { method: "POST", body: JSON.stringify({ profileKey, policyId }) })
export const updateAccountPolicy = (profileKey: string, policyId: string, trackingStatus: TrackingStatus, note: string) =>
  request<{ items: SavedPolicy[] }>("/users/saved", { method: "PATCH", body: JSON.stringify({ profileKey, policyId, trackingStatus, note }) })
export const viewAccountProfile = (username: string, password: string, snapshot: "current" | "diagnosis") => request<UserProfileInput | null>("/users/profile/view", { method: "POST", body: JSON.stringify({ username, password, snapshot }) })

export const loadPolicyCatalog = (query: string, category: string, page: number) =>
  request<CatalogResponse>("/policies?" + new URLSearchParams({ q: query, category, page: String(page), page_size: "12" }))
export const loadPolicyDetail = (id: string) => request<CatalogDetail>("/policies/" + encodeURIComponent(id))
