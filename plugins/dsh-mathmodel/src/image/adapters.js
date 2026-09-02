import { resolveCodexSession } from './codex-auth.js';
import { resolveGrokSession } from './grok-auth.js';

const JSON_HEADERS = { 'content-type': 'application/json' };
const DEFAULT_SLEEP = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

async function jsonResponse(response, provider) {
  if (!response.ok) {
    let payload = null;
    try { payload = await response.json(); } catch { /* 非 JSON 错误体 */ }
    const error = new Error(`${provider} 请求失败（HTTP ${response.status}）${typeof payload?.error?.code === 'string' ? `：${payload.error.code}` : ''}`);
    error.status = response.status;
    if (typeof payload?.error?.code === 'string') error.providerCode = payload.error.code;
    throw error;
  }
  return await response.json();
}

function genericAssets(data) {
  const rows = data?.data ?? data?.output?.results ?? data?.results ?? data?.result?.data ?? [];
  return rows.flatMap((item) => {
    if (typeof item?.b64_json === 'string') return [{ kind: 'base64', data: item.b64_json, mime: 'image/png' }];
    if (typeof item?.base64 === 'string') return [{ kind: 'base64', data: item.base64, mime: item.mime_type ?? 'image/png' }];
    if (typeof item?.url === 'string') return [{ kind: 'url', url: item.url }];
    return [];
  });
}

function dashScopeAssets(data) {
  const direct = genericAssets(data);
  const contents = data?.output?.choices?.flatMap((choice) => choice?.message?.content ?? []) ?? [];
  return [...direct, ...contents.flatMap((item) => typeof item?.image === 'string' ? [{ kind: 'url', url: item.image }] : [])];
}

