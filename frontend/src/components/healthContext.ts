import { createContext, useContext } from 'react'

import type { Health } from '../types'

export const HealthContext = createContext<Health | null>(null)

export function useHealth(): Health | null {
  return useContext(HealthContext)
}

/** Models a provider reports, used to fill the model suggestions in forms. */
export function useModels(provider: string): string[] {
  const health = useHealth()
  return health?.providers[provider]?.models ?? []
}
