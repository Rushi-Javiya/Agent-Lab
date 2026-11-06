import { Link, useSearchParams } from 'react-router-dom'

import { api } from '../api'
import { ErrorBox, ScoreBar, Spinner, Stat, StatusBadge } from '../components/ui'
import { modelLabel, score, signed } from '../lib/format'
import { useAsync } from '../lib/hooks'

export function ComparePage() {
  const [params] = useSearchParams()
  const baseline = Number(params.get('baseline'))
  const candidate = Number(params.get('candidate'))
  const comparison = useAsync(() => api.compare(baseline, candidate), [baseline, candidate])

  if (!baseline || !candidate) {
    return (
      <div className="notice">
        Pick two completed runs on the <Link to="/evals">Evaluations</Link> page.
      </div>
    )
  }
  if (comparison.loading && !comparison.data) return <Spinner />
  if (comparison.error) return <ErrorBox message={comparison.error} />
  if (!comparison.data) return null
  const data = comparison.data
  const names = new Map(data.cases.map((c) => [c.case_id, c]))

  return (
    <>
      <div className="page-head">
        <div className="muted small">
          <Link to="/evals">Evaluations</Link> / compare
        </div>
        <h1>Baseline vs candidate</h1>
        <div className="muted">
          Same dataset, case by case. A regression is a case that passed before and fails now.
        </div>
      </div>

      <div className="grid cols-4" style={{ marginBottom: '1rem' }}>
        <Stat label={`Baseline #${data.baseline.id}`} value={score(data.mean_score_a)} />
        <Stat label={`Candidate #${data.candidate.id}`} value={score(data.mean_score_b)} />
        <Stat label="Mean change" value={signed(data.mean_delta)} />
        <Stat label="Regressions" value={String(data.regressions.length)} />
      </div>

      <div className="grid cols-2">
        {[data.baseline, data.candidate].map((run, index) => (
          <div className="card" key={run.id}>
            <div className="muted small">{index === 0 ? 'Baseline' : 'Candidate'}</div>
            <h2>
              {run.agent.name} v{run.version}
            </h2>
            <div className="muted small">{modelLabel(run.config)}</div>
          </div>
        ))}
      </div>

      <div className="card">
        <h2>Cases</h2>
        <table>
          <thead>
            <tr>
              <th>Question</th>
              <th>Baseline</th>
              <th>Candidate</th>
              <th className="num">Change</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {[...data.cases]
              .sort((a, b) => a.delta - b.delta)
              .map((c) => (
                <tr key={c.case_id}>
                  <td>
                    {names.get(c.case_id)?.question}
                    <div className="muted small">{c.case_id}</div>
                  </td>
                  <td>
                    <ScoreBar value={c.score_a} />
                  </td>
                  <td>
                    <ScoreBar value={c.score_b} /> <StatusBadge status={c.status_b} />
                  </td>
                  <td className={`num ${c.delta < 0 ? 'delta-neg' : c.delta > 0 ? 'delta-pos' : ''}`}>
                    {signed(c.delta)}
                  </td>
                  <td>
                    {data.regressions.includes(c.case_id) && <span className="badge bad">regression</span>}
                    {data.improvements.includes(c.case_id) && (
                      <span className="badge good">improved</span>
                    )}
                  </td>
                </tr>
              ))}
          </tbody>
        </table>
      </div>
    </>
  )
}
