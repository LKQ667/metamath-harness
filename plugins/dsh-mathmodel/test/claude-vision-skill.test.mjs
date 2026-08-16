import test from 'node:test';
import assert from 'node:assert/strict';
import { readFile, stat } from 'node:fs/promises';
import { resolve } from 'node:path';
import { parseDocument } from 'yaml';

const root = resolve(import.meta.dirname, '../../../.dsh/skills/claude-vision-skill');

test('Claude Vision 仅手动触发并固定使用 DSH 原生工具', async () => {
  const source = await readFile(resolve(root, 'SKILL.md'), 'utf8');
  const match = source.match(/^---\s*\r?\n([\s\S]*?)\r?\n---/);
  const meta = parseDocument(match[1], { strict: true, uniqueKeys: true }).toJS();
  assert.equal(meta['user-invocable'], true);
  assert.equal(meta['disable-model-invocation'], true);
  assert.match(source, /只调用原生 `vision_analyze`/);
  assert.match(source, /qwen3\.7-plus/);
  assert.match(source, /qwen3\.7-flash-2026-07-15/);
});

test('旧 vision.js 不再读取当前目录或 Skill 目录 .env', async () => {
  const source = await readFile(resolve(root, 'vision.js'), 'utf8');
  assert.doesNotMatch(source, /loadEnvFile|readFileSync\([^\n]*\.env|__dirname[^\n]*\.env|process\.cwd\(\)[^\n]*\.env/);
  assert.match(source, /仅读取调用进程显式提供的环境变量/);
  assert.equal((await stat(resolve(root, '.env'))).isFile(), true);
});

test('凭据与连通性流程不把 Key 放入 Prompt 或伪造成功', async () => {
  const source = await readFile(resolve(root, 'SKILL.md'), 'utf8');
  assert.match(source, /不要要求用户把 Key 粘贴到对话文本/);
  assert.match(source, /没有测试图片时只说明尚未测试，不编造连通成功/);
  assert.match(source, /不得读取、复制、移动、改写或删除它/);
});
