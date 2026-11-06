export const PROVIDERS = ['mock', 'ollama', 'llamacpp', 'nim', 'openai'] as const
export type ProviderName = (typeof PROVIDERS)[number]

export interface AgentConfig {
  provider: ProviderName
  model: string
  system_prompt: string
  temperature: number
  top_k: number
  max_retries: number
  router: 'heuristic' | 'llm'
  require_citations: boolean
  max_tokens: number | null
}

export interface LatestEval {
  run_id: number
  dataset: string
  mean_score: number | null
  pass_rate: number | null
}

export interface Version {
  id: number
  version: number
  config: AgentConfig
  note: string
  created_at: string
  latest_eval: LatestEval | null
}

export interface AgentSummary {
  id: number
  slug: string
  name: string
  description: string
  kind: string
  created_at: string
  version_count: number
  latest_version: Version | null
}

export interface AgentDetail extends AgentSummary {
  versions: Version[]
}

/** One step of an agent run: the routing decision, a tool call or a retry. */
export interface TraceStep {
  type: 'route' | 'tool' | 'retry'
  [key: string]: unknown
}

export type RunStatus = 'answered' | 'refused' | 'rejected' | 'error'

export interface AgentRun {
  id: number
  agent_version_id: number
  version: number | null
  question: string
  answer: string
  raw_answer: string
  status: RunStatus
  citations: string[]
  tool_calls: TraceStep[]
  validation_errors: string[]
  latency_ms: number
  prompt_tokens: number
  completion_tokens: number
  llm_calls: number
  error: string | null
  created_at: string
}

export interface Dataset {
  id: number
  slug: string
  name: string
  kind: string
  description: string
  case_count: number
}

export interface EvalSummary {
  cases?: number
  mean_score?: number
  pass_rate?: number
  mean_latency_ms?: number
  p95_latency_ms?: number
  total_tokens?: number
  metrics?: Record<string, number>
  statuses?: Record<string, number>
}

export type JobStatus = 'queued' | 'running' | 'completed' | 'failed'

export interface EvalResult {
  case_id: string
  question: string
  answer: string
  status: RunStatus
  metrics: Record<string, number>
  score: number
  passed: boolean
  latency_ms: number
  tokens: number
  tool_calls: TraceStep[]
  error: string | null
}

export interface EvalRun {
  id: number
  status: JobStatus
  agent: { id: number; slug: string; name: string }
  version: number
  config: AgentConfig
  dataset: { id: number; slug: string; name: string }
  progress: { done: number; total: number }
  summary: EvalSummary
  error: string | null
  created_at: string
  finished_at: string | null
  results?: EvalResult[]
}

export interface CompareCase {
  case_id: string
  question: string
  score_a: number
  score_b: number
  delta: number
  passed_a: boolean
  passed_b: boolean
  status_a: RunStatus
  status_b: RunStatus
}

export interface Comparison {
  baseline: EvalRun
  candidate: EvalRun
  cases: CompareCase[]
  regressions: string[]
  improvements: string[]
  mean_score_a: number
  mean_score_b: number
  mean_delta: number
}

export interface BenchStats {
  calls?: number
  errors?: number
  error_sample?: string[]
  latency_p50_ms?: number
  latency_p95_ms?: number
  latency_mean_ms?: number
  tokens_per_second?: number | null
  completion_tokens_mean?: number
  fact_coverage?: number
  grounded_rate?: number
}

export interface BenchResult {
  id: number
  provider: string
  model: string
  stats: BenchStats
  error: string | null
}

export interface BenchmarkRun {
  id: number
  status: JobStatus
  prompt_set: string
  repeats: number
  progress: { done: number; total: number }
  error: string | null
  created_at: string
  finished_at: string | null
  results: BenchResult[]
}

export interface PromptSet {
  slug: string
  name: string
  description: string
  prompts: number
}

export interface DocumentSummary {
  doc_id: string
  title: string
  kind: 'winloss' | 'manual'
  chunks: number
}

export interface DocumentDetail extends Omit<DocumentSummary, 'chunks'> {
  text: string
  chunks: { chunk_id: string; text: string }[]
}

export interface SearchHit {
  chunk_id: string
  doc_id: string
  score: number
  text: string
}

export interface RecordRow {
  doc_id: string
  customer: string | null
  region: string | null
  deal_date: string | null
  outcome: string | null
  our_price_eur: number | null
  competitor: string | null
  competitor_price_eur: number | null
  reason_category: string | null
  method: string
  model: string
}

export interface ExtractionField {
  expected: string | number | null
  got: string | number | null
  correct: boolean
}

export interface ExtractionReport {
  method: 'rules' | 'llm'
  provider: string | null
  model: string | null
  documents: {
    doc_id: string
    extracted: Record<string, unknown> | null
    fields: Record<string, ExtractionField>
    error: string | null
  }[]
  field_accuracy: Record<string, number>
  overall_accuracy: number
  applied: number
}

export interface Health {
  status: string
  providers: Record<string, { available: boolean; models: string[] }>
}
