import test from 'node:test'
import assert from 'node:assert/strict'
import { resolveLocalizedText } from '../src/client/locales.ts'

test('resolveLocalizedText prefers an exact language tag match', () => {
  const text = {
    values: { 'zh-CN': 'SOTA 专属积分', 'en-US': 'SOTA Exclusive Credits' },
    fallback: 'sota model series',
  }
  assert.equal(resolveLocalizedText(text, 'zh-CN'), 'SOTA 专属积分')
  assert.equal(resolveLocalizedText(text, 'en-US'), 'SOTA Exclusive Credits')
})

test('resolveLocalizedText matches the built-in zh/en ids against regional provider keys', () => {
  const text = {
    values: { 'zh-CN': 'SOTA 专属积分', 'en-US': 'SOTA Exclusive Credits' },
    fallback: 'sota model series',
  }
  assert.equal(resolveLocalizedText(text, 'zh'), 'SOTA 专属积分')
  assert.equal(resolveLocalizedText(text, 'en'), 'SOTA Exclusive Credits')
  assert.equal(resolveLocalizedText(text, 'EN'), 'SOTA Exclusive Credits')
})

test('resolveLocalizedText prefers an exact key over a shared primary subtag', () => {
  const text = { values: { zh: '通用中文', 'zh-CN': '简体中文' }, fallback: 'generic' }
  assert.equal(resolveLocalizedText(text, 'zh-CN'), '简体中文')
  assert.equal(resolveLocalizedText(text, 'zh-TW'), '通用中文')
})

test('resolveLocalizedText falls back to the provider copy when the locale is untranslated', () => {
  const text = { values: { 'zh-CN': 'SOTA 专属积分' }, fallback: 'sota model series' }
  assert.equal(resolveLocalizedText(text, 'fr'), 'sota model series')
  assert.equal(resolveLocalizedText(text, ''), 'sota model series')
})

test('resolveLocalizedText falls back to any translation when no language-neutral copy exists', () => {
  const text = { values: { 'zh-CN': 'SOTA 专属积分' }, fallback: '' }
  assert.equal(resolveLocalizedText(text, 'fr'), 'SOTA 专属积分')
})

test('resolveLocalizedText ignores blank entries and returns undefined when nothing is usable', () => {
  assert.equal(resolveLocalizedText(undefined, 'zh'), undefined)
  assert.equal(resolveLocalizedText({ values: {}, fallback: '' }, 'zh'), undefined)
  assert.equal(resolveLocalizedText({ values: { 'zh-CN': '   ' }, fallback: '  ' }, 'zh'), undefined)
  assert.equal(
    resolveLocalizedText({ values: { 'zh-CN': ' SOTA 专属积分 ' }, fallback: '' }, 'zh'),
    'SOTA 专属积分',
  )
})
