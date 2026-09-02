import test from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { resolve } from 'node:path';

const workspaceRoot = resolve(import.meta.dirname, '../../../');
const skillRoot = resolve(workspaceRoot, '.dsh/skills/image-to-editable-ppt');
const presetFile = resolve(workspaceRoot, '.dsh/.agent-presets/editable-ppt/agent.cordis.yml');
const standardFile = 'C:\\Users\\Lenovo\\AppData\\Roaming\\npm\\node_modules\\@deepseek-ai\\dsh\\config\\agent-presets\\standard\\agent.cordis.yml';
const ids = (text) => [...text.matchAll(/^\s*- id:\s*([^\s]+)\s*$/gm)].map((match) => match[1]);

test('editable-ppt Persona 声明 DSH 当前连接边界但不复制工具 schema', async () => {
  const source = await readFile(presetFile, 'utf8');
  assert.match(source, /DSH 当前生图连接/);
  assert.match(source, /editable_ppt_image/);
  assert.match(source, /禁止 Codex 和任何后端回退/);
  assert.match(source, /任务开始时锁定/);
  // Persona 保持短小：不含枚举 schema、错误矩阵或执行步骤清单。
  assert.doesNotMatch(source, /additionalProperties|"enum"|codex_backend_forbidden|dsh_current_cli_forbidden/);
  const personaText = source.match(/text: >-\n((?: {6}.+\n?)+)/)?.[1] ?? '';
  assert.ok(personaText.length > 0 && personaText.length < 800, `Persona 应保持短小，当前 ${personaText.length} 字符`);
});

test('editable-ppt roster 与官方 standard 无差异（仅 Persona 文本不同）', async () => {
  const [source, baseline] = await Promise.all([readFile(presetFile, 'utf8'), readFile(standardFile, 'utf8')]);
  assert.deepEqual(ids(source), ids(baseline));
});

test('dsh-current Worker 分支：锁定连接、串行、import 校验哈希、失败 passed:false，且无 Codex/config/Key 建议', async () => {
  const builder = await readFile(resolve(skillRoot, 'scripts/build-page-worker-prompt.py'), 'utf8');
  const dshBlock = builder.split('IMAGE_BACKEND_DSH_CURRENT = """')[1]?.split('"""')[0] ?? '';
  assert.ok(dshBlock.length > 0);
  assert.match(dshBlock, /editable_ppt_image/);
  assert.match(dshBlock, /connection_id|connectionId/);
  assert.match(dshBlock, /page_request\.json/);
  assert.match(dshBlock, /sha256/);
  assert.match(dshBlock, /editppt image import[\s\S]*--metadata-file/);
  assert.match(dshBlock, /"passed": false/);
  assert.doesNotMatch(dshBlock, /codex login|OPENAI_API_KEY|editppt config/);
  const legacyBlock = builder.split('IMAGE_BACKEND_LEGACY = """')[1]?.split('"""')[0] ?? '';
  assert.match(legacyBlock, /codex login/); // 原后端分支保持原文案
  const template = await readFile(resolve(skillRoot, 'prompts/page-worker.md'), 'utf8');
  assert.match(template, /\{\{IMAGE_BACKEND\}\}/);
});

test('Skill 仍保留原质量门禁与串行图像调用关键词', async () => {
  const skill = await readFile(resolve(skillRoot, 'SKILL.md'), 'utf8');
  for (const keyword of ['finalize', 'object-level editable', 'no-fallback rule', 'serial', 'dsh-current', 'editable_ppt_image', 'editppt image import', 'never a quality downgrade', 'dsh_current_cli_forbidden', 'external_processing_forbidden']) {
    assert.match(skill, new RegExp(keyword.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')), `Skill 缺少关键词：${keyword}`);
  }
  const helper = await readFile(resolve(skillRoot, 'references/cli-helper.md'), 'utf8');
  assert.match(helper, /--image-backend dsh-current/);
  assert.match(helper, /--metadata-file/);
  assert.match(helper, /Codex OAuth first/); // 原后端文档保留
});
