export function percent(value: number | null | undefined, digits = 0): string {
  if (value === null || value === undefined || Number.isNaN(value)) return '–'
  return `${(value * 100).toFixed(digits)}%`
}

export function score(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(value)) return '–'
  return value.toFixed(2)
}

export function milliseconds(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(value)) return '–'
  if (value >= 1000) return `${(value / 1000).toFixed(1)} s`
  return `${value.toFixed(value < 10 ? 1 : 0)} ms`
}

export function euro(value: number | null | undefined): string {
  if (value === null || value === undefined) return '–'
  return `EUR ${Math.round(value).toLocaleString('en-US')}`
}

/** Colour class for a score between 0 and 1. */
export function scoreTone(value: number | null | undefined): 'good' | 'warn' | 'bad' | 'none' {
  if (value === null || value === undefined || Number.isNaN(value)) return 'none'
  if (value >= 0.85) return 'good'
  if (value >= 0.6) return 'warn'
  return 'bad'
}

/** Signed difference such as +0.12 or -0.30. */
export function signed(value: number, digits = 2): string {
  const text = Math.abs(value).toFixed(digits)
  if (value > 0) return `+${text}`
  if (value < 0) return `-${text}`
  return text
}

export function shortDate(iso: string | null | undefined): string {
  if (!iso) return '–'
  const date = new Date(iso)
  if (Number.isNaN(date.getTime())) return '–'
  return date.toLocaleString('en-GB', {
    day: '2-digit',
    month: 'short',
    hour: '2-digit',
    minute: '2-digit',
  })
}

export function modelLabel(config: { provider: string; model: string }): string {
  return `${config.provider}/${config.model}`
}
