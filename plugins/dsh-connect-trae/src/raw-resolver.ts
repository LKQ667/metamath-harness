import type { TraeCredentialStore } from './auth.ts'
import { readTraeIdentity, type TraeIdentity } from './identity.ts'
import { readTraeCachedModel } from './model-cache.ts'
import { buildTraeRawChatRuntimeConfig, type TraeRawChatRuntimeConfig } from './raw-runtime-config.ts'

export interface TraeRawResolverResult {
  identity: TraeIdentity
  runtime: TraeRawChatRuntimeConfig
}

/** Resolve current desktop identity and safe cached model config for capability probing. */
export async function resolveTraeRawRuntime(store: TraeCredentialStore, modelName: string): Promise<TraeRawResolverResult> {
  const credential = await store.resolve()
  const candidate = store.candidates().find(item => item.edition === credential.edition)
  if (candidate === undefined) throw new Error(`no Trae ${credential.edition} storage candidate for Raw Chat identity`)
  const identity = await readTraeIdentity(candidate)
  const cached = credential.edition === 'cn'
    ? await readTraeCachedModel('solo_agent', modelName, credential.userId).catch(() => undefined)
    : undefined
  return {
    identity,
    runtime: buildTraeRawChatRuntimeConfig(modelName, cached, {
      passBackReasoning: true,
      nativeFunctionCall: cached?.customConfig?.['native_function_call'] === true,
      useV2Process: cached?.customConfig?.['use_v2_process'] === true,
    }),
  }
}
