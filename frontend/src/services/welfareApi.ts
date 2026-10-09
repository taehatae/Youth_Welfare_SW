import type {
  MatchedPoliciesResponse,
  ReverseRecommendationsResponse,
  SaveProfileResponse,
  UserProfileInput,
  WelfareAnalysis,
} from '../types/welfareApi'

const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api/v1').replace(/\/$/, '')

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response
  try {
    response = await fetch(`${API_BASE_URL}${path}`, {
      ...init,
      headers: { 'Content-Type': 'application/json', ...init?.headers },
    })
  } catch {
    throw new Error(`서버에 연결할 수 없습니다. 백엔드 실행 상태와 API 주소(${API_BASE_URL})를 확인해주세요.`)
  }

  if (!response.ok) {
    const detail = await response.text().catch(() => '')
    throw new Error(detail || `요청에 실패했습니다. (HTTP ${response.status})`)
  }

  return response.json() as Promise<T>
}

export async function analyzeWelfareProfile(profile: UserProfileInput): Promise<WelfareAnalysis> {
  const saved = await request<SaveProfileResponse>('/users/profile', {
    method: 'POST',
    body: JSON.stringify(profile),
  })

  if (!saved.user_id) throw new Error('프로필 저장 응답에 user_id가 없습니다.')

  const userId = encodeURIComponent(saved.user_id)
  const [matched, reverse] = await Promise.all([
    request<MatchedPoliciesResponse>(`/welfare/matched?user_id=${userId}`),
    request<ReverseRecommendationsResponse>(`/welfare/reverse-engineering?user_id=${userId}`),
  ])

  return { userId: saved.user_id, matched, reverse }
}
