import test from 'node:test'
import assert from 'node:assert/strict'
import { QoderAdapter } from '../src/dsh/adapter.ts'
import { QODER_PROVIDER_ID } from '../src/dsh/provider.ts'
import type { QoderTransport } from '../src/qoder/transport/index.ts'
import type { QoderCatalogModel } from '../src/qoder/catalog.ts'

function transport(discoverModels: () => Promise<readonly QoderCatalogModel[]>): QoderTransport {
  return { discoverModels } as QoderTransport
}

test('explicit discovery supersedes cached metadata and older in-flight discovery', async (t) => {
  t.mock.timers.enable({ apis: ['Date'], now: 1000 })
  const old = [{ id: 'chosen', name: 'Chosen', supportsImages: false, priceFactor: 2 }]
  let complete!: (models: readonly QoderCatalogModel[]) => void
  let calls = 0
  const remote = transport(() => ++calls === 1
    ? Promise.resolve(old)
    : new Promise(resolve => { complete = resolve }))
  const adapter = new QoderAdapter({ resolveTransport: () => remote, models: old })
  await adapter.listModels(QODER_PROVIDER_ID)
  t.mock.timers.tick(300000)
  const pending = adapter.listModels(QODER_PROVIDER_ID)
  await Promise.resolve()
  const fresh = [{ id: 'chosen', name: 'Chosen', supportsImages: true, priceFactor: 4,
    reasoningEfforts: [{ id: 'high', name: 'High' }] }]
  adapter.updateDiscoveredModels(remote, fresh)
  adapter.replaceModels(fresh)
  const resolved = await adapter.resolveModel(QODER_PROVIDER_ID, 'chosen')
  assert.deepEqual(resolved.inputModalities, ['text', 'image'])
  assert.equal(resolved.reasoning?.efforts[0].id, 'high')
  assert.match(resolved.name, /4x/u)
  complete(old)
  assert.match((await pending)[0].name, /4x/u)
  assert.match((await adapter.listModels(QODER_PROVIDER_ID))[0].name, /4x/u)
  assert.equal(calls, 2)
})

test('model reads share discovery, cache for five minutes, and preserve enabled models', async (t) => {
  t.mock.timers.enable({ apis: ['Date'], now: 1000 })
  let calls = 0
  let complete!: (models: readonly QoderCatalogModel[]) => void
  const remote = transport(() => {
    calls++
    return new Promise(resolve => { complete = resolve })
  })
  const adapter = new QoderAdapter({
    resolveTransport: () => remote,
    models: [{ id: 'chosen', name: 'Chosen' }],
  })
  const first = adapter.listModels(QODER_PROVIDER_ID)
  const concurrent = adapter.listModels(QODER_PROVIDER_ID)
  await Promise.resolve()
  assert.equal(calls, 1)
  complete([{ id: 'chosen', name: 'Chosen', priceFactor: 2 }, { id: 'disabled', name: 'Disabled' }])
  assert.deepEqual((await first).map(model => model.id), ['chosen'])
  assert.deepEqual(await concurrent, await first)
  assert.match((await adapter.resolveModel(QODER_PROVIDER_ID, 'chosen')).name, /2x/u)
  t.mock.timers.tick(299999)
  await adapter.listModels(QODER_PROVIDER_ID)
  assert.equal(calls, 1)
  t.mock.timers.tick(1)
  const refreshed = adapter.listModels(QODER_PROVIDER_ID)
  await Promise.resolve()
  assert.equal(calls, 2)
  complete([{ id: 'chosen', name: 'Chosen', priceFactor: 3 }])
  assert.match((await refreshed)[0].name, /3x/u)
})

test('failed refresh retains metadata and a changed transport ignores the old in-flight result', async (t) => {
  t.mock.timers.enable({ apis: ['Date'], now: 1000 })
  let fail = false
  let active = transport(async () => {
    if (fail) throw new Error('offline')
    return [{ id: 'chosen', name: 'Chosen', priceFactor: 2 }]
  })
  const adapter = new QoderAdapter({ resolveTransport: () => active, models: [{ id: 'chosen', name: 'Chosen' }] })
  await adapter.listModels(QODER_PROVIDER_ID)
  fail = true
  t.mock.timers.tick(300000)
  assert.match((await adapter.listModels(QODER_PROVIDER_ID))[0].name, /2x/u)
  let complete!: (models: readonly QoderCatalogModel[]) => void
  active = transport(() => new Promise(resolve => { complete = resolve }))
  const stale = adapter.listModels(QODER_PROVIDER_ID)
  await Promise.resolve()
  active = transport(async () => [{ id: 'chosen', name: 'Chosen', priceFactor: 4 }])
  complete([{ id: 'chosen', name: 'Chosen', priceFactor: 3 }])
  assert.match((await stale)[0].name, /4x/u)
})
