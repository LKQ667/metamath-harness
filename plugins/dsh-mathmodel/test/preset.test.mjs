import test from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { resolve } from 'node:path';
import YAML from 'yaml';

const webPatch = resolve(import.meta.dirname, '../../../.dsh/profiles/web/cordis.patch.yml');
const webPackage = resolve(import.meta.dirname, '../../../.dsh/profiles/web/package.json');
const subscriptionsPatch = resolve(import.meta.dirname, '../../../.dsh/profiles/web/patches/dsh-plugin-subscriptions@0.9.15.patch');
const subscriptionsClient = resolve(import.meta.dirname, '../../../.dsh/profiles/web/node_modules/dsh-plugin-subscriptions/lib/client.js');
const codexAuth = resolve(import.meta.dirname, '../src/image/codex-auth.js');
const grokAuth = resolve(import.meta.dirname, '../src/image/grok-auth.js');
// DSH 0.2.2-rc.5 把官方 standard 预设放在 dsh-web-app/presets/standard.patch.yml，自定义预设改由 Profile cordis.patch.yml 声明。
const npmRoot = resolve(process.env.APPDATA ?? '', 'npm', 'node_modules', '@deepseek-ai', 'dsh');
const standardPatchPath = resolve(npmRoot, 'node_modules', '@deepseek-ai', 'dsh-web-app', 'presets', 'standard.patch.yml');

const customYamlTags = {
  logLevel: 'silent',
  customTags: [{ tag: '!js', resolve: (str) => ({ __jsExpr: str }) }, { tag: '!!js', resolve: (str) => ({ __jsExpr: str }) }],
};

async function loadLivePresets() {
  const raw = await readFile(webPatch, 'utf8');
  const doc = YAML.parse(raw, customYamlTags);
  const presets = new Map();
  for (const row of doc ?? []) {
    const items = Array.isArray(row?.insert) ? row.insert : [row];
    for (const item of items) {
      if (item?.name === '@deepseek-ai/dsh-agent-preset' && item?.config?.id) {
        presets.set(item.config.id, item.config);
      }
    }
  }
  return presets;
}

async function loadStandardPlugins() {
  const raw = await readFile(standardPatchPath, 'utf8');
  const doc = YAML.parse(raw, customYamlTags);
  for (const row of doc ?? []) {
    const items = Array.isArray(row?.insert) ? row.insert : [row];
    for (const item of items) {
      if (item?.name === '@deepseek-ai/dsh-agent-preset' && item?.config?.id === 'standard') {
        return item.config.plugins;
      }
    }
  }
  throw new Error(`未在 ${standardPatchPath} 中找到 standard 预设`);
}

test('所有本地 preset 完整保留目标 standard 公共配置，不能只验前三个', async () => {
  const [presets, standardPlugins] = await Promise.all([loadLivePresets(), loadStandardPlugins()]);
  assert.deepEqual([...presets.keys()].sort(), ['editable-ppt', 'imagegen', 'infinite-gen-3', 'mathmodel']);
  const baseline = standardPlugins.filter((row) => row.id !== 'persona');
  for (const [name, cfg] of presets.entries()) {
    const actual = (cfg.plugins ?? []).filter((row) => row.id !== 'persona');
    assert.deepEqual(actual, baseline, `${name} 的官方公共配置失配`);
  }
});

test('mathmodel 保留 standard 全部插件行，公共生图工具由 Web Profile 统一加载', async () => {
  const [presets, standardPlugins] = await Promise.all([loadLivePresets(), loadStandardPlugins()]);
  const plugins = presets.get('mathmodel')?.plugins ?? [];
  const sourceIds = new Set(plugins.map((row) => row.id));
  for (const row of standardPlugins) assert.equal(sourceIds.has(row.id), true, `缺少 standard 行 ${row.id}`);
  assert.deepEqual(
    plugins.filter((row) => row.id !== 'persona'),
    standardPlugins.filter((row) => row.id !== 'persona'),
    '公共配置须与目标 standard 一致',
  );
  assert.equal(sourceIds.has('mathmodel-tools'), false);
});

