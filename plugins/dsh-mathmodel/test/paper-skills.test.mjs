import test from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { resolve } from 'node:path';
import { parseDocument } from 'yaml';
import { CardRegistry } from '../lib/cards/registry.js';
import { MathModelCardsRemote } from '../lib/cards/remote.js';

const root = resolve(import.meta.dirname, '../../../.dsh/skills');
const names = ['math-paper-cn', 'math-paper-huashu', 'math-paper-huawei'];

function frontmatter(source) {
  const match = source.match(/^---\s*\r?\n([\s\S]*?)\r?\n---/);
  assert.ok(match);
  return parseDocument(match[1], { strict: true, uniqueKeys: true }).toJS();
}

test('两套论文 Skill 仅手动调用且不再绑定历史绝对工程路径', async () => {
  for (const name of names) {
    const source = await readFile(resolve(root, name, 'SKILL.md'), 'utf8');
    const meta = frontmatter(source);
    assert.equal(meta['user-invocable'], true);
    assert.equal(meta['disable-model-invocation'], true);
    assert.doesNotMatch(source, /F:\\数学建模skills搭建|F:\\Py-Nature skills/);
  }
});

test('论文 Skill 消费卡片配置、Goal、付费健康门和旧项目兼容规则', async () => {
  for (const name of names) {
    const source = await readFile(resolve(root, name, 'SKILL.md'), 'utf8');
    for (const token of ['dsh.mathmodel.request/v1', 'body_pages', 'competition_language', 'figure_total', '顶刊一区 Top 1', 'drawing_mode', 'bar_policy', 'image_generate', 'confirm_paid_calls=true', 'ai_image_limit>0', 'get_goal', 'create_goal', 'verify_delivery.py']) {
      assert.match(source, new RegExp(token.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')));
    }
    assert.match(source, /仅在没有结构化配置的手动调用或旧项目缺记录时询问一次/);
  }
});

test('手动目录可发现论文卡片并把锁定值写入结构化草稿', async () => {
  const registry = new CardRegistry(root);
  const cards = await registry.list();
  assert.deepEqual(cards.filter((card) => names.includes(card.skill)).map((card) => card.skill), names);
  const remote = new MathModelCardsRemote(registry);
  const rendered = await remote.render('math-paper-cn', {
    problem_path: '赛题/题目.pdf', output_dir: '项目', body_pages: 18,
    competition_language: '英文', figure_total: 15,
    drawing_mode: 'Draw.io成图+AI概念提示词', bar_policy: '禁用',
    three_d_preference: '适合时建议',
    reference_excellent_papers: false, run_to_pdf: true,
    ai_image_limit: 0, confirm_paid_calls: false,
  });
  assert.match(rendered.text, /"body_pages": 18/);
  assert.match(rendered.text, /"bar_policy": "禁用"/);
  assert.match(rendered.text, /零例外禁止 bar\/Bar、barh、broken_barh、barplot、mark_bar、vbar、hbar/);
  assert.match(rendered.text, /时间区间改用线段与端点标记/);
  assert.match(rendered.text, /"competition_language": "英文"/);
  assert.match(rendered.text, /"figure_total": 15/);
  assert.match(rendered.text, /"run_to_pdf": true/);
});
