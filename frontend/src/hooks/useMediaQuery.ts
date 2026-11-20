import { useEffect, useState } from "react"

const supported = () =>
  typeof window !== "undefined" && typeof window.matchMedia === "function"

export function useMediaQuery(query: string): boolean {
  const [matches, setMatches] = useState(() =>
    supported() ? window.matchMedia(query).matches : false,
  )
  useEffect(() => {
    if (!supported()) return
    const media = window.matchMedia(query)
    const update = () => setMatches(media.matches)
    update()
    media.addEventListener("change", update)
    return () => media.removeEventListener("change", update)
  }, [query])
  return matches
}
