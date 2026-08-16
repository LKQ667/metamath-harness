import { isValidConnectionId } from './image-connections.js';
import { safeError } from './redact.js';

const REF_PATTERN = /^[A-Za-z_][A-Za-z0-9_]*$/;

/**
 * 只允许由已存在的 connectionId 派生 `MATHMODEL_IMAGE_<ID>` 引用；
 * 浏览器既不能传入引用名，也不能通过此存储读写任意凭据。
 */
export class ImageConnectionCredentialStore {
  constructor(provider) {
    this.provider = provider;
  }

  refFor(id) {
    if (!isValidConnectionId(id)) throw new TypeError(`不允许为无效连接派生凭据引用：${id}`);
    const ref = `MATHMODEL_IMAGE_${id.toUpperCase().replaceAll('-', '_')}`;
    if (!REF_PATTERN.test(ref)) throw new TypeError(`派生凭据引用无效：${ref}`);
    return ref;
  }

  assertConnection(id) {
    if (!isValidConnectionId(id)) throw new TypeError(`未知生图连接：${id}`);
  }

  async describe(id) {
    this.assertConnection(id);
    const ref = this.refFor(id);
    const info = await this.provider.describe(ref);
    return Object.freeze({
      ref,
      configured: info.configured === true,
      writable: info.writable === true,
      ...(typeof info.source === 'string' ? { source: info.source } : {}),
    });
  }

  async set(id, value) {
    this.assertConnection(id);
    if (typeof value !== 'string' || value.trim() === '') throw new TypeError('凭据值不能为空');
    const ref = this.refFor(id);
    try {
      await this.provider.set(ref, value);
    } catch (error) {
      throw safeError(error, [value]);
    }
    return await this.describe(id);
  }

  async clear(id) {
    this.assertConnection(id);
    await this.provider.unset(this.refFor(id));
    return await this.describe(id);
  }

  async resolve(id) {
    this.assertConnection(id);
    const ref = this.refFor(id);
    const info = await this.provider.resolve(ref);
    return {
      ref,
      value: typeof info?.value === 'string' ? info.value : '',
      source: typeof info?.source === 'string' ? info.source : 'managed',
    };
  }
}
