import test from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { resolve } from 'node:path';

const preset = resolve(import.meta.dirname, '../../../.dsh/.agent-presets/mathmodel/agent.cordis.yml');
const imagegenPreset = resolve(import.meta.dirname, '../../../.dsh/.agent-presets/imagegen/agent.cordis.yml');
const webPatch = resolve(import.meta.dirname, '../../../.dsh/profiles/web/cordis.patch.yml');
const standard = 'C:\\Users\\Lenovo\\AppData\\Roaming\\npm\\node_modules\\@deepseek-ai\\dsh\\config\\agent-presets\\standard\\agent.cordis.yml';
const ids = (text) => [...text.matchAll(/^\s*- id:\s*([^\s]+)\s*$/gm)].map((match) => match[1]);

test('mathmodel 保留 standard 全部插件行，公共生图工具由 Web Profile 统一加载', async () => {
  const [source, baseline] = await Promise.all([readFile(preset, 'utf8'), readFile(standard, 'utf8')]);
  const sourceIds = new Set(ids(source));
  for (const id of ids(baseline)) assert.equal(sourceIds.has(id), true, `缺少 standard 行 ${id}`);
  assert.equal(sourceIds.has('mathmodel-tools'), false);
});

test('imagegen 保留 standard 全部插件行，公共生图工具由 Web Profile 统一加载', async () => {
  const [source, baseline] = await Promise.all([readFile(imagegenPreset, 'utf8'), readFile(standard, 'utf8')]);
  const sourceIds = new Set(ids(source));
  for (const id of ids(baseline)) assert.equal(sourceIds.has(id), true, `缺少 standard 行 ${id}`);
  assert.equal(sourceIds.size, ids(baseline).length);
  assert.equal(sourceIds.has('mathmodel-tools'), false);
});

test('Web Profile 全局加载一次生图工具，使任意 Agent 模式可用且不重复注册', async () => {
  const source = await readFile(webPatch, 'utf8');
  assert.match(source, /id: mathmodel-tools/);
  assert.match(source, /@deepseek-harness\/dsh-mathmodel\/tools/);
});

test('mathmodel Persona 明示中文建模、证据边界和卡片锁定配置', async () => {
  const source = await readFile(preset, 'utf8');
  assert.match(source, /Chinese-first mathematical modeling agent/);
  assert.match(source, /Never fabricate data, citations, experiments, scores, or verification/);
  assert.match(source, /honor every locked option and do not ask it again/);
});
