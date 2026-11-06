import { describe, expect, it } from 'vitest'

import { euro, milliseconds, modelLabel, percent, score, scoreTone, signed } from './format'

describe('format helpers', () => {
  it('formats percentages and missing values', () => {
    expect(percent(0.9)).toBe('90%')
    expect(percent(0.9567, 1)).toBe('95.7%')
    expect(percent(null)).toBe('–')
    expect(percent(Number.NaN)).toBe('–')
  })

  it('formats scores', () => {
    expect(score(0.97)).toBe('0.97')
    expect(score(undefined)).toBe('–')
  })

  it('formats durations', () => {
    expect(milliseconds(4.567)).toBe('4.6 ms')
    expect(milliseconds(250)).toBe('250 ms')
    expect(milliseconds(12065)).toBe('12.1 s')
    expect(milliseconds(null)).toBe('–')
  })

  it('formats euros', () => {
    expect(euro(4200000)).toBe('EUR 4,200,000')
    expect(euro(null)).toBe('–')
  })

  it('maps scores to tones', () => {
    expect(scoreTone(0.97)).toBe('good')
    expect(scoreTone(0.7)).toBe('warn')
    expect(scoreTone(0.3)).toBe('bad')
    expect(scoreTone(null)).toBe('none')
  })

  it('formats signed deltas', () => {
    expect(signed(0.123)).toBe('+0.12')
    expect(signed(-0.3)).toBe('-0.30')
    expect(signed(0)).toBe('0.00')
  })

  it('builds a model label', () => {
    expect(modelLabel({ provider: 'ollama', model: 'llama3.2' })).toBe('ollama/llama3.2')
  })
})
