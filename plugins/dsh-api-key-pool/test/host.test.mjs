import test from 'node:test';
import assert from 'node:assert/strict';
import { credentialKey } from '@deepseek-ai/dsh-credentials';
import { CredentialFacade } from '../src/credentials.js';
import {
  ApiKeyPoolService,
  recursiveSecretScan,
  makeHealthRoutes,
  makeExclusivePoolRouteGuard,
  HEALTH_ROUTE_PATH,
} from '../src/host.js';

// ---------------------------------------------------------------------------
// 测试夹具：全部为 sk- 占位符 Key，非真实凭据。
// ---------------------------------------------------------------------------

const SECRET = 'sk-fixture-abc123';

test('路由共存：普通 Provider 不需要守卫；独占守卫只放行 pool-*', () => {
  const guard = makeExclusivePoolRouteGuard();
  let nextCalls = 0;
  const next = () => { nextCalls += 1; return 'passed'; };
  assert.equal(guard({ provider: 'pool-main' }, next), 'passed');
  assert.equal(nextCalls, 1);
  assert.throws(
    () => guard({ provider: 'deepseek' }, next),
    (error) => error?.code === 'POOL_PROFILE_NATIVE_ROUTE_FORBIDDEN',
  );
  assert.equal(nextCalls, 1);
});

function makeMockCredentials() {
  const records = new Map();
  return {
    records,
    async listRecords() { return [...records].map(([key, record]) => ({ key, kind: record.kind })); },
    async readRecord(key) { return records.get(key); },
    async modifyRecord(key, mutate) {
      const next = await mutate(records.get(key));
      if (next === undefined) records.delete(key); else records.set(key, next);
    },
    async deleteRecord(key) { records.delete(key); },
  };
}

function makeMockSettings(initial) {
  let value = initial;
  const watchers = new Set();
  return {
    get: () => value,
    async replace(next) { value = next; },
    watch(cb) { watchers.add(cb); return () => watchers.delete(cb); },
    async commit(next) { value = next; for (const cb of watchers) cb(); },
  };
}

const BASE_SETTINGS = {
  schema: 'dsh.api-key-pool/v1',
  pools: {
    main: {
      api: 'openai-completions',
      baseURL: 'https://api.example.com',
      models: [{ id: 'm-1', name: '模型一' }],
      keyIds: [],
    },
  },
};

function makeService({ settings = makeMockSettings(BASE_SETTINGS), credentials = makeMockCredentials(), label = 'web-key-pool' } = {}) {
  return new ApiKeyPoolService({
    settings,
    credentials: new CredentialFacade(credentials),
    profileLabel: label,
  });
}

// ---------------------------------------------------------------------------

test('recursiveSecretScan：嵌套对象/数组/对象键中的完整 Key 都会被命中', () => {
  const secrets = [SECRET];
  assert.deepEqual(recursiveSecretScan({ a: { b: `prefix ${SECRET} suffix` } }, secrets), [
    { path: '$.a.b', secret: 'sk-…' },
  ]);
  assert.equal(recursiveSecretScan({ list: ['x', { k: SECRET }] }, secrets).length, 1);
  const masked = 'sk-…c123';
  assert.deepEqual(recursiveSecretScan({ masked, other: 'noise' }, secrets), []);
  assert.deepEqual(recursiveSecretScan({ nested: { deep: [1, true, null] } }, secrets), []);
  assert.deepEqual(recursiveSecretScan(null, secrets), []);
  assert.deepEqual(recursiveSecretScan({ a: SECRET }, []), []);
});

