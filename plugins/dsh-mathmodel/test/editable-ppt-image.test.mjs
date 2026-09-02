import test from 'node:test';
import assert from 'node:assert/strict';
import { mkdir, mkdtemp, readFile, symlink, writeFile } from 'node:fs/promises';
import { dirname, join } from 'node:path';
import { tmpdir } from 'node:os';
import {
  EMPTY_IMAGE_CONNECTIONS, ImageConnectionCredentialStore, ImageConnectionService, ImageGenerationService,
} from '../lib/index.js';

const stamp = '2026-09-02T02:00:00.000Z';
const fakeKey = 'sk-fixture123';
const gatewayHost = 'images.example';
const tinyPng = Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg==', 'base64');
const tinyJpeg = Buffer.from([0xff, 0xd8, 0xff, 0xe0, 0x00, 0x10, 0x4a, 0x46, 0x49, 0x46]);
const b64 = tinyPng.toString('base64');
const json = (data, status = 200) => ({ ok: status >= 200 && status < 300, status, json: async () => data, headers: { get: () => null } });
const okImage = () => json({ data: [{ b64_json: b64 }] });

function memoryProvider(initial = {}) {
  const values = new Map(Object.entries(initial));
  return {
    values,
    async describe(ref) { return { configured: values.has(ref), writable: true, source: values.has(ref) ? 'managed' : 'none' }; },
    async resolve(ref) { return { value: values.get(ref) ?? '', source: values.has(ref) ? 'managed' : 'none' }; },
    async set(ref, value) { values.set(ref, value); },
    async unset(ref) { values.delete(ref); },
  };
}

/** 真实 ImageConnectionService + 内存凭据面，可准备就绪当前连接与 Codex 陷阱连接。 */
function subject({ fetchImpl = async () => okImage() } = {}) {
  let value = EMPTY_IMAGE_CONNECTIONS;
  const provider = memoryProvider();
  const settings = { get: () => value, async replace(next) { value = next; } };
  const connections = new ImageConnectionService({
    settings,
    legacySettings: { get: () => ({}) },
    credentialStore: new ImageConnectionCredentialStore(provider),
    credentialProvider: provider,
    hasV2UserSection: () => true,
    now: () => stamp,
    fetchImpl: async () => ({ ok: true, json: async () => ({ data: [] }) }),
  });
  const fetchCalls = [];
  const instrumented = async (url, init) => { fetchCalls.push({ url, init }); return await fetchImpl(url, init); };
  const service = new ImageGenerationService({ connections, fetchImpl: instrumented, now: () => 1, sleep: async () => {} });
  return {
    connections,
    service,
    provider,
    fetchCalls,
    value: () => value,
    async addReady(draft, { key = fakeKey, active = true } = {}) {
      const list = await this.connections.upsert(draft);
      const created = list.connections.at(-1);
      if (draft.template !== 'codex-subscription' && draft.template !== 'grok-subscription') await this.connections.setKey(created.id, key);
      const current = this.value();
      const verification = {
        status: 'ready', protocol: draft.adapter, model: draft.model, template: draft.template,
        baseUrlFingerprint: 'a'.repeat(64), keyFingerprint: 'b'.repeat(64), verifiedAt: stamp, message: '',
      };
      await this.connections.settings.replace({
        ...current,
        connections: current.connections.map((item) => (item.id === created.id ? { ...item, verification } : item)),
        activeConnectionId: active ? created.id : current.activeConnectionId,
      });
      return created;
    },
    async patchConnection(id, patch, { setActive } = {}) {
      const current = this.value();
      await this.connections.settings.replace({
        ...current,
        connections: current.connections.map((item) => (item.id === id ? { ...item, ...patch(item) } : item)),
        ...(setActive === undefined ? {} : { activeConnectionId: setActive }),
      });
    },
  };
}

const openAiDraft = { name: 'tokenbom-image2', template: 'openai-compatible', adapter: 'openai-images', model: 'gpt-image-2', baseUrl: `https://${gatewayHost}/v1` };
const dashscopeDraft = { name: '百炼生图', template: 'dashscope', adapter: 'dashscope-async', model: 'qwen-image-3.0-pro' };
const codexDraft = { name: 'ChatGPT 订阅', template: 'codex-subscription', adapter: 'codex-images', model: 'gpt-image-2' };

