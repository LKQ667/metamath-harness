/**
 * Local record of reasoning-effort probes.
 *
 * What this stores is an *observation*, never a claim about the upstream: a
 * model's row is only consulted when the catalog carries no explicit
 * `supportedEfforts` set, and it always loses to a declared set. The plan this
 * implements (`docs/reasoning-effort-probe-plan.md` §5) requires that a result
 * is invalidated whenever the model's catalog row changes, so every record
 * carries a fingerprint of the fields the probe depended on.
 *
 * The file lives beside the plugin's own credential copy under `$DSH_HOME`,
 * never in the desktop app's files, and carries no token, prompt, or response
 * body — only model ids, effort spellings, and timestamps.
 *
 * @module dsh-workbuddy-connect/probe-store
 */

import { createHash } from 'node:crypto'
import { existsSync, mkdirSync, readFileSync, renameSync, writeFileSync } from 'node:fs'
import { dirname, join, resolve } from 'node:path'
import { resolveDshHome } from '@deepseek-ai/dsh-home-paths'
import type { WorkBuddyModelInfo } from './catalog.ts'
import type { WorkBuddyEffort } from './upstream.ts'

/** Basename of the probe record inside the Harness home. */
export const WORKBUDDY_PROBE_FILENAME = '.workbuddy-probe.json'

/** On-disk format this reader accepts; other versions are discarded. */
const PROBE_FORMAT_VERSION = 1

/**
 * How long an observation stays usable. Conservative on purpose: the plan's
 * whole argument is that upstream metadata moves fast, so a result that has
 * outlived its fingerprint's usefulness should not quietly keep granting a
 * picker entry.
 */
const DEFAULT_TTL_MS = 14 * 24 * 60 * 60 * 1000

/**
 * Whether the model's effort parameter is actually validated.
 *
 * - `validating`: the upstream rejected an unknown sentinel value, so a
 *   per-level answer is meaningful.
 * - `non-validating`: the upstream accepted the sentinel, so it ignores or
 *   loosely coerces the parameter and no per-level answer can be trusted.
 * - `unknown`: baseline or sentinel failed for an unrelated reason (auth,
 *   rate limit, transport, ambiguous error body). Not a negative claim.
 */
export type WorkBuddyProbeValidation = 'validating' | 'non-validating' | 'unknown'

/** One model's recorded observation. */
export interface WorkBuddyProbeRecord {
  /** Fingerprint of the catalog row this observation was made against. */
  fingerprint: string
  validation: WorkBuddyProbeValidation
  /** Efforts verified as accepted; only ever non-empty for `validating`. */
  efforts: readonly WorkBuddyEffort[]
  /** When the probe ran, epoch milliseconds. */
  probedAtMs: number
  /** Plugin version that produced the record. */
  pluginVersion: string
  /**
   * The account this observation was made under, as `uid:enterpriseId`.
   *
   * An effort set is a fact about one account's entitlement as much as about
   * the model: the same model id can accept different levels under a different
   * subscription. Without this a record outlived the account that produced it,
   * so signing out and in as someone else inherited the previous account's
   * detected levels. Records written before this field existed carry no
   * identity and are therefore never reused.
   */
  account?: string
}

interface ProbeDocument {
  version: typeof PROBE_FORMAT_VERSION
  records: Record<string, WorkBuddyProbeRecord>
}

/**
 * Plugin-owned probe record path inside the Harness home.
 *
 * One file per variant. Same-named models exist on both endpoints (the
 * international catalog repeats `glm-5.3`, `glm-5.2`, `hy3`, `kimi-k2.6`), and
 * {@link fingerprintModel} covers only `id`/`reasoning`/`supportsImages` —
 * never the provider — so a single shared file would let one variant's
 * observation answer for the other. The paths differ; the format does not.
 */
export function workbuddyProbePath(filename: string = WORKBUDDY_PROBE_FILENAME): string {
  return join(resolveDshHome(), filename)
}

/**
 * Fingerprint the catalog fields a probe depends on.
 *
 * Deliberately excludes display-only fields (`name`, `billing`, `contextWindow`)
 * so a rename or a promo badge does not throw away a valid observation, and
 * deliberately includes the whole reasoning object so any change to the
 * declared shape re-probes.
 */
export function fingerprintModel(info: WorkBuddyModelInfo): string {
  const basis = JSON.stringify({
    id: info.id,
    reasoning: info.reasoning ?? null,
    supportsImages: info.supportsImages ?? null,
  })
  return createHash('sha256').update(basis).digest('hex').slice(0, 16)
}

/** Read-and-validate the documents on disk; anything malformed reads as empty. */
function readDocument(path: string): ProbeDocument | undefined {
  if (!existsSync(path)) return undefined
  let parsed: unknown
  try {
    parsed = JSON.parse(readFileSync(path, 'utf8'))
  } catch {
    return undefined
  }
  if (typeof parsed !== 'object' || parsed === null || Array.isArray(parsed)) return undefined
  const wrapped = parsed as Record<string, unknown>
  if (wrapped['version'] !== PROBE_FORMAT_VERSION) return undefined
  const records = wrapped['records']
  if (typeof records !== 'object' || records === null || Array.isArray(records)) return undefined
  return parsed as ProbeDocument
}

