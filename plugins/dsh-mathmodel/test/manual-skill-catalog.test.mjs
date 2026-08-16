import test from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { resolve } from 'node:path';
import { parseDocument } from 'yaml';
import { CardRegistry } from '../lib/cards/registry.js';

const names = [
  'math-paper-cn', 'math-paper-huashu', 'grill-with-docs', 'ai-draw-skills', 'py-nature',
  'grill-ai-review', 'humanizer', 'research-writing-skill', 'claude-vision-skill', 'anti-autoresearch',
  'imagegen',
];
const root = resolve(import.meta.dirname, '../../../.dsh/skills');

test('十一项卡片 Skill 全部仅手动调用', async () => {
  for (const name of names) {
    const source = await readFile(resolve(root, name, 'SKILL.md'), 'utf8');
    const match = source.match(/^---\s*\r?\n([\s\S]*?)\r?\n---/);
    const meta = parseDocument(match[1], { strict: true, uniqueKeys: true }).toJS();
    assert.equal(meta['user-invocable'], true, name);
    assert.equal(meta['disable-model-invocation'], true, name);
  }
});

test('手动卡片目录恰好发现十一项 Skill', async () => {
  const cards = await new CardRegistry(root).list();
  assert.deepEqual(cards.map((card) => card.skill), [...names].sort((a, b) => a.localeCompare(b)));
});

test('ImageGen 只能调用原生生图工具且不检查环境变量', async () => {
  const imagegen = await readFile(resolve(root, 'imagegen', 'SKILL.md'), 'utf8');
  assert.match(imagegen, /直接原生调用一次 `image_generate`/);
  assert.match(imagegen, /不使用 `run_code`、PowerShell/);
  assert.match(imagegen, /confirm_paid_call.*`true`/);
  assert.doesNotMatch(imagegen, /OPENAI_API_KEY|DASHSCOPE_API_KEY|CUSTOM_IMAGE_API_KEY/);
});

test('AI Draw 不把卡片值当付费授权，Py-Nature 不依赖固定盘符', async () => {
  const aiDraw = await readFile(resolve(root, 'ai-draw-skills', 'SKILL.md'), 'utf8');
  const pyNature = await readFile(resolve(root, 'py-nature', 'SKILL.md'), 'utf8');
  assert.match(aiDraw, /不把该布尔值视为付费授权/);
  assert.match(aiDraw, /不调用 `image_generate`/);
  assert.match(pyNature, /输出目录不得越出工作区/);
  assert.doesNotMatch(pyNature, /F:\\Py-Nature skills/);
});
