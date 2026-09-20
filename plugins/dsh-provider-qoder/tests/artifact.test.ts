import test from 'node:test'
import assert from 'node:assert/strict'
import { access, readFile } from 'node:fs/promises'

interface Manifest {
  name?: string
  dsh?: {
    bundle?: {
      patch?: string
    }
  }
}

test('build emits installable host and invariant entries with declarations', async () => {
  await Promise.all([
    access(new URL('../lib/index.js', import.meta.url)),
    access(new URL('../lib/index.d.ts', import.meta.url)),
    access(new URL('../lib/invariant.js', import.meta.url)),
    access(new URL('../lib/invariant.d.ts', import.meta.url)),
    access(new URL('../lib/client.js', import.meta.url)),
    access(new URL('../cordis.patch.yml', import.meta.url)),
  ])
  const manifest: Manifest = JSON.parse(await readFile(new URL('../package.json', import.meta.url), 'utf8'))
  assert.equal(manifest.name, 'dsh-provider-qoder')
  assert.equal(manifest.dsh?.bundle?.patch, './cordis.patch.yml')
  const patch = await readFile(new URL('../cordis.patch.yml', import.meta.url), 'utf8')
  assert.match(patch, /name: 'dsh-provider-qoder'/u)
  const built = (await import('../lib/index.js')) as { name?: string; apply?: unknown }
  assert.equal(built.name, 'provider-qoder')
  assert.equal(typeof built.apply, 'function')
  const entry = await readFile(new URL('../lib/index.js', import.meta.url), 'utf8')
  assert.doesNotMatch(
    entry,
    /import\s*\{[^}]*\b(?:installSettingsSection|settingsNamespace)\b[^}]*\}\s*from\s*["']@deepseek-ai\/dsh-settings["']/su,
  )
  assert.doesNotMatch(entry, /pt-[A-Za-z0-9_-]{20,}/u)
  assert.doesNotMatch(entry, /QODER_PERSONAL_ACCESS_TOKEN/u)
  const client = await readFile(new URL('../lib/client.js', import.meta.url), 'utf8')
  assert.match(client, /window\.__ModuleLoader__\.load\(\{\s*id: "dsh-provider-qoder"/u)
  assert.match(client, /remote\.credentials/u)
  assert.match(client, /credentials\.describe\(\[qoderCredentialRef\]\)/u)
  assert.match(client, /data-plugin-css/u)
  assert.match(client, /--dsw-alias-bg-layer-1/u)
  assert.match(client, /--dsw-alias-label-primary/u)
  assert.doesNotMatch(client, /--dsw-surface/u)
  assert.doesNotMatch(client, /connection\.api\.credentials/u)
  assert.doesNotMatch(client, /QODER_PERSONAL_ACCESS_TOKEN/u)
})
