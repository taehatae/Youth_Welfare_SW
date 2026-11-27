import { useLayoutEffect, useRef, useState } from "react"

// 첫 렌더는 항상 최종 숫자(서버 렌더·테스트 안전). 마운트 뒤에만 0에서 올라가고,
// 값이 바뀌면 이전 값에서 새 값으로 이어서 올라간다. 모션 줄이기 설정이면 바로 최종값.
export function useCountUp(target: number, { duration = 700 } = {}) {
  const [value, setValue] = useState(target)
  const shown = useRef(target)
  const started = useRef(false)
  useLayoutEffect(() => {
    const reduce =
      typeof window === "undefined" ||
      typeof window.matchMedia !== "function" ||
      typeof requestAnimationFrame !== "function" ||
      window.matchMedia("(prefers-reduced-motion: reduce)").matches
    // 첫 마운트는 0에서, 이후 변경은 현재 표시값에서 출발
    const from = started.current ? shown.current : 0
    started.current = true
    if (reduce || !Number.isFinite(target) || from === target) {
      shown.current = target
      setValue(target)
      return
    }
    let frame = 0
    const t0 = performance.now()
    const tick = (now: number) => {
      const t = Math.min(1, (now - t0) / duration)
      const eased = 1 - Math.pow(1 - t, 3)
      shown.current = Math.round(from + (target - from) * eased)
      setValue(shown.current)
      if (t < 1) frame = requestAnimationFrame(tick)
    }
    shown.current = from
    setValue(from)
    frame = requestAnimationFrame(tick)
    return () => cancelAnimationFrame(frame)
  }, [target, duration])
  return value
}