async function workspace() {
  const root = await mkdtemp(join(tmpdir(), 'dsh-epp-'));
  await mkdir(join(root, 'assets'), { recursive: true });
  return root;
}

function baseRequest(overrides = {}) {
  return {
    action: 'generate', prompt: '重建干净的幻灯片背景', outputPath: 'assets/clean_base.png',
    authorizePaid: true, ...overrides,
  };
}

// —— 1. status：当前连接安全描述 ——
test('status 返回当前连接的非敏感锁定描述与能力矩阵', async () => {
  const root = await workspace(); const ctx = subject();
  const created = await ctx.addReady(openAiDraft);
  const result = await ctx.service.editablePptImage({ action: 'status' }, { workspace: root });
  assert.equal(result.ok, true);
  assert.equal(result.schema, 'dsh.mathmodel.editable-ppt-image-status/v1');
  assert.equal(result.connectionId, created.id);
  assert.equal(result.connectionName, 'tokenbom-image2');
  assert.equal(result.template, 'openai-compatible');
  assert.equal(result.model, 'gpt-image-2');
  assert.equal(result.protocol, 'openai-images');
  assert.deepEqual(result.capabilities, { generate: true, edit: true, multiReference: true, mask: true, quality: true });
  assert.equal(result.codexForbidden, true);
  assert.equal(ctx.fetchCalls.length, 0);
  assert.doesNotMatch(JSON.stringify(result), new RegExp(`${fakeKey}|${gatewayHost}|credentialRef|baseUrl|MATHMODEL`));
});

test('status 未选择当前连接时返回 no_active_connection 且零网络', async () => {
  const root = await workspace();
  const empty = subject();
  const result = await empty.service.editablePptImage({ action: 'status' }, { workspace: root });
  assert.equal(result.ok, false);
  assert.equal(result.error.code, 'no_active_connection');
  assert.equal(empty.fetchCalls.length, 0);
});

test('活动连接凭据被清除后 status 返回 credential_missing', async () => {
  const root = await workspace(); const ctx = subject();
  const created = await ctx.addReady(openAiDraft);
  ctx.provider.values.delete(created.credentialRef);
  const result = await ctx.service.editablePptImage({ action: 'status' }, { workspace: root });
  assert.equal(result.error.code, 'credential_missing');
});

// —— 2. Codex 三层识别（status 与 generate 都在凭据/付费前失败关闭） ——
test('当前连接是 Codex：status/generate 在凭据与网络前失败 codex_backend_forbidden', async () => {
  const root = await workspace(); const ctx = subject();
  await ctx.addReady(codexDraft);
  const status = await ctx.service.editablePptImage({ action: 'status' }, { workspace: root });
  assert.equal(status.ok, false);
  assert.equal(status.error.code, 'codex_backend_forbidden');
  const codexId = ctx.value().activeConnectionId;
  const gen = await ctx.service.editablePptImage(baseRequest({ connectionId: codexId }), { workspace: root });
  assert.equal(gen.error.code, 'codex_backend_forbidden');
  assert.equal(ctx.fetchCalls.length, 0);
});

test('验证协议为 codex-images 的伪兼容连接同样被第二层拒绝', async () => {
  const root = await workspace(); const ctx = subject();
  const trap = await ctx.addReady(openAiDraft);
  await ctx.patchConnection(trap.id, () => ({ verification: { status: 'ready', protocol: 'codex-images', model: 'gpt-image-2', template: 'openai-compatible', baseUrlFingerprint: 'a'.repeat(64), keyFingerprint: 'b'.repeat(64), verifiedAt: stamp, message: '' } }));
  const result = await ctx.service.editablePptImage(baseRequest({ connectionId: trap.id }), { workspace: root });
  assert.equal(result.error.code, 'codex_backend_forbidden');
  assert.equal(ctx.fetchCalls.length, 0);
});

test('直连端点主机为 chatgpt.com 且路径属于 Codex Images 时第三层拒绝', async () => {
  const root = await workspace(); const ctx = subject();
  const trap = await ctx.addReady({ ...openAiDraft, name: '可疑网关', baseUrl: 'https://chatgpt.com/backend-api/codex' });
  const result = await ctx.service.editablePptImage(baseRequest({ connectionId: trap.id }), { workspace: root });
  assert.equal(result.error.code, 'codex_backend_forbidden');
  assert.equal(ctx.fetchCalls.length, 0);
});

