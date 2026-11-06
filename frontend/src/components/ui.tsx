import { Link } from 'react-router-dom'

import { percent, scoreTone } from '../lib/format'
import type { AgentRun, JobStatus, RunStatus, TraceStep } from '../types'

const STATUS_TONE: Record<string, string> = {
  answered: 'good',
  completed: 'good',
  refused: 'info',
  running: 'info',
  queued: '',
  rejected: 'warn',
  failed: 'bad',
  error: 'bad',
}

export function StatusBadge({ status }: { status: RunStatus | JobStatus }) {
  return <span className={`badge ${STATUS_TONE[status] ?? ''}`}>{status}</span>
}

export function ScoreBar({ value }: { value: number | null | undefined }) {
  const tone = scoreTone(value)
  const width = value === null || value === undefined ? 0 : Math.max(0, Math.min(1, value)) * 100
  return (
    <span className="bar">
      <span className="track">
        <span className={`fill ${tone}`} style={{ width: `${width}%` }} />
      </span>
      <span className="num">{percent(value)}</span>
    </span>
  )
}

export function Spinner() {
  return <span className="spinner" aria-label="loading" />
}

export function ErrorBox({ message }: { message: string | null }) {
  if (!message) return null
  return <div className="error">{message}</div>
}

export function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="stat">
      <div className="label">{label}</div>
      <div className="value">{value}</div>
    </div>
  )
}

export function Citations({ ids }: { ids: string[] }) {
  if (ids.length === 0) return <span className="muted small">no citations</span>
  return (
    <span>
      {ids.map((id) => (
        <Link key={id} className="chip" to={`/data?doc=${id.split('#')[0]}`}>
          {id}
        </Link>
      ))}
    </span>
  )
}

export function TraceView({ steps }: { steps: TraceStep[] }) {
  if (steps.length === 0) return null
  return (
    <div className="trace">
      {steps.map((step, index) => (
        <div className="step" key={index}>
          {step.type === 'route' && (
            <>
              <strong>route</strong> ({String(step.source)}) → <code>{String(step.tool)}</code>{' '}
              <code>{JSON.stringify(step.args)}</code>
            </>
          )}
          {step.type === 'tool' && (
            <>
              <strong>tool</strong> <code>{String(step.name)}</code>{' '}
              <code>{JSON.stringify(step.args)}</code>
              <div className="muted small">
                {String(step.summary)} · {String(step.latency_ms)} ms
              </div>
            </>
          )}
          {step.type === 'retry' && (
            <>
              <strong>retry {String(step.attempt)}</strong>
              <div className="muted small">
                rejected because: {Array.isArray(step.reason) ? step.reason.join('; ') : ''}
              </div>
            </>
          )}
        </div>
      ))}
    </div>
  )
}

export function RunView({ run }: { run: AgentRun }) {
  return (
    <div>
      <div className="row">
        <StatusBadge status={run.status} />
        <span className="muted small">
          {run.latency_ms} ms · {run.llm_calls} model call{run.llm_calls === 1 ? '' : 's'} ·{' '}
          {run.prompt_tokens + run.completion_tokens} tokens
        </span>
      </div>
      {run.error && <ErrorBox message={run.error} />}
      <div className="answer">{run.answer || '(no answer)'}</div>
      {run.status === 'rejected' && (
        <>
          <div className="muted small">The model said:</div>
          <pre>{run.raw_answer}</pre>
          <div className="notice">Validation: {run.validation_errors.join('; ')}</div>
        </>
      )}
      <div>
        <span className="muted small">Citations: </span>
        <Citations ids={run.citations} />
      </div>
      <TraceView steps={run.tool_calls} />
    </div>
  )
}
