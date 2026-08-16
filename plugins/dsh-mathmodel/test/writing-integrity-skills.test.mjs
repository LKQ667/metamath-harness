import test from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { resolve } from 'node:path';
import { parseDocument } from 'yaml';

const root = resolve(import.meta.dirname, '../../../.dsh/skills');

function metadata(source) {
  const match = source.match(/^---\s*\r?\n([\s\S]*?)\r?\n---/);
  assert.ok(match);
  return parseDocument(match[1], { strict: true, uniqueKeys: true }).toJS();
}

test('三类写作与诚信 Skill 仅手动调用', async () => {
  for (const name of ['humanizer', 'research-writing-skill', 'anti-autoresearch']) {
    const source = await readFile(resolve(root, name, 'SKILL.md'), 'utf8');
    assert.equal(metadata(source)['user-invocable'], true);
    assert.equal(metadata(source)['disable-model-invocation'], true);
  }
});

test('Humanizer 先定位聚类风险且不承诺检测率或整篇改写', async () => {
  const source = await readFile(resolve(root, 'humanizer', 'SKILL.md'), 'utf8');
  assert.match(source, /多个具体模式共同支撑的高风险段落/);
  assert.match(source, /不得转换成作者身份概率、AIGC 百分比、查重率/);
  assert.match(source, /禁止无差别重写整篇/);
  assert.match(source, /公式及编号逐字保持/);
  assert.match(source, /参考文献条目逐字保持/);
});

test('Research Writing 按强度处理并保护术语公式引用', async () => {
  const source = await readFile(resolve(root, 'research-writing-skill', 'SKILL.md'), 'utf8');
  assert.match(source, /轻度校对只修正/);
  assert.match(source, /中度润色可重组句子/);
  assert.match(source, /深度重构可调整论证顺序/);
  assert.match(source, /缺证据处只能标记待补/);
});

test('Anti-autoresearch 由实际 manifest 限定等级且只给证据措辞', async () => {
  const source = await readFile(resolve(root, 'anti-autoresearch', 'SKILL.md'), 'utf8');
  assert.match(source, /artifact_manifest\.json.*实际可见材料确定 L0\/L1\/L2/);
  assert.match(source, /不代表 L3 完整复现/);
  assert.match(source, /只能写带 claim\/span 的异常、不一致、证据不足或需要核查/);
  assert.match(source, /不得输出作者身份概率、AI 生成率/);
  assert.match(source, /可能的无辜解释/);
});
