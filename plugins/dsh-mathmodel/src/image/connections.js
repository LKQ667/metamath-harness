import { safeError } from '../security/redact.js';
import {
  IMAGE_CONNECTIONS_SCHEMA_TAG, MAX_CONNECTIONS, capabilityOf, fail, generateConnectionId,
  isValidConnectionId, migrateFromV1, validateConnectionDraft, validateImageConnections,
} from '../security/image-connections.js';
import { describeCodexCredential, resolveCodexSession } from './codex-auth.js';
import { describeGrokCredential, resolveGrokSession } from './grok-auth.js';
import { verifyConnection } from './verify.js';
import { assertNotCodex, capabilitiesForProtocol } from './capabilities.js';

const LEGACY_CREDENTIAL_REFS = new Set(['DASHSCOPE_API_KEY', 'OPENAI_API_KEY', 'GEMINI_API_KEY', 'CUSTOM_IMAGE_API_KEY']);
const CODEX_TEMPLATE_ID = 'codex-subscription';
const GROK_TEMPLATE_ID = 'grok-subscription';

function withoutVerification(connection) {
  const { verification: _ignored, ...rest } = connection;
  return rest;
}

function parseModels(payload) {
  if (!Array.isArray(payload?.data)) throw fail('invalid_models_response', '模型列表接口未返回 data 数组；请手动填写模型');
  const seen = new Set();
  const models = [];
  for (const entry of payload.data) {
    const id = typeof entry?.id === 'string' ? entry.id.trim() : '';
    if (!id || seen.has(id)) continue;
    seen.add(id);
    const name = typeof entry?.name === 'string' && entry.name.trim() ? entry.name.trim() : undefined;
    models.push(Object.freeze({ id, ...(name ? { name } : {}) }));
  }
  return Object.freeze(models);
}

function summaryFor(connection, credential, verification) {
  return Object.freeze({
    id: connection.id,
    name: connection.name,
    template: connection.template,
    adapter: connection.adapter,
    model: connection.model,
    baseUrl: connection.baseUrl,
    credentialRef: connection.credentialRef,
    createdAt: connection.createdAt,
    updatedAt: connection.updatedAt,
    legacyProvider: connection.legacyProvider,
    capability: capabilityOf(connection, credential.configured),
    credential: Object.freeze({
      configured: credential.configured,
      writable: credential.writable,
      ...(typeof credential.source === 'string' ? { source: credential.source } : {}),
    }),
    ...(verification ? Object.freeze({ verification: {
      status: verification.status,
      protocol: verification.protocol,
      model: verification.model,
      verifiedAt: verification.verifiedAt,
      ...(verification.message ? { message: verification.message } : {}),
    } }) : {}),
  });
}

/**
 * 生图连接服务：迁移、连接生命周期、动态凭据、模型发现、能力验证与当前连接切换。
 * 所有 Remote 错误经脱敏；浏览器只接收脱敏摘要。
 */
export class ImageConnectionService {
  constructor({ settings, legacySettings, credentialStore, credentialProvider, hasV2UserSection, fetchImpl = globalThis.fetch, now = () => new Date().toISOString(), sleep, subscriptionSessions } = {}) {
    this.settings = settings;
    this.legacySettings = legacySettings;
    this.credentialStore = credentialStore;
    this.credentialProvider = credentialProvider;
    this.hasV2UserSection = hasV2UserSection ?? (() => true);
    this.fetch = fetchImpl;
    this.now = now;
    this.sleep = sleep;
    this.subscriptionSessions = subscriptionSessions;
  }

  value() {
    return validateImageConnections(this.settings.get());
  }

  /** v1→v2 一次性迁移：仅在 v2 用户区尚未写入时执行；写前校验、失败不覆盖 v1。 */
  async ensureMigrated() {
    const current = this.settings.get();
    if (current?.schema === IMAGE_CONNECTIONS_SCHEMA_TAG && this.hasV2UserSection()) return current;
    let v1 = {};
    try { v1 = this.legacySettings?.get?.() ?? {}; } catch { v1 = {}; }
    const states = {};
    for (const ref of LEGACY_CREDENTIAL_REFS) {
      try { states[ref] = (await this.credentialProvider.describe(ref))?.configured === true; } catch { states[ref] = false; }
    }
    const migrated = migrateFromV1(v1, {
      now: this.now,
      isConfigured: (ref) => states[ref] === true,
    });
    await this.settings.replace(migrated);
    return this.value();
  }