test('imagegen 保留 standard 全部插件行，公共生图工具由 Web Profile 统一加载', async () => {
  const [presets, standardPlugins] = await Promise.all([loadLivePresets(), loadStandardPlugins()]);
  const plugins = presets.get('imagegen')?.plugins ?? [];
  const sourceIds = new Set(plugins.map((row) => row.id));
  for (const row of standardPlugins) assert.equal(sourceIds.has(row.id), true, `缺少 standard 行 ${row.id}`);
  assert.deepEqual(
    plugins.filter((row) => row.id !== 'persona'),
    standardPlugins.filter((row) => row.id !== 'persona'),
    '公共配置须与目标 standard 一致',
  );
  assert.equal(sourceIds.size, standardPlugins.length);
  assert.equal(sourceIds.has('mathmodel-tools'), false);
});

test('Web Profile 全局加载一次生图工具，使任意 Agent 模式可用且不重复注册', async () => {
  const source = await readFile(webPatch, 'utf8');
  assert.match(source, /id: mathmodel-tools/);
  assert.match(source, /@deepseek-harness\/dsh-mathmodel\/tools/);
});

test('订阅插件 0.9.15 统一 Codex/Claude/Grok 且 Host/Client 不重复注册 image_generate', async () => {
  const [profileSource, patchSource, compatibilityPatch, clientSource] = await Promise.all([
    readFile(webPackage, 'utf8'),
    readFile(webPatch, 'utf8'),
    readFile(subscriptionsPatch, 'utf8'),
    readFile(subscriptionsClient, 'utf8'),
  ]);
  const profile = JSON.parse(profileSource);
  const providerBlock = patchSource.match(/- id: llm-subscriptions\s*\n\s*config:\s*\n\s*providers:\s*\n((?:\s+- [^\n]+\n)+)/)?.[1];
  const patchAdditions = compatibilityPatch.split('\n').filter((line) => line.startsWith('+') && !line.startsWith('+++')).join('\n');
  assert.equal(profile.dependencies['dsh-plugin-subscriptions'], '0.9.15');
  assert.equal('dsh-llm-oauth' in profile.dependencies, false);
  assert.equal(profile.dsh.profile.bundles.includes('dsh-llm-oauth'), false);
  assert.deepEqual([...(providerBlock ?? '').matchAll(/^\s*-\s+([^\s]+)\s*$/gm)].map((match) => match[1]), ['codex', 'claude', 'grok']);
  assert.match(patchSource, /registerImageTool:\s*false/);
  assert.doesNotMatch(patchSource, /id:\s*llm-oauth/);
  assert.match(patchAdditions, /subscriptionSessions/);
  assert.match(patchAdditions, /subscriptionTokenManagers\.set\("codex", tokens\)/);
  assert.match(patchAdditions, /subscriptionTokenManagers\.set\("grok", tokens\)/);
  assert.match(patchAdditions, /tokens\.session\(void 0, options\.force === true\)/);
  assert.match(patchAdditions, /config\.registerImageTool !== false/);
  assert.match(compatibilityPatch, /key: "image_generate"/);
  assert.match(compatibilityPatch, /^-\s*key: "image_generate"/m);
  assert.doesNotMatch(patchAdditions, /key: "image_generate"/);
  assert.doesNotMatch(clientSource, /key: "image_generate"/);
  assert.match(clientSource, /key: "video_generate"/);
});

test('本地 Codex/Grok 认证只消费 Host service，不再直接读写凭据文件', async () => {
  const [codexSource, grokSource] = await Promise.all([
    readFile(codexAuth, 'utf8'),
    readFile(grokAuth, 'utf8'),
  ]);
  for (const source of [codexSource, grokSource]) {
    assert.match(source, /subscriptionSessions/);
    assert.doesNotMatch(source, /node:fs|readFile|writeFile|auth\.json|pi-ai-oauth/);
  }
});

test('mathmodel Persona 明示中文建模、证据边界和卡片锁定配置', async () => {
  const presets = await loadLivePresets();
  const persona = presets.get('mathmodel')?.plugins?.find((row) => row.id === 'persona')?.config?.prefix ?? '';
  assert.match(persona, /Chinese-first mathematical modeling agent/);
  assert.match(persona, /Never fabricate data, citations, experiments, scores, or verification/);
  assert.match(persona, /honor every locked option and do not ask it again/);
});
