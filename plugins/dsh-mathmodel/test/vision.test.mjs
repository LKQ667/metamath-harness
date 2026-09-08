import test from 'node:test';
import assert from 'node:assert/strict';
import { mkdtemp, readFile, writeFile } from 'node:fs/promises';
import { join } from 'node:path';
import { tmpdir } from 'node:os';
import { ManualVisionService, VisionService, detectImageMime } from '../lib/index.js';

const secret = 'dashscope-secret-fixture';
const credentials = { resolve: async () => ({ value: secret, source: 'file' }) };
const ok = (text = '识别成功') => ({ ok: true, status: 200, json: async () => ({ choices: [{ message: { content: text } }] }) });

test('HTTPS URL 使用主模型且结果不含凭据', async () => {
  const calls = [];
  const service = new VisionService({ credentials, fetchImpl: async (url, init) => { calls.push({ url, init }); return ok(); } });
  const result = await service.analyze({ image: 'https://example.com/chart.png', prompt: '分析图表' });
  assert.equal(result.model, 'qwen3.7-plus');
  assert.equal(result.sourceType, 'url');
  assert.equal(calls.length, 1);
  assert.match(calls[0].init.headers.authorization, /^Bearer /);
  assert.doesNotMatch(JSON.stringify(result), new RegExp(secret));
});

test('主模型失败后切换到指定回退模型', async () => {
  const models = [];
  const service = new VisionService({ credentials, fetchImpl: async (_url, init) => {
    const model = JSON.parse(init.body).model;
    models.push(model);
    return model === 'qwen3.7-plus' ? { ok: false, status: 503, json: async () => ({}) } : ok('回退成功');
  } });
  const result = await service.analyze({ image: 'https://example.com/a.png' });
  assert.deepEqual(models, ['qwen3.7-plus', 'qwen3.7-flash-2026-07-15']);
  assert.equal(result.text, '回退成功');
  assert.equal(result.warnings.length, 1);
});

test('本地图片转 data URL 且限制在工作区', async () => {
  const workspace = await mkdtemp(join(tmpdir(), 'dsh-vision-'));
  await writeFile(join(workspace, 'tiny.png'), Buffer.from([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a]));
  let body;
  const service = new VisionService({ credentials, fetchImpl: async (_url, init) => { body = JSON.parse(init.body); return ok(); } });
  const result = await service.analyze({ image: 'tiny.png', workspace });
  assert.equal(result.sourceType, 'local');
  assert.match(body.messages[0].content[0].image_url.url, /^data:image\/png;base64,/);
  await assert.rejects(() => service.analyze({ image: '..\\outside.png', workspace }), (error) => error.code === 'path_outside_workspace');
});

test('无扩展名内容寻址附件按文件签名识别，扩展名冲突与截断内容失败关闭', async () => {
  const workspace = await mkdtemp(join(tmpdir(), 'dsh-vision-signature-'));
  const png = Buffer.from([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a, 0x00]);
  await writeFile(join(workspace, 'sha256-object'), png);
  await writeFile(join(workspace, 'wrong.jpg'), png);
  await writeFile(join(workspace, 'truncated.png'), Buffer.from([0x89, 0x50, 0x4e]));
  let body;
  const service = new VisionService({ credentials, fetchImpl: async (_url, init) => { body = JSON.parse(init.body); return ok(); } });
  await service.analyze({ image: 'sha256-object', workspace });
  assert.match(body.messages[0].content[0].image_url.url, /^data:image\/png;base64,/);
  await assert.rejects(() => service.analyze({ image: 'wrong.jpg', workspace }), (error) => error.code === 'image_type_mismatch');
  await assert.rejects(() => service.analyze({ image: 'truncated.png', workspace }), (error) => error.code === 'unsupported_image');
  assert.equal(detectImageMime(Buffer.from('GIF89a', 'ascii')), 'image/gif');
  assert.equal(detectImageMime(Buffer.from([0xff, 0xd8, 0xff])), 'image/jpeg');
  assert.equal(detectImageMime(Buffer.from('RIFF0000WEBP', 'ascii')), 'image/webp');
});

test('文件不存在、HTTP URL 和取消返回稳定错误码', async () => {
  const workspace = await mkdtemp(join(tmpdir(), 'dsh-vision-errors-'));
  const service = new VisionService({ credentials, fetchImpl: async () => ok() });
  await assert.rejects(() => service.analyze({ image: 'missing.png', workspace }), (error) => error.code === 'file_not_found');
  await assert.rejects(() => service.analyze({ image: 'http://example.com/a.png', workspace }), (error) => error.code === 'invalid_url');
  const controller = new AbortController();
  controller.abort();
  await assert.rejects(() => service.analyze({ image: 'https://example.com/a.png', signal: controller.signal }), (error) => error.code === 'cancelled');
});

test('全部失败时错误详情脱敏', async () => {
  const service = new VisionService({ credentials, fetchImpl: async () => { throw new Error(`network leaked ${secret}`); } });
  await assert.rejects(
    () => service.analyze({ image: 'https://example.com/a.png' }),
    (error) => error.code === 'all_models_failed' && !JSON.stringify(error.details).includes(secret),
  );
});

test('全部 HTTP 失败时公开消息只包含逐模型 code/status，不包含秘密或上游正文', async () => {
  const service = new VisionService({ credentials, fetchImpl: async () => ({ ok: false, status: 403, json: async () => ({ message: `leak ${secret}` }) }) });
  await assert.rejects(
    () => service.analyze({ image: 'https://example.com/a.png' }),
    (error) => error.code === 'all_models_failed'
      && error.message.includes('qwen3.7-plus: provider_http_error/HTTP 403')
      && error.message.includes('qwen3.7-flash-2026-07-15: provider_http_error/HTTP 403')
      && !error.message.includes(secret),
  );
});

test('手动附图把草稿原图保存到工作区 uploads 并返回相对路径', async () => {
  const service = new ManualVisionService({ now: () => 1786790000000 });
  const root = await mkdtemp(join(tmpdir(), 'dsh-stage-'));
  const data = Buffer.from([137, 80, 78, 71]).toString('base64');
  const result = await service.stageDraftImages({ workspace: root, images: [
    { mediaType: 'image/png', data, name: '图一.png' },
    { mediaType: 'image/png', data, name: '图二.png' },
  ] });
  assert.equal(result.schema, 'dsh.mathmodel.manual-vision-stage/v1');
  assert.deepEqual(result.files.map((file) => file.path), ['uploads/img-1786790000000-1.png', 'uploads/img-1786790000000-2.png']);
  const saved = await readFile(join(root, 'uploads', 'img-1786790000000-1.png'));
  assert.equal(saved.toString('base64'), data, '落盘字节必须与草稿原图一致');
  await assert.rejects(
    () => service.stageDraftImages({ workspace: root, images: [{ mediaType: 'image/png', data: 'not base64' }] }),
    (error) => error.code === 'invalid_image_data',
  );
  await assert.rejects(
    () => service.stageDraftImages({ workspace: join(root, '不存在'), images: [{ mediaType: 'image/png', data }] }),
    (error) => error.code === 'workspace_not_found',
  );
  await assert.rejects(
    () => service.stageDraftImages({ workspace: '', images: [{ mediaType: 'image/png', data }] }),
    (error) => error.code === 'workspace_required',
  );
});
