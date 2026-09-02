import { LlmError } from '@deepseek-ai/dsh-llm';
import { Remote, TypertRemoteService } from '@deepseek-ai/dsh-typert-protocol';
import {
  API_KEY_POOL_NAMESPACE,
  ApiKeyPoolSchema,
  assertServiceablePoolConfig,
  isPoolRoute,
  validatePoolConfig,
} from './schema.js';
import { CredentialFacade, KEY_ID_PATTERN } from './credentials.js';
import { KeyPoolRuntime } from './pools.js';
import { PoolPiAiAdapter, resolvePoolProfiles } from './adapter.js';
import { API_KEY_POOL_SERVICE } from './typert-shared.js';

/**
 * Host 分面：settings 注册（无秘密）、号池运行时、LLM 适配器接线、
 * llm/stream fail-closed 守卫、Typert Remote 网关与只读健康端点。
 * 完整 Key 只经 CredentialFacade 逐流解析；一切 Remote/HTTP 输出经递归脱敏断言。
 */

export const API_KEY_POOL_STATUS_TAG = 'dsh.api-key-pool.status/v1';
export const HEALTH_ROUTE_PATH = '/api/dsh-api-key-pool/health';

const NATIVE_ROUTE_FORBIDDEN_CODE = 'POOL_PROFILE_NATIVE_ROUTE_FORBIDDEN';

/** 独占模式的 fail-closed 守卫；共存模式不注册该守卫。 */
export function makeExclusivePoolRouteGuard() {
  return (options, next) => {
    if (!isPoolRoute(options?.provider)) {
      throw new LlmError(
        `dsh-api-key-pool: 独占号池 Profile 拒绝非 pool-* route 的模型请求（"${options?.provider}"）`,
        NATIVE_ROUTE_FORBIDDEN_CODE,
      );
    }
    return next();
  };
}

// ---------------------------------------------------------------------------
// 递归 secret 扫描：任何输出值（对象/数组/字符串）不得包含已知完整 Key 片段。
// ---------------------------------------------------------------------------

/** 递归收集 value 中所有字符串（含对象键），与 secrets 逐一子串比对。 */
export function recursiveSecretScan(value, secrets) {
  const hits = [];
  const needles = (secrets ?? []).filter((s) => typeof s === 'string' && s.length > 0);
  if (needles.length === 0) return hits;
  const visit = (node, path) => {
    if (node === null || node === undefined) return;
    if (typeof node === 'string') {
      for (const secret of needles) {
        if (node.includes(secret)) hits.push({ path, secret: `${secret.slice(0, 3)}…` });
      }
      return;
    }
    if (typeof node === 'number' || typeof node === 'boolean') return;
    if (Array.isArray(node)) {
      node.forEach((item, index) => visit(item, `${path}[${index}]`));
      return;
    }
    if (typeof node === 'object') {
      for (const [key, child] of Object.entries(node)) visit(child, `${path}.${key}`);
    }
  };
  visit(value, '$');
  return hits;
}

// ---------------------------------------------------------------------------
// 服务层：组合 settings scope + CredentialFacade + KeyPoolRuntime。
// 不依赖 cordis，可独立单测。
// ---------------------------------------------------------------------------

export class ApiKeyPoolService {
  /**
   * @param {object} options
   * @param {{ get(): object, replace(section: object): Promise<void>, watch(cb: () => void): () => void }} options.settings
   * @param {CredentialFacade} options.credentials
   * @param {string|null} [options.profileLabel] 健康端点展示的 profile 标签
   */
  constructor({ settings, credentials, profileLabel = null }) {
    if (!settings || typeof settings.get !== 'function' || typeof settings.replace !== 'function') {
      throw new Error('ApiKeyPoolService 需要带 get/replace 的 settings scope');
    }
    this.settings = settings;
    this.credentials = credentials;
    this.profileLabel = profileLabel;
    this.runtime = new KeyPoolRuntime({
      config: validatePoolConfig(settings.get()),
      resolveKey: (keyId) => this.credentials.resolveValue(keyId),
    });
    // 所有 Remote 写入口共享同一条队列，形成进程内原子“读—校验—写”临界区。
    // 队列尾始终恢复为 fulfilled，单次失败不会阻断后续写操作。
    this.writeTail = Promise.resolve();
  }

