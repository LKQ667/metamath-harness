import { createHash } from 'node:crypto';

// 私有适配点必须同时通过版本及函数指纹检查，升级后禁止盲目套用。
export const SUPPORTED_VERSION = '0.1.5-rc.2';
export const SUPPORTED_HASH = '2bac107cc0f85b31ff9f5f05d975775909101fd284218a711d7bc741811addca';
const installed = new WeakMap();

export function withSessionHeader(options, snapshot) {
  const profile = snapshot.profiles.get(options.provider);
  const model = snapshot.models.getModel(options.provider, options.model);
  let openCodeHost = false;
  try { openCodeHost = new URL(model?.baseUrl ?? profile?.baseURL).hostname === 'opencode.ai'; } catch { /* 内置路由用名称识别 */ }
  if (!/^opencode(?:-|$)/.test(options.provider) && !openCodeHost) return snapshot;
  if (!profile) return snapshot; // 保留官方 NO_ADAPTER 行为。
  const id = options.sessionId == null ? '' : String(options.sessionId);
  if (!id.trim() || /[^\x21-\x7e]/.test(id)) {
    throw new Error('OpenCode 请求缺少有效会话 ID；拒绝使用全局固定值或临时随机值');
  }
  const headers = Object.fromEntries(Object.entries(profile.headers ?? {})
    .filter(([key]) => key.toLowerCase() !== 'x-opencode-session'));
  headers['x-opencode-session'] = id;
  const profiles = new Map(snapshot.profiles);
  profiles.set(options.provider, { ...profile, headers });
  return { ...snapshot, profiles }; // 保留已冻结的模型、凭据路径和其他会话快照。
}

export function installSessionHeader(Adapter, version) {
  const prototype = Adapter.prototype;
  if (installed.has(prototype)) throw new Error('opencode-session 不允许重复挂载');
  const original = prototype.streamWithSnapshot;
  const hash = typeof original === 'function'
    ? createHash('sha256').update(original.toString()).digest('hex') : '';
  if (version !== SUPPORTED_VERSION || hash !== SUPPORTED_HASH) {
    throw new Error(`opencode-session 兼容门失败：${version}；需重新验证适配器，当前修复未安装`);
  }
  function wrapped(options, snapshot) {
    return original.call(this, options, withSessionHeader(options, snapshot));
  }
  prototype.streamWithSnapshot = wrapped;
  installed.set(prototype, wrapped);
  return () => {
    if (prototype.streamWithSnapshot === wrapped) prototype.streamWithSnapshot = original;
    installed.delete(prototype);
  };
}