  async requireConnection(id) {
    const value = await this.ensureMigrated();
    if (!isValidConnectionId(id)) throw fail('invalid_connection_id', '连接 ID 无效');
    const connection = value.connections.find((item) => item.id === id);
    if (!connection) throw fail('connection_not_found', `生图连接不存在：${id}`);
    return connection;
  }

  async describeCredential(connection) {
    if (connection.template === CODEX_TEMPLATE_ID) return await describeCodexCredential(this.subscriptionSessions);
    if (connection.template === GROK_TEMPLATE_ID) return await describeGrokCredential(this.subscriptionSessions);
    if (LEGACY_CREDENTIAL_REFS.has(connection.credentialRef)) {
      const info = await this.credentialProvider.describe(connection.credentialRef);
      return Object.freeze({
        ref: connection.credentialRef,
        configured: info?.configured === true,
        writable: info?.writable === true,
        ...(typeof info?.source === 'string' ? { source: info.source } : {}),
      });
    }
    return await this.credentialStore.describe(connection.id);
  }

  async resolveCredential(connection) {
    if (connection.template === CODEX_TEMPLATE_ID) {
      const session = await resolveCodexSession({ subscriptionSessions: this.subscriptionSessions });
      return { ref: 'subscriptions-auth', value: JSON.stringify({ access: session.accessToken, accountId: session.accountId }), source: 'subscriptions-auth' };
    }
    if (connection.template === GROK_TEMPLATE_ID) {
      const session = await resolveGrokSession({ subscriptionSessions: this.subscriptionSessions });
      return { ref: 'subscriptions-auth', value: JSON.stringify({ access: session.accessToken }), source: 'subscriptions-auth' };
    }
    if (LEGACY_CREDENTIAL_REFS.has(connection.credentialRef)) {
      const info = await this.credentialProvider.resolve(connection.credentialRef);
      return { ref: connection.credentialRef, value: typeof info?.value === 'string' ? info.value : '', source: typeof info?.source === 'string' ? info.source : 'managed' };
    }
    return await this.credentialStore.resolve(connection.id);
  }

  async setCredential(connection, value) {
    if (connection.template === CODEX_TEMPLATE_ID) {
      throw fail('subscription_credential_managed', 'ChatGPT 订阅连接的凭据由订阅登录管理；请到“设置 → 订阅”登录 Codex');
    }
    if (connection.template === GROK_TEMPLATE_ID) {
      throw fail('subscription_credential_managed', 'Grok 订阅连接的凭据由订阅登录管理；请到“设置 → 订阅”登录 Grok');
    }
    if (typeof value !== 'string' || !value.trim()) throw fail('invalid_key', 'API Key 不能为空');
    if (LEGACY_CREDENTIAL_REFS.has(connection.credentialRef)) {
      await this.credentialProvider.set(connection.credentialRef, value);
    } else {
      await this.credentialStore.set(connection.id, value);
    }
  }

  async clearCredential(id) {
    const connection = await this.requireConnection(id);
    if (connection.template === CODEX_TEMPLATE_ID) {
      throw fail('subscription_credential_managed', 'ChatGPT 订阅连接的凭据由订阅登录管理；如需移除请到“设置 → 订阅”登出 Codex');
    }
    if (connection.template === GROK_TEMPLATE_ID) {
      throw fail('subscription_credential_managed', 'Grok 订阅连接的凭据由订阅登录管理；如需移除请到“设置 → 订阅”登出 Grok');
    }
    if (LEGACY_CREDENTIAL_REFS.has(connection.credentialRef)) {
      await this.credentialProvider.unset(connection.credentialRef);
    } else {
      await this.credentialStore.clear(id);
    }
  }

  /** 写前守卫：当前连接失去就绪（缺 Key/未验证/验证失败）时原子清空，不静默切换。 */
  async persistWithActiveGuard(next) {
    let guarded = next;
    if (next.activeConnectionId) {
      const active = next.connections.find((item) => item.id === next.activeConnectionId);
      if (!active) {
        guarded = { ...next, activeConnectionId: '' };
      } else {
        const credential = await this.describeCredential(active);
        if (capabilityOf(active, credential.configured) !== 'ready') guarded = { ...next, activeConnectionId: '' };
      }
    }
    const validated = validateImageConnections(guarded);
    await this.settings.replace(validated);
    return this.value();
  }

  async list() {
    const value = await this.ensureMigrated();
    const connections = [];
    for (const connection of value.connections) {
      const credential = await this.describeCredential(connection);
      connections.push(summaryFor(connection, credential, connection.verification));
    }
    const active = value.connections.find((item) => item.id === value.activeConnectionId);
    const ready = connections.filter((item) => item.capability === 'ready').length;
    return Object.freeze({
      schema: IMAGE_CONNECTIONS_SCHEMA_TAG,
      activeConnectionId: value.activeConnectionId,
      connections,
      summary: `生图连接 ${connections.length} 条 · 就绪 ${ready} 条${active ? ` · 当前：${active.name}` : ' · 未选择当前连接'}`,
    });
  }

