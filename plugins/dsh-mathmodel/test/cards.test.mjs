import test from 'node:test';
import assert from 'node:assert/strict';
import { mkdtemp, mkdir, writeFile } from 'node:fs/promises';
import { join } from 'node:path';
import { tmpdir } from 'node:os';
import { CardRegistry, MathModelCardsRemote, SkillHelpCatalog, parseAndValidateCard } from '../lib/index.js';

const skillMd = `---\nname: demo-card\ndescription: demo\nuser-invocable: true\ndisable-model-invocation: true\n---\n# demo\n`;
const sidecar = (summary = '演示卡片') => `schema: dsh.mathmodel.card/v1
skill: demo-card
title: 演示
summary: ${summary}
category: test
fields:
  - id: mode
    label: 模式
    type: select
    required: true
    default: safe
    options: [safe, fast]
  - id: count
    label: 数量
    type: number
    default: 1
    min: 1
    max: 4
  - id: user_notes
    label: 补充要求
    type: text
prompt:
  objective: 完成演示任务
  instructions:
    - 不发送，只生成草稿
help:
  purpose: 验证动态卡片
  inputs: [模式]
  outputs: [结构化草稿]
  limits: [不自动发送]
  dependencies: []
`;

async function fixture() {
  const root = await mkdtemp(join(tmpdir(), 'dsh-mathmodel-card-'));
  const skill = join(root, 'demo-card');
  await mkdir(skill);
  await writeFile(join(skill, 'SKILL.md'), skillMd, 'utf8');
  await writeFile(join(skill, 'mathmodel-card.yml'), sidecar(), 'utf8');
  return { root, skill };
}

test('严格拒绝未知顶层字段和字段类型', () => {
  assert.throws(() => parseAndValidateCard(`${sidecar()}unknown: true\n`), /unknown.*未知字段/);
  assert.throws(() => parseAndValidateCard(sidecar().replace('type: select', 'type: mystery')), /不支持类型 mystery/);
});

test('目录扫描只返回显式 user-invocable 的同名卡片', async () => {
  const { root } = await fixture();
  const cards = await new CardRegistry(root).list();
  assert.equal(cards.length, 1);
  assert.equal(cards[0].skill, 'demo-card');
});

test('内容哈希使缓存自动失效', async () => {
  const { root, skill } = await fixture();
  const registry = new CardRegistry(root);
  const first = await registry.list();
  assert.equal((await registry.list()), first);
  await writeFile(join(skill, 'mathmodel-card.yml'), sidecar('已更新'), 'utf8');
  const second = await registry.list();
  assert.notEqual(second, first);
  assert.equal(second[0].summary, '已更新');
});

test('Remote render 校验值并输出稳定草稿，不含发送动作', async () => {
  const { root } = await fixture();
  const remote = new MathModelCardsRemote(new CardRegistry(root), new SkillHelpCatalog(root));
  const list = await remote.list();
  assert.equal(list.schema, 'dsh.mathmodel.cards/v1');
  const rendered = await remote.render('demo-card', { mode: 'fast', count: 2, user_notes: '保留中文' });
  assert.match(rendered.text, /^\/demo-card/);
  assert.match(rendered.text, /dsh\.mathmodel\.request\/v1/);
  assert.match(rendered.text, /保留中文/);
  assert.doesNotMatch(rendered.text, /conversation\.send/);
  await assert.rejects(() => remote.render('demo-card', { mode: 'invalid' }), /不在允许范围/);
  const help = await remote.help();
  assert.equal(help.schema, 'dsh.mathmodel.skill-help/v1');
  assert.equal(help.skills[0].skill, 'demo-card');
  assert.equal(help.skills[0].summary, 'demo');
});
