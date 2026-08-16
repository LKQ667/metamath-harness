import test from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { resolve } from 'node:path';
import { parseDocument } from 'yaml';

const skills = resolve(import.meta.dirname, '../../../.dsh/skills');

function metadata(source) {
  const match = source.match(/^---\s*\r?\n([\s\S]*?)\r?\n---/);
  assert.ok(match);
  return parseDocument(match[1], { strict: true, uniqueKeys: true }).toJS();
}

test('拷问和评委 Skill 都保持仅手动调用', async () => {
  for (const name of ['grill-with-docs', 'grill-ai-review']) {
    const source = await readFile(resolve(skills, name, 'SKILL.md'), 'utf8');
    assert.equal(metadata(source)['user-invocable'], true);
    assert.equal(metadata(source)['disable-model-invocation'], true);
  }
});

test('赛题启发只问改变路线的关键问题且三种方法按阶段组合', async () => {
  const source = await readFile(resolve(skills, 'grill-with-docs', 'SKILL.md'), 'utf8');
  for (const phrase of ['question_budget` 是最多问题数，不是配额', '每轮只问一个最重要的问题', '不同答案会导致哪两条不同路线', '笛卡尔式清零', '苏格拉底式拷问', '归谬法极限测试']) {
    assert.match(source, new RegExp(phrase.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')));
  }
  assert.match(source, /路线尚未成形时不得提前使用/);
});

test('比赛评审固定三名独立专项评委加一名后置主审', async () => {
  const source = await readFile(resolve(skills, 'grill-ai-review', 'SKILL.md'), 'utf8');
  for (const role of ['规则与完整性评委', '模型与计算评委', '论文表达与图表评委']) assert.match(source, new RegExp(role));
  assert.match(source, /三个相互独立的专项子评委并行审查/);
  assert.match(source, /主审只在三份专项意见完成后工作/);
  assert.match(source, /当届官方规则与赛题要求 > 用户明确约束 > 通用数学建模评审量表/);
  assert.match(source, /不得伪造复现成功/);
});

test('优秀论文目录为空时按“暂无样本”正常回退', async () => {
  const source = await readFile(resolve(skills, 'grill-ai-review', 'SKILL.md'), 'utf8');
  assert.match(source, /暂无样本/);
  assert.match(source, /不得阻断评审/);
});