// —— 3/4/5. 运行锁定语义 ——
test('generate/edit 必须显式携带锁定 connectionId，缺失即失败且零网络', async () => {
  const root = await workspace(); const ctx = subject();
  await ctx.addReady(openAiDraft);
  const gen = await ctx.service.editablePptImage(baseRequest(), { workspace: root });
  assert.equal(gen.error.code, 'connection_id_required');
  const edit = await ctx.service.editablePptImage(baseRequest({ action: 'edit', referenceImages: ['assets/source.png'] }), { workspace: root });
  assert.equal(edit.error.code, 'connection_id_required');
  assert.equal(ctx.fetchCalls.length, 0);
});

test('锁定调用跟随显式 connectionId，不跟随当前连接漂移', async () => {
  const root = await workspace(); const ctx = subject();
  const pinned = await ctx.addReady({ ...openAiDraft, name: '锁定连接' });
  const other = await ctx.addReady({ ...openAiDraft, name: '后来的当前连接', model: 'other-model' });
  assert.equal(ctx.value().activeConnectionId, other.id);
  const result = await ctx.service.editablePptImage(baseRequest({ connectionId: pinned.id, outputPath: 'assets/a.png' }), { workspace: root });
  assert.equal(result.ok, true);
  assert.equal(result.connectionId, pinned.id);
  assert.notEqual(pinned.id, other.id);
});

test('锁定连接被删除后不切换其他就绪连接', async () => {
  const root = await workspace(); const ctx = subject();
  const pinned = await ctx.addReady(openAiDraft);
  await ctx.addReady({ ...openAiDraft, name: '备份连接' }, { active: false });
  await ctx.connections.remove(pinned.id);
  const result = await ctx.service.editablePptImage(baseRequest({ connectionId: pinned.id }), { workspace: root });
  assert.equal(result.error.code, 'connection_not_found');
  assert.equal(ctx.fetchCalls.length, 0);
});

test('锁定连接被取消验证后返回 capability_pending，不换连接', async () => {
  const root = await workspace(); const ctx = subject();
  const pinned = await ctx.addReady(openAiDraft, { active: false });
  await ctx.addReady({ ...openAiDraft, name: '当前连接' });
  await ctx.patchConnection(pinned.id, () => ({ verification: undefined }));
  const result = await ctx.service.editablePptImage(baseRequest({ connectionId: pinned.id }), { workspace: root });
  assert.equal(result.error.code, 'capability_pending');
  assert.equal(ctx.fetchCalls.length, 0);
});

// —— 6/7. openai-images 参数映射：image[] / mask / quality / size ——
test('edit 把参考图放入 image[]、mask 独立成 mask 字段并传 size/quality', async () => {
  const root = await workspace(); const ctx = subject();
  const ready = await ctx.addReady(openAiDraft);
  await writeFile(join(root, 'assets', 'source.png'), tinyPng);
  await writeFile(join(root, 'assets', 'style.png'), tinyPng);
  await writeFile(join(root, 'assets', 'mask.png'), tinyPng);
  const result = await ctx.service.editablePptImage(baseRequest({
    action: 'edit', connectionId: ready.id, outputPath: 'assets/sheet-a.png',
    referenceImages: ['assets/source.png', 'assets/style.png'], maskImage: 'assets/mask.png',
    size: '1536x1024', quality: 'high',
  }), { workspace: root });
  assert.equal(result.ok, true);
  assert.equal(result.operation, 'edit');
  const call = ctx.fetchCalls.at(-1);
  assert.match(call.url, /\/images\/edits$/);
  assert.ok(call.init.body instanceof FormData);
  assert.equal(call.init.body.getAll('image[]').length, 2, 'mask 不得混入 image[]');
  const maskEntry = [...call.init.body.entries()].find(([key]) => key === 'mask');
  assert.ok(maskEntry, '必须存在独立 mask 字段');
  assert.equal(call.init.body.get('quality'), 'high');
  assert.equal(call.init.body.get('size'), '1536x1024');
  assert.equal(call.init.body.get('n'), '1');
});

