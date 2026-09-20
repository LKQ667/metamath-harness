import test from 'node:test'
import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'

const clientUrl = new URL('../src/client/', import.meta.url)

test('Qoder account and credential cards use the intended settings slots and scoped styles', async () => {
  const [credentialCard, modelCatalog, accountCard, entry, stylesheet] = await Promise.all([
    readFile(new URL('QoderCredentialCard.tsx', clientUrl), 'utf8'),
    readFile(new URL('QoderModelCatalog.tsx', clientUrl), 'utf8'),
    readFile(new URL('QoderAccountCard.tsx', clientUrl), 'utf8'),
    readFile(new URL('index.ts', clientUrl), 'utf8'),
    readFile(new URL('QoderCredentialCard.module.css', clientUrl), 'utf8'),
  ])

  assert.match(credentialCard, /import css from '\.\/QoderCredentialCard\.module\.css'/u)
  assert.match(accountCard, /import css from '\.\/QoderCredentialCard\.module\.css'/u)
  assert.match(credentialCard, /css\.credentialEditor/u)
  assert.match(accountCard, /className=\{css\.credential\}/u)
  assert.match(entry, /name: 'settings\.section',[\s\S]*QoderAccountCard/u)
  assert.match(entry, /name: 'settings\.models\.footer',[\s\S]*QoderCredentialCard/u)
  assert.match(credentialCard, /aria-expanded=\{editing\}/u)
  assert.match(credentialCard, /placeholder=\{configured \? t\('configuredHint'\) : t\('tokenPlaceholder'\)\}/u)
  assert.match(credentialCard, /<summary[^>]*>\{t\('customized'\)\}<\/summary>/u)
  assert.match(modelCatalog, /operations\.discoverModels\(\)/u)
  assert.match(modelCatalog, /t\('modelsFetch'\)/u)
  assert.match(modelCatalog, /type="checkbox"/u)
  assert.match(modelCatalog, /t\('modelUnavailable'\)/u)
  assert.match(modelCatalog, /model\.priceFactor/u)
  assert.match(modelCatalog, /t\('modelRate'/u)
  assert.doesNotMatch(modelCatalog, /type="(?:text|number)"/u)
  assert.doesNotMatch(modelCatalog, /modelsReset|modelAdd|modelRemove|modelsAdopt/u)
  assert.doesNotMatch(entry, /document\.createElement\('style'\)/u)
  assert.match(stylesheet, /var\(--dsw-alias-bg-layer-1\)/u)
  assert.match(stylesheet, /\.regionBadge/u)
  assert.match(stylesheet, /\.regionSelector/u)
  assert.match(accountCard, /operations\.storeWebSearchMode/u)
  assert.match(accountCard, /t\('searchModeLabel'\)/u)
  assert.match(accountCard, /css\.searchModeSection/u)
  assert.match(stylesheet, /\.searchModeSection/u)
  assert.match(stylesheet, /\.searchModeHintText/u)
  assert.match(accountCard, /usage\?\.dedicatedResourcePackages/u)
  assert.match(accountCard, /activeLocale\(\)/u)
  assert.match(accountCard, /css\.quotaDescription/u)
  assert.match(stylesheet, /\.quotaDescription/u)
  assert.doesNotMatch(stylesheet, /--dsw-(?:surface|border|text-secondary|input-bg|accent|danger|success)\b/u)
  assert.doesNotMatch(stylesheet, /#[0-9a-f]{3,8}\b/iu)
})
