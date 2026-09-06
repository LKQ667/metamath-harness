import { createHash } from 'node:crypto'
import type { TraeRawChatDraft } from './raw-chat.ts'

export interface TraeFusionRawChatEnvelope {
  arg: TraeRawChatDraft
  args_hash: string
  config_json: string
}

/** Stable JSON hash candidate used by the native DTO's arg/args_hash fields. */
export function hashTraeRawChatArg(arg: TraeRawChatDraft): string {
  return createHash('sha256').update(JSON.stringify(arg)).digest('hex')
}

/**
 * Evidence-bounded fusion envelope candidate. The native DTO exposes exactly
 * arg/args_hash/config_json, but the hash algorithm and config_json contents
 * remain candidates until a live response validates them.
 */
export function buildTraeFusionRawChatEnvelope(arg: TraeRawChatDraft, config: Record<string, unknown>): TraeFusionRawChatEnvelope {
  return {
    arg: structuredClone(arg),
    args_hash: hashTraeRawChatArg(arg),
    config_json: JSON.stringify(config),
  }
}