test('generate 走 generations JSON 且透传 size/quality，单张写确定性路径与元数据', async () => {
  const root = await workspace(); const ctx = subject();
  const ready = await ctx.addReady(openAiDraft);
  const result = await ctx.service.editablePptImage(baseRequest({ connectionId: ready.id, outputPath: 'assets/base.png', size: 'auto', quality: 'medium' }), { workspace: root });
  assert.equal(result.ok, true);
  assert.equal(result.file, 'assets/base.png');
  const body = JSON.parse(ctx.fetchCalls.at(-1).init.body);
  assert.equal(body.n, 1); assert.equal(body.size, 'auto'); assert.equal(body.quality, 'medium');
  const stored = await readFile(join(root, 'assets', 'base.png'));
  assert.deepEqual(stored, tinyPng);
  const metadata = JSON.parse(await readFile(join(root, 'assets', 'base.dsh-image.json'), 'utf8'));
  assert.equal(metadata.schema, 'dsh.mathmodel.editable-ppt-image-metadata/v1');
  assert.equal(metadata.connectionId, ready.id);
  assert.equal(metadata.protocol, 'openai-images');
  assert.equal(metadata.operation, 'generate');
  assert.equal(metadata.files[0].sha256, result.sha256);
  assert.doesNotMatch(JSON.stringify(metadata), /重建干净|sk-|images\.example|baseUrl/);
});

// —— 8. 协议能力缺失 → capability_unsupported，不静默忽略、不发起请求 ——
test('mask/quality 不被协议支持时 capability_unsupported 失败且零网络', async () => {
  const root = await workspace(); const ctx = subject();
  const ready = await ctx.addReady(dashscopeDraft);
  await writeFile(join(root, 'assets', 'source.png'), tinyPng);
  await writeFile(join(root, 'assets', 'mask.png'), tinyPng);
  const withMask = await ctx.service.editablePptImage(baseRequest({
    action: 'edit', connectionId: ready.id, outputPath: 'assets/x.png',
    referenceImages: ['assets/source.png'], maskImage: 'assets/mask.png',
  }), { workspace: root });
  assert.equal(withMask.error.code, 'capability_unsupported');
  const withQuality = await ctx.service.editablePptImage(baseRequest({
    action: 'generate', connectionId: ready.id, outputPath: 'assets/y.png', quality: 'high',
  }), { workspace: root });
  assert.equal(withQuality.error.code, 'capability_unsupported');
  assert.equal(ctx.fetchCalls.length, 0);
});

// —— 9. 输出路径攻击 ——
test('outputPath 绝对越界、穿越与已存在输出失败', async () => {
  const root = await workspace(); const ctx = subject();
  const ready = await ctx.addReady(openAiDraft);
  const outside = await ctx.service.editablePptImage(baseRequest({ connectionId: ready.id, outputPath: join(dirname(root), 'outside.png') }), { workspace: root });
  assert.equal(outside.error.code, 'path_outside_workspace');
  const traverse = await ctx.service.editablePptImage(baseRequest({ connectionId: ready.id, outputPath: '../escape.png' }), { workspace: root });
  assert.equal(traverse.error.code, 'path_outside_workspace');
  const first = await ctx.service.editablePptImage(baseRequest({ connectionId: ready.id, outputPath: 'assets/twice.png' }), { workspace: root });
  assert.equal(first.ok, true);
  const second = await ctx.service.editablePptImage(baseRequest({ connectionId: ready.id, outputPath: 'assets/twice.png' }), { workspace: root });
  assert.equal(second.error.code, 'output_exists');
});

test('输出 sidecar 已存在时在付费调用前失败', async () => {
  const root = await workspace(); const ctx = subject();
  const ready = await ctx.addReady(openAiDraft);
  await writeFile(join(root, 'assets', 'clean_base.dsh-image.json'), '{}');
  const result = await ctx.service.editablePptImage(baseRequest({ connectionId: ready.id }), { workspace: root });
  assert.equal(result.error.code, 'output_exists');
  assert.equal(ctx.fetchCalls.length, 0);
  assert.equal(await readFile(join(root, 'assets', 'clean_base.dsh-image.json'), 'utf8'), '{}');
});

test('硬中断留下的本工具孤儿 sidecar 可安全恢复后重试', async () => {
  const root = await workspace(); const ctx = subject();
  const ready = await ctx.addReady(openAiDraft);
  await writeFile(join(root, 'assets', 'clean_base.dsh-image.json'), JSON.stringify({
    schema: 'dsh.mathmodel.editable-ppt-image-metadata/v1', files: [{ file: 'clean_base.png' }],
  }));
  const result = await ctx.service.editablePptImage(baseRequest({ connectionId: ready.id }), { workspace: root });
  assert.equal(result.ok, true);
  assert.equal(ctx.fetchCalls.length, 1);
  const metadata = JSON.parse(await readFile(join(root, 'assets', 'clean_base.dsh-image.json'), 'utf8'));
  assert.equal(metadata.connectionId, ready.id);
});

