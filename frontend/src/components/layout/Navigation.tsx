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
      <nav className="sticky top-0 z-50 bg-white border-b-2 border-slate-900">
        <div className="max-w-6xl mx-auto px-4 sm:px-6">
          <div className="flex items-center justify-between min-h-[72px] gap-3">
            <a
              href="#home"
              onClick={() => setPage("home")}
              className="interface-nav-brand flex shrink-0 items-center rounded-md focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue-600"
              aria-label="자격있청 홈으로"
            >
              <BrandLogo />
            </a>

            <div className="hidden lg:flex items-center">
              {links.map((l) => (
                <button
                  key={l.id}
                  aria-current={page === l.id ? "page" : undefined}
                  onClick={() => setPage(l.id)}
                  className={`relative px-4 py-4 text-sm font-bold transition-colors ${
                    page === l.id
                      ? "text-blue-600"
                      : "text-slate-500 hover:text-slate-900"
                  }`}
                >
                  {l.label}
                  {page === l.id && (
                    <span className="absolute bottom-0 left-2 right-2 h-0.5 bg-blue-600 rounded-full" />
                  )}
                </button>
              ))}
            </div>

            <div className="flex items-center gap-2">
              {account && <span className="auth-name" title={account.display_name}>{account.display_name}님</span>}
              <button type="button" className="interface-login-button" disabled={busy} onClick={account ? onLogout : onLogin} aria-haspopup={account ? undefined : "dialog"}>{account ? "로그아웃" : "로그인"}</button>
              <button
                onClick={() => setPage("diagnosis")}
                className="bg-slate-900 text-white text-sm font-semibold px-3 sm:px-4 py-2 rounded-lg hover:bg-blue-700 transition-colors whitespace-nowrap"
              >
                진단 시작 <span className="hidden sm:inline" aria-hidden="true">→</span>
              </button>
            </div>
          </div>
        </div>
      </nav>

      {/* Mobile bottom nav */}
      <div className="lg:hidden fixed bottom-0 left-0 right-0 bg-white border-t border-slate-300 flex z-50">
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
            className={`flex-1 flex flex-col items-center gap-0.5 py-3 text-[10px] font-black transition-colors ${
              page === l.id ? "text-blue-600" : "text-slate-400"
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
