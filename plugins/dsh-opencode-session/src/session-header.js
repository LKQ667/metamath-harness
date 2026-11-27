export const SUPPORTED_VERSIONS = ['0.2.2-rc.5'];

export function isOpenCodeRequest(request) {
  const provider = typeof request?.provider === 'string' ? request.provider : '';
  if (/^opencode(?:-|$)/.test(provider)) return true;
  const baseURL = typeof request?.baseURL === 'string' ? request.baseURL : '';
  if (!baseURL) return false;
  try {
    return new URL(baseURL).hostname === 'opencode.ai';
  } catch {
    return false;
  }
}

/**
 * 为 OpenCode 请求写入动态 `x-opencode-session` 请求头（DSH 0.2.2+ 官方
 * `llm-pi-ai/request-headers` waterfall 契约）。
 * 缺失或非法 sessionId 直接抛错失败关闭，绝不生成随机值或全局固定值。
 */
export function applyOpenCodeSessionHeader(request, headers) {
  if (!isOpenCodeRequest(request)) return headers;
  const id = request?.sessionId == null ? '' : String(request.sessionId);
  if (!id.trim() || /[^\x21-\x7e]/.test(id)) {
    throw new Error('OpenCode 请求缺少有效会话 ID；拒绝使用全局固定值或临时随机值');
  }
  const nextHeaders = headers instanceof Headers ? headers : new Headers(headers ?? {});
  nextHeaders.set('x-opencode-session', id);
  return nextHeaders;
}

export function assertCompatiblePiAiVersion(version) {
  if (!SUPPORTED_VERSIONS.includes(version)) {
    throw new Error(`opencode-session 兼容门失败：需要 ${SUPPORTED_VERSIONS.join(' 或 ')}，当前 ${version ?? '未知'}；当前修复未安装`);
  }
  return version;
}
