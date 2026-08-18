import test from 'node:test';
import assert from 'node:assert/strict';
import { mkdtemp, readFile, readdir, writeFile } from 'node:fs/promises';
import { dirname, join } from 'node:path';
import { tmpdir } from 'node:os';
import { ImageGenerationService } from '../lib/index.js';

const secret = 'sk' + '-image-secret-fixture-long';
// 真实 1x1 PNG 字节：供应商 base64 路径必须携带真实图片魔数才能通过嗅探
const tinyPngBytes = Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg==', 'base64');
const b64 = tinyPngBytes.toString('base64');
// JPEG 魔数（FF D8 FF …JFIF）：复现“供应商返回 JPEG、适配器默认 PNG”的根因场景
const jpegBytes = Buffer.from([0xff, 0xd8, 0xff, 0xe0, 0x00, 0x10, 0x4a, 0x46, 0x49, 0x46, 0x00, 0x01]);
const request = { prompt: '绘制模型结构图', count: 1, authorizePaid: true, outputDir: 'generated' };
const ready = Object.freeze({ id: 'img_ready_01', name: '测试 OpenAI Images', template: 'openai-compatible', adapter: 'openai-images', model: 'test-image', baseUrl: 'https://images.example/v1', verification: { status: 'ready', protocol: 'openai-images' } });
const json = (data, status = 200) => ({ ok: status >= 200 && status < 300, status, json: async () => data, headers: { get: () => null } });
const image = (bytes = Buffer.from('downloaded-image'), mime = 'image/png') => ({ ok: true, status: 200, headers: { get: (key) => key.toLowerCase() === 'content-type' ? mime : key.toLowerCase() === 'content-length' ? String(bytes.length) : null }, arrayBuffer: async () => bytes });

async function workspace() { return await mkdtemp(join(tmpdir(), 'dsh-image-')); }
function connections({ active = ready, explicit = ready, legacy = ready } = {}) {
  const calls = [];
  return {
    calls,
    async resolveForGenerate(id) {
      calls.push({ method: 'resolveForGenerate', id });
      const connection = id ? explicit : active;
      if (connection instanceof Error) throw connection;
      return { connection, adapterId: connection.verification.protocol, credentialValue: secret };
    },
    async resolveLegacyProvider(provider) {
      calls.push({ method: 'resolveLegacyProvider', provider });
      if (legacy instanceof Error) throw legacy;
      return { connection: legacy, adapterId: legacy.verification.protocol, credentialValue: secret };
    },
  };
}

test('默认当前连接只调用一次并写入无秘密连接元数据', async () => {
  const root = await workspace(); const resolver = connections(); const fetchCalls = [];
  const service = new ImageGenerationService({ connections: resolver, now: () => 100, fetchImpl: async (url, init) => { fetchCalls.push({ url, init }); return json({ data: [{ b64_json: b64 }] }); } });
  const result = await service.generate({ ...request, outputDir: undefined }, { workspace: root });
  assert.equal(result.ok, true); assert.equal(result.connectionId, ready.id); assert.equal(result.provider, ready.template); assert.equal(dirname(result.files[0]), root); assert.equal(fetchCalls.length, 1); assert.equal((await readFile(result.files[0])).toString('base64'), b64);
  const metadata = await readFile(result.metadataFile, 'utf8');
  assert.match(metadata, /"connectionId": "img_ready_01"/); assert.match(metadata, /"protocol": "openai-images"/); assert.doesNotMatch(metadata, /绘制模型结构图|image-secret-fixture|images\.example/);
});

test('显式 connectionId 优先于当前连接且不改变当前状态', async () => {
  const root = await workspace(); const chosen = { ...ready, id: 'img_explicit_02', name: '显式连接' }; const resolver = connections({ explicit: chosen });
  const service = new ImageGenerationService({ connections: resolver, now: () => 200, fetchImpl: async () => json({ data: [{ b64_json: b64 }] }) });
  const result = await service.generate({ ...request, connectionId: chosen.id }, { workspace: root });
  assert.equal(result.ok, true); assert.deepEqual(resolver.calls, [{ method: 'resolveForGenerate', id: chosen.id }]); assert.equal(result.connectionId, chosen.id);
});

test('旧 provider 仅走唯一迁移连接，不触发多供应商自动兜底', async () => {
  const root = await workspace(); const resolver = connections();
  const service = new ImageGenerationService({ connections: resolver, now: () => 300, fetchImpl: async () => json({ data: [{ b64_json: b64 }] }) });
  const result = await service.generate({ ...request, provider: 'custom' }, { workspace: root });
  assert.equal(result.ok, true); assert.deepEqual(resolver.calls, [{ method: 'resolveLegacyProvider', provider: 'custom' }]);
});

