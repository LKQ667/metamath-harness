import { createHash } from 'node:crypto';
import { mkdir, readFile, stat, writeFile } from 'node:fs/promises';
import { basename, extname, isAbsolute, relative, resolve } from 'node:path';
import { ADAPTER_BY_ID } from './adapters.js';
import { MAX_DOWNLOAD_BYTES, MIME_EXT, decodeImageAsset, downloadImage, mimeForPath, requestError } from './assets.js';
import { redactText } from '../security/redact.js';

function inside(root, candidate) {
  const rel = relative(root, candidate);
  return rel === '' || (!rel.startsWith('..') && !isAbsolute(rel));
}

function validateRequest(request) {
  if (!request || typeof request !== 'object' || Array.isArray(request)) throw requestError('invalid_request', '生图请求必须是对象');
  if (typeof request.prompt !== 'string' || !request.prompt.trim()) throw requestError('invalid_prompt', '生图 Prompt 不能为空');
  const count = request.count ?? 1;
  if (!Number.isInteger(count) || count < 1 || count > 4) throw requestError('count_out_of_range', '单次生图数量必须为 1 到 4');
  if (request.authorizePaid !== true) throw requestError('paid_not_authorized', '必须显式确认允许本次付费生图调用');
  if (request.budgetRemaining !== undefined && (!Number.isInteger(request.budgetRemaining) || request.budgetRemaining < count)) throw requestError('budget_exceeded', '任务剩余生图预算不足');
  if (request.connectionId !== undefined && (typeof request.connectionId !== 'string' || !request.connectionId.trim())) throw requestError('invalid_connection_id', 'connectionId 无效');
  return { ...request, count, referenceImages: request.referenceImages ?? [] };
}

async function loadReferences(items, workspace) {
  const refs = [];
  for (const item of items) {
    if (typeof item !== 'string' || /^https?:\/\//i.test(item)) throw requestError('reference_url_unsupported', '参考图必须是当前工作区内的本地图片');
    const path = resolve(workspace, item);
    if (!inside(workspace, path)) throw requestError('path_outside_workspace', '参考图必须位于当前工作区内');
    const info = await stat(path).catch((error) => { if (error?.code === 'ENOENT') throw requestError('reference_not_found', `参考图不存在：${basename(path)}`); throw error; });
    if (!info.isFile() || info.size > MAX_DOWNLOAD_BYTES) throw requestError('invalid_reference', '参考图不是文件或超过 25 MB');
    const mime = mimeForPath(path);
    if (!mime) throw requestError('unsupported_reference', '参考图仅支持 PNG、JPEG、WebP 或 GIF');
    refs.push({ bytes: await readFile(path), mime, ext: MIME_EXT.get(mime) });
  }
  return refs;
}

function connectionFailure(error, credentialValue, messagePrefix = '') {
  return {
    code: error?.code ?? 'provider_error',
    message: `${messagePrefix}${redactText(error?.message ?? error, [credentialValue])}`,
  };
}

export class ImageGenerationService {
  constructor({ connections, fetchImpl = globalThis.fetch, adapters = ADAPTER_BY_ID, now = () => Date.now(), sleep } = {}) {
    this.connections = connections;
    this.fetch = fetchImpl;
    this.adapters = adapters;
    this.now = now;
    this.sleep = sleep;
  }

  async generate(rawRequest, { workspace = process.cwd(), signal } = {}) {
    const request = validateRequest(rawRequest);
    const root = resolve(workspace);
    const outputDir = resolve(root, request.outputDir ?? '.');
    if (!inside(root, outputDir)) throw requestError('path_outside_workspace', '输出目录必须位于当前工作区内');
    const references = await loadReferences(request.referenceImages, root);

    let resolved;
    try {
      if (typeof request.connectionId === 'string' && request.connectionId.trim()) {
        resolved = await this.connections.resolveForGenerate(request.connectionId);
      } else if (typeof request.provider === 'string' && request.provider.trim()) {
        resolved = await this.connections.resolveLegacyProvider(request.provider);
      } else {
        resolved = await this.connections.resolveForGenerate();
      }
    } catch (error) {
      return {
        ok: false,
        schema: 'dsh.mathmodel.image-result/v1',
        error: { code: error?.code ?? 'connection_unavailable', message: redactText(error?.message ?? String(error)) },
        fallback: { skill: 'ai-draw-skills', prompt: request.prompt },
      };
    }
    const { connection, adapterId, credentialValue, subscriptionSessions } = resolved;
    const adapter = this.adapters[adapterId];
    if (typeof adapter !== 'function') {
      return {
        ok: false,
        schema: 'dsh.mathmodel.image-result/v1',
        error: { code: 'unknown_adapter', message: `连接“${connection.name}”的适配器不可用` },
        fallback: { skill: 'ai-draw-skills', prompt: request.prompt },
      };
    }
    try {
      const assets = await adapter({
        provider: connection.template,
        endpoint: connection.baseUrl,
        model: connection.model,
        credential: credentialValue,
        request,
        references,
        fetchImpl: this.fetch,
        signal,
        sleep: this.sleep,
        subscriptionSessions,
      });
      if (!Array.isArray(assets) || assets.length < request.count) throw new Error(`供应商只返回 ${assets?.length ?? 0} 张图片`);
      await mkdir(outputDir, { recursive: true });
      const files = [];
      const metadataFiles = [];
      for (const [index, asset] of assets.slice(0, request.count).entries()) {
        const image = asset.kind === 'url' ? await downloadImage(this.fetch, asset.url, signal) : decodeImageAsset(asset);
        const filename = `image-${this.now()}-${index + 1}.${MIME_EXT.get(image.mime)}`;
        const path = resolve(outputDir, filename);
        await writeFile(path, image.bytes, { flag: 'wx' });
        files.push(path);
        metadataFiles.push({ file: filename, sha256: createHash('sha256').update(image.bytes).digest('hex'), mime: image.mime });
      }
      const metadata = {
        schema: 'dsh.mathmodel.image-metadata/v1',
        connectionId: connection.id,
        connectionName: connection.name,
        template: connection.template,
        model: connection.model,
        protocol: adapterId,
        promptSha256: createHash('sha256').update(request.prompt).digest('hex'),
        count: files.length,
        aspectRatio: request.aspectRatio ?? null,
        size: request.size ?? null,
        files: metadataFiles,
      };
      const metadataFile = resolve(outputDir, `metadata-${this.now()}.json`);
      await writeFile(metadataFile, `${JSON.stringify(metadata, null, 2)}\n`, { flag: 'wx' });
      return {
        ok: true,
        schema: 'dsh.mathmodel.image-result/v1',
        connectionId: connection.id,
        provider: connection.template,
        model: metadata.model,
        files,
        metadataFile,
        warnings: [],
      };
    } catch (error) {
      if (signal?.aborted || error?.name === 'AbortError') throw requestError('cancelled', '生图任务已取消');
      return {
        ok: false,
        schema: 'dsh.mathmodel.image-result/v1',
        error: {
          code: 'image_generation_failed',
          message: `连接“${connection.name}”生图失败：${redactText(error?.message ?? error, [credentialValue])}`,
          failures: [connectionFailure(error, credentialValue, `连接“${connection.name}”：`)],
        },
        fallback: { skill: 'ai-draw-skills', prompt: request.prompt },
      };
    }
  }
}
