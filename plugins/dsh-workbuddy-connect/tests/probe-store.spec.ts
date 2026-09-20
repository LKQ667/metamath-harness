import { mkdtempSync, readFileSync, rmSync, writeFileSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { afterEach, describe, expect, it } from 'vitest'
import { FALLBACK_WORKBUDDY_MODELS, WorkBuddyCatalog } from '../src/catalog.ts'
import { fingerprintModel, newestFirst, WorkBuddyProbeStore } from '../src/probe-store.ts'
import { WorkBuddyProbeService } from '../src/probe-service.ts'
import type { WorkBuddyModelInfo } from '../src/catalog.ts'

/**
 * Offline tests for the probe record and its precedence rules
 * (`docs/reasoning-effort-probe-plan.md` §5): an observation is invalidated by
 * a catalog change, expires, never overrides a declared set, and is never
 * erased by a transient failure.
 */

const CLEANUP: string[] = []

afterEach(() => {
  for (const path of CLEANUP.splice(0)) rmSync(path, { recursive: true, force: true })
})

function tempStore(now?: () => number): { store: WorkBuddyProbeStore; path: string; dir: string } {
  const dir = mkdtempSync(join(tmpdir(), 'wb-probe-'))
  CLEANUP.push(dir)
  const path = join(dir, 'probe.json')
  return { store: new WorkBuddyProbeStore({ path, pluginVersion: '9.9.9', ...now === undefined ? {} : { now } }), path, dir }
}

/** The fallback catalog's old-form row, which declares no effort set. */
const AUTO = FALLBACK_WORKBUDDY_MODELS.find(model => model.id === 'auto') as WorkBuddyModelInfo
/** The fallback catalog's new-form row, which declares one. */
const GLM53 = FALLBACK_WORKBUDDY_MODELS.find(model => model.id === 'glm-5.3') as WorkBuddyModelInfo

/** The account these observations are attributed to. */
const ACCOUNT = 'uid-1:ent-1'

describe('fingerprintModel', () => {
  it('is stable for the same row and changes when the reasoning object changes', () => {
    const before = fingerprintModel(AUTO)
    expect(fingerprintModel(AUTO)).toBe(before)

    const changed: WorkBuddyModelInfo = {
      ...AUTO,
      reasoning: { ...AUTO.reasoning!, defaultEffort: 'low' },
    }
    expect(fingerprintModel(changed)).not.toBe(before)
  })

  it('ignores display-only fields so a rename does not discard an observation', () => {
    const renamed: WorkBuddyModelInfo = { ...AUTO, name: 'Auto (renamed)' }
    expect(fingerprintModel(renamed)).toBe(fingerprintModel(AUTO))
  })
})

describe('WorkBuddyProbeStore', () => {
  it('round-trips a record through disk', () => {
    const { store, path } = tempStore()
    const fingerprint = fingerprintModel(AUTO)
    store.set('auto', store.record(fingerprint, 'validating', ['low', 'high'], ACCOUNT))

    const reopened = new WorkBuddyProbeStore({ path, pluginVersion: '9.9.9' })
    const record = reopened.get('auto', fingerprint, ACCOUNT)
    expect(record?.validation).toBe('validating')
    expect(record?.efforts).toEqual(['low', 'high'])
    expect(record?.pluginVersion).toBe('9.9.9')
  })

  it('refuses a record whose fingerprint no longer matches', () => {
    const { store } = tempStore()
    store.set('auto', store.record(fingerprintModel(AUTO), 'validating', ['low'], ACCOUNT))
    expect(store.get('auto', fingerprintModel(AUTO), ACCOUNT)).toBeDefined()
    expect(store.get('auto', 'a-different-fingerprint', ACCOUNT)).toBeUndefined()
  })

  it('expires a record past the TTL', () => {
    let now = 1_000_000
    const { store } = tempStore(() => now)
    const fingerprint = fingerprintModel(AUTO)
    store.set('auto', store.record(fingerprint, 'validating', ['low'], ACCOUNT))
    expect(store.get('auto', fingerprint, ACCOUNT)).toBeDefined()

    now += 15 * 24 * 60 * 60 * 1000
    expect(store.get('auto', fingerprint, ACCOUNT)).toBeUndefined()
  })

  it('never stores efforts for a non-validating observation', () => {
    const { store } = tempStore()
    const record = store.record(fingerprintModel(AUTO), 'non-validating', ['low', 'high'], ACCOUNT)
    expect(record.efforts).toEqual([])
  })

  it('does not let an unknown result erase a decisive one', () => {
    const { store } = tempStore()
    const fingerprint = fingerprintModel(AUTO)
    store.set('auto', store.record(fingerprint, 'validating', ['low'], ACCOUNT))
    store.set('auto', store.record(fingerprint, 'unknown', [], ACCOUNT))

    const kept = store.get('auto', fingerprint, ACCOUNT)
    expect(kept?.validation).toBe('validating')
    expect(kept?.efforts).toEqual(['low'])
  })

  it('does let a decisive result replace a previous unknown', () => {
    const { store } = tempStore()
    const fingerprint = fingerprintModel(AUTO)
    store.set('auto', store.record(fingerprint, 'unknown', [], ACCOUNT))
    store.set('auto', store.record(fingerprint, 'validating', ['high'], ACCOUNT))
    expect(store.get('auto', fingerprint, ACCOUNT)?.efforts).toEqual(['high'])
  })

  it('reads a corrupt or foreign-version file as empty rather than throwing', () => {
    const { store, path } = tempStore()
    store.set('auto', store.record(fingerprintModel(AUTO), 'validating', ['low'], ACCOUNT))
    expect(store.all()).toHaveProperty('auto')

    // A format version this reader does not know must not be half-understood.
    const document = JSON.parse(readFileSync(path, 'utf8')) as Record<string, unknown>
    document['version'] = 999
    writeFileSync(path, JSON.stringify(document))
    expect(new WorkBuddyProbeStore({ path, pluginVersion: '9.9.9' }).all()).toEqual({})

    // Garbage on disk reads as empty too, rather than taking the plugin down.
    writeFileSync(path, '{ not json')
    expect(new WorkBuddyProbeStore({ path, pluginVersion: '9.9.9' }).all()).toEqual({})
  })

  it('clears every record on request', () => {
    const { store } = tempStore()
    store.set('auto', store.record(fingerprintModel(AUTO), 'validating', ['low'], ACCOUNT))
    store.clear()
    expect(store.all()).toEqual({})
  })
})

describe('WorkBuddyProbeService precedence', () => {
  /** Minimal service with a caller-supplied consent answer. */
  function service(options: { consent: boolean; stored?: boolean }): WorkBuddyProbeService {
    const { store } = tempStore()
    const catalog = new WorkBuddyCatalog()
    if (options.stored === true) {
      store.set('auto', store.record(fingerprintModel(AUTO), 'validating', ['low', 'high'], ACCOUNT))
    }
    return new WorkBuddyProbeService({
      store,
      catalog,
      credentials: { current: async () => undefined } as never,
      client: {} as never,
      consent: () => options.consent,
      account: () => ACCOUNT,
    })
  }

  it('never answers from an observation when the upstream declares a set', () => {
    const probe = service({ consent: true, stored: true })
    // `glm-5.3` declares supportedEfforts, so it is declared-set-only.
    expect(probe.recordFor(GLM53.id)).toBeUndefined()
  })

  it('returns the stored observation for an undeclared model', () => {
    const probe = service({ consent: true, stored: true })
    expect(probe.recordFor(AUTO.id)?.efforts).toEqual(['low', 'high'])
  })

  it('refuses to probe without consent', async () => {
    const probe = service({ consent: false })
    const status = await probe.probe('auto')
    expect(status.state).toBe('unavailable')
    expect(status.state === 'unavailable' && status.reason).toContain('not authorized')
  })
})

describe('newestFirst', () => {
  it('puts the most recent observation first', () => {
    // The store appends, so a just-run detection would otherwise land below
    // every earlier one — the exact complaint this helper exists to fix.
    const ordered = newestFirst([
      { probedAt: 100, id: 'oldest' },
      { probedAt: 300, id: 'newest' },
      { probedAt: 200, id: 'middle' },
    ])
    expect(ordered.map(entry => entry.id)).toEqual(['newest', 'middle', 'oldest'])
  })

  it('does not mutate its input', () => {
    const input = [{ probedAt: 1 }, { probedAt: 2 }]
    newestFirst(input)
    expect(input.map(entry => entry.probedAt)).toEqual([1, 2])
  })
})

describe('recordFor: the single judgement the card and adapter share', () => {
  /**
   * The card used to read raw records while the adapter read fingerprint- and
   * TTL-checked ones, so the card could show levels the model picker no longer
   * offered. Both now go through `recordFor`, and these pin what it refuses.
   */
  function serviceFor(store: WorkBuddyProbeStore): WorkBuddyProbeService {
    return new WorkBuddyProbeService({
      store,
      catalog: new WorkBuddyCatalog(),
      credentials: { current: async () => undefined } as never,
      client: {} as never,
      consent: () => true,
      account: () => ACCOUNT,
    })
  }

  it('refuses a record whose catalog row changed', () => {
    const { store } = tempStore()
    const service = serviceFor(store)
    // Recorded against a fingerprint that no longer describes the row.
    store.set('auto', store.record('stale-fingerprint', 'validating', ['low'], ACCOUNT))
    expect(service.recordFor('auto')).toBeUndefined()
  })

  it('refuses an expired record even though the store still holds it', () => {
    let now = 1_000_000
    const { store } = tempStore(() => now)
    const service = serviceFor(store)
    store.set('auto', store.record(fingerprintModel(AUTO), 'validating', ['low'], ACCOUNT))
    expect(service.recordFor('auto')?.efforts).toEqual(['low'])

    now += 15 * 24 * 60 * 60 * 1000
    // Past the TTL the card must stop reporting it, exactly as the adapter does.
    expect(service.recordFor('auto')).toBeUndefined()
  })

  it('refuses a record for a model the catalog no longer lists', () => {
    const { store } = tempStore()
    const service = serviceFor(store)
    // A row recorded for an id the upstream has since dropped.
    store.set('retired-model', store.record('whatever', 'validating', ['low'], ACCOUNT))
    expect(service.recordFor('retired-model')).toBeUndefined()
  })
})
