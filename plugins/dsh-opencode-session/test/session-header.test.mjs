import test from 'node:test';
import assert from 'node:assert/strict';
import { createServer } from 'node:http';
import { createRequire } from 'node:module';
import { pathToFileURL } from 'node:url';
import { dirname, resolve } from 'node:path';
import { applyOpenCodeSessionHeader, assertCompatiblePiAiVersion, isOpenCodeRequest } from '../src/session-header.js';

test('并发独立 Headers、静态头大小写替换、同会话稳定', () => {
  const make = (sessionId) => {
    const h = new Headers({ 'X-OpenCode-Session': 'stale', extra: 'keep' });
    return applyOpenCodeSessionHeader({ provider: 'opencode-go', baseURL: 'https://opencode.ai/zen/go/v1', sessionId }, h);
  };
  const a = make('session-a');
  const b = make('session-b');
  assert.equal(a.get('x-opencode-session'), 'session-a');
  assert.equal(a.get('extra'), 'keep');
  assert.equal(b.get('x-opencode-session'), 'session-b');
  assert.equal(make('session-a').get('x-opencode-session'), 'session-a');
});

test('自定义 OpenCode 端点覆盖，其他端点不变，近似域名不命中', () => {
  for (const baseURL of ['https://example.com/v1', 'https://opencode.ai.evil.invalid/v1']) {
    assert.equal(isOpenCodeRequest({ provider: 'custom', baseURL }), false);
    const h = new Headers({ extra: '1' });
    const out = applyOpenCodeSessionHeader({ provider: 'custom', baseURL }, h);
    assert.equal(out.get('x-opencode-session'), null);
  }
  const out = applyOpenCodeSessionHeader(
    { provider: 'custom', baseURL: 'https://opencode.ai/zen/go/v1', sessionId: 'session-c' },
    new Headers(),
  );
  assert.equal(out.get('x-opencode-session'), 'session-c');
});

test('缺失或非法 ID 拒绝，不生成随机值；未知版本拒绝', () => {
  for (const sessionId of [undefined, '', ' ', 'a\nb']) {
    assert.throws(() => applyOpenCodeSessionHeader({ provider: 'opencode-go', baseURL: 'https://opencode.ai/zen/go/v1', sessionId }, new Headers()));
  }
  assert.throws(() => assertCompatiblePiAiVersion('0.1.5-rc.2'), /兼容门失败/);
  assert.equal(assertCompatiblePiAiVersion('0.2.2-rc.5'), '0.2.2-rc.5');
});

test('宿主真实适配器（0.2.2 prepareHeaders）：三种协议线上头、并发、prepareCall', { skip: !process.env.DSH_PI_AI_ENTRY }, async () => {
  const entry = process.env.DSH_PI_AI_ENTRY;
  const req = createRequire(entry);
  const { PiAiAdapter } = await import(pathToFileURL(entry));
  const piAiPkgDir = dirname(req.resolve('@deepseek-ai/dsh-llm-pi-ai/package.json'));
  const piDist = resolve(piAiPkgDir, '../../@earendil-works/pi-ai/dist');
  const { createProvider } = await import(pathToFileURL(resolve(piDist, 'index.js')));
  const seen = [];
  const server = createServer(async (request, response) => {
    for await (const _ of request) { /* 消费测试消息体 */ }
    seen.push({ path: request.url, id: request.headers['x-opencode-session'] });
    response.writeHead(400, { 'Content-Type': 'application/json' });
    response.end(JSON.stringify({ error: { message: 'wire-test-stop', type: 'invalid_request_error' } }));
  });
  await new Promise((res) => server.listen(0, '127.0.0.1', res));
  let enabled = false;
  try {
    assertCompatiblePiAiVersion(req('@deepseek-ai/dsh-llm-pi-ai/package.json').version);
    const profiles = new Map();
    const specs = [
      ['openai-completions', 'openAICompletionsApi'],
      ['openai-responses', 'openAIResponsesApi'],
      ['anthropic-messages', 'anthropicMessagesApi'],
    ];
    for (const [api, factoryName] of specs) {
      const mod = await import(pathToFileURL(resolve(piDist, `api/${api}.lazy.js`)));
      const route = `opencode-${api}`;
      const baseUrl = `http://127.0.0.1:${server.address().port}/v1`;
      const piProvider = createProvider({
        id: route,
        name: route,
        baseUrl,
        auth: { apiKey: { name: 'test', resolve: async () => ({ auth: { apiKey: 'fake-wire-test' }, source: 'test' }) } },
        api: mod[factoryName](),
        models: [{
          id: 'probe', name: 'probe', api, provider: route, baseUrl,
          input: ['text'], cost: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0 },
          contextWindow: 8192, maxTokens: 128, reasoning: false,
        }],
      });
      profiles.set(route, {
        provider: route,
        displayName: route,
        piProvider,
        configuredMaxTokens: new Map(),
        modelErrors: new Map(),
        streamIdleTimeoutMs: 10000,
      });
    }
    const adapter = new PiAiAdapter({
      profiles: () => profiles,
      resolveApiKey: async () => 'fake-wire-test',
      prepareHeaders: (request, headers) => (enabled ? applyOpenCodeSessionHeader(request, headers) : headers),
      auth: { credentials: { read: async () => undefined, list: async () => [] }, authContext: { env: async () => undefined } },
    });
    const run = async (provider, sessionId, prepared = false) => {
      const options = {
        provider, model: 'probe', sessionId, maxTokens: 8,
        messages: [{ role: 'user', content: [{ type: 'text', text: 'hi' }] }],
      };
      const stream = prepared ? (await adapter.prepareCall(provider, 'probe')).stream(options) : adapter.stream(options);
      for await (const _ of stream) { /* 消费流结束 */ }
    };
    await run('opencode-openai-completions', 'before');
    assert.equal(seen.at(-1).id, undefined);
    enabled = true;
    await Promise.all(specs.flatMap(([api]) => ['session-a', 'session-b'].map((id) => run(`opencode-${api}`, id, true))));
    assert.equal(seen.length, 7);
    assert.equal(seen.filter((x) => x.id === 'session-a').length, 3);
    assert.equal(seen.filter((x) => x.id === 'session-b').length, 3);
    await run('opencode-openai-completions', 'session-a');
    assert.equal(seen.at(-1).id, 'session-a');
    enabled = false;
    await run('opencode-openai-completions', 'after');
    assert.equal(seen.at(-1).id, undefined);
  } finally {
    await new Promise((res) => server.close(res));
  }
});
