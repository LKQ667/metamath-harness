import test from 'node:test';
import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import { readFile } from 'node:fs/promises';
import { resolve } from 'node:path';
import { parseAndValidateCard, renderCardPrompt } from '../lib/index.js';

const names = [
  'math-paper-cn', 'math-paper-huashu', 'grill-with-docs', 'ai-draw-skills', 'py-nature',
  'grill-ai-review', 'humanizer', 'research-writing-skill', 'claude-vision-skill', 'anti-autoresearch',
  'imagegen',
];
const skillRoot = resolve(import.meta.dirname, '../../../.dsh/skills');
const snapshots = JSON.parse(await readFile(new URL('./card-snapshots.json', import.meta.url), 'utf8'));

async function loadCards() {
  return await Promise.all(names.map(async (name) => parseAndValidateCard(
    await readFile(resolve(skillRoot, name, 'mathmodel-card.yml'), 'utf8'),
    name,
  )));
}

function requiredFixture(card) {
  return Object.fromEntries(card.fields.filter((field) => field.required).map((field) => [
    field.id,
    field.type === 'number' ? field.min ?? 1 : field.type === 'boolean' ? field.default ?? false : 'fixture',
  ]));
}

test('十一张手动卡片全部通过严格 schema 且目录同名', async () => {
  const cards = await loadCards();
  assert.deepEqual(cards.map((card) => card.skill), names);
  assert.ok(cards.every((card) => card.schema === 'dsh.mathmodel.card/v1'));
});

test('关键产品默认值符合需求', async () => {
  const cards = new Map((await loadCards()).map((card) => [card.skill, card]));
  const defaults = (name) => Object.fromEntries(cards.get(name).fields.map((field) => [field.id, field.default]));
  assert.deepEqual(
    { language: defaults('math-paper-cn').competition_language, figures: defaults('math-paper-cn').figure_total, drawing: defaults('math-paper-cn').drawing_mode, bars: defaults('math-paper-cn').bar_policy, run: defaults('math-paper-cn').run_to_pdf, paid: defaults('math-paper-cn').confirm_paid_calls },
    { language: '中文', figures: 15, drawing: 'Draw.io成图+AI概念提示词', bars: '少用', run: true, paid: false },
  );
  assert.equal(defaults('math-paper-huashu').competition_language, '中文');
  assert.equal(defaults('math-paper-huashu').figure_total, 15);
  assert.equal(defaults('grill-ai-review').panel_mode, '3名专项评委+1名主审');
  assert.equal(defaults('humanizer').output_mode, '只报告');
  assert.equal(defaults('ai-draw-skills').prompt_only, true);
  assert.ok(!cards.get('ai-draw-skills').fields.some((field) => field.type === 'credential-status'));
  assert.equal(defaults('claude-vision-skill').primary_model, 'qwen3.7-plus');
  assert.equal(defaults('claude-vision-skill').fallback_model, 'qwen3.7-flash-2026-07-15');
  assert.equal(defaults('imagegen').connection_id, undefined);
  assert.equal(defaults('imagegen').size, '模型默认');
  assert.equal(defaults('imagegen').count, 1);
  assert.equal(defaults('imagegen').output_dir, '.');
  assert.equal(defaults('imagegen').confirm_paid_call, false);
});

test('所有必填字段均由渲染器执行失败关闭', async () => {
  for (const card of await loadCards()) {
    if (!card.fields.some((field) => field.required)) continue;
    assert.throws(() => renderCardPrompt(card, {}), /为必填项/, card.skill);
  }
});

test('十一张默认 Prompt 快照稳定', async () => {
  for (const card of await loadCards()) {
    const prompt = renderCardPrompt(card, requiredFixture(card));
    const digest = createHash('sha256').update(prompt).digest('hex');
    assert.equal(digest, snapshots[card.skill], card.skill);
    assert.match(prompt, new RegExp(`^/${card.skill}`));
    assert.match(prompt, /dsh\.mathmodel\.request\/v1/);
  }
});
