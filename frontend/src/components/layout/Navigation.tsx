import { useState } from 'react'
import type { Page } from '../../types/page'
import { LogoMark } from '../brand/LogoMark'

export default function Navigation({ page, setPage }: { page: Page; setPage: (p: Page) => void }) {
  const [mobileOpen, setMobileOpen] = useState(false)
  const links: { id: Page; label: string }[] = [
    { id: 'home', label: '홈' },
    { id: 'explorer', label: '정책 찾기' },
    { id: 'diagnosis', label: '자격 진단' },
    { id: 'result', label: '진단 결과' },
    { id: 'dashboard', label: '나의 현황' },
  ]
  return (
    <>
      <nav className="sticky top-0 z-50 bg-white border-b-2 border-slate-900">
        <div className="max-w-6xl mx-auto px-4 sm:px-6">
          <div className="flex items-center justify-between h-14">
            <button onClick={() => setPage('home')} className="flex items-center gap-2.5">
              <LogoMark size={32} />
              <div className="flex flex-col leading-none -mt-0.5">
                <span className="text-slate-900 font-black text-lg tracking-tighter">자격있청</span>
                <span className="text-blue-600 text-[8px] font-black tracking-[0.15em] uppercase">For Youth</span>
              </div>
            </button>

            <div className="hidden md:flex items-center">
              {links.map(l => (
                <button
                  key={l.id}
                  onClick={() => setPage(l.id)}
                  className={`relative px-4 py-4 text-sm font-bold transition-colors ${
                    page === l.id ? 'text-blue-600' : 'text-slate-500 hover:text-slate-900'
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
              <button className="hidden sm:block text-sm font-bold text-slate-600 hover:text-slate-900 px-3 py-1.5 rounded-lg transition-colors">로그인</button>
              <button
                onClick={() => setPage('diagnosis')}
                className="bg-slate-900 text-white text-sm font-black px-4 py-2 rounded-lg hover:bg-blue-700 transition-colors"
              >
                진단 시작 →
              </button>
            </div>
          </div>
        </div>
      </nav>

      {/* Mobile bottom nav */}
      <div className="md:hidden fixed bottom-0 left-0 right-0 bg-white border-t-2 border-slate-900 flex z-50">
        {[
          { id: 'home' as Page, icon: '🏠', label: '홈' },
          { id: 'explorer' as Page, icon: '🔍', label: '정책' },
          { id: 'diagnosis' as Page, icon: '📋', label: '진단' },
          { id: 'dashboard' as Page, icon: '👤', label: '현황' },
        ].map(l => (
          <button
            key={l.id}
            onClick={() => setPage(l.id)}
            className={`flex-1 flex flex-col items-center gap-0.5 py-3 text-[10px] font-black transition-colors ${
              page === l.id ? 'text-blue-600' : 'text-slate-400'
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
