import test from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { resolve } from 'node:path';
import YAML from 'yaml';

const workspaceRoot = resolve(import.meta.dirname, '../../../');
const skillRoot = resolve(workspaceRoot, '.dsh/skills/image-to-editable-ppt');
const webPatch = resolve(workspaceRoot, '.dsh/profiles/web/cordis.patch.yml');
const npmRoot = resolve(process.env.APPDATA ?? '', 'npm', 'node_modules', '@deepseek-ai', 'dsh');
const standardPatchPath = resolve(npmRoot, 'node_modules', '@deepseek-ai', 'dsh-web-app', 'presets', 'standard.patch.yml');

const customYamlTags = {
  logLevel: 'silent',
  customTags: [{ tag: '!js', resolve: (str) => ({ __jsExpr: str }) }, { tag: '!!js', resolve: (str) => ({ __jsExpr: str }) }],
};

async function findPresetPlugins(filePath, presetId) {
  const raw = await readFile(filePath, 'utf8');
  const doc = YAML.parse(raw, customYamlTags);
  for (const row of doc ?? []) {
    const items = Array.isArray(row?.insert) ? row.insert : [row];
    for (const item of items) {
      if (item?.name === '@deepseek-ai/dsh-agent-preset' && item?.config?.id === presetId) {
        return item.config.plugins;
      }
    }
  }
  throw new Error(`未在 ${filePath} 中找到预设 ${presetId}`);
}

test('editable-ppt Persona 声明 DSH 当前连接边界但不复制工具 schema', async () => {
  const plugins = await findPresetPlugins(webPatch, 'editable-ppt');
  const personaText = plugins.find((row) => row.id === 'persona')?.config?.prefix ?? '';
  assert.match(personaText, /DSH 当前生图连接/);
  assert.match(personaText, /editable_ppt_image/);
  assert.match(personaText, /禁止 Codex 和任何后端回退/);
  assert.match(personaText, /任务开始时锁定/);
  // Persona 保持短小：不含枚举 schema、错误矩阵或执行步骤清单。
  assert.doesNotMatch(personaText, /additionalProperties|"enum"|codex_backend_forbidden|dsh_current_cli_forbidden/);
  assert.ok(personaText.length > 0 && personaText.length < 800, `Persona 应保持短小，当前 ${personaText.length} 字符`);
});

test('editable-ppt roster 与官方 standard 无差异（仅 Persona 文本不同）', async () => {
  const [source, baseline] = await Promise.all([
    findPresetPlugins(webPatch, 'editable-ppt'),
    findPresetPlugins(standardPatchPath, 'standard'),
  ]);
  assert.deepEqual(source.map((r) => r.id), baseline.map((r) => r.id));
  assert.deepEqual(
    source.filter((row) => row.id !== 'persona'),
    baseline.filter((row) => row.id !== 'persona'),
  );
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
