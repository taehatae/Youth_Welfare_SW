import { useEffect, useRef, type MouseEvent } from "react"
import QuickFinderPage from "./QuickFinderPage"
import "./quick-widget.css"

// 화면 오른쪽 아래에 떠 있는 간편 정책 찾기 채팅. 닫아도 대화는 그대로 남는다.
export default function QuickChatWidget({ open, onOpenChange, hidden, onDiagnosis }: {
  open: boolean
  onOpenChange: (open: boolean) => void
  hidden: boolean
  onDiagnosis: () => void
}) {
  const button = useRef<HTMLButtonElement>(null)
  const panel = useRef<HTMLDivElement>(null)
  const wasOpen = useRef(false)
  const visible = open && !hidden

  useEffect(() => {
    if (hidden && open) onOpenChange(false)
  }, [hidden, open, onOpenChange])

  useEffect(() => {
    if (visible) panel.current?.focus()
    else if (wasOpen.current && !hidden) button.current?.focus()
    wasOpen.current = visible
  }, [visible, hidden])

  useEffect(() => {
    if (!visible) return
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") onOpenChange(false) }
    document.addEventListener("keydown", onKey)
    return () => document.removeEventListener("keydown", onKey)
  }, [visible, onOpenChange])

  const fullScreen = () => { onOpenChange(false); window.location.hash = "quick" }
  const onPanelClick = (e: MouseEvent) => {
    const link = (e.target as HTMLElement).closest("a")
    if (link?.getAttribute("href")?.startsWith("#detail")) onOpenChange(false)
  }

  return <div className="quick-widget" data-open={visible} data-hidden={hidden}>
    {visible && <div className="quick-widget-backdrop" onClick={() => onOpenChange(false)} aria-hidden="true" />}
    <div ref={panel} id="quick-widget-panel" className="quick-widget-panel" role="dialog" aria-modal="false"
      aria-labelledby="quick-widget-title" tabIndex={-1} hidden={!visible} onClick={onPanelClick}>
      <header className="quick-widget-head">
        <span className="quick-avatar" aria-hidden="true">청</span>
        <div className="quick-widget-titles">
          <h2 id="quick-widget-title">간편 정책 찾기</h2>
          <p>로그인 없이 버튼으로 답해요</p>
        </div>
        <button type="button" className="quick-widget-text-btn" onClick={fullScreen}>전체 화면</button>
        <button type="button" className="quick-widget-close" aria-label="닫기" onClick={() => onOpenChange(false)}>
          <span aria-hidden="true">×</span>
        </button>
      </header>
      <div className="quick-widget-scroll">
        <QuickFinderPage variant="widget" onDiagnosis={onDiagnosis} />
      </div>
    </div>
    {!hidden && <>
      {!open && <span className="quick-widget-label" aria-hidden="true" onClick={() => onOpenChange(true)}>궁금한 정책, 여기서 물어보세요!</span>}
      <button ref={button} type="button" className="quick-widget-fab"
        aria-label="간편 정책 찾기 열기" aria-expanded={visible} aria-controls="quick-widget-panel"
        onClick={() => onOpenChange(!open)}>
        <svg viewBox="0 0 24 24" width="28" height="28" fill="none" aria-hidden="true">
          <path d="M5 4h14a2 2 0 0 1 2 2v9a2 2 0 0 1-2 2h-7l-4.5 3.5V17H5a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2Z" fill="currentColor" />
          <circle cx="8.5" cy="10.5" r="1.1" fill="var(--ink)" /><circle cx="12" cy="10.5" r="1.1" fill="var(--ink)" /><circle cx="15.5" cy="10.5" r="1.1" fill="var(--ink)" />
        </svg>
      </button>
    </>}
  </div>
}
