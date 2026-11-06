import { useState } from 'react'
import type { FormEvent } from 'react'
import { Link, useParams } from 'react-router-dom'

import { api } from '../api'
import { ConfigFields } from '../components/ConfigFields'
import { ErrorBox, RunView, ScoreBar, Spinner, StatusBadge } from '../components/ui'
import { modelLabel, shortDate } from '../lib/format'
import { useAsync } from '../lib/hooks'
import type { AgentConfig, AgentRun } from '../types'

const EXAMPLES = [
  'Why did we lose the Nordgrid Utilities deal?',
  'How many deals did we lose?',
  'List the deals we won in Central Europe',
  'How often should transformer oil be sampled?',
  'Why did Tasman Networks choose VoltEdge?',
  "What is the CEO's salary?",
]

export function AgentDetailPage() {
  const { slug = '' } = useParams()
  const agent = useAsync(() => api.agent(slug), [slug])
  const runs = useAsync(() => api.agentRuns(slug), [slug])

  const [versionNumber, setVersionNumber] = useState<number | undefined>(undefined)
  const [question, setQuestion] = useState(EXAMPLES[0])
  const [result, setResult] = useState<AgentRun | null>(null)
  const [asking, setAsking] = useState(false)
  const [askError, setAskError] = useState<string | null>(null)

  const [draft, setDraft] = useState<AgentConfig | null>(null)
  const [note, setNote] = useState('')
  const [saveError, setSaveError] = useState<string | null>(null)

  if (agent.loading && !agent.data) return <Spinner />
  if (agent.error) return <ErrorBox message={agent.error} />
  if (!agent.data) return null
  const data = agent.data
  const selected = versionNumber ?? data.versions[data.versions.length - 1].version

  const ask = async (event: FormEvent) => {
    event.preventDefault()
    setAsking(true)
    setAskError(null)
    try {
      setResult(await api.runAgent(slug, question, selected))
      runs.reload()
    } catch (exc) {
      setAskError(exc instanceof Error ? exc.message : String(exc))
    } finally {
      setAsking(false)
    }
  }

  const saveVersion = async (event: FormEvent) => {
    event.preventDefault()
    if (!draft) return
    setSaveError(null)
    try {
      const created = await api.createVersion(slug, draft, note)
      setDraft(null)
      setNote('')
      setVersionNumber(created.version)
      agent.reload()
    } catch (exc) {
      setSaveError(exc instanceof Error ? exc.message : String(exc))
    }
  }

  return (
    <>
      <div className="page-head">
        <h1>{data.name}</h1>
        <div className="muted">{data.description}</div>
      </div>

      <div className="card">
        <div className="row between">
          <h2>Versions</h2>
          <Link to="/evals">Run an evaluation →</Link>
        </div>
        <table>
          <thead>
            <tr>
              <th>Version</th>
              <th>Model</th>
              <th>Router</th>
              <th>Top k</th>
              <th>Retries</th>
              <th>Note</th>
              <th>Latest eval</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {data.versions.map((v) => (
              <tr key={v.id}>
                <td>v{v.version}</td>
                <td>{modelLabel(v.config)}</td>
                <td>{v.config.router}</td>
                <td>{v.config.top_k}</td>
                <td>{v.config.max_retries}</td>
                <td className="small">{v.note}</td>
                <td>
                  {v.latest_eval ? (
                    <Link to={`/evals/${v.latest_eval.run_id}`}>
                      <ScoreBar value={v.latest_eval.mean_score} />
                    </Link>
                  ) : (
                    <span className="muted small">not evaluated</span>
                  )}
                </td>
                <td>
                  <button className="link" onClick={() => setDraft({ ...v.config })}>
                    use as template
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>

        {draft && (
          <form onSubmit={saveVersion} style={{ marginTop: '1rem' }}>
            <h3>New version</h3>
            <ErrorBox message={saveError} />
            <ConfigFields value={draft} onChange={setDraft} />
            <label style={{ marginBottom: '0.75rem' }}>
              Note (what changed and why)
              <input type="text" value={note} onChange={(event) => setNote(event.target.value)} />
            </label>
            <div className="row">
              <button className="primary" type="submit">
                Save as v{data.versions.length + 1}
              </button>
              <button type="button" onClick={() => setDraft(null)}>
                Cancel
              </button>
            </div>
          </form>
        )}
      </div>

      <div className="card">
        <h2>Playground</h2>
        <form onSubmit={ask}>
          <div className="row" style={{ marginBottom: '0.6rem' }}>
            <label className="inline">
              Version
              <select
                value={selected}
                onChange={(event) => setVersionNumber(Number(event.target.value))}
              >
                {data.versions.map((v) => (
                  <option key={v.id} value={v.version}>
                    v{v.version} · {modelLabel(v.config)}
                  </option>
                ))}
              </select>
            </label>
          </div>
          <div className="row">
            <input
              type="text"
              style={{ flex: 1 }}
              value={question}
              onChange={(event) => setQuestion(event.target.value)}
              placeholder="Ask a question about the win/loss reports or the manuals"
            />
            <button className="primary" type="submit" disabled={asking || !question.trim()}>
              {asking ? 'Thinking…' : 'Ask'}
            </button>
          </div>
        </form>
        <div style={{ margin: '0.6rem 0' }}>
          {EXAMPLES.map((example) => (
            <button
              key={example}
              className="link small"
              style={{ marginRight: '0.9rem' }}
              onClick={() => setQuestion(example)}
            >
              {example}
            </button>
          ))}
        </div>
        <ErrorBox message={askError} />
        {asking && <Spinner />}
        {result && !asking && <RunView run={result} />}
      </div>

      <div className="card">
        <h2>Recent runs</h2>
        {runs.data?.length === 0 && <div className="muted">No runs yet.</div>}
        <table>
          <tbody>
            {runs.data?.map((run) => (
              <tr key={run.id} className="clickable" onClick={() => setResult(run)}>
                <td className="small muted">{shortDate(run.created_at)}</td>
                <td>v{run.version}</td>
                <td>{run.question}</td>
                <td>
                  <StatusBadge status={run.status} />
                </td>
                <td className="num small">{run.latency_ms} ms</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  )
}