test('输出目录经 symlink/Junction 指向工作区外时失败且零网络', async () => {
  const root = await workspace(); const outside = await workspace(); const ctx = subject();
  const ready = await ctx.addReady(openAiDraft);
  await writeFile(join(outside, 'assets', 'source.png'), tinyPng);
  await symlink(outside, join(root, 'linked'), process.platform === 'win32' ? 'junction' : 'dir');
  const result = await ctx.service.editablePptImage(baseRequest({ connectionId: ready.id, outputPath: 'linked/escape.png' }), { workspace: root });
  assert.equal(result.error.code, 'path_outside_workspace');
  const input = await ctx.service.editablePptImage(baseRequest({
    action: 'edit', connectionId: ready.id, outputPath: 'assets/inside.png', referenceImages: ['linked/assets/source.png'],
  }), { workspace: root });
  assert.equal(input.error.code, 'path_outside_workspace');
  assert.equal(ctx.fetchCalls.length, 0);
});

test('供应商图片 MIME 与 outputPath 扩展名不一致时不落盘', async () => {
  const root = await workspace();
  const ctx = subject({ fetchImpl: async () => json({ data: [{ b64_json: tinyJpeg.toString('base64') }] }) });
  const ready = await ctx.addReady(openAiDraft);
  const result = await ctx.service.editablePptImage(baseRequest({ connectionId: ready.id }), { workspace: root });
  assert.equal(result.error.code, 'output_format_mismatch');
  assert.equal(await pathExistsForTest(join(root, 'assets', 'clean_base.png')), false);
  assert.equal(await pathExistsForTest(join(root, 'assets', 'clean_base.dsh-image.json')), false);
});

// —— 10. 输入图攻击 ——
test('URL 参考图、越界、非图片与超过 25 MB 的输入被拒绝', async () => {
  const root = await workspace(); const ctx = subject();
  const ready = await ctx.addReady(openAiDraft);
  await writeFile(join(root, 'assets', 'source.png'), tinyPng);
  await writeFile(join(root, 'assets', 'notimage.txt'), 'hello');
  await writeFile(join(root, 'assets', 'fake.png'), 'not really a png');
  await writeFile(join(root, 'assets', 'mask.jpg'), tinyJpeg);
  await writeFile(join(root, 'assets', 'big.png'), Buffer.alloc(26 * 1024 * 1024));
  const checks = [
    [baseRequest({ action: 'edit', connectionId: ready.id, referenceImages: ['https://evil.example/x.png'] }), 'reference_url_unsupported'],
    [baseRequest({ action: 'edit', connectionId: ready.id, referenceImages: [join(dirname(root), 'x.png')] }), 'path_outside_workspace'],
    [baseRequest({ action: 'edit', connectionId: ready.id, referenceImages: ['assets/notimage.txt'] }), 'unsupported_reference'],
    [baseRequest({ action: 'edit', connectionId: ready.id, referenceImages: ['assets/fake.png'] }), 'invalid_reference'],
    [baseRequest({ action: 'edit', connectionId: ready.id, referenceImages: ['assets/source.png'], maskImage: 'assets/mask.jpg' }), 'unsupported_mask'],
    [baseRequest({ action: 'edit', connectionId: ready.id, referenceImages: ['assets/missing.png'] }), 'reference_not_found'],
    [baseRequest({ action: 'edit', connectionId: ready.id, referenceImages: ['assets/big.png'] }), 'invalid_reference'],
  ];
  for (const [request, code] of checks) {
    const result = await ctx.service.editablePptImage(request, { workspace: root });
    assert.equal(result.error?.code, code, `期望 ${code}，实得 ${result.error?.code}`);
  }
  assert.equal(ctx.fetchCalls.length, 0);
});

async function pathExistsForTest(path) {
  try { await readFile(path); return true; } catch { return false; }
}

// —— 11. 重试矩阵 ——
async function retryCase(fetchImpl) {
  const root = await workspace(); const ctx = subject({ fetchImpl });
  const ready = await ctx.addReady(openAiDraft);
  const result = await ctx.service.editablePptImage(baseRequest({ connectionId: ready.id }), { workspace: root });
  return { ctx, result };
}

