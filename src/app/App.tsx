import { useState } from 'react'
import Navigation from '../components/layout/Navigation'
import { POLICIES } from '../data/policies'
import type { Page } from '../types/page'
import type { Policy } from '../types/policy'
import HomePage from '../features/home/HomePage'
import PolicyExplorerPage from '../features/policies/PolicyExplorerPage'
import PolicyDetailPage from '../features/policies/PolicyDetailPage'
import DiagnosisPage from '../features/diagnosis/DiagnosisPage'
import ResultPage from '../features/diagnosis/ResultPage'
import DashboardPage from '../features/dashboard/DashboardPage'

export default function App() {
  const [page, setPage] = useState<Page>('home')
  const [selectedPolicy, setSelectedPolicy] = useState<Policy>(POLICIES[0])

  return (
    <div className="min-h-screen bg-white">
      <Navigation page={page} setPage={setPage} />
      <main>
        {page === 'home'      && <HomePage setPage={setPage} setSelectedPolicy={setSelectedPolicy} />}
        {page === 'explorer'  && <PolicyExplorerPage setPage={setPage} setSelectedPolicy={setSelectedPolicy} />}
        {page === 'detail'    && <PolicyDetailPage policy={selectedPolicy} setPage={setPage} />}
        {page === 'diagnosis' && <DiagnosisPage setPage={setPage} />}
        {page === 'result'    && <ResultPage setPage={setPage} setSelectedPolicy={setSelectedPolicy} />}
        {page === 'dashboard' && <DashboardPage setPage={setPage} setSelectedPolicy={setSelectedPolicy} />}
      </main>
    </div>
  )
}
