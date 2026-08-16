import test from 'node:test';
import assert from 'node:assert/strict';
import {
  openaiImagesAdapter, openaiChatImageAdapter, sub2apiAsyncImagesAdapter,
} from '../lib/index.js';

const png = Buffer.from('adapter-image').toString('base64');
const request = Object.freeze({ prompt: '受控测试图', count: 1, size: '1024x1024' });
const context = Object.freeze({
  endpoint: 'https://gateway.example/v1', model: 'image-test', credential: 'adapter-secret',
  request, references: [],
});
const json = (data, status = 200) => ({
  ok: status >= 200 && status < 300,
  status,
  json: async () => data,
  headers: { get: () => null },
});

test('OpenAI Images 适配器使用连接端点，解析 base64 图片且不泄漏凭据', async () => {
  let captured;
  const assets = await openaiImagesAdapter({
    ...context,
    fetchImpl: async (url, init) => {
      captured = { url, init };
      return json({ data: [{ b64_json: png }] });
    },
  });
  assert.equal(captured.url, 'https://gateway.example/v1/images/generations');
  assert.equal(captured.init.headers.authorization, 'Bearer adapter-secret');
  assert.deepEqual(assets, [{ kind: 'base64', data: png, mime: 'image/png' }]);
});

test('OpenAI Images 有参考图时仅改用 edits multipart 端点', async () => {
  let captured;
  await openaiImagesAdapter({
    ...context,
    references: [{ bytes: Buffer.from('reference'), mime: 'image/png', ext: 'png' }],
    fetchImpl: async (url, init) => {
      captured = { url, init };
      return json({ data: [{ b64_json: png }] });
    },
  });
  assert.equal(captured.url, 'https://gateway.example/v1/images/edits');
  assert.ok(captured.init.body instanceof FormData);
  assert.equal('content-type' in captured.init.headers, false);
});

test('Sub2API 异步适配器在主轮询 404 后只改试一次兼容任务路径', async () => {
  const calls = [];
  const assets = await sub2apiAsyncImagesAdapter({
    ...context,
    sleep: async () => {},
    fetchImpl: async (url, init) => {
      calls.push({ url, init });
      if (url.endsWith('/images/generations/async')) return json({ task_id: 'task/one' });
      if (url.includes('/images/tasks/')) return json({}, 404);
      return json({ status: 'completed', data: [{ b64_json: png }] });
    },
  });
  assert.equal(calls.length, 3);
  assert.equal(calls[0].url, 'https://gateway.example/v1/images/generations/async');
  assert.match(calls[1].url, /images\/tasks\/task%2Fone$/);
  assert.match(calls[2].url, /images\/task\/task%2Fone$/);
  assert.deepEqual(assets, [{ kind: 'base64', data: png, mime: 'image/png' }]);
});

test('Sub2API 在取消时不继续轮询或切换其他供应商', async () => {
  const controller = new AbortController();
  controller.abort();
  let calls = 0;
  await assert.rejects(
    () => sub2apiAsyncImagesAdapter({
      ...context,
      signal: controller.signal,
      fetchImpl: async () => { calls += 1; return json({ task_id: 'unused' }); },
    }),
    (error) => error?.name === 'AbortError',
  );
  assert.equal(calls, 1);
});

test('受限 Chat 图片适配器只接受真实图片字段，忽略普通文本', async () => {
  let captured;
  const assets = await openaiChatImageAdapter({
    ...context,
    fetchImpl: async (url, init) => {
      captured = { url, init };
      return json({ choices: [{ message: { content: ['普通文字', { image_url: { url: `data:image/png;base64,${png}` } }] } }] });
    },
  });
  assert.equal(captured.url, 'https://gateway.example/v1/chat/completions');
  assert.deepEqual(assets, [{ kind: 'base64', data: png, mime: 'image/png' }]);
  assert.doesNotMatch(JSON.stringify(assets), /adapter-secret/);
});
