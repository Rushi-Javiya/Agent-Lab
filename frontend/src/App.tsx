import { NavLink, Route, Routes } from 'react-router-dom'

import { HealthProvider, ProviderStatus } from './components/health'
import { AgentDetailPage } from './pages/AgentDetailPage'
import { AgentsPage } from './pages/AgentsPage'
import { BenchmarksPage } from './pages/BenchmarksPage'
import { ComparePage } from './pages/ComparePage'
import { DataPage } from './pages/DataPage'
import { EvalRunPage } from './pages/EvalRunPage'
import { EvalsPage } from './pages/EvalsPage'

function NotFound() {
  return <div className="notice">Page not found.</div>
}

export default function App() {
  return (
    <HealthProvider>
      <header className="topbar">
        <div className="brand">Agent Lab</div>
        <nav>
          <NavLink to="/" end>
            Agents
          </NavLink>
          <NavLink to="/evals">Evaluations</NavLink>
          <NavLink to="/benchmarks">Benchmark</NavLink>
          <NavLink to="/data">Data</NavLink>
        </nav>
        <ProviderStatus />
      </header>
      <main>
        <Routes>
          <Route path="/" element={<AgentsPage />} />
          <Route path="/agents/:slug" element={<AgentDetailPage />} />
          <Route path="/evals" element={<EvalsPage />} />
          <Route path="/evals/compare" element={<ComparePage />} />
          <Route path="/evals/:id" element={<EvalRunPage />} />
          <Route path="/benchmarks" element={<BenchmarksPage />} />
          <Route path="/data" element={<DataPage />} />
          <Route path="*" element={<NotFound />} />
        </Routes>
      </main>
    </HealthProvider>
  )
}