/** One record's shape check; a bad row is dropped rather than trusted. */
function isRecord(value: unknown): value is WorkBuddyProbeRecord {
  if (typeof value !== 'object' || value === null || Array.isArray(value)) return false
  const wrapped = value as Record<string, unknown>
  const validation = wrapped['validation']
  if (validation !== 'validating' && validation !== 'non-validating' && validation !== 'unknown') return false
  if (typeof wrapped['fingerprint'] !== 'string') return false
  if (typeof wrapped['probedAtMs'] !== 'number' || !Number.isFinite(wrapped['probedAtMs'])) return false
  if (typeof wrapped['pluginVersion'] !== 'string') return false
  const efforts = wrapped['efforts']
  if (!Array.isArray(efforts) || efforts.some(effort => typeof effort !== 'string')) return false
  return true
}

/** Options for {@link WorkBuddyProbeStore}. */
export interface WorkBuddyProbeStoreOptions {
  /** Explicit state-file path, overriding the `$DSH_HOME` default. */
  path?: string
  /** Observation lifetime; defaults to 14 days. */
  ttlMs?: number
  /** Plugin version stamped into new records. */
  pluginVersion: string
  /** Clock injection for tests. */
  now?: () => number
}

/**
 * The plugin's probe records: read once, written atomically, never trusted
 * across a fingerprint change or past the TTL.
 */
export class WorkBuddyProbeStore {
  private readonly path: string
  private readonly ttlMs: number
  private readonly pluginVersion: string
  private readonly now: () => number
  private records: Record<string, WorkBuddyProbeRecord> | undefined

  constructor(options: WorkBuddyProbeStoreOptions | string) {
    // A bare string stays accepted for the pre-plan call sites that only cared
    // about the path.
    const opts: WorkBuddyProbeStoreOptions = typeof options === 'string'
      ? { path: options, pluginVersion: '0.0.0' }
      : options
    this.path = opts.path ?? workbuddyProbePath()
    this.ttlMs = opts.ttlMs ?? DEFAULT_TTL_MS
    this.pluginVersion = opts.pluginVersion
    this.now = opts.now ?? (() => Date.now())
  }

  /** Resolved state-file path, for the CLI and tests. */
  filePath(): string {
    return this.path
  }

  private load(): Record<string, WorkBuddyProbeRecord> {
    if (this.records === undefined) {
      const document = readDocument(this.path)
      const records: Record<string, WorkBuddyProbeRecord> = {}
      for (const [id, record] of Object.entries(document?.records ?? {})) {
        if (isRecord(record)) records[id] = record
      }
      this.records = records
    }
    return this.records
  }

  /**
   * The usable record for a model, or `undefined` when there is none, it is
   * expired, it was taken against a different catalog row, or it belongs to a
   * different account.
   *
   * @param account - the account in effect, as `uid:enterpriseId`. Records are
   *   only returned for the account that produced them.
   */
  get(modelId: string, fingerprint: string, account: string): WorkBuddyProbeRecord | undefined {
    const record = this.load()[modelId]
    if (record === undefined) return undefined
    if (record.fingerprint !== fingerprint) return undefined
    // A record with no identity is one written before account binding existed;
    // it cannot be attributed, so it is not reused.
    if (record.account !== account) return undefined
    if (this.now() - record.probedAtMs > this.ttlMs) return undefined
    return record
  }

  /**
   * Store one observation. Only a decisive answer (`validating` /
   * `non-validating`) replaces an existing decisive record: a transient
   * `unknown` must not erase knowledge the user already paid for.
   */
  set(modelId: string, record: WorkBuddyProbeRecord): void {
    const records = this.load()
    const existing = records[modelId]
    if (
      record.validation === 'unknown'
      && existing !== undefined
      && existing.fingerprint === record.fingerprint
      && existing.validation !== 'unknown'
    ) {
      return
    }
    records[modelId] = record
    this.persist()
  }

  /** Drop every record; used by the card's explicit "clear" action. */
  clear(): void {
    this.records = {}
    this.persist()
  }

  /** Every record currently held, for status display. */
  all(): Readonly<Record<string, WorkBuddyProbeRecord>> {
    return { ...this.load() }
  }

  /** Build a record stamped with this store's clock, version, and account. */
  record(
    fingerprint: string,
    validation: WorkBuddyProbeValidation,
    efforts: readonly WorkBuddyEffort[],
    account: string,
  ): WorkBuddyProbeRecord {
    return {
      fingerprint,
      validation,
      // An observation that could not validate the parameter cannot support a
      // per-level claim, whatever the levels answered.
      efforts: validation === 'validating' ? [...efforts] : [],
      probedAtMs: this.now(),
      pluginVersion: this.pluginVersion,
      account,
    }
  }

  /**
   * Write through a temporary file and rename, so a crash mid-write cannot
   * leave a half-parsed document that reads as "no records" and silently drops
   * every observation.
   */
  private persist(): void {
    const directory = dirname(this.path)
    try {
      if (!existsSync(directory)) mkdirSync(directory, { recursive: true })
      const document: ProbeDocument = { version: PROBE_FORMAT_VERSION, records: this.load() }
      const temporary = resolve(`${this.path}.tmp`)
      writeFileSync(temporary, `${JSON.stringify(document, null, 2)}\n`, { mode: 0o600 })
      renameSync(temporary, this.path)
    } catch {
      // A state file that cannot be written must not take the plugin down: the
      // worst case is that the observation is not remembered.
    }
  }
}

/**
 * Order observations newest-first for display.
 *
 * The store keeps insertion order so the file reads chronologically, but the
 * card wants the most recent detection at the top: a sweep the user just ran
 * should not appear below every earlier one, which is what appending to an
 * insertion-ordered list does.
 */
export function newestFirst<T extends { probedAt: number }>(records: readonly T[]): T[] {
  return [...records].sort((a, b) => b.probedAt - a.probedAt)
}
