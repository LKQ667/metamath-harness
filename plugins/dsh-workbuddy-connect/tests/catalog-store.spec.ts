import { mkdtempSync, readFileSync, rmSync, writeFileSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { afterEach, describe, expect, it } from 'vitest'
import { WorkBuddyCatalogStore, workbuddyCatalogPath } from '../src/catalog-store.ts'
import type { WorkBuddyUpstreamModel } from '../src/upstream.ts'

/**
 * The saved catalog is the middle rung of the plan's degradation order (§4):
 * live fetch → this account's last successful fetch → the built-in roster.
 *
 * It is an optimization for the restart and offline cases, so the tests that
 * matter are the ones proving it can never make things worse: a corrupt file
 * reads as empty, a foreign account's catalog is never served, and no secret
 * is written.
 */

const CLEANUP: string[] = []

afterEach(() => {
  for (const path of CLEANUP.splice(0)) rmSync(path, { recursive: true, force: true })
})

function tempStore(): { store: WorkBuddyCatalogStore; path: string } {
  const dir = mkdtempSync(join(tmpdir(), 'wb-catalog-'))
  CLEANUP.push(dir)
  const path = join(dir, 'catalog.json')
  return { store: new WorkBuddyCatalogStore({ path }), path }
}

function model(id: string): WorkBuddyUpstreamModel {
  return {
    id,
    name: id,
    contextWindow: 1000,
    maxTokens: 100,
    supportsImages: true,
    billing: { credits: 'x1.00', free: false },
  }
}

describe('WorkBuddyCatalogStore', () => {
  it('round-trips a catalog per account', () => {
    const { store, path } = tempStore()
    store.set('uid-1:ent-1', { source: 'workbuddy:cli', fetchedAtMs: 111, models: [model('a')] })

    const reopened = new WorkBuddyCatalogStore({ path })
    const saved = reopened.get('uid-1:ent-1')
    expect(saved?.models.map(entry => entry.id)).toEqual(['a'])
    expect(saved?.source).toBe('workbuddy:cli')
    expect(saved?.fetchedAtMs).toBe(111)
  })

  it('keeps accounts apart, so one account never serves another catalog', () => {
    const { store } = tempStore()
    store.set('uid-1:ent-1', { source: 's', fetchedAtMs: 1, models: [model('for-a')] })
    store.set('uid-2:ent-2', { source: 's', fetchedAtMs: 2, models: [model('for-b')] })
    expect(store.get('uid-1:ent-1')?.models.map(m => m.id)).toEqual(['for-a'])
    expect(store.get('uid-2:ent-2')?.models.map(m => m.id)).toEqual(['for-b'])
    expect(store.get('uid-3:ent-3')).toBeUndefined()
  })

  it('replaces an account catalog rather than accumulating models', () => {
    const { store } = tempStore()
    store.set('uid-1:ent-1', { source: 's', fetchedAtMs: 1, models: [model('old')] })
    store.set('uid-1:ent-1', { source: 's', fetchedAtMs: 2, models: [model('new')] })
    expect(store.get('uid-1:ent-1')?.models.map(m => m.id)).toEqual(['new'])
  })

  it('forgets one account on request', () => {
    const { store } = tempStore()
    store.set('uid-1:ent-1', { source: 's', fetchedAtMs: 1, models: [model('a')] })
    store.delete('uid-1:ent-1')
    expect(store.get('uid-1:ent-1')).toBeUndefined()
    // Deleting an absent account is a no-op, not a crash.
    expect(() => store.delete('uid-9:ent-9')).not.toThrow()
  })

  it('reads a corrupt or foreign-version file as empty instead of throwing', () => {
    const dir = mkdtempSync(join(tmpdir(), 'wb-catalog-bad-'))
    CLEANUP.push(dir)
    const cases = [
      'not json at all',
      '[]',
      JSON.stringify({ version: 99, entries: { 'uid-1:ent-1': { account: 'uid-1:ent-1', source: 's', fetchedAtMs: 1, models: [model('a')] } } }),
      JSON.stringify({ version: 1, entries: { 'uid-1:ent-1': { account: 'uid-1:ent-1', source: 's', fetchedAtMs: 1, models: [] } } }),
      JSON.stringify({ version: 1, entries: { 'uid-1:ent-1': { account: '', source: 's', fetchedAtMs: 1, models: [model('a')] } } }),
      JSON.stringify({ version: 1, entries: { 'uid-1:ent-1': { account: 'uid-1:ent-1', source: 's', fetchedAtMs: 1, models: [{ id: 'x' }] } } }),
    ]
    for (const [index, body] of cases.entries()) {
      const path = join(dir, `case-${index}.json`)
      writeFileSync(path, body)
      const store = new WorkBuddyCatalogStore({ path })
      expect(store.get('uid-1:ent-1'), `case ${index} must read as empty`).toBeUndefined()
    }
  })

  it('writes no token material', () => {
    const { store, path } = tempStore()
    store.set('uid-1:ent-1', { source: 'workbuddy:cli', fetchedAtMs: 1, models: [model('a')] })
    const text = readFileSync(path, 'utf8')
    // The file holds model metadata and the account key only. A token is the
    // one thing that must never reach it.
    expect(text).not.toMatch(/eyJ[A-Za-z0-9_-]+\./)
    expect(text).not.toMatch(/refreshToken|accessToken/i)
    expect(text).toContain('uid-1:ent-1')
  })

  it('survives an unwritable path without throwing', () => {
    const store = new WorkBuddyCatalogStore({ path: '/proc/definitely-not-writable/catalog.json' })
    // Saving is best-effort: the plugin has already served these models, and a
    // failed write must not surface as a crash.
    expect(() => store.set('uid-1:ent-1', { source: 's', fetchedAtMs: 1, models: [model('a')] })).not.toThrow()
  })

  it('defaults its path under the DSH home', () => {
    expect(workbuddyCatalogPath()).toMatch(/\.workbuddy-catalog\.json$/)
    expect(workbuddyCatalogPath('.workbuddy-ai-catalog.json')).toMatch(/\.workbuddy-ai-catalog\.json$/)
  })
})