test('无当前连接、待验证或缺少 Key 失败关闭且不产生网络请求', async () => {
  const root = await workspace();
  for (const [code, message] of [['no_active_connection', '未选择当前连接'], ['capability_pending', '尚未验证'], ['credential_missing', '缺少 Key']]) {
    const error = Object.assign(new Error(`${message} ${secret}`), { code }); let fetches = 0;
    const service = new ImageGenerationService({ connections: connections({ active: error }), fetchImpl: async () => { fetches += 1; return json({}); } });
    const result = await service.generate(request, { workspace: root });
    assert.equal(result.ok, false); assert.equal(result.error.code, code); assert.equal(fetches, 0); assert.doesNotMatch(JSON.stringify(result), new RegExp(secret));
  }
});

test('参考图使用当前连接的 edits 协议，原图保持不变', async () => {
  const root = await workspace(); const ref = join(root, 'reference.png'); await writeFile(ref, Buffer.from('reference-bytes')); let body; let url;
  const service = new ImageGenerationService({ connections: connections(), now: () => 400, fetchImpl: async (nextUrl, init) => { url = nextUrl; body = init.body; return json({ data: [{ b64_json: b64 }] }); } });
  const result = await service.generate({ ...request, referenceImages: ['reference.png'] }, { workspace: root });
  assert.equal(result.ok, true); assert.match(url, /\/images\/edits$/); assert.ok(body instanceof FormData); assert.equal((await readFile(ref)).toString(), 'reference-bytes');
});

test('单连接生成失败保留结构化回退并脱敏', async () => {
  const root = await workspace();
  const service = new ImageGenerationService({ connections: connections(), adapters: { 'openai-images': async () => { throw new Error(`provider leaked ${secret}`); } } });
  const result = await service.generate(request, { workspace: root });
  assert.equal(result.ok, false); assert.equal(result.error.code, 'image_generation_failed'); assert.equal(result.error.failures.length, 1); assert.equal(result.fallback.skill, 'ai-draw-skills'); assert.doesNotMatch(JSON.stringify(result), new RegExp(secret));
});

test('下载拒绝非图片响应且不会改试其他连接', async () => {
  const root = await workspace(); let fetches = 0;
  const service = new ImageGenerationService({ connections: connections(), now: () => 600, adapters: { 'openai-images': async () => [{ kind: 'url', url: 'https://files.example/not-image' }] }, fetchImpl: async () => { fetches += 1; return image(Buffer.from('text'), 'text/plain'); } });
  const result = await service.generate(request, { workspace: root });
  assert.equal(result.ok, false); assert.equal(result.error.failures[0].code, 'invalid_content_type'); assert.equal(fetches, 1);
});

test('数量、付费授权、任务预算和路径边界在解析连接前失败关闭', async () => {
  const root = await workspace(); const resolver = connections(); const service = new ImageGenerationService({ connections: resolver, fetchImpl: async () => json({}) });
  await assert.rejects(() => service.generate({ ...request, count: 5 }, { workspace: root }), (error) => error.code === 'count_out_of_range');
  await assert.rejects(() => service.generate({ ...request, authorizePaid: false }, { workspace: root }), (error) => error.code === 'paid_not_authorized');
  await assert.rejects(() => service.generate({ ...request, count: 2, budgetRemaining: 1 }, { workspace: root }), (error) => error.code === 'budget_exceeded');
  await assert.rejects(() => service.generate({ ...request, outputDir: '..\\outside' }, { workspace: root }), (error) => error.code === 'path_outside_workspace');
  assert.equal(resolver.calls.length, 0);
});

test('供应商返回 JPEG 字节时按魔数纠正为 .jpg，不再误存 .png', async () => {
  const root = await workspace();
  const service = new ImageGenerationService({ connections: connections(), now: () => 700, fetchImpl: async () => json({ data: [{ b64_json: jpegBytes.toString('base64') }] }) });
  const result = await service.generate(request, { workspace: root });
  assert.equal(result.ok, true);
  assert.match(result.files[0], /\.jpg$/);
  assert.equal((await readFile(result.files[0])).toString('hex').slice(0, 6), jpegBytes.toString('hex').slice(0, 6));
  const metadata = JSON.parse(await readFile(result.metadataFile, 'utf8'));
  assert.equal(metadata.files[0].mime, 'image/jpeg');
});

test('供应商返回非图片字节时失败关闭且不落盘', async () => {
  const root = await workspace();
  const service = new ImageGenerationService({ connections: connections(), now: () => 800, fetchImpl: async () => json({ data: [{ b64_json: Buffer.from('not-an-image-at-all').toString('base64') }] }) });
  const result = await service.generate(request, { workspace: root });
  assert.equal(result.ok, false);
  assert.equal(result.error.code, 'image_generation_failed');
  assert.equal(result.error.failures[0].code, 'invalid_image_bytes');
  const leftovers = await readdir(join(root, 'generated')).catch(() => []);
  assert.equal(leftovers.length, 0);
});
