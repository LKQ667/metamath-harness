import test from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';
import path from 'node:path';

const pluginRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const repoRoot = path.resolve(pluginRoot, '..', '..');

test('原生 web：号池 dependency/bundle 单例且紧跟 Free Search', async () => {
  const profile = JSON.parse(await readFile(path.join(repoRoot, '.dsh/profiles/web/package.json'), 'utf8'));
  assert.equal(profile.dependencies['@deepseek-harness/dsh-api-key-pool'], 'file:../../../plugins/dsh-api-key-pool');
  const bundles = profile.dsh.profile.bundles;
  assert.equal(bundles.filter((name) => name === '@deepseek-harness/dsh-api-key-pool').length, 1);
  assert.equal(bundles.indexOf('@deepseek-harness/dsh-api-key-pool'), bundles.indexOf('dsh-free-search') + 1);
});

test('独立 web-key-pool：显式保持独占路由与 profile 标签', async () => {
  const patch = await readFile(path.join(repoRoot, '.dsh-key-pool/profiles/web-key-pool/cordis.patch.yml'), 'utf8');
  assert.match(patch, /id:\s*api-key-pool/);
  assert.match(patch, /profileLabel:\s*web-key-pool/);
  assert.match(patch, /exclusivePoolRoutes:\s*true/);
});
