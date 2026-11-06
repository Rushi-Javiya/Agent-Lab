import type { AgentConfig } from '../types'

export const DEFAULT_CONFIG: AgentConfig = {
  provider: 'mock',
  model: 'mock-extractive',
  system_prompt:
    'You are a careful analyst for a grid equipment company. You answer questions about ' +
    'win/loss reports and maintenance manuals. You never invent facts.',
  temperature: 0,
  top_k: 4,
  max_retries: 1,
  router: 'heuristic',
  require_citations: true,
  max_tokens: null,
}
