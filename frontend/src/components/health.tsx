import type { ReactNode } from 'react'

import { api } from '../api'
import { useAsync } from '../lib/hooks'
import { HealthContext, useHealth } from './healthContext'

export function HealthProvider({ children }: { children: ReactNode }) {
  const { data } = useAsync(() => api.health(), [])
  return <HealthContext.Provider value={data}>{children}</HealthContext.Provider>
}

export function ProviderStatus() {
  const health = useHealth()
  if (!health) return null
  return (
    <div className="providers" title="Model servers that Agent Lab can reach">
      {Object.entries(health.providers).map(([name, info]) => (
        <span key={name}>
          <span className={`dot ${info.available ? 'on' : ''}`} />
          {name}
        </span>
      ))}
    </div>
  )
}
