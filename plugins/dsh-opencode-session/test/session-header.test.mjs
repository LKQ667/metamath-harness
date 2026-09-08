import test from 'node:test';
import assert from 'node:assert/strict';
import { createServer } from 'node:http';
import { createRequire } from 'node:module';
import { pathToFileURL } from 'node:url';
import { dirname, resolve } from 'node:path';
import { withSessionHeader, installSessionHeader } from '../src/session-header.js';

function fixture(provider = 'opencode-go', baseUrl = 'https://opencode.ai/zen/go/v1') {
  return { profiles: new Map([[provider, { headers: { 'X-OpenCode-Session': 'stale', extra: 'keep' } }]]),
    models: { getModel: () => ({ baseUrl }) } };
}
test('并发独立快照、静态头大小写替换、同会话稳定', () => {
  const snapshot = fixture();
  const make = sessionId => withSessionHeader({ provider: 'opencode-go', sessionId }, snapshot);
  const a = make('session-a'), b = make('session-b');
  assert.deepEqual(a.profiles.get('opencode-go').headers, { extra: 'keep', 'x-opencode-session': 'session-a' });
  assert.equal(b.profiles.get('opencode-go').headers['x-opencode-session'], 'session-b');
  assert.deepEqual(make('session-a').profiles, a.profiles);
  assert.equal(snapshot.profiles.get('opencode-go').headers['X-OpenCode-Session'], 'stale');
  assert.equal(a.models, snapshot.models);
});
test('自定义 OpenCode 端点覆盖，其他端点不变，近似域名不命中', () => {
  for (const host of ['https://example.com/v1', 'https://opencode.ai.evil.invalid/v1']) {
    const snapshot = fixture('custom', host);
    assert.equal(withSessionHeader({ provider: 'custom' }, snapshot), snapshot);
  }
  assert.equal(withSessionHeader({ provider: 'custom', sessionId: 'session-c' }, fixture('custom'))
    .profiles.get('custom').headers['x-opencode-session'], 'session-c');
});
test('缺失或非法 ID 拒绝，不生成随机值；未知版本拒绝', () => {
  for (const sessionId of [undefined, '', ' ', 'a\nb']) {
    assert.throws(() => withSessionHeader({ provider: 'opencode-go', sessionId }, fixture()));
  }
  assert.throws(() => installSessionHeader(class {}, '0.1.3-alpha.2'), /兼容门失败/);
});

test('宿主真实适配器：三种协议线上头、并发、prepareCall、卸载恢复', { skip: !process.env.DSH_PI_AI_ENTRY }, async () => {
  const entry = process.env.DSH_PI_AI_ENTRY;
  const req = createRequire(entry);
  const { PiAiAdapter } = await import(pathToFileURL(entry));
  const piDist = resolve(dirname(req.resolve('@deepseek-ai/dsh-llm-pi-ai/package.json')), '../../@earendil-works/pi-ai/dist');
  const { createProvider } = await import(pathToFileURL(resolve(piDist, 'index.js')));
  const seen = [];
  const server = createServer(async (request, response) => {
    for await (const _ of request) { /* 仅消费测试消息 */ }
    seen.push({ path: request.url, id: request.headers['x-opencode-session'] });
    // 有意结束推理：本测试验证真实 HTTP 传输，不模拟各协议生成内容。
    response.writeHead(400, { 'Content-Type': 'application/json' });
    response.end(JSON.stringify({ error: { message: 'wire-test-stop', type: 'invalid_request_error' } }));
  });
  await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
  const original = PiAiAdapter.prototype.streamWithSnapshot;
  let dispose;
  try {
    const profiles = new Map();
    const specs = [['openai-completions', 'openAICompletionsApi'], ['openai-responses', 'openAIResponsesApi'], ['anthropic-messages', 'anthropicMessagesApi']];
    for (const [api, factoryName] of specs) {
      const module = await import(pathToFileURL(resolve(piDist, `api/${api}.lazy.js`)));
      const route = `opencode-${api}`;
      const baseUrl = `http://127.0.0.1:${server.address().port}/v1`;
      const piProvider = createProvider({ id: route, name: route, baseUrl,
        auth: { apiKey: { name: 'test', resolve: async () => ({ auth: { apiKey: 'fake-wire-test' }, source: 'test' }) } },
        api: module[factoryName](), models: [{ id: 'probe', name: 'probe', api, provider: route, baseUrl,
          input: ['text'], cost: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0 }, contextWindow: 8192, maxTokens: 128, reasoning: false }] });
      profiles.set(route, { provider: route, displayName: route, piProvider, configuredMaxTokens: new Map(), streamIdleTimeoutMs: 10000 });
    }
    const adapter = new PiAiAdapter({ profiles: () => profiles, resolveApiKey: async () => 'fake-wire-test',
      auth: { credentials: { read: async () => undefined, list: async () => [] }, authContext: { env: async () => undefined } } });
    const run = async (provider, sessionId, prepared = false) => {
      const options = { provider, model: 'probe', sessionId, maxTokens: 8,
        messages: [{ role: 'user', content: [{ type: 'text', text: 'hi' }] }] };
      const stream = prepared ? (await adapter.prepareCall(provider, 'probe')).stream(options) : adapter.stream(options);
      for await (const _ of stream) { /* 官方适配器把测试 400 转成 finish */ }
    };
    await run('opencode-openai-completions', 'before');
    assert.equal(seen.at(-1).id, undefined);
    dispose = installSessionHeader(PiAiAdapter, req('@deepseek-ai/dsh-llm-pi-ai/package.json').version);
    assert.throws(() => installSessionHeader(PiAiAdapter, '0.1.2-rc.1'), /重复挂载/);
    await Promise.all(specs.flatMap(([api]) => ['session-a', 'session-b'].map(id => run(`opencode-${api}`, id, true))));
    assert.equal(seen.length, 7);
    assert.equal(seen.filter(x => x.id === 'session-a').length, 3);
    assert.equal(seen.filter(x => x.id === 'session-b').length, 3);
    await run('opencode-openai-completions', 'session-a');
    assert.equal(seen.at(-1).id, 'session-a');
    dispose(); dispose = undefined;
    assert.equal(PiAiAdapter.prototype.streamWithSnapshot, original);
    await run('opencode-openai-completions', 'after');
    assert.equal(seen.at(-1).id, undefined);
  } finally {
    dispose?.();
    await new Promise(resolve => server.close(resolve));
  }
});
