import test from 'node:test';
import assert from 'node:assert/strict';
import { readdir } from 'node:fs/promises';
import { resolve } from 'node:path';
import { SkillHelpCatalog } from '../lib/index.js';

const skillRoot = resolve(import.meta.dirname, '../../../.dsh/skills');

test('技能说明覆盖当前 skills 目录的每一个 Skill', async () => {
  const directories = (await readdir(skillRoot, { withFileTypes: true }))
    .filter((entry) => entry.isDirectory())
    .map((entry) => entry.name)
    .sort();
  const skills = await new SkillHelpCatalog(skillRoot).list();
  assert.deepEqual(skills.map((item) => item.skill), directories);
  assert.ok(skills.length >= 16);
  assert.equal(new Set(skills.map((item) => item.skill)).size, skills.length);
  for (const skill of skills) {
    assert.ok(skill.title.length >= 2, `${skill.skill} 缺少通俗标题`);
    assert.ok(skill.summary.length >= 8 && skill.summary.length <= 88, `${skill.skill} 说明长度不合格`);
    assert.ok(skill.useWhen.length >= 8, `${skill.skill} 缺少适用场景`);
    assert.ok(skill.output.length >= 4, `${skill.skill} 缺少输出说明`);
  }
});

test('当前 Skill 都有人工通俗说明', async () => {
  const skills = await new SkillHelpCatalog(skillRoot).list();
  const summaries = Object.fromEntries(skills.map((item) => [item.skill, item.summary]));
  assert.match(summaries['academic-search'], /查找论文/);
  assert.match(summaries['humanizer'], /AI 味道/);
  assert.match(summaries.imagegen, /生图模型/);
  assert.match(summaries['skill-installer'], /安装/);
  assert.match(summaries['yatai-cn'], /亚太杯/);
});
