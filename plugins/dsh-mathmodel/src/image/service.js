import { createHash, randomUUID } from 'node:crypto';
import { mkdir, readFile, realpath, rename, rm, stat, writeFile } from 'node:fs/promises';
import { basename, dirname, extname, isAbsolute, relative, resolve } from 'node:path';
import { ADAPTER_BY_ID } from './adapters.js';
import { MAX_DOWNLOAD_BYTES, MIME_EXT, decodeImageAsset, downloadImage, mimeForPath, requestError, sniffImageMime } from './assets.js';
import { redactText } from '../security/redact.js';
import { requireCapabilities } from './capabilities.js';

export const EDITABLE_PPT_STATUS_SCHEMA = 'dsh.mathmodel.editable-ppt-image-status/v1';
export const EDITABLE_PPT_RESULT_SCHEMA = 'dsh.mathmodel.editable-ppt-image-result/v1';
export const EDITABLE_PPT_METADATA_SCHEMA = 'dsh.mathmodel.editable-ppt-image-metadata/v1';
const STRICT_SIZES = new Set(['auto', '1024x1024', '1536x1024', '1024x1536']);
const STRICT_QUALITIES = new Set(['auto', 'low', 'medium', 'high']);
const STRICT_RETRY_DELAYS = Object.freeze([1000, 2000]);
const STRICT_INVALID_IMAGE_CODES = new Set([
  'invalid_content_type', 'invalid_image_bytes', 'download_too_large', 'invalid_base64_image',
  'unsafe_download_url', 'too_many_redirects', 'invalid_redirect',
]);

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

