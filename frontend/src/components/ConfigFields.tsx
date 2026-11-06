import { PROVIDERS } from '../types'
import type { AgentConfig, ProviderName } from '../types'
import { useModels } from './healthContext'

interface Props {
  value: AgentConfig
  onChange: (value: AgentConfig) => void
}

export function ConfigFields({ value, onChange }: Props) {
  const models = useModels(value.provider)
  const set = <K extends keyof AgentConfig>(key: K, next: AgentConfig[K]) =>
    onChange({ ...value, [key]: next })

  const changeProvider = (provider: ProviderName) => {
    const first = provider === 'mock' ? 'mock-extractive' : ''
    onChange({ ...value, provider, model: first })
  }

  return (
    <div className="form-grid">
      <label>
        Provider
        <select
          value={value.provider}
          onChange={(event) => changeProvider(event.target.value as ProviderName)}
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
          list={`models-${value.provider}`}
          value={value.model}
          placeholder="for example llama3.2"
          onChange={(event) => set('model', event.target.value)}
        />
        <datalist id={`models-${value.provider}`}>
          {models.map((name) => (
            <option key={name} value={name} />
          ))}
        </datalist>
      </label>
      <label>
        Router
        <select
          value={value.router}
          onChange={(event) => set('router', event.target.value as AgentConfig['router'])}
        >
          <option value="heuristic">heuristic (rules)</option>
          <option value="llm">llm (model decides)</option>
        </select>
      </label>
      <label>
        Top k chunks
        <input
          type="number"
          min={1}
          max={12}
          value={value.top_k}
          onChange={(event) => set('top_k', Number(event.target.value))}
        />
      </label>
      <label>
        Max retries
        <input
          type="number"
          min={0}
          max={3}
          value={value.max_retries}
          onChange={(event) => set('max_retries', Number(event.target.value))}
        />
      </label>
      <label>
        Temperature
        <input
          type="number"
          min={0}
          max={2}
          step={0.1}
          value={value.temperature}
          onChange={(event) => set('temperature', Number(event.target.value))}
        />
      </label>
      <label className="inline">
        <input
          type="checkbox"
          checked={value.require_citations}
          onChange={(event) => set('require_citations', event.target.checked)}
        />
        Require citations
      </label>
      <label className="wide">
        System prompt
        <textarea
          value={value.system_prompt}
          onChange={(event) => set('system_prompt', event.target.value)}
        />
      </label>
    </div>
  )
}