function openAiUrl(base, path) {
  return new URL(path.replace(/^\//, ''), base.endsWith('/') ? base : `${base}/`).toString();
}

async function openAiRequest({ provider, endpoint, model, credential, request, references, maskRef, fetchImpl, signal }) {
  const headers = { authorization: `Bearer ${credential}`, ...JSON_HEADERS };
  let body;
  let url = openAiUrl(endpoint, 'images/generations');
  if (references.length > 0) {
    url = openAiUrl(endpoint, 'images/edits');
    const form = new FormData();
    form.set('model', model);
    form.set('prompt', request.prompt);
    form.set('n', String(request.count));
    if (request.size) form.set('size', request.size);
    if (request.quality) form.set('quality', request.quality);
    for (const [index, ref] of references.entries()) form.append('image[]', new Blob([ref.bytes], { type: ref.mime }), `reference-${index + 1}.${ref.ext}`);
    if (maskRef) form.append('mask', new Blob([maskRef.bytes], { type: maskRef.mime }), `mask.${maskRef.ext}`);
    body = form;
    delete headers['content-type'];
  } else {
    body = JSON.stringify({ model, prompt: request.prompt, n: request.count, ...(request.size ? { size: request.size } : {}), ...(request.quality ? { quality: request.quality } : {}), response_format: 'b64_json' });
  }
  const data = await jsonResponse(await fetchImpl(url, { method: 'POST', headers, body, signal }), provider);
  return genericAssets(data);
}

/** OpenAI Images API 通用适配器（连接携带 Base URL；火山 Ark 图片端点也走此协议）。 */
export async function openaiImagesAdapter(context) {
  if (!context?.endpoint || !context?.model) throw new Error('openai-images 适配器缺少 Base URL 或模型');
  return await openAiRequest({ ...context, provider: context.provider ?? 'openai-images', endpoint: context.endpoint });
}

export async function openaiAdapter(context) {
  return await openaiImagesAdapter({ ...context, provider: 'openai', endpoint: 'https://api.openai.com/v1' });
}

export async function customAdapter(context) {
  if (!context.endpoint || !context.model) throw new Error('自定义供应商缺少 Base URL 或模型名');
  return await openaiImagesAdapter({ ...context, provider: 'custom', endpoint: context.endpoint });
}

export async function dashscopeAdapter({ model, credential, request, references, fetchImpl, signal, sleep = DEFAULT_SLEEP }) {
  const endpoint = 'https://dashscope.aliyuncs.com/api/v1/services/aigc/multimodal-generation/generation';
  const content = [
    ...references.map((ref) => ({ image: `data:${ref.mime};base64,${ref.bytes.toString('base64')}` })),
    { text: request.prompt },
  ];
  const response = await fetchImpl(endpoint, {
    method: 'POST',
    headers: { authorization: `Bearer ${credential}`, 'x-dashscope-async': 'enable', ...JSON_HEADERS },
    body: JSON.stringify({ model, input: { messages: [{ role: 'user', content }] }, parameters: { n: request.count, size: request.size, aspect_ratio: request.aspectRatio } }),
    signal,
  });
  const first = await jsonResponse(response, 'dashscope');
  const taskId = first?.output?.task_id;
  if (!taskId) return dashScopeAssets(first);
  for (let attempt = 0; attempt < 30; attempt += 1) {
    if (signal?.aborted) throw new DOMException('Aborted', 'AbortError');
    if (attempt > 0) await sleep(1000);
    const poll = await jsonResponse(await fetchImpl(`https://dashscope.aliyuncs.com/api/v1/tasks/${encodeURIComponent(taskId)}`, {
      headers: { authorization: `Bearer ${credential}` }, signal,
    }), 'dashscope');
    const status = poll?.output?.task_status;
    if (status === 'SUCCEEDED') return dashScopeAssets(poll);
    if (['FAILED', 'CANCELED', 'UNKNOWN'].includes(status)) throw new Error(`dashscope 异步任务失败（${status}）`);
  }
  throw new Error('dashscope 异步任务轮询超时');
}

export async function geminiAdapter({ model, credential, request, references, fetchImpl, signal }) {
  const endpoint = `https://generativelanguage.googleapis.com/v1beta/models/${encodeURIComponent(model)}:generateContent`;
  const parts = [
    { text: request.prompt },
    ...references.map((ref) => ({ inlineData: { mimeType: ref.mime, data: ref.bytes.toString('base64') } })),
  ];
  const data = await jsonResponse(await fetchImpl(endpoint, {
    method: 'POST',
    headers: { 'x-goog-api-key': credential, ...JSON_HEADERS },
    body: JSON.stringify({ contents: [{ role: 'user', parts }], generationConfig: { responseModalities: ['IMAGE'], candidateCount: request.count } }),
    signal,
  }), 'gemini');
  return (data?.candidates ?? []).flatMap((candidate) => candidate?.content?.parts ?? []).flatMap((part) => {
    if (typeof part?.inlineData?.data === 'string') return [{ kind: 'base64', data: part.inlineData.data, mime: part.inlineData.mimeType ?? 'image/png' }];
    if (typeof part?.fileData?.fileUri === 'string') return [{ kind: 'url', url: part.fileData.fileUri }];
    return [];
  });
}

const SUB2API_DONE = new Set(['succeeded', 'success', 'done', 'completed', 'complete', 'succeed', 'ok']);
const SUB2API_FAIL = new Set(['failed', 'failure', 'error', 'canceled', 'cancelled', 'fail']);

/** Sub2API 异步 Images API：提交 /images/generations|edits/async，轮询任务端点。 */
export async function sub2apiAsyncImagesAdapter({ endpoint, model, credential, request, references, fetchImpl, signal, sleep = DEFAULT_SLEEP }) {
  if (!endpoint || !model) throw new Error('Sub2API 适配器缺少 Base URL 或模型');
  const headers = { authorization: `Bearer ${credential}`, ...JSON_HEADERS };
  let body;
  let url;
  if (references.length > 0) {
    url = openAiUrl(endpoint, 'images/edits/async');
    const form = new FormData();
    form.set('model', model);
    form.set('prompt', request.prompt);
    form.set('n', String(request.count));
    if (request.size) form.set('size', request.size);
    for (const [index, ref] of references.entries()) form.append('image[]', new Blob([ref.bytes], { type: ref.mime }), `reference-${index + 1}.${ref.ext}`);
    body = form;
    delete headers['content-type'];
  } else {
    url = openAiUrl(endpoint, 'images/generations/async');
    body = JSON.stringify({ model, prompt: request.prompt, n: request.count, ...(request.size ? { size: request.size } : {}) });
  }
  const submit = await jsonResponse(await fetchImpl(url, { method: 'POST', headers, body, signal }), 'sub2api');
  const taskId = submit?.task_id ?? submit?.data?.task_id;
  if (!taskId) throw new Error('Sub2API 异步任务未返回 task_id');
  for (let attempt = 0; attempt < 90; attempt += 1) {
    if (signal?.aborted) throw new DOMException('Aborted', 'AbortError');
    if (attempt > 0) await sleep(2000);
    let pollUrl = openAiUrl(endpoint, `images/tasks/${encodeURIComponent(taskId)}`);
    let poll = await fetchImpl(pollUrl, { headers: { authorization: `Bearer ${credential}` }, signal });
    if (poll.status === 404) {
      // 兼容 `/images/task/{id}` 形态，仅单次尝试
      pollUrl = openAiUrl(endpoint, `images/task/${encodeURIComponent(taskId)}`);
      poll = await fetchImpl(pollUrl, { headers: { authorization: `Bearer ${credential}` }, signal });
    }
    const data = await jsonResponse(poll, 'sub2api');
    const status = String(data?.status ?? data?.task_status ?? data?.state ?? '').toLowerCase();
    if (SUB2API_DONE.has(status)) {
      const assets = genericAssets(data);
      if (assets.length === 0) throw new Error('Sub2API 任务成功但未返回图片');
      return assets;
    }
    if (SUB2API_FAIL.has(status)) throw new Error(`Sub2API 异步任务失败（${data?.status ?? data?.task_status ?? 'unknown'}）`);
  }
  throw new Error('Sub2API 异步任务轮询超时');
}

/** 受限 OpenAI Chat 图片解析：仅接受明确的图片 data URL / base64 / 安全图片 URL。 */
export async function openaiChatImageAdapter({ endpoint, model, credential, request, references, fetchImpl, signal }) {
  if (!endpoint || !model) throw new Error('openai-chat-image 适配器缺少 Base URL 或模型');
  const headers = { authorization: `Bearer ${credential}`, ...JSON_HEADERS };
  const content = [
    { type: 'text', text: request.prompt },
    ...references.map((ref) => ({ type: 'image_url', image_url: { url: `data:${ref.mime};base64,${ref.bytes.toString('base64')}` } })),
  ];
  const data = await jsonResponse(await fetchImpl(openAiUrl(endpoint, 'chat/completions'), {
    method: 'POST',
    headers,
    body: JSON.stringify({
      model,
      modalities: ['text', 'image'],
      ...(request.size ? { image: { size: request.size } } : {}),
      messages: [{ role: 'user', content }],
    }),
    signal,
  }), 'openai-chat-image');
  const parts = (data?.choices ?? []).flatMap((choice) => choice?.message?.content ?? []);
  const assets = parts.flatMap((part) => {
    if (typeof part === 'string') return [];
    const url = typeof part?.image_url?.url === 'string' ? part.image_url.url : part?.url;
    if (typeof url !== 'string') return [];
    const dataUrl = url.match(/^data:(image\/[a-z0-9.+-]+);base64,(.+)$/i);
    if (dataUrl) return [{ kind: 'base64', data: dataUrl[2], mime: dataUrl[1].toLowerCase() }];
    if (/^https?:\/\//i.test(url)) return [{ kind: 'url', url }];
    return [];
  });
  if (assets.length === 0) throw new Error('openai-chat-image 响应中没有可解析的图片');
  return assets;
}

/** ChatGPT 订阅（Codex）生图适配器：镜像 codex-rs images 端点，会话由订阅插件统一协调。 */
export async function codexImagesAdapter({ endpoint, model, credential, request, references, fetchImpl, signal, subscriptionSessions }) {
  if (references.length > 0) throw new Error('codex-images 适配器不支持参考图；请改用其他连接或去掉参考图');
  let session;
  try {
    const parsed = JSON.parse(credential);
    if (typeof parsed?.access !== 'string' || typeof parsed?.accountId !== 'string') throw new Error('bad shape');
    session = parsed;
  } catch {
    session = await resolveCodexSession({ subscriptionSessions, signal });
  }
  // 快照与 resolveCodexSession 返回形状不同（access vs accessToken）；统一取值
  const accessToken = typeof session.access === 'string' ? session.access : session.accessToken;
  const url = openAiUrl(endpoint ?? 'https://chatgpt.com/backend-api', 'codex/images/generations');
  const headers = {
    'authorization': `Bearer ${accessToken}`,
    'chatgpt-account-id': session.accountId,
    'originator': 'codex_cli_rs',
    'accept': 'application/json',
    ...JSON_HEADERS,
  };
  const call = () => fetchImpl(url, {
    method: 'POST',
    headers,
    body: JSON.stringify({ prompt: request.prompt, model, ...(request.size ? { size: request.size } : {}) }),
    signal,
  });
  let response = await call();
  if (response.status === 401) {
    // 未到期但被拒：强刷一次 token 再重试（codex CLI 同款模式）
    session = await resolveCodexSession({ subscriptionSessions, signal, force: true });
    headers.authorization = `Bearer ${typeof session.access === 'string' ? session.access : session.accessToken}`;
    response = await call();
  }
  const data = await jsonResponse(response, 'codex-images');
  const assets = genericAssets(data);
  if (assets.length === 0) throw new Error('codex-images 响应中没有可解析的图片');
  // Codex 端点单请求单图；count>1 时补足循环调用
  for (let index = 1; index < request.count; index += 1) {
    if (signal?.aborted) throw new DOMException('Aborted', 'AbortError');
    const extra = genericAssets(await jsonResponse(await call(), 'codex-images'));
    if (extra.length === 0) break;
    assets.push(...extra);
  }
  return assets;
}

/** 会话 token 取值：兼容连接快照 {access} 与 resolveGrokSession 返回 {accessToken} 两种形状。 */
function grokAccessToken(session) {
  if (typeof session?.access === 'string' && session.access.length > 0) return session.access;
  if (typeof session?.accessToken === 'string' && session.accessToken.length > 0) return session.accessToken;
  return undefined;
}

/** Grok 订阅生图适配器：api.x.ai/v1/images/generations（OpenAI Images 兼容，n 原生支持），会话由订阅插件统一协调。 */
export async function grokImagesAdapter({ endpoint, model, credential, request, references, fetchImpl, signal, subscriptionSessions }) {
  if (references.length > 0) throw new Error('grok-images 适配器不支持参考图；请改用其他连接或去掉参考图');
  let session;
  try {
    const parsed = JSON.parse(credential);
    if (typeof parsed?.access !== 'string' || parsed.access.length === 0) throw new Error('bad shape');
    session = parsed;
  } catch {
    session = await resolveGrokSession({ subscriptionSessions, signal });
  }
  const url = openAiUrl(endpoint ?? 'https://api.x.ai/v1', 'images/generations');
  const headers = { authorization: `Bearer ${grokAccessToken(session)}`, ...JSON_HEADERS };
  const call = () => fetchImpl(url, {
    method: 'POST',
    headers,
    body: JSON.stringify({ model, prompt: request.prompt, n: request.count, response_format: 'b64_json' }),
    signal,
  });
  let response = await call();
  if (response.status === 401) {
    // 未到期但被拒：强刷一次 token 再重试（与 grok 插件路由同款模式）
    session = await resolveGrokSession({ subscriptionSessions, signal, force: true });
    headers.authorization = `Bearer ${grokAccessToken(session)}`;
    response = await call();
  }
  const data = await jsonResponse(response, 'grok-images');
  const assets = genericAssets(data);
  if (assets.length === 0) throw new Error('grok-images 响应中没有可解析的图片');
  return assets;
}

export const IMAGE_ADAPTERS = Object.freeze({ dashscope: dashscopeAdapter, openai: openaiAdapter, gemini: geminiAdapter, custom: customAdapter });

/** 按协议 ID 的适配器注册表（连接携带 adapter / verification.protocol）。 */
export const ADAPTER_BY_ID = Object.freeze({
  'dashscope-async': dashscopeAdapter,
  'openai-images': openaiImagesAdapter,
  'gemini-content': geminiAdapter,
  'sub2api-async-images': sub2apiAsyncImagesAdapter,
  'openai-chat-image': openaiChatImageAdapter,
  'codex-images': codexImagesAdapter,
  'grok-images': grokImagesAdapter,
});