  async describe(id) {
    const connection = await this.requireConnection(id);
    const credential = await this.describeCredential(connection);
    return summaryFor(connection, credential, connection.verification);
  }

  async upsert(draft, id) {
    await this.ensureMigrated();
    const value = this.value();
    const normalized = validateConnectionDraft(draft);
    let next;
    if (!id) {
      if (value.connections.length >= MAX_CONNECTIONS) throw fail('too_many_connections', `生图连接最多 ${MAX_CONNECTIONS} 条`);
      const connectionId = generateConnectionId(Date.now());
      const stamp = this.now();
      next = {
        ...value,
        connections: [...value.connections, Object.freeze({
          id: connectionId,
          ...normalized,
          credentialRef: this.credentialStore.refFor(connectionId),
          createdAt: stamp,
          updatedAt: stamp,
        })],
      };
    } else {
      if (!isValidConnectionId(id)) throw fail('invalid_connection_id', '连接 ID 无效');
      const existing = value.connections.find((item) => item.id === id);
      if (!existing) throw fail('connection_not_found', `生图连接不存在：${id}`);
      const capabilityFieldsChanged = normalized.template !== existing.template
        || normalized.adapter !== existing.adapter
        || normalized.model !== existing.model
        || normalized.baseUrl !== existing.baseUrl;
      const updated = Object.freeze({
        // 模板、协议、模型或地址变化后，旧验证身份不再可信；不能让
        // 展开 existing 时携带的 verification 穿透到新连接。
        ...withoutVerification(existing),
        ...normalized,
        updatedAt: this.now(),
        ...(capabilityFieldsChanged ? {} : existing.verification ? { verification: existing.verification } : {}),
      });
      next = { ...value, connections: value.connections.map((item) => item.id === id ? updated : item) };
    }
    await this.persistWithActiveGuard(next);
    return await this.list();
  }

  async setKey(id, value) {
    const connection = await this.requireConnection(id);
    await this.setCredential(connection, value);
    const current = this.value();
    await this.persistWithActiveGuard({
      ...current,
      connections: current.connections.map((item) => item.id === id ? withoutVerification(item) : item),
    });
    return await this.describe(id);
  }

  async clearKey(id) {
    await this.requireConnection(id);
    await this.clearCredential(id);
    const current = this.value();
    await this.persistWithActiveGuard({
      ...current,
      connections: current.connections.map((item) => item.id === id ? withoutVerification(item) : item),
    });
    return await this.describe(id);
  }

  async discoverModels(id) {
    const connection = await this.requireConnection(id);
    if (connection.template === CODEX_TEMPLATE_ID) {
      // Codex 订阅生图端点无 /models 目录；返回连接配置的模型本身
      return Object.freeze({ connectionId: id, models: Object.freeze([{ id: connection.model }]) });
    }
    if (connection.template === GROK_TEMPLATE_ID) {
      // api.x.ai /models 目录同时含聊天/嵌入模型；仅保留 imagine-image 生图模型
      const credential = await this.resolveCredential(connection);
      let token = '';
      try { token = JSON.parse(credential.value)?.access ?? ''; } catch { /* 快照解析失败按未配置处理 */ }
      if (!token) throw fail('credential_missing', '尚未登录 Grok 订阅；请到“设置 → 订阅”完成 Grok 登录');
      const response = await this.fetch(`${connection.baseUrl}/models`, {
        method: 'GET',
        headers: { accept: 'application/json', authorization: `Bearer ${token}` },
      });
      if (!response?.ok) {
        const status = response?.status ?? '未知';
        if (status === 401 || status === 403) throw fail('models_endpoint_rejected', `模型列表接口拒绝了请求（HTTP ${status}）；模型仍可手动填写，且这不等同于生图不可用`);
        throw fail('models_http_error', `模型列表接口请求失败（HTTP ${status}）`);
      }
      const models = parseModels(await response.json())
        .filter((entry) => /imagine-image/.test(entry.id));
      return Object.freeze({ connectionId: id, models: Object.freeze(models) });
    }
    const credential = await this.resolveCredential(connection);
    if (!credential.value) throw fail('credential_missing', '该连接尚未保存 API Key；请先保存后再获取模型');
    const url = `${connection.baseUrl}/models`;
    try {
      const response = await this.fetch(url, {
        method: 'GET',
        headers: { accept: 'application/json', authorization: `Bearer ${credential.value}` },
      });
      if (!response?.ok) {
        const status = response?.status ?? '未知';
        if (status === 401 || status === 403) throw fail('models_endpoint_rejected', `模型列表接口拒绝了请求（HTTP ${status}）；模型仍可手动填写，且这不等同于生图不可用`);
        throw fail('models_http_error', `模型列表接口请求失败（HTTP ${status}）`);
      }
      return Object.freeze({ connectionId: id, models: parseModels(await response.json()) });
    } catch (error) {
      if (error?.code) throw error;
      const cleaned = safeError(error, [credential.value]);
      throw cleaned;
    }
  }

