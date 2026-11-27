import { createRequire } from 'node:module';
import { applyOpenCodeSessionHeader, assertCompatiblePiAiVersion } from './session-header.js';

export const name = 'opencode-session';
export const inject = ['llm'];

export function apply(ctx) {
  const require = createRequire(ctx?.baseUrl ?? import.meta.url);
  let version = null;
  try {
    version = require('@deepseek-ai/dsh-llm-pi-ai/package.json')?.version ?? null;
  } catch {
    try {
      version = createRequire(import.meta.url)('@deepseek-ai/dsh-llm-pi-ai/package.json')?.version ?? null;
    } catch {
      version = null;
    }
  }
  assertCompatiblePiAiVersion(version);
  ctx.on('llm-pi-ai/request-headers', (request, headers, next) => {
    const resolved = next();
    return applyOpenCodeSessionHeader(request, resolved);
  });
  ctx.logger.info('OpenCode 动态会话请求头已启用（官方 llm-pi-ai/request-headers 钩子，适配器 %s）', version);
}