  async #serializeWrite(operation) {
    const result = this.writeTail.then(operation, operation);
    this.writeTail = result.then(() => undefined, () => undefined);
    return await result;
  }

  /** 当前已知的全部完整 Key 值（仅供 secret 扫描使用，绝不输出）。 */
  async #knownSecrets() {
    const entries = await this.credentials.describeKeys();
    const values = [];
    for (const { keyId } of entries) {
      const value = await this.credentials.resolveValue(keyId);
      if (value !== undefined) values.push(value);
    }
    return values;
  }

  /** 递归脱敏断言：输出前确保不含任何完整 Key。 */
  async #assertNoSecrets(output) {
    const secrets = await this.#knownSecrets();
    const hits = recursiveSecretScan(output, secrets);
    if (hits.length > 0) {
      throw new Error(`dsh-api-key-pool: 输出包含未脱敏的 Key（${hits.map((h) => h.path).join(', ')}），已阻断`);
    }
    return output;
  }

  /** Remote list：池配置 + 健康快照 + 脱敏 Key 描述 + 孤儿报告。 */
  async describe() {
    const normalized = validatePoolConfig(this.settings.get());
    const health = this.runtime.healthSnapshot();
    const keys = await this.credentials.describeKeys();
    const referenced = Object.values(normalized.pools).flatMap((pool) => pool.keyIds);
    const orphans = await this.credentials.orphanKeyIds(referenced);
    const keyById = new Map(keys.map((entry) => [entry.keyId, entry]));
    const pools = Object.entries(health.pools).map(([poolId, snapshot]) => ({
      id: poolId,
      route: snapshot.route,
      displayName: snapshot.displayName,
      enabled: snapshot.enabled,
      selection: snapshot.selection,
      // 编辑器需要预填这两项才能像原生「模型」页那样一张卡片改完；它们本就是
      // settings 非秘密分节里的传输元数据，递归 secret 扫描仍会拦截任何 Key 形态。
      api: normalized.pools[poolId]?.api,
      baseURL: normalized.pools[poolId]?.baseURL,
      // 未勾选识图时整个 input 键都不出现：Typert 结果边界校验不接受显式 undefined
      models: (normalized.pools[poolId]?.models ?? []).map((model) => ({
        id: model.id,
        name: model.name,
        contextWindow: model.contextWindow,
        maxTokens: model.maxTokens,
        ...(model.input === undefined ? {} : { input: model.input }),
      })),
      cooldownMs: normalized.pools[poolId]?.cooldownMs,
      maxCooldownMs: normalized.pools[poolId]?.maxCooldownMs,
      maxRetries: normalized.pools[poolId]?.maxRetries,
      keyCount: snapshot.keyCount,
      providerFailures: snapshot.providerFailures,
      lastFailure: snapshot.lastFailure,
      keys: snapshot.keys.map((keyState) => {
        const described = keyById.get(keyState.keyId);
        return {
          keyId: keyState.keyId,
          masked: described?.masked ?? '…',
          fingerprint: described?.fingerprint ?? '',
          state: keyState.state,
          cooldownRemainingMs: keyState.cooldownRemainingMs,
          failureCount: keyState.failureCount,
        };
      }),
    }));
    return this.#assertNoSecrets({
      schema: API_KEY_POOL_STATUS_TAG,
      profile: this.profileLabel,
      generatedAt: health.generatedAt,
      pools,
      orphans,
    });
  }

  /**
   * 新增 Key：校验 → 写凭据记录 →（可选）挂到某个池的 keyIds 尾部。
   * @returns {{ keyId, fingerprint, masked }}
   */
  async addKey(value, poolId = undefined) {
    return await this.#serializeWrite(async () => {
      const added = await this.credentials.addKey(value);
      if (poolId !== undefined) {
        try {
          await this.#attachKey(poolId, added.keyId);
        } catch (error) {
          try {
            await this.credentials.removeKey(added.keyId);
          } catch (rollbackError) {
            const combined = new Error(
              `${error instanceof Error ? error.message : String(error)}；新凭据回滚失败：${rollbackError instanceof Error ? rollbackError.message : String(rollbackError)}`,
            );
            combined.code = error?.code;
            throw combined;
          } finally {
            this.runtime.replaceConfig(validatePoolConfig(this.settings.get()));
          }
          throw error;
        }
        this.runtime.replaceConfig(validatePoolConfig(this.settings.get()));
      }
      return await this.#assertNoSecrets(added);
    });
  }

  /** 删除 Key：先从所有池的 keyIds 移除（可恢复顺序），再删凭据记录。 */
  async removeKey(keyId) {
    return await this.#serializeWrite(async () => {
      if (!KEY_ID_PATTERN.test(String(keyId ?? ''))) {
        throw new Error('dsh-api-key-pool: keyId 非法');
      }
      const current = validatePoolConfig(this.settings.get());
      let touched = false;
      for (const pool of Object.values(current.pools)) {
        const index = pool.keyIds.indexOf(keyId);
        if (index >= 0) {
          pool.keyIds.splice(index, 1);
          touched = true;
        }
      }
      if (touched) await this.settings.replace(current);
      const removed = await this.credentials.removeKey(keyId);
      this.runtime.replaceConfig(validatePoolConfig(this.settings.get()));
      return await this.#assertNoSecrets({ removed, keyId });
    });
  }

  /** 手工重置冷却/禁用；keyId 省略时重置整个池。 */
  async resetCooldown(route, keyId = undefined) {
    return await this.#serializeWrite(async () => {
      if (keyId !== undefined && !KEY_ID_PATTERN.test(String(keyId))) {
        throw new Error('dsh-api-key-pool: keyId 非法');
      }
      this.runtime.resetCooldown(route, keyId);
      return await this.#assertNoSecrets({ reset: true, route, keyId: keyId ?? null });
    });
  }

  /**
   * 新建/更新池：完整校验候选配置后原子写入 settings；
   * 更新时保留既有 keyIds（入参未显式提供 keyIds 的情况下）。
   * @returns {{ poolId, created, keyCount }}
   */
  async upsertPool(pool) {
    return await this.#serializeWrite(async () => {
      const current = validatePoolConfig(this.settings.get());
      const id = pool?.id;
      if (typeof id !== 'string' || id.length === 0) throw new Error('dsh-api-key-pool: 池 id 不能为空');
      const existing = current.pools[id];
      const candidate = { ...current, pools: { ...current.pools } };
      const next = { ...pool };
      if (next.keyIds === undefined) next.keyIds = existing !== undefined ? existing.keyIds : [];
      candidate.pools[id] = next;
      const normalized = validatePoolConfig(candidate);
      await this.settings.replace(normalized);
      this.runtime.replaceConfig(validatePoolConfig(this.settings.get()));
      return await this.#assertNoSecrets({
        poolId: id,
        created: existing === undefined,
        keyCount: normalized.pools[id].keyIds.length,
      });
    });
  }

  /**
   * 删除池：仅摘除池配置，其 keyIds 对应凭据记录转为孤儿（不自动删除）。
   * @returns {{ removed, poolId, orphanedKeys }}
   */
  async deletePool(poolId) {
    return await this.#serializeWrite(async () => {
      const current = validatePoolConfig(this.settings.get());
      if (typeof poolId !== 'string' || current.pools[poolId] === undefined) {
        throw new Error(`dsh-api-key-pool: 未找到池 "${poolId}"`);
      }
      const orphanedKeys = current.pools[poolId].keyIds.length;
      const candidate = { ...current, pools: { ...current.pools } };
      delete candidate.pools[poolId];
      await this.settings.replace(candidate);
      this.runtime.replaceConfig(validatePoolConfig(this.settings.get()));
      return await this.#assertNoSecrets({ removed: true, poolId, orphanedKeys });
    });
  }

  /**
   * 探测：向上游发一次真实请求（仅取第一个 Key；anthropic 用 x-api-key 头）。
   * 可能产生真实调用费用，只能由用户显式确认后触发。输出仅状态码/时延/错误码。
   */
  async probe(poolId) {
    const current = validatePoolConfig(this.settings.get());
    const pool = typeof poolId === 'string' ? current.pools[poolId] : undefined;
    if (pool === undefined) throw new Error(`dsh-api-key-pool: 未找到池 "${poolId}"`);
    if (pool.keyIds.length === 0) throw new Error(`dsh-api-key-pool: 池 "${poolId}" 没有可用 Key，无法探测`);
    const value = await this.credentials.resolveValue(pool.keyIds[0]);
    if (value === undefined) {
      throw new Error(`dsh-api-key-pool: 池 "${poolId}" 的首枚 Key 凭据记录缺失`);
    }
    const target = `${pool.baseURL.replace(/\/+$/, '')}/models`;
    const headers = pool.api === 'anthropic-messages'
      ? { 'x-api-key': value }
      : { authorization: `Bearer ${value}` };
    const began = Date.now();
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), 10_000);
    let outcome;
    try {
      const response = await fetch(target, { headers, signal: controller.signal, redirect: 'error' });
      outcome = { ok: response.ok, status: response.status };
    } catch (err) {
      const reason = err?.cause?.code ?? err?.name ?? 'PROBE_FAILED';
      outcome = { ok: false, error: String(reason) };
    } finally {
      clearTimeout(timer);
    }
    return this.#assertNoSecrets({ poolId, ...outcome, latencyMs: Date.now() - began });
  }

  /** 把 keyId 追加到目标池的 keyIds（不存在该池或已存在时抛错）。 */
  async #attachKey(poolId, keyId) {
    const current = validatePoolConfig(this.settings.get());
    const pool = current.pools[poolId];
    if (pool === undefined) throw new Error(`dsh-api-key-pool: 未找到池 "${poolId}"`);
    if (pool.keyIds.includes(keyId)) throw new Error(`dsh-api-key-pool: keyId ${keyId} 已在池 "${poolId}" 中`);
    pool.keyIds.push(keyId);
    await this.settings.replace(current);
  }

  /** settings watch 回调：热更新运行时配置。 */
  applyConfigChange() {
    this.runtime.replaceConfig(validatePoolConfig(this.settings.get()));
  }
}

