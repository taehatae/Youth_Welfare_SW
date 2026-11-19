import { useEffect, useRef, useState, type ReactNode } from "react"
import type { ConditionGuideTarget } from "../../types/welfareApi"
import { createPrivateGuideLoader, guideTargetKey, type PrivateDifficulties } from "../../services/conditionGuidance"
import { subscribeApiIdentityChange, viewConditionGuides } from "../../services/welfareApi"

// 맞춤 안내는 정책/스냅샷/영구 저장소에 합치지 않고 열린 미충족 탭에서만 사용한다.
export default function PersonalizedGuideAccess({ target, children }: {
  target?: ConditionGuideTarget; children: (guides: ReadonlyMap<string, string>, difficulties: PrivateDifficulties) => ReactNode
}) {
  const loader = useRef<ReturnType<typeof createPrivateGuideLoader> | null>(null)
  const key = target ? guideTargetKey(target) : ""
  const [, update] = useState(0)
  useEffect(() => {
    if (!target) return
    let active = true
    const current = createPrivateGuideLoader(viewConditionGuides, () => { if (active) update(n => n + 1) })
    loader.current = current
    const clear = () => current.clear()
    // 다른 창을 잠깐 누르는 것(blur)으로는 지우지 않는다. 탭을 숨기거나 떠날 때만 지운다.
    const reload = () => {
      if (!document.hidden) void current.load(target)
      else clear()
    }
    const visibility = () => { if (document.hidden) clear(); else reload() }
    const unsubscribe = subscribeApiIdentityChange(() => current.clear("로그인 상태가 변경됐어요. 로그인한 계정을 확인한 뒤 결과를 다시 열어주세요."))
    window.addEventListener("focus", reload)
    window.addEventListener("pagehide", clear)
    window.addEventListener("pageshow", reload)
    document.addEventListener("visibilitychange", visibility)
    // 서버 측 만료/세션 폐기는 푸시되지 않으므로 활성 화면에서도 1분마다 다시 검증한다.
    const timer = window.setInterval(reload, 60_000)
    reload()
    return () => {
      active = false; current.clear(); loader.current = null; unsubscribe()
      window.clearInterval(timer)
      window.removeEventListener("focus", reload)
      window.removeEventListener("pagehide", clear)
      window.removeEventListener("pageshow", reload)
      document.removeEventListener("visibilitychange", visibility)
    }
  }, [key])
  const state = target ? loader.current?.read(target) : null
  return <>
    {target && <div className="private-guide-controls">
      <p className="condition-scope-note">역설계 안내는 조건 하나를 기준으로 한 설명이며 신청 자격을 보장하지 않아요. 진단 당시 입력값 기준이에요.</p>
      {state?.status === "loading" && <p role="status" className="condition-scope-note">맞춤 안내를 불러오는 중이에요.</p>}
      {state?.error && <p role="alert" className="auth-error">{state.error}</p>}
      {state?.unavailableReason && <p className="condition-scope-note">저장 당시 조건과 현재 조건의 동일성을 확인할 수 없어 맞춤 안내·난이도 재계산을 생략했어요. 기존 진단 결과는 그대로 표시합니다.</p>}
    </div>}
    {children(state?.guides ?? new Map<string, string>(), state?.difficulties ?? new Map())}
  </>
}
