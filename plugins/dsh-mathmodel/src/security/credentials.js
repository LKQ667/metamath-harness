import { safeError } from './redact.js';

export const CREDENTIAL_ALLOWLIST = Object.freeze([
  'DASHSCOPE_API_KEY',
  'OPENAI_API_KEY',
  'GEMINI_API_KEY',
  'CUSTOM_IMAGE_API_KEY',
]);
const ALLOWED = new Set(CREDENTIAL_ALLOWLIST);

function assertRef(ref) {
  if (!ALLOWED.has(ref)) throw new TypeError(`不允许管理凭据引用：${ref}`);
  return ref;
}

function publicInfo(ref, info) {
  return Object.freeze({
    ref,
    configured: info.configured === true,
    writable: info.writable === true,
    ...(typeof info.source === 'string' ? { source: info.source } : {}),
  });
}

export class CredentialFacade {
  constructor(provider) {
    this.provider = provider;
  }

  async describe(ref) {
    assertRef(ref);
    return publicInfo(ref, await this.provider.describe(ref));
  }

  async describeAll() {
    return await Promise.all(CREDENTIAL_ALLOWLIST.map((ref) => this.describe(ref)));
  }

  async set(ref, value) {
    assertRef(ref);
    if (typeof value !== 'string' || value.trim() === '') throw new TypeError('凭据值不能为空');
    try {
      await this.provider.set(ref, value);
      return await this.describe(ref);
    } catch (error) {
      throw safeError(error, [value]);
    }
  }

  async unset(ref) {
    assertRef(ref);
    await this.provider.unset(ref);
    return await this.describe(ref);
  }
}