// ---------------------------------------------------------------------------
// Typert Remote 网关（复刻 dsh-mathmodel 的装饰器等价物）。
// ---------------------------------------------------------------------------

const REMOTE_INITIALIZERS = new WeakMap();

function remote(target, method) {
  const initializers = REMOTE_INITIALIZERS.get(target) ?? [];
  Remote(method)(target.prototype[method], {
    kind: 'method', name: method, static: false, private: false,
    addInitializer(initializer) { initializers.push(initializer); },
  });
  REMOTE_INITIALIZERS.set(target, initializers);
}

function initializeRemotes(instance, target) {
  for (const initializer of REMOTE_INITIALIZERS.get(target) ?? []) initializer.call(instance);
}

export class ApiKeyPoolGateway extends TypertRemoteService {
  constructor(ctx, service) {
    super(ctx, API_KEY_POOL_SERVICE);
    this.service = service;
    initializeRemotes(this, ApiKeyPoolGateway);
  }
  async list() { return await this.service.describe(); }
  async upsertPool(pool) { return await this.service.upsertPool(pool); }
  async deletePool(poolId) { return await this.service.deletePool(poolId); }
  async addKey(value, poolId) { return await this.service.addKey(value, poolId); }
  async removeKey(keyId) { return await this.service.removeKey(keyId); }
  async resetCooldown(route, keyId) { return await this.service.resetCooldown(route, keyId); }
  async probe(poolId) { return await this.service.probe(poolId); }
}
remote(ApiKeyPoolGateway, 'list');
remote(ApiKeyPoolGateway, 'upsertPool');
remote(ApiKeyPoolGateway, 'deletePool');
remote(ApiKeyPoolGateway, 'addKey');
remote(ApiKeyPoolGateway, 'removeKey');
remote(ApiKeyPoolGateway, 'resetCooldown');
remote(ApiKeyPoolGateway, 'probe');

