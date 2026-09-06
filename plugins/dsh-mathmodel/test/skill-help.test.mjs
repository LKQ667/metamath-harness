import test from 'node:test';
import assert from 'node:assert/strict';
import { access, mkdir, mkdtemp, readdir, rm, writeFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { resolve } from 'node:path';
import { SkillHelpCatalog } from '../lib/index.js';

const skillRoot = resolve(import.meta.dirname, '../../../.dsh/skills');

test('技能说明覆盖当前 skills 目录的每一个 Skill', async () => {
  const directories = [];
  for (const entry of (await readdir(skillRoot, { withFileTypes: true })).filter((item) => item.isDirectory())) {
    try {
      await access(resolve(skillRoot, entry.name, 'SKILL.md'));
      directories.push(entry.name);
    } catch (error) {
      if (error?.code !== 'ENOENT') throw error;
    }
  }
  directories.sort();
  const skills = await new SkillHelpCatalog(skillRoot).list();
  assert.deepEqual(skills.map((item) => item.skill), directories);
  assert.ok(skills.length >= 17);
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
  assert.match(summaries['math-paper-huawei'], /华为杯/);
  assert.match(summaries['exploratory-data-analysis'], /探索分析/);
  assert.doesNotMatch(summaries['exploratory-data-analysis'], /Perform bounded/);
});

test('单个损坏的 frontmatter 不会拖垮其他 Skill 说明', async (t) => {
  const root = await mkdtemp(resolve(tmpdir(), 'dsh-skill-help-'));
  t.after(() => rm(root, { recursive: true, force: true }));
  await mkdir(resolve(root, 'valid'));
  await mkdir(resolve(root, 'broken'));
  await writeFile(resolve(root, 'valid', 'SKILL.md'), [
    '---',
    'name: valid',
    'description: 这是一个完整有效的测试技能说明。',
    '---',
    '',
    '# Valid',
  ].join('\n'));
  await writeFile(resolve(root, 'broken', 'SKILL.md'), '***\nname: broken\n***\n');

  const skills = await new SkillHelpCatalog(root).list();
  assert.deepEqual(skills.map((item) => item.skill), ['valid']);
});
