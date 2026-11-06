import { useState } from 'react'
import type { FormEvent } from 'react'
import { Link, useNavigate } from 'react-router-dom'

import { api } from '../api'
import { ErrorBox, ScoreBar, Spinner, StatusBadge } from '../components/ui'
import { milliseconds, modelLabel, shortDate } from '../lib/format'
import { useAsync, usePolling } from '../lib/hooks'

export function EvalsPage() {
  const navigate = useNavigate()
  const agents = useAsync(() => api.agents(), [])
  const datasets = useAsync(() => api.datasets(), [])
  const runs = useAsync(() => api.evalRuns(), [])

  const [agentSlug, setAgentSlug] = useState('')
  const [version, setVersion] = useState<number | undefined>(undefined)
  const [datasetSlug, setDatasetSlug] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [starting, setStarting] = useState(false)
  const [picked, setPicked] = useState<number[]>([])

  const anyActive = runs.data?.some((r) => r.status === 'queued' || r.status === 'running') ?? false
  usePolling(runs.reload, anyActive)

  const agent = agents.data?.find((a) => a.slug === (agentSlug || agents.data?.[0]?.slug))
  const chosenAgent = agent?.slug ?? ''
  const chosenDataset = datasetSlug || datasets.data?.[0]?.slug || ''

  const agentDetail = useAsync(
    () => (chosenAgent ? api.agent(chosenAgent) : Promise.resolve(null)),
    [chosenAgent],
  )

  const start = async (event: FormEvent) => {
    event.preventDefault()
    setStarting(true)
    setError(null)
    try {
      const run = await api.startEval({ dataset: chosenDataset, agent: chosenAgent, version })
      navigate(`/evals/${run.id}`)
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : String(exc))
    } finally {
      setStarting(false)
    }
  }

  const toggle = (id: number) =>
    setPicked((current) =>
      current.includes(id) ? current.filter((x) => x !== id) : [...current, id].slice(-2),
    )

  return (
    <>
      <div className="page-head">
        <h1>Evaluations</h1>
        <div className="muted">
          Run an agent version on a dataset and score it with deterministic metrics: fact
          coverage, citation validity and recall, tool choice, refusals and latency.
        </div>
      </div>

      <form className="card" onSubmit={start}>
        <h2>New evaluation run</h2>
        <ErrorBox message={error} />
        <div className="form-grid">
          <label>
            Agent
            <select
              value={chosenAgent}
              onChange={(event) => {
                setAgentSlug(event.target.value)
                setVersion(undefined)
              }}
            >
              {agents.data?.map((a) => (
                <option key={a.id} value={a.slug}>
                  {a.name}
                </option>
              ))}
            </select>
          </label>
          <label>
            Version
            <select
              value={version ?? ''}
              onChange={(event) =>
                setVersion(event.target.value ? Number(event.target.value) : undefined)
              }
            >
              <option value="">latest</option>
              {agentDetail.data?.versions.map((v) => (
                <option key={v.id} value={v.version}>
                  v{v.version} · {modelLabel(v.config)}
                </option>
              ))}
            </select>
          </label>
          <label>
            Dataset
            <select value={chosenDataset} onChange={(event) => setDatasetSlug(event.target.value)}>
              {datasets.data?.map((d) => (
                <option key={d.id} value={d.slug}>
                  {d.name} ({d.case_count} cases)
                </option>
              ))}
            </select>
          </label>
        </div>
        <button className="primary" type="submit" disabled={starting || !chosenAgent}>
          {starting ? 'Starting…' : 'Start run'}
        </button>
      </form>

      <div className="card">
        <div className="row between">
          <h2>Runs</h2>
          <button
            className="primary"
            disabled={picked.length !== 2}
            onClick={() => navigate(`/evals/compare?baseline=${picked[0]}&candidate=${picked[1]}`)}
          >
            Compare selected ({picked.length}/2)
          </button>
        </div>
        {runs.loading && !runs.data && <Spinner />}
        <ErrorBox message={runs.error} />
        {runs.data?.length === 0 && <div className="muted">No runs yet.</div>}
        <table>
          <thead>
            <tr>
              <th />
              <th>Run</th>
              <th>Agent</th>
              <th>Model</th>
              <th>Status</th>
              <th>Score</th>
              <th>Pass rate</th>
              <th className="num">Mean latency</th>
              <th>Started</th>
            </tr>
          </thead>
          <tbody>
            {runs.data?.map((run) => (
              <tr key={run.id}>
                <td>
                  <input
                    type="checkbox"
                    checked={picked.includes(run.id)}
                    disabled={run.status !== 'completed'}
                    onChange={() => toggle(run.id)}
                  />
                </td>
                <td>
                  <Link to={`/evals/${run.id}`}>#{run.id}</Link>
                </td>
                <td>
                  {run.agent.name} v{run.version}
                </td>
                <td className="small">{modelLabel(run.config)}</td>
                <td>
                  <StatusBadge status={run.status} />
                  {run.status === 'running' && (
                    <span className="muted small">
                      {' '}
                      {run.progress.done}/{run.progress.total}
                    </span>
                  )}
                </td>
                <td>
                  <ScoreBar value={run.summary.mean_score} />
                </td>
                <td>
                  <ScoreBar value={run.summary.pass_rate} />
                </td>
                <td className="num">{milliseconds(run.summary.mean_latency_ms)}</td>
                <td className="small muted">{shortDate(run.created_at)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  )
}