  async verify(id, authorizePaid) {
    if (authorizePaid !== true) throw fail('verify_not_authorized', '真实测试可能产生供应商费用，必须显式确认');
    const connection = await this.requireConnection(id);
    const credential = await this.resolveCredential(connection);
    if (!credential.value) throw fail('credential_missing', '该连接尚未保存 API Key；请先保存后再验证');
    const result = await verifyConnection({
      connection,
      credential: credential.value,
      fetchImpl: this.fetch,
      now: this.now,
      sleep: this.sleep,
      subscriptionSessions: this.subscriptionSessions,
    });
    const value = this.value();
    const verification = result.ok
      ? {
        status: 'ready', protocol: result.protocol, model: connection.model,
        template: connection.template,
        baseUrlFingerprint: result.identity.baseUrlFingerprint,
        keyFingerprint: result.identity.keyFingerprint,
        verifiedAt: result.verifiedAt, message: '',
      }
      : {
        status: 'failed', protocol: connection.adapter, model: connection.model,
        template: connection.template,
        baseUrlFingerprint: result.identity.baseUrlFingerprint,
        keyFingerprint: result.identity.keyFingerprint,
        verifiedAt: result.verifiedAt,
        message: result.error.message,
      };
    await this.persistWithActiveGuard({
      ...value,
      connections: value.connections.map((item) => item.id === id ? Object.freeze({ ...withoutVerification(item), verification }) : item),
    });
    return await this.describe(id);
  }

  async setActive(id) {
    const value = await this.ensureMigrated();
    const connection = value.connections.find((item) => item.id === id);
    if (!connection) throw fail('connection_not_found', '连接不存在');
    if (!isValidConnectionId(id)) throw fail('invalid_connection_id', '连接 ID 无效');
    const credential = await this.describeCredential(connection);
    if (!credential.configured) throw fail('credential_missing', `连接“${connection.name}”尚未配置 API Key，不能设为当前`);
    if (connection.verification?.status !== 'ready') throw fail('capability_pending', `连接“${connection.name}”尚未通过真实生图验证，不能设为当前`);
    const next = { ...value, activeConnectionId: id };
    await this.settings.replace(validateImageConnections(next));
    return await this.list();
  }

  async remove(id, { clearCredential = false } = {}) {
    const value = await this.ensureMigrated();
    const removed = value.connections.find((item) => item.id === id);
    if (!isValidConnectionId(id) || !removed) throw fail('connection_not_found', '连接不存在');
    const next = {
      ...value,
      activeConnectionId: value.activeConnectionId === id ? '' : value.activeConnectionId,
      connections: value.connections.filter((item) => item.id !== id),
    };
    await this.settings.replace(validateImageConnections(next));
    if (clearCredential === true) {
      if (LEGACY_CREDENTIAL_REFS.has(removed.credentialRef)) await this.credentialProvider.unset(removed.credentialRef);
      else await this.credentialStore.clear(id);
    }
    return await this.list();
  }

  /** 工具状态读取：只返回当前连接的非敏感描述；Codex 在读取凭据前失败关闭。 */
  async describeActiveForTool() {
    const value = await this.ensureMigrated();
    const id = value.activeConnectionId;
    if (!id) throw fail('no_active_connection', '尚未选择当前生图连接；请到“设置 > 模型 > 生图模型”验证并选择一条连接');
    const connection = value.connections.find((item) => item.id === id);
    if (!connection) throw fail('connection_not_found', `生图连接不存在：${id}`);
    assertNotCodex(connection);
    const credential = await this.describeCredential(connection);
    if (!credential.configured) throw fail('credential_missing', `连接“${connection.name}”尚未配置 API Key；请在设置页补齐后重试`);
    const capability = capabilityOf(connection, credential.configured);
    if (capability === 'failed') throw fail('capability_failed', `连接“${connection.name}”上次真实验证失败；请到设置页重新验证`);
    if (capability !== 'ready') throw fail('capability_pending', `连接“${connection.name}”尚未通过真实生图验证；请到设置页完成验证`);
    const protocol = connection.verification.protocol;
    return Object.freeze({
      connectionId: connection.id,
      connectionName: connection.name,
      template: connection.template,
      model: connection.model,
      protocol,
      capabilities: capabilitiesForProtocol(protocol),
      codexForbidden: true,
    });
  }

