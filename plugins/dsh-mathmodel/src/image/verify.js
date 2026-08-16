import { createHash } from 'node:crypto';
import { safeError } from '../security/redact.js';
import { fail } from '../security/image-connections.js';
import { ADAPTER_BY_ID } from './adapters.js';
import { decodeImageAsset, downloadImage } from './assets.js';

const MINIMAL_PROMPT = '1px red dot';

function sha256(value) {
  return createHash('sha256').update(String(value)).digest('hex');
}

/** 验证身份：绑定模板、规范化 Base URL、模型与不可逆 Key 指纹。 */
export function verificationIdentity(connection, keyValue) {
  return Object.freeze({
    template: connection.template,
    baseUrlFingerprint: sha256(connection.baseUrl),
    model: connection.model,
    keyFingerprint: sha256(keyValue),
  });
}

export function classifyVerifyError(error) {
  const status = error?.status;
  if (status === 401 || status === 403) return fail('auth_rejected', `接口拒绝了凭据（HTTP ${status}）；请检查 API Key 与网关配置`);
  if (status === 429) return fail('rate_limited', '接口触发限流（HTTP 429）；请稍后重试');
  if (status === 405) return fail('endpoint_mismatch', '接口不支持该端点（HTTP 405）');
  if (status === 422) return fail('endpoint_mismatch', '接口返回参数错误（HTTP 422），可能是端点协议不匹配');
  if (status === 404) {
    if (error?.providerCode === 'model_not_found' || /model/i.test(error?.message ?? '')) {
      return fail('model_not_found', '接口找不到该模型（HTTP 404）；请检查模型名');
    }
    return fail('endpoint_mismatch', '接口端点不存在（HTTP 404）');
  }
  if (error?.code === 'endpoint_mismatch') return error;
  if (error?.code === 'auth_rejected' || error?.code === 'rate_limited' || error?.code === 'model_not_found') return error;
  if (error?.code && typeof error.code === 'string' && typeof error.message === 'string') return error;
  const cleaned = safeError(error);
  return fail('provider_error', cleaned.message);
}

/** 仅通用 OpenAI 兼容模板在明确端点不匹配的测试阶段允许改试 openai-chat-image。 */
export function shouldTryChatImage(connection, protocol, classified) {
  return connection.template === 'openai-compatible' && protocol === 'openai-images' && classified?.code === 'endpoint_mismatch';
}

/**
 * 无落盘的最小真实验证：发送一次最小生图请求并校验真实图片；成功返回
 * 协议与身份记录，失败返回分类错误。绝不写入工作区、不挂附件、不进对话。
 */
export async function verifyConnection({
  connection, credential, adapters = ADAPTER_BY_ID, fetchImpl, signal, sleep,
  now = () => new Date().toISOString(),
  request = { prompt: MINIMAL_PROMPT, count: 1, authorizePaid: true },
} = {}) {
  const identity = verificationIdentity(connection, credential);
  const attempt = async (adapterId) => {
    const adapter = adapters[adapterId];
    if (typeof adapter !== 'function') throw fail('unknown_adapter', `未知适配器：${adapterId}`);
    const assets = await adapter({
      endpoint: connection.baseUrl,
      model: connection.model,
      credential,
      request,
      references: [],
      fetchImpl,
      signal,
      sleep,
    });
    if (!Array.isArray(assets) || assets.length === 0) throw fail('no_image_asset', '测试未返回任何图片');
    const image = assets[0].kind === 'url' ? await downloadImage(fetchImpl, assets[0].url, signal) : decodeImageAsset(assets[0]);
    if (!image?.bytes?.length) throw fail('no_image_asset', '测试未返回可解析的图片');
    return image;
  };
  try {
    let protocol = connection.adapter;
    try {
      await attempt(protocol);
    } catch (error) {
      const classified = classifyVerifyError(error);
      if (shouldTryChatImage(connection, protocol, classified)) {
        protocol = 'openai-chat-image';
        await attempt(protocol);
      } else {
        throw classified;
      }
    }
    return { ok: true, protocol, identity, verifiedAt: now() };
  } catch (error) {
    if (signal?.aborted || error?.name === 'AbortError') throw fail('cancelled', '验证已取消');
    return { ok: false, error: classifyVerifyError(error), identity, verifiedAt: now() };
  }
}
