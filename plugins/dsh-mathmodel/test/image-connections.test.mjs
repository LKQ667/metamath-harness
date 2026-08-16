import test from 'node:test';
import assert from 'node:assert/strict';
import {
  EMPTY_IMAGE_CONNECTIONS, ImageConnectionCredentialStore, ImageConnectionService,
  IMAGE_CONNECTIONS_SCHEMA_TAG, MAX_CONNECTIONS, migrateFromV1, validateBaseUrl, validateImageConnections,
} from '../lib/index.js';

const stamp = '2026-08-16T10:00:00.000Z';
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
function subject({ legacy = {}, credentials = {} } = {}) {
  let value = EMPTY_IMAGE_CONNECTIONS;
  const provider = memoryProvider(credentials);
  const settings = { get: () => value, async replace(next) { value = next; } };
  const service = new ImageConnectionService({ settings, legacySettings: { get: () => legacy }, credentialStore: new ImageConnectionCredentialStore(provider), credentialProvider: provider, hasV2UserSection: () => value !== EMPTY_IMAGE_CONNECTIONS, now: () => stamp, fetchImpl: async () => ({ ok: true, json: async () => ({ data: [{ id: 'candidate-image' }] }) }) });
  return { service, provider, value: () => value };
}

test('严格 schema 拒绝非法 URL、未知字段、重复凭据、超限与未就绪 active', () => {
  for (const raw of ['http://images.example/v1', 'https://user:pass@images.example/v1', 'https://images.example/v1?token=x', 'https://192.168.1.2/v1']) assert.throws(() => validateBaseUrl(raw));
  assert.equal(validateBaseUrl('http://localhost:8080/v1/'), 'http://localhost:8080/v1');
  const base = migrateFromV1({}, { now: () => stamp });
  assert.throws(() => validateImageConnections({ ...base, unexpected: true }), /未知字段/);
  assert.throws(() => validateImageConnections({ ...base, activeConnectionId: base.connections[0].id }), /真实生图验证/);
  assert.throws(() => validateImageConnections({ ...base, connections: Array.from({ length: MAX_CONNECTIONS + 1 }, () => base.connections[0]) }), /最多/);
  assert.throws(() => validateImageConnections({ ...base, connections: [base.connections[0], { ...base.connections[1], credentialRef: base.connections[0].credentialRef }] }), /重复的凭据引用/);
});

test('v1 迁移保留四类历史连接并且幂等、不把旧 Key 误设为当前', async () => {
  const legacy = { providerOrder: ['openai', 'dashscope', 'gemini', 'custom'], customBaseUrl: 'https://gateway.example/v1/', customModel: 'custom-image' };
  const migrated = migrateFromV1(legacy, { now: () => stamp, isConfigured: () => true });
  assert.equal(migrated.schema, IMAGE_CONNECTIONS_SCHEMA_TAG);
  assert.equal(migrated.connections.length, 4);
  assert.equal(migrated.activeConnectionId, '');
  assert.equal(migrated.connections.at(-1).credentialRef, 'CUSTOM_IMAGE_API_KEY');
  const ctx = subject({ legacy, credentials: { OPENAI_API_KEY: 'sk-old-key' } });
  const first = await ctx.service.list(); const second = await ctx.service.list();
  assert.equal(first.connections.length, 4); assert.equal(second.connections.length, 4); assert.equal(ctx.value().connections.length, 4);
});

test('两条同模板连接的动态 Key 隔离，模型发现不泄漏 Key', async () => {
  const ctx = subject(); await ctx.service.ensureMigrated();
  const draft = { name: '网关一', template: 'openai-compatible', adapter: 'openai-images', model: 'image-a', baseUrl: 'https://gateway.example/v1' };
  const one = (await ctx.service.upsert(draft)).connections.at(-1);
  const two = (await ctx.service.upsert({ ...draft, name: '网关二', model: 'image-b' })).connections.at(-1);
  await ctx.service.setKey(one.id, 'sk-first-secret'); await ctx.service.setKey(two.id, 'sk-second-secret');
  const listed = await ctx.service.list();
  assert.notEqual(one.credentialRef, two.credentialRef);
  assert.equal(ctx.provider.values.get(one.credentialRef), 'sk-first-secret'); assert.equal(ctx.provider.values.get(two.credentialRef), 'sk-second-secret');
  assert.doesNotMatch(JSON.stringify(listed), /sk-first-secret|sk-second-secret/);
  const discovered = await ctx.service.discoverModels(one.id); assert.deepEqual(discovered.models, [{ id: 'candidate-image' }]);
});

test('删除当前连接原子清空 active；默认保留 Key，显式清除只影响目标', async () => {
  const ctx = subject(); await ctx.service.ensureMigrated();
  const connection = (await ctx.service.upsert({ name: '待删', template: 'openai-compatible', adapter: 'openai-images', model: 'image-a', baseUrl: 'https://gateway.example/v1' })).connections.at(-1);
  await ctx.service.setKey(connection.id, 'sk-delete-secret');
  const value = ctx.value();
  const verified = { ...value.connections.find((item) => item.id === connection.id), verification: { status: 'ready', protocol: 'openai-images', model: 'image-a', template: 'openai-compatible', baseUrlFingerprint: 'a'.repeat(64), keyFingerprint: 'b'.repeat(64), verifiedAt: stamp, message: '' } };
  await ctx.service.settings.replace({ ...value, connections: value.connections.map((item) => item.id === connection.id ? verified : item) });
  await ctx.service.setActive(connection.id); await ctx.service.remove(connection.id);
  assert.equal(ctx.value().activeConnectionId, ''); assert.equal(ctx.provider.values.get(connection.credentialRef), 'sk-delete-secret');
  const again = (await ctx.service.upsert({ name: '再删', template: 'openai-compatible', adapter: 'openai-images', model: 'image-b', baseUrl: 'https://gateway.example/v1' })).connections.at(-1);
  await ctx.service.setKey(again.id, 'sk-clear-secret'); await ctx.service.remove(again.id, { clearCredential: true });
  assert.equal(ctx.provider.values.has(again.credentialRef), false);
});

test('编辑已验证连接的模板、协议、模型或地址会移除旧验证并清空当前连接', async () => {
  const ctx = subject(); await ctx.service.ensureMigrated();
  const connection = (await ctx.service.upsert({ name: '待编辑', template: 'openai-compatible', adapter: 'openai-images', model: 'image-a', baseUrl: 'https://gateway.example/v1' })).connections.at(-1);
  await ctx.service.setKey(connection.id, 'sk-edit-secret');
  const value = ctx.value();
  const verified = {
    ...value.connections.find((item) => item.id === connection.id),
    verification: { status: 'ready', protocol: 'openai-images', model: 'image-a', template: 'openai-compatible', baseUrlFingerprint: 'a'.repeat(64), keyFingerprint: 'b'.repeat(64), verifiedAt: stamp, message: '' },
  };
  await ctx.service.settings.replace({ ...value, connections: value.connections.map((item) => item.id === connection.id ? verified : item) });
  await ctx.service.setActive(connection.id);
  await ctx.service.upsert({ name: '已变更', template: 'volcengine-ark', adapter: 'openai-images', model: 'doubao-seedream-5.0-lite', baseUrl: 'https://ark.cn-beijing.volces.com/api/v3' }, connection.id);
  const edited = ctx.value().connections.find((item) => item.id === connection.id);
  assert.equal(edited.verification, undefined);
  assert.equal(ctx.value().activeConnectionId, '');
});
