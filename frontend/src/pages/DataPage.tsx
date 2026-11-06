import { useState } from 'react'
import type { FormEvent } from 'react'
import { useSearchParams } from 'react-router-dom'

import { api } from '../api'
import { useModels } from '../components/healthContext'
import { ErrorBox, ScoreBar, Spinner } from '../components/ui'
import { euro, percent } from '../lib/format'
import { useAsync } from '../lib/hooks'
import { PROVIDERS } from '../types'
import type { ExtractionReport } from '../types'

type Tab = 'documents' | 'records' | 'extraction'

function Documents() {
  const [params, setParams] = useSearchParams()
  const docs = useAsync(() => api.documents(), [])
  const selected = params.get('doc') ?? ''
  const detail = useAsync(
    () => (selected ? api.document(selected) : Promise.resolve(null)),
    [selected],
  )
  const [query, setQuery] = useState('')
  const [hits, setHits] = useState<Awaited<ReturnType<typeof api.search>> | null>(null)

  const search = async (event: FormEvent) => {
    event.preventDefault()
    setHits(query.trim() ? await api.search(query) : null)
  }

  return (
    <div className="grid" style={{ gridTemplateColumns: '300px 1fr' }}>
      <div className="card">
        <form onSubmit={search} style={{ marginBottom: '0.75rem' }}>
          <input
            type="text"
            style={{ width: '100%' }}
            placeholder="Search chunks (BM25)…"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
          />
        </form>
        {docs.loading && <Spinner />}
        <div className="doc-list">
          {docs.data?.map((doc) => (
            <button
              key={doc.doc_id}
              className={doc.doc_id === selected ? 'active' : ''}
              onClick={() => setParams({ doc: doc.doc_id })}
            >
              {doc.title}
              <div className="muted small">
                {doc.doc_id} · {doc.chunks} chunk(s)
              </div>
            </button>
          ))}
        </div>
      </div>
      <div>
        {hits && (
          <div className="card">
            <h2>Search results</h2>
            {hits.length === 0 && <div className="muted">Nothing found.</div>}
            {hits.map((hit) => (
              <div key={hit.chunk_id} style={{ marginBottom: '0.75rem' }}>
                <button className="link" onClick={() => setParams({ doc: hit.doc_id })}>
                  {hit.chunk_id}
                </button>{' '}
                <span className="muted small">score {hit.score.toFixed(2)}</span>
                <pre>{hit.text}</pre>
              </div>
            ))}
          </div>
        )}
        {detail.data && (
          <div className="card">
            <h2>{detail.data.title}</h2>
            {detail.data.chunks.map((chunk) => (
              <div key={chunk.chunk_id}>
                <span className="chip">{chunk.chunk_id}</span>
                <pre>{chunk.text}</pre>
              </div>
            ))}
          </div>
        )}
        {!detail.data && !hits && (
          <div className="muted">
            Choose a document. All 16 documents are synthetic and were written for this project.
          </div>
        )}
      </div>
    </div>
  )
}

