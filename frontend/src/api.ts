import type {
  AgentConfig,
  AgentDetail,
  AgentRun,
  AgentSummary,
  BenchmarkRun,
  Comparison,
  Dataset,
  DocumentDetail,
  DocumentSummary,
  EvalRun,
  ExtractionReport,
  Health,
  PromptSet,
  RecordRow,
  SearchHit,
  Version,
} from './types'

const BASE: string = import.meta.env.VITE_API_URL ?? ''

export class ApiError extends Error {
  status: number

  constructor(status: number, message: string) {
    super(message)
    this.status = status
  }
}

function describeDetail(detail: unknown): string {
  if (typeof detail === 'string') return detail
  if (Array.isArray(detail)) {
    return detail
      .map((item) => {
        const entry = item as { loc?: unknown[]; msg?: string }
        const where = Array.isArray(entry.loc) ? entry.loc.slice(1).join('.') : ''
        return where ? `${where}: ${entry.msg}` : String(entry.msg)
      })
      .join('; ')
  }
  return JSON.stringify(detail)
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${BASE}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...init,
  })
  if (!response.ok) {
    let message = response.statusText
    try {
      const body = await response.json()
      message = describeDetail(body.detail ?? body)
    } catch {
      // keep the status text
    }
    throw new ApiError(response.status, message)
  }
  return (await response.json()) as T
}

const post = <T>(path: string, body: unknown) =>
  request<T>(path, { method: 'POST', body: JSON.stringify(body) })

export const api = {
  health: () => request<Health>('/api/health'),

  agents: () => request<AgentSummary[]>('/api/agents'),
  agent: (slug: string) => request<AgentDetail>(`/api/agents/${slug}`),
  createAgent: (body: { slug: string; name: string; description: string; config: AgentConfig }) =>
    post<AgentDetail>('/api/agents', body),
  createVersion: (slug: string, config: AgentConfig, note: string) =>
    post<Version>(`/api/agents/${slug}/versions`, { config, note }),
  runAgent: (slug: string, question: string, version?: number) =>
    post<AgentRun>(`/api/agents/${slug}/run`, { question, version }),
  agentRuns: (slug: string) => request<AgentRun[]>(`/api/agents/${slug}/runs`),

  datasets: () => request<Dataset[]>('/api/datasets'),
  startEval: (body: { dataset: string; agent: string; version?: number }) =>
    post<EvalRun>('/api/evals/runs', body),
  evalRuns: () => request<EvalRun[]>('/api/evals/runs'),
  evalRun: (id: number) => request<EvalRun>(`/api/evals/runs/${id}`),
  compare: (baseline: number, candidate: number) =>
    request<Comparison>(`/api/evals/compare?baseline=${baseline}&candidate=${candidate}`),

  promptSets: () => request<PromptSet[]>('/api/benchmarks/prompt-sets'),
  startBenchmark: (body: {
    targets: { provider: string; model: string }[]
    prompt_set: string
    repeats: number
  }) => post<BenchmarkRun>('/api/benchmarks/runs', body),
  benchmarks: () => request<BenchmarkRun[]>('/api/benchmarks/runs'),
  benchmark: (id: number) => request<BenchmarkRun>(`/api/benchmarks/runs/${id}`),

  documents: () => request<DocumentSummary[]>('/api/documents'),
  document: (id: string) => request<DocumentDetail>(`/api/documents/${id}`),
  search: (q: string) => request<SearchHit[]>(`/api/search?q=${encodeURIComponent(q)}&top_k=6`),
  records: () => request<RecordRow[]>('/api/records'),
  extract: (body: { method: 'rules' | 'llm'; provider: string; model: string; apply: boolean }) =>
    post<ExtractionReport>('/api/records/extract', body),
}
