import type { Page } from "../../types/page"

import { BrandLogo } from "../brand/BrandLogo"
import type { Account } from "../../services/welfareApi"

export default function Navigation({
  page,
  setPage,
  account,
  busy,
  onLogin,
  onLogout,
}: {
  page: Page
  setPage: (p: Page) => void
  account: Account | null
  busy: boolean
  onLogin: () => void
  onLogout: () => void
}) {
  const links: Array<{ id: Page; label: string }> = [
    { id: "home", label: "홈" },

    { id: "explorer", label: "정책 찾기" },

    { id: "diagnosis", label: "자격 진단" },

    { id: "result", label: "진단 결과" },

    { id: "dashboard", label: "나의 현황" },
  ]

  return (
    <>
      <nav className="sticky top-0 z-50 bg-white border-b border-[var(--line)]">
        <div className="max-w-6xl mx-auto px-4 sm:px-6">
          <div className="flex items-center justify-between min-h-[72px] gap-3">
            <a
              href="#home"
              onClick={() => setPage("home")}
              className="interface-nav-brand flex shrink-0 items-center rounded-full focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--accent)]"
              aria-label="자격있청 홈으로"
            >
              <BrandLogo />
            </a>

            <div className="hidden lg:flex items-center gap-1">
              {links.map((l) => (
                <button
                  key={l.id}
                  aria-current={page === l.id ? "page" : undefined}
                  onClick={() => setPage(l.id)}
                  className={`rounded-full px-4 py-2 text-sm font-bold transition-colors focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--accent)] ${
                    page === l.id
                      ? "bg-[var(--accent-soft)] text-[var(--accent-ink)]"
                      : "text-[var(--sub)] hover:bg-[var(--bg)] hover:text-[var(--ink)]"
                  }`}
                >
                  {l.label}
                </button>
              ))}
            </div>

            <div className="flex items-center gap-2">
              {account && <span className="auth-name" title={account.display_name}>{account.display_name}님</span>}
              <button type="button" className="interface-login-button" disabled={busy} onClick={account ? onLogout : onLogin} aria-haspopup={account ? undefined : "dialog"}>{account ? "로그아웃" : "로그인"}</button>
              <button
                onClick={() => setPage("diagnosis")}
                className="bg-[var(--ink)] text-white text-sm font-bold px-3 sm:px-5 py-2.5 rounded-full hover:bg-[var(--ink-hover)] transition-colors whitespace-nowrap focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--accent)]"
              >
                진단 시작 <span className="hidden sm:inline" aria-hidden="true">→</span>
              </button>
            </div>
          </div>
        </div>
      </nav>

      {/* Mobile bottom nav */}
      <div className="lg:hidden fixed bottom-0 left-0 right-0 bg-white border-t border-[var(--line)] flex z-50 px-2 pb-1 pt-1">
        {[
          { id: "home" as Page, icon: "🏠", label: "홈" },

          { id: "explorer" as Page, icon: "🔍", label: "정책" },

          { id: "diagnosis" as Page, icon: "📋", label: "진단" },

          { id: "result" as Page, icon: "📊", label: "결과" },

          { id: "dashboard" as Page, icon: "👤", label: "현황" },
        ].map((l) => (
          <button
            key={l.id}
            aria-current={page === l.id ? "page" : undefined}
            onClick={() => setPage(l.id)}
            className={`flex-1 flex flex-col items-center gap-0.5 py-2 mx-0.5 rounded-2xl text-[10px] font-extrabold transition-colors focus-visible:outline-2 focus-visible:outline-[var(--accent)] ${
              page === l.id ? "bg-[var(--accent-soft)] text-[var(--accent-ink)]" : "text-[var(--sub)]"
            }`}
          >
            <span className="text-xl leading-none">{l.icon}</span>
            {l.label}
          </button>
        ))}
      </div>
    </>
  )
}