test('describe：输出只有脱敏 Key（递归 secret scan 零命中）+ 孤儿报告', async () => {
  const service = makeService();
  const added = await service.addKey(SECRET, 'main');
  assert.match(added.keyId, /^k-[0-9a-f-]{36}$/);
  assert.equal(added.masked, 'sk-…c123');
  assert.match(added.fingerprint, /^[0-9a-f]{16}$/);

  const described = await service.describe();
  assert.equal(described.schema, 'dsh.api-key-pool.status/v1');
  assert.equal(described.profile, 'web-key-pool');
  assert.equal(described.pools.length, 1);
  const pool = described.pools[0];
  assert.equal(pool.id, 'main');
  assert.equal(pool.route, 'pool-main');
  assert.equal(pool.keyCount, 1);
  // 编辑器预填契约：一张卡片改完端点/协议，因此列表必须回读这两项非秘密元数据
  assert.equal(pool.api, 'openai-completions');
  assert.equal(pool.baseURL, 'https://api.example.com');
  // 模型目录要能逐行回填，容量原样回读（缺省即 schema 默认值）；未勾选识图时不得出现 input 键，
  // 否则 Typert 结果边界校验会拒绝整个 list 响应。
  assert.deepEqual(pool.models[0], {
    id: 'm-1', name: '模型一', contextWindow: 262144, maxTokens: 32768,
  });
  assert.equal('input' in pool.models[0], false);

  // 勾选识图后 input 必须回读，供卡片复现勾选态
  await service.upsertPool({
    id: 'main',
    api: 'openai-completions',
    baseURL: 'https://api.example.com',
    models: [{ id: 'm-1', input: ['text', 'image'] }],
  });
  const withVision = await service.describe();
  assert.deepEqual(withVision.pools[0].models[0].input, ['text', 'image']);
  assert.equal(pool.keys[0].keyId, added.keyId);
  assert.equal(pool.keys[0].masked, 'sk-…c123');
  assert.equal(pool.keys[0].state, 'ready');
  // 核心：完整 Key 不得出现在任何层级的任何字符串里
  assert.deepEqual(recursiveSecretScan(described, [SECRET]), []);
  assert.ok(!JSON.stringify(described).includes(SECRET));

  // 未挂到池的记录为孤儿
  const orphan = await service.addKey('sk-fixture-orphan');
  const described2 = await service.describe();
  assert.deepEqual(described2.orphans, [orphan.keyId]);
  await service.removeKey(orphan.keyId);
});

test('addKey：非法值 fail-closed；重复指纹拒绝；挂池后进入 settings', async () => {
  const settings = makeMockSettings(BASE_SETTINGS);
  const service = makeService({ settings });
  await assert.rejects(() => service.addKey('   '), (e) => e.code === 'INVALID_KEY_VALUE');
  await assert.rejects(() => service.addKey('has space inside'), (e) => e.code === 'INVALID_KEY_VALUE');
  const first = await service.addKey(SECRET, 'main');
  await assert.rejects(() => service.addKey(SECRET), (e) => e.code === 'DUPLICATE_KEY');
  await assert.rejects(() => service.addKey(SECRET, 'not-exist'), (e) => e instanceof Error);
  assert.deepEqual(settings.get().pools.main.keyIds, [first.keyId]);
  assert.equal(service.runtime.healthSnapshot().pools.main.keyCount, 1);
});

test('并发写入：同值 Key 100 次只入库一次，队列失败后仍可继续', async () => {
  const credentials = makeMockCredentials();
  const service = makeService({ credentials });
  const attempts = await Promise.allSettled(
    Array.from({ length: 100 }, () => service.addKey('sk-concurrent-same', 'main')),
  );
  assert.equal(attempts.filter((entry) => entry.status === 'fulfilled').length, 1);
  assert.equal(attempts.filter((entry) => entry.status === 'rejected').length, 99);
  assert.equal(credentials.records.size, 1);
  assert.equal(service.settings.get().pools.main.keyIds.length, 1);

  // 拒绝不会毒化队列尾，后续不同 Key 仍能正常写入并挂池。
  await service.addKey('sk-after-rejection', 'main');
  assert.equal(credentials.records.size, 2);
  assert.equal(service.settings.get().pools.main.keyIds.length, 2);
});

test('并发写入：不同 Key 同时挂池不丢失更新', async () => {
  const credentials = makeMockCredentials();
  const service = makeService({ credentials });
  const count = 40;
  const added = await Promise.all(Array.from(
    { length: count },
    (_, index) => service.addKey(`sk-distinct-${String(index).padStart(3, '0')}`, 'main'),
  ));
  assert.equal(credentials.records.size, count);
  assert.equal(service.settings.get().pools.main.keyIds.length, count);
  assert.deepEqual(new Set(service.settings.get().pools.main.keyIds), new Set(added.map((entry) => entry.keyId)));
});

test('addKey：挂池写入失败时精确回滚本次新凭据且运行时保持原配置', async () => {
  let value = structuredClone(BASE_SETTINGS);
  const settings = {
    get: () => value,
    async replace() { throw new Error('settings-write-failed'); },
  };
  const credentials = makeMockCredentials();
  const service = makeService({ settings, credentials });
  await assert.rejects(
    () => service.addKey('sk-rollback-fixture', 'main'),
    /settings-write-failed/,
  );
  assert.equal(credentials.records.size, 0);
  assert.deepEqual(value.pools.main.keyIds, []);
  assert.equal(service.runtime.healthSnapshot().pools.main.keyCount, 0);
});