test('400/401/403/404/429 稳定分类且绝不重试', async () => {
  for (const [status, code] of [[400, 'provider_request_invalid'], [401, 'provider_auth_failed'], [403, 'provider_auth_failed'], [404, 'provider_request_invalid'], [429, 'provider_quota_exhausted']]) {
    const { ctx, result } = await retryCase(async () => json({ error: { code: 'x' } }, status));
    assert.equal(result.error.code, code, `HTTP ${status}`);
    assert.equal(ctx.fetchCalls.length, 1, `HTTP ${status} 不应重试`);
  }
});

test('网络错误与 5xx 最多重试 2 次后失败，仍用同一连接', async () => {
  let networkCalls = 0;
  const network = await retryCase(async () => { networkCalls += 1; throw new TypeError(`connect ECONNRESET leaked ${fakeKey}`); });
  assert.equal(network.result.error.code, 'provider_transport_failed');
  assert.equal(networkCalls, 3);
  let serverCalls = 0;
  const server = await retryCase(async () => { serverCalls += 1; return json({}, 503); });
  assert.equal(server.result.error.code, 'provider_server_failed');
  assert.equal(serverCalls, 3);
});

// —— 12. 零秘密泄漏（结果、错误、元数据） ——
test('错误与结果绝不携带 Key、Base URL、凭据引用，也无提示词回退', async () => {
  const root = await workspace();
  const ctx = subject({ fetchImpl: async () => { throw Object.assign(new Error(`upstream rejected ${fakeKey} at https://${gatewayHost}/v1 Authorization: Bearer ${fakeKey}`), { status: 418 }); } });
  const ready = await ctx.addReady(openAiDraft);
  const result = await ctx.service.editablePptImage(baseRequest({ connectionId: ready.id }), { workspace: root });
  assert.equal(result.ok, false);
  const rendered = JSON.stringify(result);
  assert.doesNotMatch(rendered, new RegExp(fakeKey));
  assert.doesNotMatch(rendered, new RegExp(gatewayHost));
  assert.equal(result.fallback, undefined);
  const statusResult = await ctx.service.editablePptImage({ action: 'status' }, { workspace: root });
  assert.doesNotMatch(JSON.stringify(statusResult), new RegExp(`${fakeKey}|${gatewayHost}`));
});

test('严格失败不提供 ai-draw-skills 提示词回退', async () => {
  const root = await workspace(); const ctx = subject({ fetchImpl: async () => json({ data: [] }) });
  const ready = await ctx.addReady(openAiDraft);
  const result = await ctx.service.editablePptImage(baseRequest({ connectionId: ready.id }), { workspace: root });
  assert.equal(result.ok, false);
  assert.equal(result.error.code, 'invalid_image_response');
  assert.equal(result.fallback, undefined);
});

// —— 参数与授权校验 ——
test('付费授权、预算、count、size/quality 枚举与 action 校验失败关闭', async () => {
  const root = await workspace(); const ctx = subject();
  const ready = await ctx.addReady(openAiDraft);
  const cases = [
    [baseRequest({ connectionId: ready.id, authorizePaid: false }), 'paid_not_authorized'],
    [baseRequest({ connectionId: ready.id, budgetRemaining: 0 }), 'budget_exceeded'],
    [baseRequest({ connectionId: ready.id, count: 2 }), 'invalid_request'],
    [baseRequest({ connectionId: ready.id, size: '9999x9999' }), 'invalid_size'],
    [baseRequest({ connectionId: ready.id, quality: 'ultra' }), 'invalid_quality'],
    [{ action: 'staus' }, 'invalid_action'],
    [baseRequest({ connectionId: ready.id, action: 'generate', referenceImages: ['a.png'] }), 'invalid_request'],
    [baseRequest({ connectionId: ready.id, action: 'generate', maskImage: 'a.png' }), 'invalid_request'],
    [baseRequest({ connectionId: ready.id, action: 'edit', outputPath: 'assets/noext' }), 'invalid_output_path'],
  ];
  for (const [request, code] of cases) {
    const result = await ctx.service.editablePptImage(request, { workspace: root });
    assert.equal(result.error?.code, code, `期望 ${code}，实得 ${result.error?.code}`);
  }
  assert.equal(ctx.fetchCalls.length, 0);
});
