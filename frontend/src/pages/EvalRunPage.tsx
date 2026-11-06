import { Fragment, useState } from 'react'
import { Link, useParams } from 'react-router-dom'

import { api } from '../api'
import { ErrorBox, ScoreBar, Spinner, Stat, StatusBadge, TraceView } from '../components/ui'
import { milliseconds, modelLabel, percent, score } from '../lib/format'
import { useAsync, usePolling } from '../lib/hooks'

const METRIC_LABELS: Record<string, string> = {
  fact_coverage: 'Fact coverage',
  citation_valid: 'Citation valid',
  citation_recall: 'Citation recall',
  tool_correct: 'Tool correct',
  retrieval_recall: 'Retrieval recall',
  refusal_correct: 'Refusal correct',
}

export function EvalRunPage() {
  const { id = '' } = useParams()
  const run = useAsync(() => api.evalRun(Number(id)), [id])
  const [failedOnly, setFailedOnly] = useState(false)
  const [open, setOpen] = useState<string | null>(null)

  const active = run.data?.status === 'queued' || run.data?.status === 'running'
  usePolling(run.reload, active)

  if (run.loading && !run.data) return <Spinner />
  if (run.error) return <ErrorBox message={run.error} />
  if (!run.data) return null
  const data = run.data
  const summary = data.summary
  const results = (data.results ?? []).filter((r) => !failedOnly || !r.passed)

  return (
    <>
      <div className="page-head">
        <div className="muted small">
          <Link to="/evals">Evaluations</Link> / run #{data.id}
        </div>
        <h1>
          {data.agent.name} v{data.version} <StatusBadge status={data.status} />
        </h1>
        <div className="muted">
          {modelLabel(data.config)} on {data.dataset.name}
        </div>
      </div>

      {active && (
        <div className="notice">
          Running… {data.progress.done}/{data.progress.total} cases <Spinner />
        </div>
      )}
      <ErrorBox message={data.error} />

      {data.status === 'completed' && (
        <>
          <div className="grid cols-4" style={{ marginBottom: '1rem' }}>
            <Stat label="Mean score" value={score(summary.mean_score)} />
            <Stat label="Pass rate" value={percent(summary.pass_rate)} />
            <Stat label="Mean latency" value={milliseconds(summary.mean_latency_ms)} />
            <Stat label="p95 latency" value={milliseconds(summary.p95_latency_ms)} />
          </div>

          <div className="grid cols-2">
            <div className="card">
              <h2>Metrics</h2>
              <table>
                <tbody>
                  {Object.entries(summary.metrics ?? {}).map(([name, value]) => (
                    <tr key={name}>
                      <td>{METRIC_LABELS[name] ?? name}</td>
                      <td>
                        <ScoreBar value={value} />
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <div className="card">
              <h2>Outcomes</h2>
              <table>
                <tbody>
                  {Object.entries(summary.statuses ?? {}).map(([name, count]) => (
                    <tr key={name}>
                      <td>
                        <StatusBadge status={name as 'answered'} />
                      </td>
                      <td className="num">{count}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
              <div className="muted small">
                answered = grounded answer, refused = said it cannot find it, rejected = the
                citation check blocked the answer
              </div>
            </div>
          </div>
        </>
      )}

      <div className="card">
        <div className="row between">
          <h2>Cases</h2>
          <label className="inline">
            <input
              type="checkbox"
              checked={failedOnly}
              onChange={(event) => setFailedOnly(event.target.checked)}
            />
            failed only
          </label>
        </div>
        <table>
          <thead>
            <tr>
              <th>Case</th>
              <th>Question</th>
              <th>Outcome</th>
              <th>Score</th>
              <th className="num">Latency</th>
            </tr>
          </thead>
          <tbody>
            {results.map((r) => (
              <Fragment key={r.case_id}>
                <tr
                  className="clickable"
                  onClick={() => setOpen(open === r.case_id ? null : r.case_id)}
                >
                  <td className="small">{r.case_id}</td>
                  <td>{r.question}</td>
                  <td>
                    <StatusBadge status={r.status} />
                  </td>
                  <td>
                    <ScoreBar value={r.score} />
                  </td>
                  <td className="num">{milliseconds(r.latency_ms)}</td>
                </tr>
                {open === r.case_id && (
                  <tr>
                    <td colSpan={5}>
                      <div className="answer">{r.answer || '(no answer)'}</div>
                      {r.error && <ErrorBox message={r.error} />}
                      <div className="small">
                        {Object.entries(r.metrics).map(([name, value]) => (
                          <span key={name} className="chip">
                            {name}: {value.toFixed(2)}
                          </span>
                        ))}
                      </div>
                      <TraceView steps={r.tool_calls} />
                    </td>
                  </tr>
                )}
              </Fragment>
            ))}
          </tbody>
        </table>
      </div>
    </>
  )
}