test('removeKey：先从池摘除再删凭据；非法 keyId 拒绝', async () => {
  const settings = makeMockSettings(BASE_SETTINGS);
  const credentials = makeMockCredentials();
  const service = makeService({ settings, credentials });
  const added = await service.addKey(SECRET, 'main');
  assert.equal(credentials.records.size, 1);

  await assert.rejects(() => service.removeKey('not-a-key-id'), (e) => e instanceof Error);
  const removed = await service.removeKey(added.keyId);
  assert.deepEqual(removed, { removed: true, keyId: added.keyId });
  assert.deepEqual(settings.get().pools.main.keyIds, []);
  assert.equal(credentials.records.size, 0);
  assert.equal(service.runtime.healthSnapshot().pools.main.keyCount, 0);
});

test('resetCooldown：重置后健康快照恢复 ready；输出无秘密', async () => {
  const service = makeService();
  const added = await service.addKey(SECRET, 'main');
  service.runtime.recordFailure('pool-main', added.keyId, 'AUTH');
  assert.equal(service.runtime.healthSnapshot().pools.main.keys[0].state, 'cooling');
  const reset = await service.resetCooldown('pool-main', added.keyId);
  assert.deepEqual(reset, { reset: true, route: 'pool-main', keyId: added.keyId });
  assert.equal(service.runtime.healthSnapshot().pools.main.keys[0].state, 'ready');
  await assert.rejects(() => service.resetCooldown('pool-main', 'bad-id'), (e) => e instanceof Error);
});

test('upsertPool：新建池进入 settings 与运行时；更新保留既有 keyIds；非法配置拒绝', async () => {
  const settings = makeMockSettings(BASE_SETTINGS);
  const service = makeService({ settings });
  const added = await service.addKey(SECRET, 'main');

  const created = await service.upsertPool({
    id: 'gateway-b',
    api: 'openai-completions',
    baseURL: 'https://api-b.example.com',
    models: [{ id: 'm-b1' }, { id: 'm-b2', name: '模型B2' }],
  });
  assert.deepEqual(created, { poolId: 'gateway-b', created: true, keyCount: 0 });
  assert.ok(settings.get().pools['gateway-b']);
  assert.equal(service.runtime.healthSnapshot().pools['gateway-b'].keyCount, 0);

  // 更新：不传 keyIds 时保留既有挂载
  const updated = await service.upsertPool({
    id: 'main',
    api: 'openai-completions',
    baseURL: 'https://api.example.com/v2',
    models: [{ id: 'm-1' }],
  });
  assert.deepEqual(updated, { poolId: 'main', created: false, keyCount: 1 });
  assert.deepEqual(settings.get().pools.main.keyIds, [added.keyId]);
  assert.equal(settings.get().pools.main.baseURL, 'https://api.example.com/v2');
  assert.equal(service.runtime.healthSnapshot().pools.main.keyCount, 1);

  // fail-closed：HTTP baseURL、空 models、非法 id 均拒绝且不落盘
  await assert.rejects(() => service.upsertPool({
    id: 'bad-http', api: 'openai-completions', baseURL: 'http://api.example.com', models: [{ id: 'm' }],
  }), (e) => e instanceof Error);
  await assert.rejects(() => service.upsertPool({
    id: 'empty-models', api: 'openai-completions', baseURL: 'https://api.example.com', models: [],
  }), (e) => e instanceof Error);
  await assert.rejects(() => service.upsertPool({ id: '', api: 'openai-completions' }), (e) => e instanceof Error);
  assert.equal(settings.get().pools['bad-http'], undefined);
});

test('deletePool：摘除池配置；Key 转孤儿不删除；未知池拒绝', async () => {
  const settings = makeMockSettings(BASE_SETTINGS);
  const credentials = makeMockCredentials();
  const service = makeService({ settings, credentials });
  const added = await service.addKey(SECRET, 'main');

  const removed = await service.deletePool('main');
  assert.deepEqual(removed, { removed: true, poolId: 'main', orphanedKeys: 1 });
  assert.equal(settings.get().pools.main, undefined);
  assert.equal(service.runtime.healthSnapshot().pools.main, undefined);
  // 凭据记录仍在，转为孤儿
  assert.equal(credentials.records.size, 1);
  const described = await service.describe();
  assert.deepEqual(described.orphans, [added.keyId]);

  await assert.rejects(() => service.deletePool('main'), (e) => e instanceof Error);
});

