import { extname } from 'node:path';

export const MAX_DOWNLOAD_BYTES = 25 * 1024 * 1024;
export const MIME_EXT = new Map([['image/png', 'png'], ['image/jpeg', 'jpg'], ['image/webp', 'webp'], ['image/gif', 'gif']]);

export function requestError(code, message) {
  const error = new TypeError(message);
  error.code = code;
  return error;
}

export function mimeForPath(path) {
  const ext = extname(path).toLowerCase();
  return new Map([['.png', 'image/png'], ['.jpg', 'image/jpeg'], ['.jpeg', 'image/jpeg'], ['.webp', 'image/webp'], ['.gif', 'image/gif']]).get(ext);
}

/** 魔数嗅探：以字节本身为唯一事实源，识别受支持的四种图片；无法识别时返回 null。 */
export function sniffImageMime(bytes) {
  if (bytes.length >= 8 && bytes[0] === 0x89 && bytes[1] === 0x50 && bytes[2] === 0x4e && bytes[3] === 0x47 && bytes[4] === 0x0d && bytes[5] === 0x0a && bytes[6] === 0x1a && bytes[7] === 0x0a) return 'image/png';
  if (bytes.length >= 3 && bytes[0] === 0xff && bytes[1] === 0xd8 && bytes[2] === 0xff) return 'image/jpeg';
  if (bytes.length >= 12 && bytes.toString('latin1', 0, 4) === 'RIFF' && bytes.toString('latin1', 8, 12) === 'WEBP') return 'image/webp';
  if (bytes.length >= 6 && ['GIF87a', 'GIF89a'].includes(bytes.toString('latin1', 0, 6))) return 'image/gif';
  return null;
}

export async function downloadImage(fetchImpl, url, signal, redirects = 0) {
  const parsed = new URL(url);
  const local = ['localhost', '127.0.0.1', '::1'].includes(parsed.hostname);
  if (parsed.protocol !== 'https:' && !(local && parsed.protocol === 'http:')) throw requestError('unsafe_download_url', '生成图下载地址必须使用 HTTPS');
  if (redirects > 3) throw requestError('too_many_redirects', '生成图下载重定向超过 3 次');
  const response = await fetchImpl(url, { signal, redirect: 'manual' });
  if (response.status >= 300 && response.status < 400) {
    const location = response.headers.get('location');
    if (!location) throw requestError('invalid_redirect', '下载重定向缺少 Location');
    return await downloadImage(fetchImpl, new URL(location, url).toString(), signal, redirects + 1);
  }
  if (!response.ok) throw requestError('download_failed', `生成图下载失败（HTTP ${response.status}）`);
  const mime = (response.headers.get('content-type') ?? '').split(';')[0].toLowerCase();
  if (!MIME_EXT.has(mime)) throw requestError('invalid_content_type', '生成图响应不是受支持的图片类型');
  const declared = Number(response.headers.get('content-length') ?? 0);
  if (declared > MAX_DOWNLOAD_BYTES) throw requestError('download_too_large', '生成图超过 25 MB');
  const bytes = Buffer.from(await response.arrayBuffer());
  if (bytes.length > MAX_DOWNLOAD_BYTES) throw requestError('download_too_large', '生成图超过 25 MB');
  const sniffed = sniffImageMime(bytes);
  if (!sniffed) throw requestError('invalid_image_bytes', '生成图下载内容不是受支持的 PNG、JPEG、WebP 或 GIF 图片');
  return { bytes, mime: sniffed };
}

export function decodeImageAsset(asset) {
  const bytes = Buffer.from(asset.data, 'base64');
  if (bytes.length === 0 || bytes.length > MAX_DOWNLOAD_BYTES) throw requestError('invalid_base64_image', '供应商返回的 base64 图片无效或过大');
  const sniffed = sniffImageMime(bytes);
  if (!sniffed) throw requestError('invalid_image_bytes', '供应商返回的数据不是受支持的 PNG、JPEG、WebP 或 GIF 图片');
  return { bytes, mime: sniffed };
}