  /** 可编辑 PPT 锁定连接解析：必须显式携带运行锁定的 connectionId；Codex 在任何凭据解析前拒绝。 */
  async resolveForEditablePpt(connectionId) {
    if (typeof connectionId !== 'string' || !connectionId.trim()) {
      throw fail('connection_id_required', 'editable_ppt_image 的生成/编辑调用必须显式携带任务开始时锁定的 connectionId');
    }
    const value = await this.ensureMigrated();
    const id = connectionId.trim();
    const connection = value.connections.find((item) => item.id === id);
    if (!connection) throw fail('connection_not_found', `运行锁定的生图连接不存在：${id}`);
    assertNotCodex(connection);
    const credential = await this.resolveCredential(connection);
    if (!credential.value) throw fail('credential_missing', `连接“${connection.name}”尚未配置 API Key`);
    const capability = capabilityOf(connection, true);
    if (capability === 'failed') throw fail('capability_failed', `连接“${connection.name}”上次真实验证失败；页面失败，不得切换其他连接`);
    if (capability !== 'ready') throw fail('capability_pending', `连接“${connection.name}”尚未通过真实生图验证；页面失败，不得切换其他连接`);
    return Object.freeze({
      connection,
      adapterId: connection.verification.protocol,
      verifiedProtocol: connection.verification.protocol,
      credentialValue: credential.value,
      subscriptionSessions: this.subscriptionSessions,
    });
  }

  /** 生成解析：显式 connectionId 优先，否则当前连接；只返回就绪且 Key 已配置的连接。 */
  async resolveForGenerate(connectionId) {
    const value = await this.ensureMigrated();
    const id = typeof connectionId === 'string' && connectionId.trim() ? connectionId.trim() : value.activeConnectionId;
    if (!id) throw fail('no_active_connection', '尚未选择当前生图连接；请到“设置 > 模型 > 生图模型”验证并选择一条连接');
    const connection = value.connections.find((item) => item.id === id);
    if (!connection) throw fail('connection_not_found', `生图连接不存在：${id}`);
    const credential = await this.resolveCredential(connection);
    if (!credential.value) throw fail('credential_missing', `连接“${connection.name}”尚未配置 API Key`);
    const capability = capabilityOf(connection, true);
    if (capability === 'failed') throw fail('capability_failed', `连接“${connection.name}”上次真实验证失败；请到设置页重新验证`);
    if (capability !== 'ready') throw fail('capability_pending', `连接“${connection.name}”尚未通过真实生图验证，不能用于生成；请到设置页完成验证`);
    return Object.freeze({
      connection,
      adapterId: connection.verification.protocol,
      verifiedProtocol: connection.verification.protocol,
      credentialValue: credential.value,
      subscriptionSessions: this.subscriptionSessions,
    });
  }

  /** 旧 provider 兼容映射：legacyProvider 唯一匹配才放行；多个同模板连接拒绝歧义。 */
  async resolveLegacyProvider(provider) {
    const value = await this.ensureMigrated();
    const matches = value.connections.filter((item) => item.legacyProvider === provider);
    if (matches.length === 0) throw fail('provider_not_migrated', `旧生图供应商“${provider}”没有对应的迁移连接；请改用 connectionId 明确指定`);
    if (matches.length > 1) throw fail('ambiguous_provider', `存在多条与旧供应商“${provider}”对应的连接；请改用 connectionId 明确指定`);
    return await this.resolveForGenerate(matches[0].id);
  }

  async status() {
    const value = await this.ensureMigrated();
    const states = [];
    for (const connection of value.connections) {
      const credential = await this.describeCredential(connection);
      states.push({ id: connection.id, name: connection.name, capability: capabilityOf(connection, credential.configured) });
    }
    const active = value.connections.find((item) => item.id === value.activeConnectionId);
    return Object.freeze({
      schema: IMAGE_CONNECTIONS_SCHEMA_TAG,
      activeConnectionId: value.activeConnectionId,
      activeName: active?.name ?? null,
      summary: `生图连接 ${states.length} 条 · 就绪 ${states.filter((item) => item.capability === 'ready').length} 条${active ? ` · 当前：${active.name}` : ' · 未选择当前连接'}`,
      connections: Object.freeze(states),
    });
  }
}
