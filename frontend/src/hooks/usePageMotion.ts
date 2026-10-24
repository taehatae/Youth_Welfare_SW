import { useLayoutEffect, useRef } from "react"

// Content is visible by default. Only an active observer opts elements into motion.
export function usePageMotion(routeKey: string) {
  const root = useRef<HTMLElement>(null)
  useLayoutEffect(() => {
    const container = root.current
    if (!container || !("IntersectionObserver" in window)) return
    const seen = new WeakSet<Element>()
    const pending = new Set<HTMLElement>()
    const show = (element: HTMLElement) => {
      element.classList.remove("reveal-pending")
      pending.delete(element)
      observer.unobserve(element)
    }
    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting) show(entry.target as HTMLElement)
        })
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
          show(element)
        element = element.parentElement
      }
    }
    const mutations = new MutationObserver(scan)
    scan()
    mutations.observe(container, { childList: true, subtree: true })
    container.addEventListener("focusin", revealFocused)
    return () => {
      mutations.disconnect()
      pending.forEach(show)
      observer.disconnect()
      container.removeEventListener("focusin", revealFocused)
    }
  }, [routeKey])
  return root
}
