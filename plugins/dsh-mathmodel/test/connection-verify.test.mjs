import test from 'node:test';
import assert from 'node:assert/strict';
import { verifyConnection } from '../lib/index.js';

const connection = Object.freeze({ id: 'img_verify_01', name: '兼容网关', template: 'openai-compatible', adapter: 'openai-images', model: 'image-a', baseUrl: 'https://gateway.example/v1' });
const png = Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg==', 'base64').toString('base64');
const json = (data, status = 200) => ({ ok: status >= 200 && status < 300, status, json: async () => data, headers: { get: () => null } });

test('真实验证只返回身份指纹与协议，不落盘', async () => {
  const result = await verifyConnection({ connection, credential: 'sk-verify-secret-long', now: () => '2026-08-16T10:00:00.000Z', fetchImpl: async () => json({ data: [{ b64_json: png }] }) });
  assert.equal(result.ok, true); assert.equal(result.protocol, 'openai-images');
  assert.match(result.identity.keyFingerprint, /^[a-f0-9]{64}$/); assert.match(result.identity.baseUrlFingerprint, /^[a-f0-9]{64}$/);
  assert.doesNotMatch(JSON.stringify(result), /sk-verify-secret-long/);
});

test('仅明确端点不匹配时，通用兼容连接可改试 chat 图片协议一次', async () => {
  const calls = [];
  const result = await verifyConnection({ connection, credential: 'sk-verify-secret-long', now: () => '2026-08-16T10:00:00.000Z', fetchImpl: async (url) => {
    calls.push(url);
    if (url.endsWith('/images/generations')) return json({ error: { code: 'not_supported' } }, 405);
    return json({ choices: [{ message: { content: [{ image_url: { url: `data:image/png;base64,${png}` } }] } }] });
  } });
  assert.equal(result.ok, true); assert.equal(result.protocol, 'openai-chat-image'); assert.equal(calls.length, 2);
});

test('认证、限流和空响应不会自动切换协议，并给出脱敏分类', async () => {
  for (const [status, expected] of [[401, 'auth_rejected'], [429, 'rate_limited']]) {
    let calls = 0;
    const result = await verifyConnection({ connection, credential: 'sk-verify-secret-long', fetchImpl: async () => { calls += 1; return json({ error: { code: 'bad' } }, status); } });
    assert.equal(result.ok, false); assert.equal(result.error.code, expected); assert.equal(calls, 1);
  }
  let calls = 0;
  const empty = await verifyConnection({ connection, credential: 'sk-verify-secret-long', fetchImpl: async () => { calls += 1; return json({ data: [] }); } });
  assert.equal(empty.ok, false); assert.equal(empty.error.code, 'no_image_asset'); assert.equal(calls, 1);
});
