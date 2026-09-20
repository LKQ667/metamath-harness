/**
 * The reasoning-effort probe: decide whether a model's `reasoning_effort`
 * parameter is actually validated, and if so which canonical values it accepts.
 *
 * Implements `docs/reasoning-effort-probe-plan.md` §4. The order matters and is
 * not an optimization:
 *
 * 1. **Baseline** (no `reasoning_effort`) proves the model, credential, and
 *    request shape work at all, so a later rejection can be attributed.
 * 2. **Sentinel** (a fresh random, impossible-to-collide value) answers the one
 *    question a per-level sweep cannot: does the upstream validate the field?
 *    A model that accepts the sentinel answers 200 to *everything*, so its
 *    per-level results would be uniformly false positives.
 * 3. **Levels**, only after the sentinel was refused.
 *
 * The result is an observation, never a capability claim. Even a fully
 * successful sweep means "the upstream accepted these spellings", not "these
 * spellings change how the model thinks".
 *
 * @module dsh-workbuddy-connect/probe
 */

import { randomBytes } from 'node:crypto'
import type { WorkBuddyEffort } from './upstream.ts'

/**
 * The canonical values a probe tests, in a fixed order.
 *
 * `minimal` is absent: it appears in no upstream vocabulary. `off` is absent
 * by policy — disabling thinking is a separate capability the upstream must
 * declare through `canDisableThinking`, never something probing may infer.
 */
export const PROBE_EFFORT_CANDIDATES: readonly WorkBuddyEffort[] = ['low', 'medium', 'high', 'xhigh', 'max']

/** Prompt body used by every probe request; carries nothing user-specific. */
export const PROBE_PROMPT = 'ping'

/** Output ceiling for a probe request; the answer itself is never read. */
export const PROBE_MAX_TOKENS = 1

/** Per-request ceiling so one hung probe cannot stall the queue. */
export const PROBE_REQUEST_TIMEOUT_MS = 30_000

/** Sentinel generator; injectable so tests get deterministic values. */
export type SentinelFactory = () => string

/** Default sentinel: unmistakably non-canonical, different on every call. */
export function randomSentinel(): string {
  return `probe_sentinel_${randomBytes(12).toString('hex')}`
}

/**
 * One response as the probe sees it, split into the only distinctions the
 * attribution rule needs.
 */
export interface ProbeAttempt {
  /** HTTP status, or 0 for a transport failure. */
  status: number
  /** True when a parseable SSE event arrived. */
  streamed: boolean
  /** `extError.code` from a JSON error body, when present. */
  errorCode?: string
  /** Free-form detail for logs; never shown as a capability claim. */
  detail?: string
}

/** How one attempt is performed; the caller owns credentials and HTTP. */
export type ProbeSender = (effort: string | undefined, signal: AbortSignal) => Promise<ProbeAttempt>

/** The outcome of probing one model. */
export type ProbeOutcome =
  | { validation: 'validating'; efforts: readonly WorkBuddyEffort[]; requests: number }
  | { validation: 'non-validating'; efforts: readonly []; requests: number }
  | { validation: 'unknown'; efforts: readonly []; requests: number; reason: string }

/**
 * The upstream's "this effort value is not supported" code, measured
 * 2026-09-11 (plan §4.2). It is *not* treated as a permanent protocol promise:
 * anything unrecognized degrades to `unknown` rather than to a capability
 * conclusion.
 */
const INVALID_EFFORT_CODE = 'invalid_reasoning_effort'

/** Whether an attempt is an attributable rejection of the effort value. */
function isEffortRejection(attempt: ProbeAttempt): boolean {
  return attempt.status === 400 && attempt.errorCode === INVALID_EFFORT_CODE
}

/** Whether an attempt shows the upstream accepted the request and streamed. */
function isAcceptance(attempt: ProbeAttempt): boolean {
  return attempt.status === 200 && attempt.streamed
}

/** Why an attempt ended in `unknown`, phrased for a log line. */
function unknownReason(stage: string, attempt: ProbeAttempt): string {
  const code = attempt.errorCode === undefined ? '' : ` (${attempt.errorCode})`
  const detail = attempt.detail === undefined ? '' : `: ${attempt.detail}`
  return `${stage} status ${attempt.status}${code}${detail}`
}

/**
 * Probe one model.
 *
 * `options.candidates` exists so tests can shorten the sweep; production always
 * uses {@link PROBE_EFFORT_CANDIDATES}.
 */
export async function probeModel(options: {
  send: ProbeSender
  sentinel?: SentinelFactory
  candidates?: readonly WorkBuddyEffort[]
  timeoutMs?: number
}): Promise<ProbeOutcome> {
  const sentinel = options.sentinel ?? randomSentinel
  const candidates = options.candidates ?? PROBE_EFFORT_CANDIDATES
  const timeoutMs = options.timeoutMs ?? PROBE_REQUEST_TIMEOUT_MS
  let requests = 0

  const attempt = async (effort: string | undefined): Promise<ProbeAttempt> => {
    requests += 1
    const controller = new AbortController()
    const timer = setTimeout(() => controller.abort(), timeoutMs)
    try {
      return await options.send(effort, controller.signal)
    } catch (error: unknown) {
      return { status: 0, streamed: false, detail: `transport error: ${String(error)}` }
    } finally {
      clearTimeout(timer)
    }
  }

  // 1. Baseline: proves the request path itself is sound. Without this a 400
  //    on the sentinel could just as well be an unrelated request problem.
  const baseline = await attempt(undefined)
  if (!isAcceptance(baseline)) {
    return { validation: 'unknown', efforts: [], requests, reason: unknownReason('baseline', baseline) }
  }

  // 2. Sentinel: the only step that can distinguish "validates the field" from
  //    "accepts anything".
  const probe = sentinel()
  const sentinelAttempt = await attempt(probe)
  if (isAcceptance(sentinelAttempt)) {
    // The upstream took a value that cannot exist. Any per-level acceptance
    // would be equally meaningless, so stop here rather than spend more
    // requests producing false positives.
    return { validation: 'non-validating', efforts: [], requests }
  }
  if (!isEffortRejection(sentinelAttempt)) {
    return { validation: 'unknown', efforts: [], requests, reason: unknownReason('sentinel', sentinelAttempt) }
  }

  // 3. Levels: meaningful only because the sentinel was refused.
  const accepted: WorkBuddyEffort[] = []
  for (const effort of candidates) {
    const levelAttempt = await attempt(effort)
    if (isAcceptance(levelAttempt)) {
      accepted.push(effort)
      continue
    }
    if (isEffortRejection(levelAttempt)) continue
    // A non-decisive answer mid-sweep: the partial list is not a finding, so
    // report the whole run as unknown rather than under-claiming a model.
    return {
      validation: 'unknown',
      efforts: [],
      requests,
      reason: unknownReason(`level ${effort}`, levelAttempt),
    }
  }

  return { validation: 'validating', efforts: accepted, requests }
}
