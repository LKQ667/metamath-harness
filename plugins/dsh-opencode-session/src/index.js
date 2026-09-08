import { createRequire } from 'node:module';
import { PiAiAdapter } from '@deepseek-ai/dsh-llm-pi-ai';
import { installSessionHeader } from './session-header.js';

export const name = 'opencode-session';
export const inject = ['llm'];
export function apply(ctx) {
  const require = createRequire(import.meta.url);
  const { version } = require('@deepseek-ai/dsh-llm-pi-ai/package.json');
  const dispose = installSessionHeader(PiAiAdapter, version);
  ctx.on('dispose', dispose);
  ctx.logger.info('OpenCode 动态会话请求头已启用（适配器 %s；版本与函数指纹均通过）', version);
}
