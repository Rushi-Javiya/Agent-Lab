import { useState } from 'react'
import type { FormEvent } from 'react'

import { api } from '../api'
import { useHealth } from '../components/healthContext'
import { ErrorBox, ScoreBar, Spinner, StatusBadge } from '../components/ui'
import { milliseconds, shortDate } from '../lib/format'
import { useAsync, usePolling } from '../lib/hooks'
import { PROVIDERS } from '../types'
import type { BenchmarkRun } from '../types'

interface Target {
  provider: string
  model: string
}

function Results({ run }: { run: BenchmarkRun }) {
  const fastest = Math.max(0, ...run.results.map((r) => r.stats.tokens_per_second ?? 0))
  return (
    <table>
      <thead>
        <tr>
          <th>Model</th>
          <th className="num">Calls</th>
          <th className="num">Errors</th>
          <th className="num">p50</th>
          <th className="num">p95</th>
          <th>Tokens / s</th>
          <th>Fact coverage</th>
          <th>Grounded</th>
        </tr>
      </thead>
      <tbody>
        {run.results.map((r) => (
          <tr key={r.id}>
            <td>
              {r.provider}/{r.model}
              {r.error && <div className="small" style={{ color: 'var(--bad)' }}>{r.error}</div>}
            </td>
            <td className="num">{r.stats.calls ?? 0}</td>
            <td className="num">{r.stats.errors ?? 0}</td>
            <td className="num">{milliseconds(r.stats.latency_p50_ms)}</td>
            <td className="num">{milliseconds(r.stats.latency_p95_ms)}</td>
            <td>
              {r.stats.tokens_per_second ? (
                <ScoreBar value={r.stats.tokens_per_second / (fastest || 1)} />
              ) : (
                <span className="muted small">n/a</span>
              )}
              {r.stats.tokens_per_second ? (
                <div className="muted small">{r.stats.tokens_per_second} tok/s</div>
              ) : null}
            </td>
            <td>
              <ScoreBar value={r.stats.fact_coverage} />
            </td>
            <td>
              <ScoreBar value={r.stats.grounded_rate} />
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  )
}

export function BenchmarksPage() {
  const health = useHealth()
  const sets = useAsync(() => api.promptSets(), [])
  const history = useAsync(() => api.benchmarks(), [])

  const [targets, setTargets] = useState<Target[]>([
    { provider: 'mock', model: 'mock-extractive' },
    { provider: 'mock', model: 'mock-sloppy' },
  ])
  const [promptSet, setPromptSet] = useState('')
  const [repeats, setRepeats] = useState(1)
  const [current, setCurrent] = useState<BenchmarkRun | null>(null)
  const [error, setError] = useState<string | null>(null)

  const active = current?.status === 'queued' || current?.status === 'running'
  usePolling(async () => {
    if (!current) return
    try {
      setCurrent(await api.benchmark(current.id))
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : String(exc))
    }
  }, active)

  const update = (index: number, patch: Partial<Target>) =>
    setTargets(targets.map((t, i) => (i === index ? { ...t, ...patch } : t)))

  const addOllama = () => {
    const models = health?.providers.ollama?.models ?? []
    const known = new Set(targets.map((t) => `${t.provider}/${t.model}`))
    const extra = models
      .filter((m) => !known.has(`ollama/${m}`))
      .map((model) => ({ provider: 'ollama', model }))
    setTargets([...targets, ...extra].slice(0, 6))
  }

  const start = async (event: FormEvent) => {
    event.preventDefault()
    setError(null)
    try {
      const run = await api.startBenchmark({
        targets: targets.filter((t) => t.model.trim()),
        prompt_set: promptSet || sets.data?.[0]?.slug || 'qa-short',
        repeats,
      })
      setCurrent(run)
      history.reload()
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : String(exc))
    }
  }

  return (
    <>
      <div className="page-head">
        <h1>Model benchmark</h1>
        <div className="muted">
          Same prompts, same retrieved context, several models. Speed comes from the server
          (Ollama reports exact generation speed). Quality is fact coverage plus whether the answer
          is grounded in citations.
        </div>
      </div>

      <form className="card" onSubmit={start}>
        <h2>Models</h2>
        <ErrorBox message={error} />
        {targets.map((target, index) => (
          <div className="row" key={index} style={{ marginBottom: '0.5rem' }}>
            <select
              value={target.provider}
              onChange={(event) => update(index, { provider: event.target.value })}
            >
              {PROVIDERS.map((name) => (
                <option key={name}>{name}</option>
              ))}
            </select>
            <input
              type="text"
              list={`bench-models-${target.provider}`}
              value={target.model}
              placeholder="model name"
              onChange={(event) => update(index, { model: event.target.value })}
            />
            <datalist id={`bench-models-${target.provider}`}>
              {(health?.providers[target.provider]?.models ?? []).map((m) => (
                <option key={m} value={m} />
              ))}
            </datalist>
            <button type="button" onClick={() => setTargets(targets.filter((_, i) => i !== index))}>
              remove
            </button>
          </div>
        ))}
        <div className="row" style={{ margin: '0.75rem 0' }}>
          <button
            type="button"
            disabled={targets.length >= 6}
            onClick={() => setTargets([...targets, { provider: 'ollama', model: '' }])}
          >
            Add model
          </button>
          <button type="button" onClick={addOllama} disabled={!health?.providers.ollama?.available}>
            Add all local Ollama models
          </button>
          <span className="spacer" />
          <label className="inline">
            Prompt set
            <select value={promptSet} onChange={(event) => setPromptSet(event.target.value)}>
              {sets.data?.map((s) => (
                <option key={s.slug} value={s.slug}>
                  {s.name} ({s.prompts})
                </option>
              ))}
            </select>
          </label>
          <label className="inline">
            Repeats
            <input
              type="number"
              min={1}
              max={5}
              value={repeats}
              onChange={(event) => setRepeats(Number(event.target.value))}
            />
          </label>
        </div>
        <button className="primary" type="submit" disabled={active || targets.length === 0}>
          {active ? 'Running…' : 'Run benchmark'}
        </button>
      </form>

      {current && (
        <div className="card">
          <div className="row between">
            <h2>
              Run #{current.id} <StatusBadge status={current.status} />
            </h2>
            {active && (
              <span className="muted small">
                {current.progress.done}/{current.progress.total} calls <Spinner />
              </span>
            )}
          </div>
          <ErrorBox message={current.error} />
          <Results run={current} />
        </div>
      )}

      <div className="card">
        <h2>History</h2>
        {history.data?.length === 0 && <div className="muted">No benchmark runs yet.</div>}
        <table>
          <tbody>
            {history.data?.map((run) => (
              <tr key={run.id} className="clickable" onClick={() => setCurrent(run)}>
                <td>#{run.id}</td>
                <td className="small muted">{shortDate(run.created_at)}</td>
                <td>{run.results.map((r) => `${r.provider}/${r.model}`).join(', ')}</td>
                <td>
                  <StatusBadge status={run.status} />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  )
}
