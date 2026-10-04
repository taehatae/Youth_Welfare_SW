export default function DownloadPage() {
  return (
    <main className="min-h-screen bg-slate-900 flex items-center justify-center p-6">
      <section className="w-full max-w-lg text-center bg-slate-800 border border-slate-700 rounded-2xl p-8">
        <div className="text-4xl mb-4">📁</div>
        <h1 className="text-2xl font-black text-white mb-2">자격있청 프로젝트 소스</h1>
        <p className="text-slate-400 text-sm mb-6">GitHub에서 전체 프로젝트 파일과 라이선스 안내를 확인하고 다운로드할 수 있어요.</p>
        <a href="https://github.com/taehatae/Youth_Welfare_SW/archive/refs/heads/Jang.zip" className="block bg-blue-600 text-white font-black py-4 px-6 rounded-xl hover:bg-blue-500 mb-3">전체 소스 ZIP 다운로드</a>
        <a href="https://github.com/taehatae/Youth_Welfare_SW/tree/Jang" className="text-blue-300 text-sm font-bold underline">Jang 브랜치에서 파일 보기</a>
        <p className="text-slate-500 text-xs mt-6">이미지 등 제3자 자료의 라이선스는 docs/THIRD_PARTY_NOTICES.md를 확인하세요.</p>
      </section>
    </main>
  )
}
