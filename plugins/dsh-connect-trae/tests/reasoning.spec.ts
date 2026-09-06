import { describe, expect, it } from 'vitest'
import { applyReasoningEffort, parseReasoningCapability, TRAE_REASONING_EFFORTS } from '../src/reasoning.ts'

describe('Trae reasoning effort capability', () => {
  it('recognizes the five effort symbols evidenced by the client binary', () => {
    expect(TRAE_REASONING_EFFORTS).toEqual(['minimal', 'low', 'medium', 'high', 'xhigh'])
  })

  it('parses advertised options and validates the default', () => {
    expect(parseReasoningCapability({ reasoning_effort_options: ['low', 'medium', 'high', 'bogus'], default_reasoning_effort: 'medium' })).toEqual({
      supported: ['low', 'medium', 'high'], defaultEffort: 'medium',
    })
  })

  it('does not claim capability when current model metadata reports none', () => {
    expect(parseReasoningCapability({ reasoning_effort_options: [], default_reasoning_effort: null })).toBeUndefined()
  })

  it('sends only an effort explicitly advertised by the model', () => {
    const capability = { supported: ['low', 'high'] as const, defaultEffort: 'low' as const }
    expect(applyReasoningEffort({ model: 'm' }, 'high', capability)).toEqual({ model: 'm', reasoning_effort: 'high' })
    expect(() => applyReasoningEffort({ model: 'm' }, 'xhigh', capability)).toThrow(/does not advertise/)
    expect(applyReasoningEffort({ model: 'm' }, undefined, undefined)).toEqual({ model: 'm' })
  })
})
