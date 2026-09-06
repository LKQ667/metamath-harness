import { describe, expect, it } from 'vitest'
import { buildTraeModelDetailRequest, TRAE_MODEL_DETAIL_FUNCTIONS } from '../src/model-detail.ts'

describe('Trae model detail request', () => {
  it('matches the complete request shape observed in successful Trae logs', () => {
    const body = buildTraeModelDetailRequest()
    expect(body).toEqual({
      functions: [...TRAE_MODEL_DETAIL_FUNCTIONS],
      agent_type: '',
      current_config_info: { config_name: '', is_custom_model: false },
      mode_type: 0,
      access_type: 0,
      ab_force_vids: '',
      ab_autotest_advanced_mode: 0,
    })
    expect(body.functions).toContain('inline_chat')
    expect(body.functions).toContain('solo_agent')
    expect(body.functions).toContain('solo_work_remote')
  })

  it('carries an exact custom config identity when requested', () => {
    expect(buildTraeModelDetailRequest('custom_openai_compatible//glm-5.2', true).current_config_info).toEqual({
      config_name: 'custom_openai_compatible//glm-5.2', is_custom_model: true,
    })
  })
})
