import { mkdir, readFile, stat, writeFile } from 'node:fs/promises';
import { extname, isAbsolute, join, relative, resolve } from 'node:path';
import { safeError } from './security/redact.js';

export const VISION_MODELS = Object.freeze(['qwen3.7-plus', 'qwen3.7-flash-2026-07-15']);
const ENDPOINT = 'https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions';
const MAX_IMAGE_BYTES = 20 * 1024 * 1024;
const MIME = new Map([['.png', 'image/png'], ['.jpg', 'image/jpeg'], ['.jpeg', 'image/jpeg'], ['.webp', 'image/webp'], ['.gif', 'image/gif']]);
const BROWSER_IMAGE_MIME = new Set(MIME.values());
export const MANUAL_VISION_LIMITS = Object.freeze({ maxImages: 4, maxImageBytes: MAX_IMAGE_BYTES, maxTotalBytes: 32 * 1024 * 1024 });
export const MANUAL_VISION_PROMPT = '请准确、简洁地描述这张图片的内容，提取用户提问时可能需要的文字、数据、结构、图表关系和重要细节。不要猜测图片中不可见的信息。';

export class VisionError extends Error {
  constructor(code, message, details = {}) {
    super(message);
    this.name = 'VisionError';
    this.code = code;
    this.details = details;
  }
}

function inside(root, candidate) {
  const rel = relative(root, candidate);
  return rel === '' || (!rel.startsWith('..') && !isAbsolute(rel));
}

