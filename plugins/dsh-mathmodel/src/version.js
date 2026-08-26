import { createRequire } from 'node:module';

export const SUPPORTED_DSH_VERSION = '0.1.1-rc.2';

/**
 * 从插件所在的 Node 解析链读取官方 Harness 版本。
 * 只读 package.json，不修改官方包。
 */
export function detectHarnessVersion(requireFrom = import.meta.url) {
  const require = createRequire(requireFrom);
  try {
    const manifest = require('@deepseek-ai/dsh/package.json');
    return typeof manifest?.version === 'string' ? manifest.version : null;
  } catch {
    return null;
  }
}

/** 对未知或不匹配版本采用失败关闭，避免开发者预览 API 静默漂移。 */
export function assertCompatibleHarnessVersion(version = detectHarnessVersion()) {
  if (version !== SUPPORTED_DSH_VERSION) {
    const found = version ?? '未检测到';
    throw new Error(
      `[dsh-mathmodel] DeepSeek Harness 版本不兼容：需要 ${SUPPORTED_DSH_VERSION}，当前 ${found}。` +
      '请使用匹配版本，或先升级 dsh-mathmodel 后再启用。',
    );
  }
  return version;
}