function Records() {
  const records = useAsync(() => api.records(), [])
  return (
    <div className="card">
      <h2>Win/loss records</h2>
      <div className="muted small" style={{ marginBottom: '0.6rem' }}>
        The records tool of the agents queries this table. It is seeded from a curated reference file;
        the extraction experiment can overwrite it.
      </div>
      {records.loading && <Spinner />}
      <ErrorBox message={records.error} />
      <table>
        <thead>
          <tr>
            <th>Customer</th>
            <th>Region</th>
            <th>Date</th>
            <th>Outcome</th>
            <th className="num">Our price</th>
            <th>Competitor</th>
            <th className="num">Their price</th>
            <th>Reason</th>
            <th>Source</th>
          </tr>
        </thead>
        <tbody>
          {records.data?.map((r) => (
            <tr key={r.doc_id}>
              <td>{r.customer ?? '–'}</td>
              <td>{r.region ?? '–'}</td>
              <td>{r.deal_date ?? '–'}</td>
              <td>{r.outcome ?? '–'}</td>
              <td className="num">{euro(r.our_price_eur)}</td>
              <td>{r.competitor ?? '–'}</td>
              <td className="num">{euro(r.competitor_price_eur)}</td>
              <td>{r.reason_category ?? '–'}</td>
              <td className="small muted">{r.method}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function Extraction() {
  const [method, setMethod] = useState<'rules' | 'llm'>('rules')
  const [provider, setProvider] = useState('mock')
  const [model, setModel] = useState('mock-extractive')
  const [apply, setApply] = useState(false)
  const [running, setRunning] = useState(false)
  const [report, setReport] = useState<ExtractionReport | null>(null)
  const [error, setError] = useState<string | null>(null)
  const models = useModels(provider)

  const run = async (event: FormEvent) => {
    event.preventDefault()
    setRunning(true)
    setError(null)
    try {
      setReport(await api.extract({ method, provider, model, apply }))
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : String(exc))
    } finally {
      setRunning(false)
    }
  }

  return (
    <>
      <form className="card" onSubmit={run}>
        <h2>Extraction experiment</h2>
        <div className="muted small" style={{ marginBottom: '0.75rem' }}>
          Extract the structured fields from the 12 win/loss reports and score them against the
          reference records. 8 reports have a header block, 4 are plain prose. Rules read the
          headers; a model can also read the prose.
        </div>
        <ErrorBox message={error} />
        <div className="form-grid">
          <label>
            Method
            <select value={method} onChange={(event) => setMethod(event.target.value as 'rules' | 'llm')}>
              <option value="rules">rules (regex)</option>
              <option value="llm">llm (JSON output)</option>
            </select>
          </label>
          <label>
            Provider
            <select
              value={provider}
              disabled={method === 'rules'}
              onChange={(event) => setProvider(event.target.value)}
            >
              {PROVIDERS.map((name) => (
                <option key={name}>{name}</option>
              ))}
            </select>
          </label>
          <label>
            Model
            <input
              type="text"
              list="extract-models"
              value={model}
              disabled={method === 'rules'}
              onChange={(event) => setModel(event.target.value)}
            />
            <datalist id="extract-models">
              {models.map((m) => (
                <option key={m} value={m} />
              ))}
            </datalist>
          </label>
          <label className="inline">
            <input type="checkbox" checked={apply} onChange={(event) => setApply(event.target.checked)} />
            Write results to the records table
          </label>
        </div>
        <button className="primary" type="submit" disabled={running}>
          {running ? 'Extracting…' : 'Run extraction'}
        </button>
        {running && method === 'llm' && (
          <span className="muted small"> This calls the model 12 times and can take a minute.</span>
        )}
      </form>

      {report && (
        <div className="card">
          <h2>
            Overall accuracy {percent(report.overall_accuracy)}
            {report.applied > 0 && (
              <span className="badge warn" style={{ marginLeft: '0.6rem' }}>
                {report.applied} records overwritten
              </span>
            )}
          </h2>
          <table style={{ marginBottom: '1rem' }}>
            <tbody>
              {Object.entries(report.field_accuracy).map(([field, value]) => (
                <tr key={field}>
                  <td>{field}</td>
                  <td>
                    <ScoreBar value={value} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          <h3>Per document</h3>
          <table>
            <thead>
              <tr>
                <th>Document</th>
                <th>Wrong or missing fields</th>
              </tr>
            </thead>
            <tbody>
              {report.documents.map((doc) => {
                const wrong = Object.entries(doc.fields).filter(([, f]) => !f.correct)
                return (
                  <tr key={doc.doc_id}>
                    <td>{doc.doc_id}</td>
                    <td className="small">
                      {doc.error && <span style={{ color: 'var(--bad)' }}>{doc.error}</span>}
                      {wrong.length === 0 && !doc.error && <span className="badge good">all correct</span>}
                      {wrong.map(([name, f]) => (
                        <span key={name} className="chip" title={`expected ${f.expected}`}>
                          {name}: {String(f.got ?? 'missing')}
                        </span>
                      ))}
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      )}
    </>
  )
}

export function DataPage() {
  const [tab, setTab] = useState<Tab>('documents')
  return (
    <>
      <div className="page-head">
        <h1>Data</h1>
        <div className="muted">The corpus the agents work on and the structured records.</div>
      </div>
      <div className="tabs">
        {(['documents', 'records', 'extraction'] as Tab[]).map((name) => (
          <button key={name} className={tab === name ? 'active' : ''} onClick={() => setTab(name)}>
            {name}
          </button>
        ))}
      </div>
      {tab === 'documents' && <Documents />}
      {tab === 'records' && <Records />}
      {tab === 'extraction' && <Extraction />}
    </>
  )
}
