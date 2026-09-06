import { describe, expect, it } from 'vitest'
import { TraeUsageClient, type TraeUsageOptions } from '../src/usage.ts'
import type { TraeCredential } from '../src/auth.ts'

const credential: TraeCredential = {
  accessToken: 'eyJhbGciOiJSUzI1NiJ9.signature',
  userId: 'uid',
  host: 'https://api.trae.cn',
  expiresAtMs: Date.now() + 1000,
  edition: 'solo',
  source: 'desktop',
}

function makeClient(json: () => Record<string, unknown>): { client: TraeUsageClient; urls: string[]; bodies: Record<string, unknown>[] } {
  const urls: string[] = []
  const bodies: Record<string, unknown>[] = []
  const fetchImpl = async (input: string | URL | Request, init?: RequestInit) => {
    urls.push(String(input))
    bodies.push(JSON.parse(String(init?.body ?? '{}')))
    return new Response(JSON.stringify(json()), { status: 200, headers: { 'Content-Type': 'application/json' } })
  }
  const options: TraeUsageOptions = { credential: async () => credential, fetchImpl, baseUrl: 'https://api.trae.cn' }
  return { client: new TraeUsageClient(options), urls, bodies }
}

describe('TraeUsageClient', () => {
  it('parses the web_user_ent_usage snapshot', async () => {
    const { client, urls, bodies } = makeClient(() => ({
      is_credits_billing: true,
      is_dollar_usage_billing: false,
      is_pay_freshman: true,
      trial_status: { is_eligible_for_trial: false, is_in_trial: false, trial_end_time: 1785835060 },
      usage_summary: { consumed_amount: 5879.63, consumption_ratio: 0.7839506666666667, total_amount: 7500 },
      user_entitlement_pack_list: [
        {
          display_desc: '老用户福利',
          entitlement_base_info: {
            entitlement_id: '326737122050',
            end_time: 1788340660,
            currency: 1,
            available_endpoint: 1,
            quota: { credits_limit: 2000 },
            product_extra: { package_extra: { quota: { credits_limit: 2000 } } },
          },
          usage: { credits_amount: 2000 },
        },
        {
          display_desc: '签到奖励',
          entitlement_base_info: {
            entitlement_id: 'checkin_20260820_x',
            end_time: 1789837484,
            currency: 1,
            available_endpoint: 0,
            product_extra: { package_extra: { quota: { credits_limit: 200 } } },
          },
          usage: { credits_amount: 179.6288 },
        },
      ],
    }))
    const snapshot = await client.snapshot()
    expect(urls[0]).toBe('https://api.trae.cn/trae/api/v2/pay/web_user_ent_usage')
    expect(bodies[0]).toEqual({ require_usage: true })
    expect(snapshot.isCreditsBilling).toBe(true)
    expect(snapshot.summary).toEqual({ totalAmount: 7500, consumedAmount: 5879.63, consumptionRatio: 0.7839506666666667 })
    expect(snapshot.packs).toHaveLength(2)
    expect(snapshot.packs[0]).toMatchObject({ displayDesc: '老用户福利', availableEndpoint: 1, creditsLimit: 2000, consumedCredits: 2000 })
    expect(snapshot.packs[1]).toMatchObject({ displayDesc: '签到奖励', availableEndpoint: 0, creditsLimit: 200, consumedCredits: 179.6288 })
  })

  it('parses check-in status', async () => {
    const { client, urls } = makeClient(() => ({ checked_in: true, code: 0, credits: 200, enable: true }))
    const status = await client.checkinStatus()
    expect(urls[0]).toBe('https://api.trae.cn/trae/api/v2/ug/checkin_credits/status')
    expect(status).toEqual({ checkedIn: true, credits: 200, enabled: true })
  })

  it('parses activity rules', async () => {
    const { client } = makeClient(() => ({
      commercial_activities: [
        { Enabled: true, activity_id: 'new_user_credits', activity_type: 102, end_time_ms: 1798646400000, start_time_ms: 1785427200000, work_extra: { general_credits: 2000, work_credits: 2000 } },
        { Enabled: false, activity_id: 'off', activity_type: 99, end_time_ms: 0, start_time_ms: 0 },
      ],
    }))
    const activities = await client.activities()
    expect(activities).toHaveLength(2)
    expect(activities[0]).toMatchObject({ activityId: 'new_user_credits', enabled: true, workExtra: { general_credits: 2000, work_credits: 2000 } })
    expect(activities[1]!.enabled).toBe(false)
  })

  it('aggregates view across snapshot, check-in, and activities', async () => {
    let call = 0
    const fetchImpl = async (input: string | URL | Request, init?: RequestInit) => {
      const url = String(input)
      call += 1
      if (url.endsWith('/web_user_ent_usage')) return new Response(JSON.stringify({ usage_summary: { total_amount: 7500, consumed_amount: 5879.63, consumption_ratio: 0.78 }, user_entitlement_pack_list: [] }), { status: 200 })
      if (url.endsWith('/checkin_credits/status')) return new Response(JSON.stringify({ checked_in: false, credits: 0, enable: true }), { status: 200 })
      return new Response(JSON.stringify({ commercial_activities: [] }), { status: 200 })
    }
    const client = new TraeUsageClient({ credential: async () => credential, fetchImpl, baseUrl: 'https://api.trae.cn' })
    const view = await client.view()
    expect(call).toBe(3)
    expect(view.snapshot.summary.totalAmount).toBe(7500)
    expect(view.checkin.checkedIn).toBe(false)
    expect(view.activities).toEqual([])
  })

  it('throws when the credential is missing', async () => {
    const fetchImpl = async () => { throw new Error('should not fetch') }
    const client = new TraeUsageClient({ credential: async () => undefined, fetchImpl, baseUrl: 'https://api.trae.cn' })
    await expect(client.snapshot()).rejects.toThrow('credential is not available')
  })

  it('throws on a non-2xx response', async () => {
    const fetchImpl = async () => new Response('boom', { status: 500 })
    const client = new TraeUsageClient({ credential: async () => credential, fetchImpl, baseUrl: 'https://api.trae.cn' })
    await expect(client.snapshot()).rejects.toThrow('HTTP 500')
  })
})