async function imageSource(image, workspace) {
  if (typeof image !== 'string' || image.trim() === '') throw new VisionError('invalid_image', '图片路径或 URL 不能为空');
  if (/^https:\/\//i.test(image)) return image;
  if (/^https?:\/\//i.test(image)) throw new VisionError('invalid_url', '远程图片只允许 HTTPS URL');
  const root = resolve(workspace);
  const path = resolve(root, image);
  if (!inside(root, path)) throw new VisionError('path_outside_workspace', '本地图片必须位于当前工作区内');
  let info;
  try {
    info = await stat(path);
  } catch (error) {
    if (error?.code === 'ENOENT') throw new VisionError('file_not_found', '本地图片不存在');
    throw error;
  }
  if (!info.isFile()) throw new VisionError('not_a_file', '图片路径不是文件');
  if (info.size > MAX_IMAGE_BYTES) throw new VisionError('image_too_large', '本地图片超过 20 MB 上限');
  const mime = MIME.get(extname(path).toLowerCase());
  if (!mime) throw new VisionError('unsupported_image', '仅支持 PNG、JPEG、WebP 或 GIF');
  return `data:${mime};base64,${(await readFile(path)).toString('base64')}`;
}

function browserDraftSource({ mediaType, data } = {}) {
  if (!BROWSER_IMAGE_MIME.has(mediaType)) throw new VisionError('unsupported_image', '仅支持 PNG、JPEG、WebP 或 GIF');
  if (typeof data !== 'string' || data.length === 0) throw new VisionError('invalid_image_data', '图片数据不能为空');
  let bytes;
  try {
    bytes = Buffer.from(data, 'base64');
  } catch {
    throw new VisionError('invalid_image_data', '图片数据不是有效 Base64');
  }
  if (bytes.length === 0 || bytes.toString('base64') !== data) throw new VisionError('invalid_image_data', '图片数据不是规范 Base64');
  if (bytes.length > MAX_IMAGE_BYTES) throw new VisionError('image_too_large', '图片超过 20 MB 上限');
  return { source: `data:${mediaType};base64,${data}`, bytes: bytes.length };
}

function answerText(data) {
  const content = data?.choices?.[0]?.message?.content;
  if (typeof content === 'string' && content.trim()) return content;
  if (Array.isArray(content)) {
    const text = content.filter((item) => item?.type === 'text' && typeof item.text === 'string').map((item) => item.text).join('\n');
    if (text.trim()) return text;
  }
  throw new VisionError('invalid_response', '视觉供应商返回了无法识别的响应结构');
}

export class VisionService {
  constructor({ credentials, fetchImpl = globalThis.fetch, endpoint = ENDPOINT } = {}) {
    this.credentials = credentials;
    this.fetch = fetchImpl;
    this.endpoint = endpoint;
  }

  async analyze({ image, prompt = '请准确描述图片内容，并提取与数学建模或论文分析相关的信息。', workspace = process.cwd(), signal } = {}) {
    if (signal?.aborted) throw new VisionError('cancelled', '视觉分析已取消');
    const source = await imageSource(image, workspace);
    return await this.analyzeSource({ source, sourceType: source.startsWith('data:') ? 'local' : 'url', prompt, signal });
  }

  async analyzeDraft({ mediaType, data, prompt = MANUAL_VISION_PROMPT, signal } = {}) {
    if (signal?.aborted) throw new VisionError('cancelled', '视觉分析已取消');
    const { source } = browserDraftSource({ mediaType, data });
    return await this.analyzeSource({ source, sourceType: 'draft', prompt, signal });
  }

  async analyzeSource({ source, sourceType, prompt, signal }) {
    if (signal?.aborted) throw new VisionError('cancelled', '视觉分析已取消');
    const credential = await this.credentials.resolve('DASHSCOPE_API_KEY');
    if (!credential?.value) throw new VisionError('credential_missing', '尚未配置 DASHSCOPE_API_KEY');
    const failures = [];
    for (const model of VISION_MODELS) {
      if (signal?.aborted) throw new VisionError('cancelled', '视觉分析已取消');
      try {
        const response = await this.fetch(this.endpoint, {
          method: 'POST',
          headers: { 'content-type': 'application/json', authorization: `Bearer ${credential.value}` },
          body: JSON.stringify({
            model,
            messages: [{ role: 'user', content: [{ type: 'image_url', image_url: { url: source } }, { type: 'text', text: prompt }] }],
          }),
          signal,
        });
        if (!response.ok) throw new VisionError('provider_http_error', `视觉供应商请求失败（HTTP ${response.status}）`, { status: response.status });
        const data = await response.json();
        return { schema: 'dsh.mathmodel.vision/v1', model, text: answerText(data), sourceType, warnings: failures };
      } catch (error) {
        if (signal?.aborted || error?.name === 'AbortError') throw new VisionError('cancelled', '视觉分析已取消');
        const sanitized = safeError(error, [credential.value]);
        failures.push({ model, code: error?.code ?? 'provider_error', message: sanitized.message });
      }
    }
    throw new VisionError('all_models_failed', '主模型与回退模型均失败', { failures });
  }
}

function safeDraftName(name, index) {
  const normalized = typeof name === 'string' ? name.replace(/[\u0000-\u001f\u007f]/g, ' ').trim().slice(0, 160) : '';
  return normalized || `图片 ${index + 1}`;
}

const EXT_BY_MIME = new Map([['image/png', 'png'], ['image/jpeg', 'jpg'], ['image/webp', 'webp'], ['image/gif', 'gif']]);

/** 仅由浏览器的明确手动动作调用；把草稿图片保存到工作区，供模型经 vision_analyze 查看原图。 */
export class ManualVisionService {
  constructor({ now = () => Date.now() } = {}) {
    this.now = now;
  }

  async stageDraftImages({ images, workspace } = {}) {
    if (!Array.isArray(images) || images.length === 0) throw new VisionError('images_required', '请先添加至少一张图片');
    if (images.length > MANUAL_VISION_LIMITS.maxImages) throw new VisionError('too_many_images', `一次最多附图 ${MANUAL_VISION_LIMITS.maxImages} 张图片`);
    if (typeof workspace !== 'string' || workspace.trim() === '') throw new VisionError('workspace_required', '当前会话未绑定工作区，无法附图');
    const root = resolve(workspace);
    const info = await stat(root).catch(() => null);
    if (!info?.isDirectory()) throw new VisionError('workspace_not_found', '会话工作区不存在，无法附图');
    let totalBytes = 0;
    const normalized = images.map((image, index) => {
      const draft = browserDraftSource(image);
      totalBytes += draft.bytes;
      return { bytes: Buffer.from(image.data, 'base64'), ext: EXT_BY_MIME.get(image.mediaType), name: safeDraftName(image.name, index) };
    });
    if (totalBytes > MANUAL_VISION_LIMITS.maxTotalBytes) throw new VisionError('images_too_large', '图片总大小超过 32 MB 上限');
    const dir = join(root, 'uploads');
    await mkdir(dir, { recursive: true });
    const stamp = this.now();
    const files = [];
    for (const [index, image] of normalized.entries()) {
      const filename = `img-${stamp}-${index + 1}.${image.ext}`;
      await writeFile(join(dir, filename), image.bytes, { flag: 'wx' });
      files.push({ name: image.name, path: `uploads/${filename}`, bytes: image.bytes.length });
    }
    return { schema: 'dsh.mathmodel.manual-vision-stage/v1', files };
  }
}