async function loadReferences(items, workspace, { strict = false } = {}) {
  const refs = [];
  for (const item of items) {
    if (typeof item !== 'string' || /^https?:\/\//i.test(item)) throw requestError('reference_url_unsupported', '参考图必须是当前工作区内的本地图片');
    const path = resolve(workspace, item);
    if (!inside(workspace, path)) throw requestError('path_outside_workspace', '参考图必须位于当前工作区内');
    const actualPath = strict
      ? await realpath(path).catch((error) => { if (error?.code === 'ENOENT') throw requestError('reference_not_found', `参考图不存在：${basename(path)}`); throw error; })
      : path;
    if (strict && !inside(workspace, actualPath)) throw requestError('path_outside_workspace', '参考图的真实路径必须位于当前工作区内');
    const info = await stat(actualPath).catch((error) => { if (error?.code === 'ENOENT') throw requestError('reference_not_found', `参考图不存在：${basename(path)}`); throw error; });
    if (!info.isFile() || info.size > MAX_DOWNLOAD_BYTES) throw requestError('invalid_reference', '参考图不是文件或超过 25 MB');
    const declaredMime = mimeForPath(path);
    if (!declaredMime) throw requestError('unsupported_reference', '参考图仅支持 PNG、JPEG、WebP 或 GIF');
    const bytes = await readFile(actualPath);
    const mime = strict ? sniffImageMime(bytes) : declaredMime;
    if (!mime || (strict && mime !== declaredMime)) throw requestError('invalid_reference', '参考图内容不是与扩展名一致的 PNG、JPEG、WebP 或 GIF 图片');
    refs.push({ bytes, mime, ext: MIME_EXT.get(mime) });
  }
  return refs;
}

function connectionFailure(error, credentialValue, messagePrefix = '') {
  return {
    code: error?.code ?? 'provider_error',
    message: `${messagePrefix}${redactText(error?.message ?? error, [credentialValue])}`,
  };
}

function validateEditablePptRequest(raw) {
  if (!raw || typeof raw !== 'object' || Array.isArray(raw)) throw requestError('invalid_request', 'editable_ppt_image 请求必须是对象');
  const action = raw.action;
  if (action !== 'status' && action !== 'generate' && action !== 'edit') throw requestError('invalid_action', 'action 必须为 status、generate 或 edit');
  if (action === 'status') return { action };
  if (raw.count !== undefined) throw requestError('invalid_request', 'editable_ppt_image 固定单张输出，不接受 count');
  if (typeof raw.connectionId !== 'string' || !raw.connectionId.trim()) throw requestError('connection_id_required', 'generate/edit 必须显式携带任务开始时锁定的 connectionId');
  if (typeof raw.prompt !== 'string' || !raw.prompt.trim()) throw requestError('invalid_prompt', 'Prompt 不能为空');
  if (typeof raw.outputPath !== 'string' || !raw.outputPath.trim()) throw requestError('invalid_output_path', 'outputPath 必填');
  if (/^[a-z]+:\/\//i.test(raw.outputPath.trim())) throw requestError('invalid_output_path', 'outputPath 必须是工作区本地路径');
  if (!extname(raw.outputPath.trim())) throw requestError('invalid_output_path', 'outputPath 必须带图片扩展名');
  if (raw.authorizePaid !== true) throw requestError('paid_not_authorized', '必须显式确认允许本次付费生图调用');
  if (raw.size !== undefined && !STRICT_SIZES.has(raw.size)) throw requestError('invalid_size', 'size 必须为 auto、1024x1024、1536x1024 或 1024x1536');
  if (raw.quality !== undefined && !STRICT_QUALITIES.has(raw.quality)) throw requestError('invalid_quality', 'quality 必须为 auto、low、medium 或 high');
  if (raw.budgetRemaining !== undefined && (!Number.isInteger(raw.budgetRemaining) || raw.budgetRemaining < 1)) throw requestError('budget_exceeded', '任务剩余生图预算不足');
  if (action === 'generate' && ((Array.isArray(raw.referenceImages) && raw.referenceImages.length > 0) || raw.maskImage)) {
    throw requestError('invalid_request', 'generate 调用不得携带参考图或 mask；对已有图像的修复/拆分必须使用 edit');
  }
  if (action === 'edit') {
    if (!Array.isArray(raw.referenceImages) || raw.referenceImages.length < 1 || raw.referenceImages.length > 4) {
      throw requestError('invalid_request', 'edit 调用必须携带 1–4 张参考图');
    }
  }
  return {
    action,
    connectionId: raw.connectionId.trim(),
    prompt: raw.prompt,
    outputPath: raw.outputPath.trim(),
    authorizePaid: true,
    size: raw.size,
    quality: raw.quality,
    budgetRemaining: raw.budgetRemaining,
    referenceImages: raw.referenceImages ?? [],
    maskImage: typeof raw.maskImage === 'string' && raw.maskImage ? raw.maskImage : undefined,
  };
}

async function loadMask(item, workspace) {
  if (typeof item !== 'string' || /^https?:\/\//i.test(item)) throw requestError('mask_url_unsupported', 'mask 必须是当前工作区内的本地图片');
  const path = resolve(workspace, item);
  if (!inside(workspace, path)) throw requestError('path_outside_workspace', 'mask 必须位于当前工作区内');
  const actualPath = await realpath(path).catch((error) => {
    if (error?.code === 'ENOENT') throw requestError('mask_not_found', `mask 不存在：${basename(path)}`);
    throw error;
  });
  if (!inside(workspace, actualPath)) throw requestError('path_outside_workspace', 'mask 的真实路径必须位于当前工作区内');
  const info = await stat(actualPath);
  if (!info.isFile() || info.size > MAX_DOWNLOAD_BYTES) throw requestError('invalid_mask', 'mask 不是文件或超过 25 MB');
  if (extname(path).toLowerCase() !== '.png') throw requestError('unsupported_mask', 'mask 必须是 PNG 图片');
  const bytes = await readFile(actualPath);
  const mime = sniffImageMime(bytes);
  if (mime !== 'image/png') throw requestError('invalid_mask', 'mask 内容必须是有效 PNG 图片');
  return { bytes, mime, ext: 'png' };
}

function sha256Hex(value) {
  return createHash('sha256').update(value).digest('hex');
}

/** 供应商错误 → §9 稳定错误码；只有传输类与 5xx 允许有界重试。 */
function classifyProviderError(error) {
  const code = error?.code;
  if (typeof code === 'string' && code) {
    if (STRICT_INVALID_IMAGE_CODES.has(code)) return { stable: 'invalid_image_response', retryable: false };
    if (code === 'cancelled' || code === 'invalid_image_response' || code === 'path_outside_workspace' || code === 'output_exists' || code === 'output_format_mismatch' || code === 'invalid_request') {
      return { stable: code, retryable: false };
    }
  }
  const status = Number(error?.status ?? 0);
  if (status === 401 || status === 403) return { stable: 'provider_auth_failed', retryable: false };
  if (status === 429) return { stable: 'provider_quota_exhausted', retryable: false };
  if (status === 400 || status === 404) return { stable: 'provider_request_invalid', retryable: false };
  if (status >= 500 && status <= 599) return { stable: 'provider_server_failed', retryable: true };
  if (status >= 400) return { stable: 'provider_request_invalid', retryable: false };
  if (status > 0) return { stable: 'provider_transport_failed', retryable: true };
  if (code) return { stable: 'provider_error', retryable: false };
  return { stable: 'provider_transport_failed', retryable: true };
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

  /** 可编辑 PPT 专用入口：status 只读锁定；generate/edit 严格确定性、失败不降级、绝不触碰 Codex。 */
  async editablePptImage(rawRequest, { workspace = process.cwd(), signal, overwrite = false } = {}) {
    try {
      const request = validateEditablePptRequest(rawRequest);
      if (request.action === 'status') {
        const description = await this.connections.describeActiveForTool();
        return { ok: true, schema: EDITABLE_PPT_STATUS_SCHEMA, ...description };
      }
      const root = await realpath(resolve(workspace));
      return await this._editablePptRun(request, { root, signal, overwrite });
    } catch (error) {
      if (signal?.aborted || error?.name === 'AbortError') {
        return { ok: false, schema: EDITABLE_PPT_RESULT_SCHEMA, error: { code: 'cancelled', message: 'editable_ppt_image 调用已取消' } };
      }
      return {
        ok: false,
        schema: EDITABLE_PPT_RESULT_SCHEMA,
        error: { code: error?.code ?? 'internal_error', message: redactText(error?.message ?? error) },
      };
    }
  }

  async _editablePptRun(request, { root, signal, overwrite }) {
    if (signal?.aborted) return { ok: false, schema: EDITABLE_PPT_RESULT_SCHEMA, error: { code: 'cancelled', message: 'editable_ppt_image 调用已取消' } };
    const outPath = resolve(root, request.outputPath);
    if (!inside(root, outPath) || resolve(outPath) === root) {
      return editablePptFailure('path_outside_workspace', 'outputPath 必须位于当前工作区内，且不允许 .. 穿越或绝对越界');
    }
    if (!/\.(png|jpe?g|webp|gif)$/i.test(outPath)) {
      return editablePptFailure('invalid_output_path', 'outputPath 必须使用 .png/.jpg/.jpeg/.webp/.gif 扩展名');
    }
    try {
      await ensureSafeOutputParent(root, outPath);
    } catch (error) {
      return editablePptFailure(error?.code ?? 'path_outside_workspace', error?.message ?? error);
    }
    const metadataPath = `${outPath.slice(0, outPath.length - extname(outPath).length)}.dsh-image.json`;
    await removeOwnedOrphanMetadata(outPath, metadataPath);
    if (request.action === 'edit') {
      const referencesError = await validateReferencePaths(request.referenceImages, root);
      if (referencesError) return editablePptFailure(referencesError.code, referencesError.message);
    }
    let references;
    let maskRef = null;
    try {
      references = await loadReferences(request.referenceImages, root, { strict: true });
      if (request.maskImage) maskRef = await loadMask(request.maskImage, root);
    } catch (error) {
      return editablePptFailure(error?.code ?? 'invalid_request', redactText(error?.message ?? error));
    }
    if (!overwrite && (await pathExists(outPath) || await pathExists(metadataPath))) {
      return editablePptFailure('output_exists', `输出文件或元数据已存在：${relative(root, outPath)}；页面重置必须由受控路径执行，不得复用同名输出`);
    }

    let resolved;
    try {
      resolved = await this.connections.resolveForEditablePpt(request.connectionId);
    } catch (error) {
      return editablePptFailure(error?.code ?? 'connection_unavailable', redactText(error?.message ?? error));
    }
    const { connection, adapterId, credentialValue, subscriptionSessions } = resolved;
    try {
      requireCapabilities({
        protocol: adapterId,
        operation: request.action,
        multiReference: references.length > 1,
        mask: Boolean(maskRef),
        quality: request.quality !== undefined,
        size: request.size !== undefined,
      });
    } catch (error) {
      return editablePptFailure(error?.code ?? 'capability_unsupported', redactText(error?.message ?? error));
    }
    const adapter = this.adapters[adapterId];
    if (typeof adapter !== 'function') return editablePptFailure('unknown_adapter', `连接“${connection.name}”的适配器不可用`);

    const providerRequest = {
      prompt: request.prompt,
      count: 1,
      ...(request.size ? { size: request.size } : {}),
      ...(request.quality ? { quality: request.quality } : {}),
    };
    const sleep = this.sleep ?? ((ms) => new Promise((done) => setTimeout(done, ms)));
    let attempt = 0;
    for (;;) {
      try {
        const assets = await adapter({
          provider: connection.template,
          endpoint: connection.baseUrl,
          model: connection.model,
          credential: credentialValue,
          request: providerRequest,
          references,
          maskRef,
          fetchImpl: this.fetch,
          signal,
          sleep,
          subscriptionSessions,
        });
        if (!Array.isArray(assets) || assets.length < 1) throw requestError('invalid_image_response', '供应商没有返回任何图片');
        const first = assets[0];
        const image = first.kind === 'url' ? await downloadImage(this.fetch, first.url, signal) : decodeImageAsset(first);
        if (mimeForPath(outPath) !== image.mime) {
          throw requestError('output_format_mismatch', `供应商返回 ${image.mime}，与请求输出扩展名 ${extname(outPath)} 不一致`);
        }
        const sha256 = sha256Hex(image.bytes);
        const metadata = {
          schema: EDITABLE_PPT_METADATA_SCHEMA,
          createdAt: new Date().toISOString(),
          connectionId: connection.id,
          connectionName: connection.name,
          template: connection.template,
          model: connection.model,
          protocol: adapterId,
          operation: request.action,
          promptSha256: sha256Hex(request.prompt),
          inputSha256: [
            ...references.map((ref) => sha256Hex(ref.bytes)),
            ...(maskRef ? [sha256Hex(maskRef.bytes)] : []),
          ],
          size: request.size ?? null,
          quality: request.quality ?? null,
          files: [{ file: basename(outPath), sha256, mime: image.mime }],
        };
        await writeImageBundle(outPath, metadataPath, image.bytes, `${JSON.stringify(metadata, null, 2)}\n`, overwrite);
        return {
          ok: true,
          schema: EDITABLE_PPT_RESULT_SCHEMA,
          connectionId: connection.id,
          model: connection.model,
          protocol: adapterId,
          operation: request.action,
          file: relative(root, outPath).split('\\').join('/'),
          sha256,
          metadataFile: relative(root, metadataPath).split('\\').join('/'),
        };
      } catch (error) {
        if (signal?.aborted || error?.name === 'AbortError') return editablePptFailure('cancelled', 'editable_ppt_image 调用已取消');
        const classified = classifyProviderError(error);
        if (classified.retryable && attempt < STRICT_RETRY_DELAYS.length) {
          attempt += 1;
          await sleep(STRICT_RETRY_DELAYS[attempt - 1]);
          continue;
        }
        const message = classified.retryable && attempt > 0
          ? `${redactText(error?.message ?? error, [credentialValue, connection.baseUrl])}（瞬时错误重试 ${attempt} 次后仍失败）`
          : redactText(error?.message ?? error, [credentialValue, connection.baseUrl]);
        return editablePptFailure(classified.stable, message);
      }
    }
  }
}

function editablePptFailure(code, message) {
  return { ok: false, schema: EDITABLE_PPT_RESULT_SCHEMA, error: { code, message: redactText(message) } };
}

async function pathExists(path) {
  try {
    await stat(path);
    return true;
  } catch {
    return false;
  }
}

/** 在创建目录前解析最近的已存在祖先，拒绝通过 symlink/Junction 越出工作区。 */
async function ensureSafeOutputParent(root, outPath) {
  let ancestor = dirname(outPath);
  while (!await pathExists(ancestor)) {
    const parent = dirname(ancestor);
    if (parent === ancestor) throw requestError('path_outside_workspace', '无法解析输出目录的工作区边界');
    ancestor = parent;
  }
  const actualAncestor = await realpath(ancestor);
  if (!inside(root, actualAncestor)) throw requestError('path_outside_workspace', '输出目录的真实路径必须位于当前工作区内');
  await mkdir(dirname(outPath), { recursive: true });
  const actualParent = await realpath(dirname(outPath));
  if (!inside(root, actualParent)) throw requestError('path_outside_workspace', '输出目录的真实路径必须位于当前工作区内');
}

/** 同目录临时文件提交；任一步失败都清理本次产生的正式文件，避免图片/sidecar 半提交。 */
async function writeImageBundle(outPath, metadataPath, imageBytes, metadataText, overwrite) {
  const nonce = randomUUID();
  const tempImage = `${outPath}.${nonce}.tmp`;
  const tempMetadata = `${metadataPath}.${nonce}.tmp`;
  let imageCommitted = false;
  let metadataCommitted = false;
  try {
    await writeFile(tempImage, imageBytes, { flag: 'wx' });
    await writeFile(tempMetadata, metadataText, { flag: 'wx' });
    if (!overwrite && (await pathExists(outPath) || await pathExists(metadataPath))) {
      throw requestError('output_exists', `输出文件或元数据已存在：${basename(outPath)}`);
    }
    await rename(tempMetadata, metadataPath);
    metadataCommitted = true;
    // 图片最后出现：任何观察到正式图片的消费者都能同时读取完整 sidecar。
    await rename(tempImage, outPath);
    imageCommitted = true;
  } catch (error) {
    if (metadataCommitted) await rm(metadataPath, { force: true }).catch(() => {});
    if (imageCommitted) await rm(outPath, { force: true }).catch(() => {});
    throw error;
  } finally {
    await rm(tempImage, { force: true }).catch(() => {});
    await rm(tempMetadata, { force: true }).catch(() => {});
  }
}

/** 硬中断可能只留下已提交的 DSH sidecar；仅清理可确认属于该目标的孤儿元数据。 */
async function removeOwnedOrphanMetadata(outPath, metadataPath) {
  if (await pathExists(outPath) || !await pathExists(metadataPath)) return;
  try {
    const metadata = JSON.parse(await readFile(metadataPath, 'utf8'));
    if (metadata?.schema === EDITABLE_PPT_METADATA_SCHEMA
      && metadata?.files?.length === 1
      && metadata.files[0]?.file === basename(outPath)) {
      await rm(metadataPath, { force: true });
    }
  } catch {
    // 非本工具或损坏 sidecar 保持不动，由 output_exists 明确阻止覆盖。
  }
}

/** 在进入任何凭据解析/付费调用前完成参考图路径与大小预检（loadReferences 复用其规则）。 */
async function validateReferencePaths(items, root) {
  for (const item of items) {
    if (typeof item !== 'string' || !item.trim()) return { code: 'reference_url_unsupported', message: '参考图必须是当前工作区内的本地图片路径' };
    if (/^[a-z]+:\/\//i.test(item)) return { code: 'reference_url_unsupported', message: '参考图必须是当前工作区内的本地图片，不接受 URL' };
    const path = resolve(root, item);
    if (!inside(root, path)) return { code: 'path_outside_workspace', message: '参考图必须位于当前工作区内' };
    if (!/\.(png|jpe?g|webp|gif)$/i.test(path)) return { code: 'unsupported_reference', message: '参考图仅支持 PNG、JPEG、WebP 或 GIF' };
  }
  return null;
}