// ---------------------------------------------------------------------------
// 健康端点（GET，只读，loopback 限定）。
// ---------------------------------------------------------------------------

function isLoopbackRequest(request) {
  const address = request.socket?.remoteAddress;
  if (address !== '127.0.0.1' && address !== '::1' && address !== '::ffff:127.0.0.1') return false;
  const host = request.headers?.host;
  if (typeof host !== 'string') return false;
  let hostUrl;
  try {
    hostUrl = new URL(`http://${host}`);
  } catch {
    return false;
  }
  if (hostUrl.hostname !== '127.0.0.1' && hostUrl.hostname !== 'localhost' && hostUrl.hostname !== '[::1]') return false;
  return true;
}

function writeJson(res, status, body) {
  const payload = JSON.stringify(body);
  res.writeHead(status, { 'content-type': 'application/json; charset=utf-8', 'referrer-policy': 'no-referrer' });
  res.end(payload);
}

export function makeHealthRoutes(service) {
  return [
    {
      kind: 'exact',
      path: HEALTH_ROUTE_PATH,
      handler: async (req, res) => {
        if (!isLoopbackRequest(req)) {
          writeJson(res, 403, { ok: false, error: 'loopback requests only' });
          return;
        }
        if (req.method !== 'GET' && req.method !== 'HEAD') {
          writeJson(res, 405, { ok: false, error: `method not allowed: ${req.method ?? ''}` });
          return;
        }
        const normalized = validatePoolConfig(service.settings.get());
        const enabled = Object.values(normalized.pools).filter((pool) => pool.enabled);
        writeJson(res, 200, {
          ok: true,
          plugin: 'dsh-api-key-pool',
          profile: service.profileLabel,
          poolCount: enabled.length,
        });
      },
    },
  ];
}

