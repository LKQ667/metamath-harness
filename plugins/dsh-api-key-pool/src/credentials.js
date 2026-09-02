import { createHash, randomUUID } from 'node:crypto';
import { credentialKey, credentialKeyScope } from '@deepseek-ai/dsh-credentials';

/**
 * 凭据 Facade：完整 Key 只存 credentials 记录（scope `dsh-api-key-pool`），
 * settings 只保存 keyId。所有对外的列表/描述输出一律脱敏 + 指纹，绝不返回完整 Key。
 */

export const CREDENTIAL_SCOPE = 'dsh-api-key-pool';

/** 与 dsh-llm `assertUsableApiKey` 的可打印 ASCII 规则保持一致（trim 后非空、无控制字符）。 */
const LEGAL_API_KEY = /^[\x21-\x7E]+$/;

/** keyId 形如 `k-<uuid>`，同时满足 credentials 键段文法（^[a-z][a-z0-9-]*$）。 */
export const KEY_ID_PATTERN = /^k-[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/;

export class PoolCredentialError extends Error {
  constructor(message, code) {
    super(message);
    this.name = 'PoolCredentialError';
    this.code = code;
  }
}

/** sha256 指纹（前 16 hex），用于重复检测与健康展示，不可逆推 Key。 */
export function fingerprintOf(value) {
  return createHash('sha256').update(value, 'utf8').digest('hex').slice(0, 16);
}

/** 脱敏显示：长 Key 保留首 3 + 尾 4，短 Key 一律 `…`。 */
export function maskKey(value) {
  if (typeof value !== 'string' || value.length === 0) return '…';
  if (value.length <= 12) return '…';
  return `${value.slice(0, 3)}…${value.slice(-4)}`;
}

/** 校验并规范化一个 Key：trim、非空、可打印 ASCII；非法即抛错（fail-closed）。 */
export function assertUsablePoolKey(raw) {
  if (typeof raw !== 'string') {
    throw new PoolCredentialError('API Key 必须是字符串', 'INVALID_KEY_VALUE');
  }
  const value = raw.trim();
  if (value.length === 0) {
    throw new PoolCredentialError('API Key 不能为空或纯空白', 'INVALID_KEY_VALUE');
  }
  if (!LEGAL_API_KEY.test(value)) {
    throw new PoolCredentialError('API Key 含有 HTTP 头无法携带的字符（仅允许可打印 ASCII，不含空格）', 'INVALID_KEY_VALUE');
  }
  return value;
}

function newKeyId() {
  return `k-${randomUUID()}`;
}

/**
 * @param {import('@deepseek-ai/dsh-credentials').CredentialProvider} credentials ctx.credentials 服务
 */
export class CredentialFacade {
  constructor(credentials) {
    if (credentials === undefined || credentials === null) {
      throw new PoolCredentialError('CredentialFacade 需要 ctx.credentials 服务', 'NO_CREDENTIALS_SERVICE');
    }
    this.credentials = credentials;
  }

  /** 该 scope 下全部记录的 keyId 列表。 */
  async listKeyIds() {
    const records = await this.credentials.listRecords();
    return records
      .map((entry) => entry.key)
      .filter((key) => credentialKeyScope(key) === CREDENTIAL_SCOPE)
      .map((key) => key.slice(key.indexOf('/') + 1));
  }

  /** 读取某个 keyId 的完整 Key（仅内部供适配器逐流解析使用）。空值视为不存在。 */
  async resolveValue(keyId) {
    if (!KEY_ID_PATTERN.test(String(keyId ?? ''))) return undefined;
    const record = await this.credentials.readRecord(credentialKey(CREDENTIAL_SCOPE, keyId));
    if (record === undefined || record === null) return undefined;
    if (record.kind !== 'api-key') return undefined;
    const value = typeof record.key === 'string' ? record.key.trim() : '';
    return value.length > 0 ? value : undefined;
  }

  /**
   * 新增一个 Key：字符合法性校验 + 重复指纹检测（同 scope 全量比对），
   * 通过 modifyRecord 原子写入 `{kind:'api-key', key}`。
   * @returns {{ keyId: string, fingerprint: string, masked: string }}
   */
  async addKey(raw) {
    const value = assertUsablePoolKey(raw);
    const fingerprint = fingerprintOf(value);
    const existing = await this.describeKeys();
    if (existing.some((entry) => entry.fingerprint === fingerprint)) {
      throw new PoolCredentialError('该 API Key 已存在于号池（指纹重复）', 'DUPLICATE_KEY');
    }
    let keyId = newKeyId();
    const taken = new Set(existing.map((entry) => entry.keyId));
    while (taken.has(keyId)) keyId = newKeyId();
    await this.credentials.modifyRecord(credentialKey(CREDENTIAL_SCOPE, keyId), () => ({
      kind: 'api-key',
      key: value,
    }));
    return { keyId, fingerprint, masked: maskKey(value) };
  }

  /**
   * 删除某个 keyId 的记录；不存在（或 id 非法）时返回 false，不抛错。
   * @returns {boolean} 是否真正删除
   */
  async removeKey(keyId) {
    if (!KEY_ID_PATTERN.test(String(keyId ?? ''))) return false;
    const key = credentialKey(CREDENTIAL_SCOPE, keyId);
    const record = await this.credentials.readRecord(key);
    if (record === undefined || record === null) return false;
    await this.credentials.deleteRecord(key);
    return true;
  }

  /** 脱敏列表：[{ keyId, fingerprint, masked }]，不含完整 Key。 */
  async describeKeys() {
    const keyIds = await this.listKeyIds();
    const entries = [];
    for (const keyId of keyIds) {
      const record = await this.credentials.readRecord(credentialKey(CREDENTIAL_SCOPE, keyId));
      const value = record?.kind === 'api-key' && typeof record.key === 'string' ? record.key : '';
      entries.push({
        keyId,
        fingerprint: fingerprintOf(value),
        masked: maskKey(value),
      });
    }
    return entries;
  }

  /** 孤儿报告：scope 下存在、但未被任何池的 keyIds 引用的记录。 */
  async orphanKeyIds(referencedKeyIds) {
    const referenced = new Set((referencedKeyIds ?? []).map(String));
    const all = await this.listKeyIds();
    return all.filter((keyId) => !referenced.has(keyId));
  }
}
