import test from 'node:test';
import assert from 'node:assert/strict';
import { createToolExecutors, IMAGE_GENERATE_TOOL, VISION_ANALYZE_TOOL } from '../lib/index.js';
import { workspaceOf } from '../src/tools.js';

test('vision_analyze 与 image_generate schema 失败关闭', () => {
  assert.equal(VISION_ANALYZE_TOOL.name, 'vision_analyze');
  assert.equal(VISION_ANALYZE_TOOL.parameters.additionalProperties, false);
  assert.deepEqual(VISION_ANALYZE_TOOL.parameters.required, ['image']);
  assert.equal(IMAGE_GENERATE_TOOL.parameters.additionalProperties, false);
  assert.deepEqual(IMAGE_GENERATE_TOOL.parameters.required, ['prompt', 'authorizePaid']);
  assert.equal(IMAGE_GENERATE_TOOL.parameters.properties.count.minimum, 1);
  assert.equal(IMAGE_GENERATE_TOOL.parameters.properties.count.maximum, 4);
  assert.equal(IMAGE_GENERATE_TOOL.parameters.properties.connectionId.minLength, 8);
  assert.match(IMAGE_GENERATE_TOOL.parameters.properties.provider.description, /旧版兼容/);
});

test('工具执行器透传工作区和取消信号', async () => {
  const calls = [];
  const controller = new AbortController();
  const executors = createToolExecutors({
    workspace: 'F:\\workspace',
    vision: { analyze: async (args) => { calls.push(['vision', args]); return { ok: true }; } },
    image: { generate: async (args, options) => { calls.push(['image', args, options]); return { ok: true }; } },
  });
  await executors.vision_analyze({ image: 'a.png' }, controller.signal);
  await executors.image_generate({ prompt: 'x', authorizePaid: true }, controller.signal);
  assert.equal(calls[0][1].workspace, 'F:\\workspace');
  assert.equal(calls[0][1].signal, controller.signal);
  assert.equal(calls[1][2].workspace, 'F:\\workspace');
  assert.equal(calls[1][2].signal, controller.signal);
});

test('工具从 Harness 官方 session.header.cwd 读取工作区', () => {
  assert.equal(workspaceOf({ agent: { session: { header: { cwd: 'F:\\workspace' } } } }), 'F:\\workspace');
  assert.throws(() => workspaceOf({ agent: { session: { meta: { cwd: 'F:\\legacy' } } } }), /需要绑定带工作区/);
});
