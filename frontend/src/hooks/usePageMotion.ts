import { useLayoutEffect, useRef } from "react"

// Content is visible by default. Only an active observer opts elements into motion.
export function usePageMotion(routeKey: string) {
  const root = useRef<HTMLElement>(null)
  useLayoutEffect(() => {
    const container = root.current
    if (!container || !("IntersectionObserver" in window)) return
    const seen = new WeakSet<Element>()
    const pending = new Set<HTMLElement>()
    const timers = new Set<number>()
    // 등장이 끝나면 reveal-ready를 떼어 hover 전환이 지연되지 않게 한다.
    const settle = (element: HTMLElement, ms: number) => {
      const timer = window.setTimeout(() => {
        timers.delete(timer)
        element.classList.remove("reveal-ready")
        element.style.removeProperty("--reveal-i")
      }, ms)
      timers.add(timer)
    }
    const show = (element: HTMLElement, order?: number) => {
      if (order !== undefined) {
        element.style.setProperty("--reveal-i", String(Math.min(order, 8)))
        settle(element, 480 + Math.min(order, 8) * 60 + 80)
      } else element.classList.remove("reveal-ready")
      pending.delete(element)
      observer.unobserve(element)
      if (order === undefined) {
        element.classList.remove("reveal-pending")
        return
      }
      // 숨긴 상태가 한 번 그려진 뒤에 풀어야 전환이 실제로 보인다(같은 프레임이면 바로 나타남).
      requestAnimationFrame(() =>
        requestAnimationFrame(() => element.classList.remove("reveal-pending")),
      )
    }
    const observer = new IntersectionObserver(
      (entries) => {
        // 같은 때 보이게 된 요소는 문서 순서대로 60ms 간격으로 등장한다.
        entries
          .filter((entry) => entry.isIntersecting)
          .map((entry) => entry.target as HTMLElement)
          .sort((a, b) =>
            a.compareDocumentPosition(b) & Node.DOCUMENT_POSITION_FOLLOWING ? -1 : 1,
          )
          .forEach((element, order) => show(element, order))
      },
      { threshold: 0, rootMargin: "0px 0px -20px 0px" },
    )
    const scan = () => {
      // Remove detached nodes when search filters or diagnosis steps change.
      pending.forEach((element) => {
        if (!container.contains(element)) show(element)
      })
      container
        .querySelectorAll<HTMLElement>("[data-reveal]")
        .forEach((element) => {
          if (seen.has(element)) return
          seen.add(element)
          if (element.contains(document.activeElement)) return
          element.classList.add("reveal-ready", "reveal-pending")
          pending.add(element)
          observer.observe(element)
        })
    }
    const revealFocused = (event: FocusEvent) => {
      if (!(event.target instanceof Element)) return
      let element: Element | null = event.target
      while (element && container.contains(element)) {
        if (element instanceof HTMLElement && pending.has(element))
          show(element, 0)
        element = element.parentElement
      }
    }
    const mutations = new MutationObserver(scan)
    scan()
    mutations.observe(container, { childList: true, subtree: true })
    container.addEventListener("focusin", revealFocused)
    return () => {
      mutations.disconnect()
      timers.forEach((timer) => window.clearTimeout(timer))
      pending.forEach((element) => show(element))
      observer.disconnect()
      container.removeEventListener("focusin", revealFocused)
    }
  }, [routeKey])
  return root
}
