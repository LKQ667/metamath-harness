import type { TraeUpstreamClient } from './upstream.ts'

export type TraeRawChatCapability =
  | { available: true; contentType: string | null }
  | { available: false; reason: 'authentication' | 'credit' | 'rate' | 'protocol' | 'transport' | 'server'; status: number }

/** One short non-tool request decides whether Raw Chat may become primary. */
export async function probeTraeRawChatCapability(client: TraeUpstreamClient, signal?: AbortSignal): Promise<TraeRawChatCapability> {
  const body = JSON.stringify({
    model: 'qwen-3.7-plus',
    messages: [{ role: 'user', content: 'Reply with exactly: OK' }],
    max_tokens: 8,
    temperature: 0,
  })
  const result = await client.chatStream(body, signal)
  if (result.ok) {
    const contentType = result.response.headers.get('content-type')
    // Never consume or replay the capability response as a user answer.
    await result.response.body?.cancel().catch(() => {})
    return { available: true, contentType }
  }
  const reason = result.kind === 'authentication' ? 'authentication'
    : result.kind === 'hard_credit' ? 'credit'
      : result.kind === 'soft_rate' ? 'rate'
        : result.status === 400 || result.status === 404 || result.status === 415 || result.kind === 'unconfigured' ? 'protocol'
          : result.kind === 'server' && result.status === 0 ? 'transport'
            : 'server'
  return { available: false, reason, status: result.status }
}
