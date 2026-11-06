import { useState } from 'react'
import type { FormEvent } from 'react'
import { Link, useNavigate } from 'react-router-dom'

import { api } from '../api'
import { ConfigFields } from '../components/ConfigFields'
import { DEFAULT_CONFIG } from '../lib/defaults'
import { ErrorBox, ScoreBar, Spinner } from '../components/ui'
import { useAsync } from '../lib/hooks'
import { modelLabel } from '../lib/format'
import type { AgentConfig } from '../types'

function slugify(text: string): string {
  return text
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '')
    .slice(0, 58)
}

export function AgentsPage() {
  const agents = useAsync(() => api.agents(), [])
  const navigate = useNavigate()
  const [open, setOpen] = useState(false)
  const [name, setName] = useState('')
  const [slug, setSlug] = useState('')
  const [description, setDescription] = useState('')
  const [config, setConfig] = useState<AgentConfig>(DEFAULT_CONFIG)
  const [error, setError] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)

  const submit = async (event: FormEvent) => {
    event.preventDefault()
    setSaving(true)
    setError(null)
    try {
      const created = await api.createAgent({
        slug: slug || slugify(name),
        name,
        description,
        config,
      })
      navigate(`/agents/${created.slug}`)
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : String(exc))
    } finally {
      setSaving(false)
    }
  }

  return (
    <>
      <div className="page-head row between">
        <div>
          <h1>Agents</h1>
          <div className="muted">
            Every change of the configuration creates a new immutable version, so results stay
            comparable.
          </div>
        </div>
        <button className="primary" onClick={() => setOpen(!open)}>
          {open ? 'Close' : 'New agent'}
        </button>
      </div>

      {open && (
        <form className="card" onSubmit={submit}>
          <h2>New agent</h2>
          <ErrorBox message={error} />
          <div className="form-grid">
            <label>
              Name
              <input
                type="text"
                required
                value={name}
                onChange={(event) => {
                  setName(event.target.value)
                  setSlug(slugify(event.target.value))
                }}
              />
            </label>
            <label>
              Slug (used in URLs and the CLI)
              <input type="text" required value={slug} onChange={(e) => setSlug(e.target.value)} />
            </label>
            <label className="wide">
              Description
              <input
                type="text"
                value={description}
                onChange={(event) => setDescription(event.target.value)}
              />
            </label>
          </div>
          <ConfigFields value={config} onChange={setConfig} />
          <button className="primary" type="submit" disabled={saving}>
            {saving ? 'Creating…' : 'Create agent'}
          </button>
        </form>
      )}

      {agents.loading && <Spinner />}
      <ErrorBox message={agents.error} />
      <div className="grid cols-2">
        {agents.data?.map((agent) => (
          <Link key={agent.id} to={`/agents/${agent.slug}`} className="card" style={{ color: 'inherit' }}>
            <div className="row between">
              <h2 style={{ margin: 0 }}>{agent.name}</h2>
              <span className="badge info">v{agent.latest_version?.version}</span>
            </div>
            <div className="muted small">{agent.slug}</div>
            <p>{agent.description}</p>
            {agent.latest_version && (
              <div className="row between small">
                <span className="muted">{modelLabel(agent.latest_version.config)}</span>
                <span className="row">
                  <span className="muted">latest eval</span>
                  <ScoreBar value={agent.latest_version.latest_eval?.mean_score} />
                </span>
              </div>
            )}
            <div className="muted small">{agent.version_count} version(s)</div>
          </Link>
        ))}
      </div>
    </>
  )
}
