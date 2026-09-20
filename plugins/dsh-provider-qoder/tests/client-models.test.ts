import test from 'node:test'
import assert from 'node:assert/strict'
import { reconcileQoderModels } from '../src/client/credential-operations.ts'

test('model settings retain smaller budgets and cap old larger budgets on rediscovery', () => {
  const current = [
    { id: 'small', name: 'Small', contextWindow: 100_000 },
    { id: 'large', name: 'Large', contextWindow: 1_000_000 },
  ]
  const discovered = current.map(model => ({ ...model, contextWindow: 200_000, maxContextWindow: 1_000_000 }))
  const result = reconcileQoderModels(current, discovered)
  assert.deepEqual(result.selected.map(model => model.contextWindow), [100_000, 200_000])
  assert.deepEqual(result.catalog, result.selected)
})

test('fetched models default to selected while removed models remain visible as unavailable', () => {
  const current = [
    { id: 'retained', name: 'Old retained name' },
    { id: 'removed', name: 'Removed model' },
  ]
  const discovered = [
    {
      id: 'retained',
      name: 'Current retained name',
      supportsEffort: true,
      reasoningEfforts: [{ id: 'high', name: 'high' }],
      defaultReasoningEffort: 'high',
      priceFactor: 1.6,
    },
    { id: 'new', name: 'New model' },
  ]

  const reconciled = reconcileQoderModels(current, discovered)

  assert.deepEqual(reconciled.catalog.map(model => model.id), ['retained', 'new', 'removed'])
  assert.deepEqual(reconciled.selected, discovered)
  assert.deepEqual([...reconciled.unavailableIds], ['removed'])
})