// ---------------------------------------------------------------------------
// Host 安装：接线 settings/llm/webServer 与守卫。
// ---------------------------------------------------------------------------

export function installApiKeyPoolHost(ctx, config = {}) {
  const profileLabel = typeof config?.profileLabel === 'string' && config.profileLabel.length > 0
    ? config.profileLabel
    : null;

  const scope = ctx.settings.register(API_KEY_POOL_NAMESPACE, ApiKeyPoolSchema, {
    applies: 'live',
    validate: assertServiceablePoolConfig,
  });

  const service = new ApiKeyPoolService({
    settings: scope,
    credentials: new CredentialFacade(ctx.credentials),
    profileLabel,
  });

  // 适配器：profiles 快照函数 + KeyPoolRuntime；注册面随配置热替换。
  let profiles = resolvePoolProfiles(validatePoolConfig(scope.get()));
  const adapter = new PoolPiAiAdapter({
    pools: service.runtime,
    profiles: () => profiles,
    resolveAttachments: () => ctx.get('attachments'),
  });

  let registration = null;
  const syncRoutes = () => {
    const llm = ctx.get('llm');
    if (llm === undefined) return;
    const routes = [...profiles.keys()];
    if (routes.length === 0) {
      if (registration !== null) {
        registration();
        registration = null;
      }
      return;
    }
    if (registration === null) {
      registration = llm.registerAdapter(routes, adapter);
      return;
    }
    registration.replace(routes);
  };

  ctx.inject(['llm'], () => { syncRoutes(); });

  // 原生 Web 默认为共存模式，不观察普通 Provider；独立号池 Profile 才启用 fail-closed 守卫。
  if (config?.exclusivePoolRoutes === true) {
    ctx.on('llm/stream', makeExclusivePoolRouteGuard(), { global: true, prepend: true });
  }

  // 配置热更新：先完整校验，再原子替换运行时与 route 注册。
  scope.watch(() => {
    service.applyConfigChange();
    profiles = resolvePoolProfiles(validatePoolConfig(scope.get()));
    syncRoutes();
  });

  // 只读健康端点（启动器复用检测依赖 profile 标签）。
  ctx.inject(['webServer'], (sctx) => {
    sctx.effect(() => {
      const disposers = makeHealthRoutes(service).map((route) => sctx.webServer.register(route));
      return () => { for (const dispose of disposers) dispose(); };
    }, 'dsh-api-key-pool: health endpoint');
  });

  new ApiKeyPoolGateway(ctx, service);
  return service;
}