test('probe：携带首枚 Key 请求 {baseURL}/models；输出无秘密；异常安全失败', async (t) => {
  const requests = [];
  const originalFetch = globalThis.fetch;
  globalThis.fetch = async (url, init) => {
    requests.push({ url: String(url), headers: init.headers });
    return { ok: true, status: 200 };
  };
  t.after(() => { globalThis.fetch = originalFetch; });

  const service = makeService();
  const added = await service.addKey(SECRET, 'main');

  const probed = await service.probe('main');
  assert.equal(probed.ok, true);
  assert.equal(probed.status, 200);
  assert.equal(typeof probed.latencyMs, 'number');
  assert.equal(probed.poolId, 'main');
  assert.ok(!JSON.stringify(probed).includes(SECRET));
  assert.equal(requests.length, 1);
  assert.equal(requests[0].url, 'https://api.example.com/models');
  assert.equal(requests[0].headers.authorization, `Bearer ${SECRET}`);

  await assert.rejects(() => service.probe('not-exist'), (e) => e instanceof Error);

  // 网络异常：返回结构化失败，不抛出、不泄露 Key
  globalThis.fetch = async () => { throw Object.assign(new Error('boom'), { cause: { code: 'ECONNREFUSED' } }); };
  const failed = await service.probe('main');
  assert.equal(failed.ok, false);
  assert.equal(failed.error, 'ECONNREFUSED');
  assert.ok(!JSON.stringify(failed).includes(SECRET));

  // 空池/缺凭据：拒绝探测
  await service.removeKey(added.keyId);
  await assert.rejects(() => service.probe('main'), (e) => e instanceof Error);
});

test('probe：anthropic-messages 使用 x-api-key 头', async (t) => {
  const requests = [];
  const originalFetch = globalThis.fetch;
  globalThis.fetch = async (url, init) => {
    requests.push({ url: String(url), headers: init.headers });
    return { ok: false, status: 401 };
  };
  t.after(() => { globalThis.fetch = originalFetch; });
  const settings = makeMockSettings({
    schema: 'dsh.api-key-pool/v1',
    pools: {
      anthropic: {
        api: 'anthropic-messages',
        baseURL: 'https://api.anthropic.example.com',
        models: [{ id: 'claude-x' }],
        keyIds: [],
      },
    },
  });
  const service = makeService({ settings });
  await service.addKey('sk-anthropic-99', 'anthropic');
  const probed = await service.probe('anthropic');
  assert.equal(probed.ok, false);
  assert.equal(probed.status, 401);
  assert.equal(requests[0].headers['x-api-key'], 'sk-anthropic-99');
  assert.equal(requests[0].headers.authorization, undefined);
});

test('健康端点：loopback GET 200 带 profile 标签；非 loopback 403；非 GET 405', async () => {
  const service = makeService();
  await service.addKey(SECRET, 'main');
  const [route] = makeHealthRoutes(service);
  assert.equal(route.kind, 'exact');
  assert.equal(route.path, HEALTH_ROUTE_PATH);

  const makeRes = () => {
    const state = { status: null, headers: null, body: '' };
    return {
      state,
      writeHead(status, headers) { state.status = status; state.headers = headers; },
      end(payload) { state.body = payload ?? ''; },
    };
  };

  const okRes = makeRes();
  await route.handler({ method: 'GET', socket: { remoteAddress: '127.0.0.1' }, headers: { host: '127.0.0.1:3081' } }, okRes);
  assert.equal(okRes.state.status, 200);
  const body = JSON.parse(okRes.state.body);
  assert.deepEqual(body, { ok: true, plugin: 'dsh-api-key-pool', profile: 'web-key-pool', poolCount: 1 });
  assert.equal(okRes.state.headers['referrer-policy'], 'no-referrer');
  assert.ok(!okRes.state.body.includes(SECRET));

  const deniedRes = makeRes();
  await route.handler({ method: 'GET', socket: { remoteAddress: '192.168.1.5' }, headers: { host: '192.168.1.5:3081' } }, deniedRes);
  assert.equal(deniedRes.state.status, 403);

  const methodRes = makeRes();
  await route.handler({ method: 'POST', socket: { remoteAddress: '::1' }, headers: { host: 'localhost:3081' } }, methodRes);
  assert.equal(methodRes.state.status, 405);
});
