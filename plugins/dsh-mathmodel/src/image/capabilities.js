import { fail } from '../security/image-connections.js';

/**
 * 可编辑 PPT 专用能力矩阵：按协议给出 generate/edit/multiReference/mask/quality 支持，
 * 并以三层识别（模板、验证协议、直连端点）把 Codex 后端标记为 forbidden。
 * 本模块只处理非敏感的连接描述字段，绝不触碰凭据值。
 */

export const CODEX_TEMPLATE_ID = 'codex-subscription';
export const CODEX_PROTOCOL_ID = 'codex-images';
export const CODEX_BACKEND_FORBIDDEN_CODE = 'codex_backend_forbidden';

const ADAPTER_CAPABILITIES = Object.freeze({
  'openai-images': Object.freeze({ generate: true, edit: true, multiReference: true, mask: true, quality: true }),
  'dashscope-async': Object.freeze({ generate: true, edit: true, multiReference: true, mask: false, quality: false }),
  'gemini-content': Object.freeze({ generate: true, edit: true, multiReference: true, mask: false, quality: false }),
  'sub2api-async-images': Object.freeze({ generate: true, edit: true, multiReference: true, mask: false, quality: false }),
  'openai-chat-image': Object.freeze({ generate: true, edit: true, multiReference: true, mask: false, quality: false }),
  'grok-images': Object.freeze({ generate: true, edit: false, multiReference: false, mask: false, quality: false }),
});

const FORBIDDEN_CAPABILITIES = Object.freeze({ forbidden: true, generate: false, edit: false, multiReference: false, mask: false, quality: false });
const UNKNOWN_CAPABILITIES = Object.freeze({ generate: false, edit: false, multiReference: false, mask: false, quality: false });

/** 协议 → 能力矩阵；codex-images 标记为 forbidden，而不是普通“不支持编辑”。 */
export function capabilitiesForProtocol(protocol) {
  if (protocol === CODEX_PROTOCOL_ID) return FORBIDDEN_CAPABILITIES;
  return ADAPTER_CAPABILITIES[protocol] ?? UNKNOWN_CAPABILITIES;
}

/** 第三层识别：配置的直接端点主机为 chatgpt.com 且路径属于 Codex Images。 */
export function isCodexImagesEndpoint(baseUrl) {
  if (typeof baseUrl !== 'string' || !baseUrl) return false;
  try {
    const url = new URL(baseUrl);
    const host = url.hostname.toLowerCase();
    if (host !== 'chatgpt.com' && !host.endsWith('.chatgpt.com')) return false;
    const path = url.pathname.toLowerCase();
    return path.includes('/codex') || path.includes('/backend-api/codex');
  } catch {
    return false;
  }
}

/** 三层任一命中即视为 Codex 后端（§5.4）。 */
export function isCodexConnection(connection) {
  if (!connection || typeof connection !== 'object') return false;
  if (connection.template === CODEX_TEMPLATE_ID) return true;
  if (connection.adapter === CODEX_PROTOCOL_ID) return true;
  if (connection.verification?.protocol === CODEX_PROTOCOL_ID) return true;
  return isCodexImagesEndpoint(connection.baseUrl);
}

/** 在任何凭据解析与付费调用前失败关闭；错误码稳定。 */
export function assertNotCodex(connection) {
  if (isCodexConnection(connection)) {
    throw fail(CODEX_BACKEND_FORBIDDEN_CODE, '图片转可编辑 PPT 模式禁止使用 Codex 订阅生图；请到“设置 → 模型 → 生图模型”把当前生图连接切换为非 Codex 连接');
  }
}

/** 参数需求 → 协议能力；不支持即 capability_unsupported，绝不静默忽略。 */
export function requireCapabilities({ protocol, operation, multiReference = false, mask = false, quality = false, size = false }) {
  const capabilities = capabilitiesForProtocol(protocol);
  if (capabilities.forbidden === true) {
    throw fail(CODEX_BACKEND_FORBIDDEN_CODE, `协议 ${protocol} 属于 Codex 后端，图片转可编辑 PPT 模式禁止使用`);
  }
  if (operation === 'generate' && !capabilities.generate) throw fail('capability_unsupported', `协议 ${protocol} 不支持生成`);
  if (operation === 'edit' && !capabilities.edit) throw fail('capability_unsupported', `协议 ${protocol} 不支持参考图编辑；请切换支持编辑的连接，不得降级为生成`);
  if (multiReference && !capabilities.multiReference) throw fail('capability_unsupported', `协议 ${protocol} 不支持多张参考图`);
  if (mask && !capabilities.mask) throw fail('capability_unsupported', `协议 ${protocol} 不支持 mask 编辑`);
  if (quality && !capabilities.quality) throw fail('capability_unsupported', `协议 ${protocol} 不支持 quality 参数`);
  if (size && !capabilities.generate) throw fail('capability_unsupported', `协议 ${protocol} 不支持 size 参数`);
  return capabilities;
}
