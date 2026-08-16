import test from 'node:test';
import assert from 'node:assert/strict';
import { TYPERT } from '../lib/typert.host.js';
import { TYPERT_REMOTE } from '../lib/typert.remote-client.js';
import { validateTypertManifest } from '../../../.dsh/profiles/node_modules/@deepseek-ai/dsh-typert-loader/lib/index.js';

test('Host Typert 清单通过官方 Harness 校验器', () => {
  const validated = validateTypertManifest('@deepseek-harness/dsh-mathmodel', TYPERT);
  assert.equal(validated.invocations.length, 20);
  assert.deepEqual(
    new Set(validated.invocations.map((item) => item.namespace)),
    new Set(['mathmodelCards', 'mathmodelCredentials', 'mathmodelPreflight', 'mathmodelProviders', 'mathmodelImageConnections', 'mathmodelOpenCodeRt', 'mathmodelStoredKeyModelDiscovery', 'mathmodelManualVision']),
  );
});

test('Client 与 Host Remote 端点完全一致', () => {
  assert.deepEqual(
    TYPERT_REMOTE.descriptors.map((item) => item.id),
    TYPERT.invocations.map((item) => item.id),
  );
});

test('浏览器 bundle 的 Remote 签名与 Host 清单一致', async () => {
  const source = await import('node:fs/promises').then(({ readFile }) => readFile(new URL('../src/client-bundle.cjs', import.meta.url), 'utf8'));
  const browserDescriptors = [...source.matchAll(/descriptor\('([^']+)', '([^']+)'(?:, \[([^\]]*)\])?\)/g)].map((match) => ({
    id: `${match[1]}.${match[2]}`,
    parameters: [...(match[3] ?? '').matchAll(/param\('([^']+)'\)/g)].map((parameter) => parameter[1]),
  }));
  const hostDescriptors = TYPERT.invocations.map((item) => ({
    id: `${item.service}.${item.method}`,
    parameters: item.parameters.map((parameter) => parameter.name),
  }));
  assert.deepEqual(browserDescriptors, hostDescriptors);
});

test('浏览器入口先挂载贡献，再访问 mathmodel Remote', async () => {
  const source = await import('node:fs/promises').then(({ readFile }) => readFile(new URL('../lib/client.js', import.meta.url), 'utf8'));
  const mount = source.indexOf('await ctx.remote.$mount(TYPERT_REMOTE)');
  const resolveRemote = source.indexOf("ctx.get('remote.mathmodelCards')");
  const firstCall = source.indexOf('mathmodelCards.list()');
  const unwrap = source.indexOf('async function unwrapRemote');
  assert.ok(mount >= 0);
  assert.ok(resolveRemote > mount);
  assert.ok(unwrap >= 0);
  assert.ok(firstCall > mount);
  assert.match(source, /unwrapRemote\(\s*mathmodelCards\.render/);
  assert.match(source, /await disposeRemote\(\)/);
});
