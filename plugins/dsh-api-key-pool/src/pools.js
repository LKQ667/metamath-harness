import { routeOf } from './schema.js';
import { decideFailureAction, nextCooldownMs } from './failure.js';

/**
 * KeyPoolRuntime：内存态的 Key 选择与健康管理。
 * - round-robin 游标逐请求推进（不可变快照选 Key，防并发串 Key 由适配器的 ALS 保证）
 * - 冷却/禁用状态只在内存（重启恢复健康），绝不写入凭据/设置文件
 * - 全部 Key 不可用 → 抛 POOL_EXHAUSTED（稳定 code）
 */

export const POOL_EXHAUSTED_CODE = 'POOL_EXHAUSTED';

export class PoolRuntimeError extends Error {
  constructor(message, code) {
    super(message);
    this.name = 'PoolRuntimeError';
    this.code = code;
  }
}

const keyState = () => ({ failureCount: 0, cooldownUntil: 0, disabled: false });

/**
 * @param {object} options
 * @param {object} options.config validatePoolConfig 的规范化输出（含 pools dict）
 * @param {(keyId: string) => Promise<string|undefined>} options.resolveKey 逐流解析完整 Key
 * @param {() => number} [options.now] 注入时钟（测试用），默认 Date.now
 */
export class KeyPoolRuntime {
  constructor({ config, resolveKey, now = () => Date.now() }) {
    if (typeof resolveKey !== 'function') {
      throw new PoolRuntimeError('KeyPoolRuntime 需要 resolveKey 函数', 'NO_KEY_RESOLVER');
    }
    this.now = now;
    this.resolveKey = resolveKey;
    /** @type {Map<string, ReturnType<keyState>>} 按 `${poolId}/${keyId}` 存 Key 健康状态 */
    this.keyStates = new Map();
    /** @type {Map<string, number>} 每池 round-robin 游标 */
    this.cursors = new Map();
    /** @type {Map<string, number>} 每池 provider 级失败计数（不罚 Key） */
    this.providerFailures = new Map();
    /** @type {Map<string, { code: string, at: number }>} 每池最近一次失败 */
    this.lastFailures = new Map();
    this.config = { pools: {} };
    this.replaceConfig(config);
  }

  /** 热替换配置：保留同 keyId 的健康状态与游标，移除消失的池。 */
  replaceConfig(config) {
    const pools = config?.pools ?? {};
    const nextKeyStates = new Map();
    for (const [poolId, pool] of Object.entries(pools)) {
      for (const keyId of pool.keyIds) {
        nextKeyStates.set(`${poolId}/${keyId}`, this.keyStates.get(`${poolId}/${keyId}`) ?? keyState());
      }
      if (!this.cursors.has(poolId)) this.cursors.set(poolId, 0);
    }
    for (const poolId of this.cursors.keys()) {
      if (!(poolId in pools)) this.cursors.delete(poolId);
    }
    for (const poolId of this.providerFailures.keys()) {
      if (!(poolId in pools)) this.providerFailures.delete(poolId);
    }
    for (const poolId of this.lastFailures.keys()) {
      if (!(poolId in pools)) this.lastFailures.delete(poolId);
    }
    this.keyStates = nextKeyStates;
    this.config = { pools };
    // 游标统一为「下一个候选下标」；池尺寸变化时收敛回合法区间
    for (const [poolId, pool] of Object.entries(pools)) {
      const cursor = this.cursors.get(poolId) ?? 0;
      this.cursors.set(poolId, pool.keyIds.length > 0 ? cursor % pool.keyIds.length : 0);
    }
  }

  poolOf(route) {
    const poolId = typeof route === 'string' && route.startsWith('pool-') ? route.slice('pool-'.length) : route;
    const pool = this.config.pools[poolId];
    if (pool === undefined) {
      throw new PoolRuntimeError(`未找到号池 route "${route}"`, POOL_EXHAUSTED_CODE);
    }
    return { poolId, pool };
  }

  /**
   * 选出下一个可用 Key（不可变快照）。round-robin：从游标（下一候选）起环形扫描，
   * 跳过冷却中/禁用/凭据缺失的 Key；全部不可用 → POOL_EXHAUSTED。
   * @returns {Promise<{ poolId: string, route: string, keyId: string, value: string }>}
   */
  async beginStream(route) {
    const { poolId, pool } = this.poolOf(route);
    const n = pool.keyIds.length;
    const started = this.now();
    let lastSkip = 'empty';
    // 已尝试过的下标：凭据缺失时换下一个候选重扫，最多 n 次。
    const tried = new Set();
    while (tried.size < n) {
      // 游标必须每轮重读：并发流在 await resolveKey 间隙会推进它。
      const cursor = this.cursors.get(poolId) ?? 0;
      let chosen = -1;
      for (let step = 0; step < n; step += 1) {
        const index = (cursor + step) % n;
        if (tried.has(index)) continue;
        const keyId = pool.keyIds[index];
        const state = this.keyStates.get(`${poolId}/${keyId}`);
        if (state === undefined) {
          lastSkip = 'unknown-key';
          tried.add(index);
          continue;
        }
        if (state.disabled) {
          lastSkip = 'disabled';
          tried.add(index);
          continue;
        }
        if (state.cooldownUntil > started) {
          lastSkip = 'cooldown';
          tried.add(index);
          continue;
        }
        chosen = index;
        break;
      }
      if (chosen < 0) break;
      tried.add(chosen);
      // 同步推进游标后再 await：防止并发流读到同一候选而挤在同一 Key 上。
      this.cursors.set(poolId, (chosen + 1) % n);
      const keyId = pool.keyIds[chosen];
      const value = await this.resolveKey(keyId);
      if (value === undefined) {
        lastSkip = 'missing-credential';
        continue;
      }
      return { poolId, route: routeOf(poolId), keyId, value };
    }
    throw new PoolRuntimeError(
      `号池 "${poolId}" 暂无可用 Key（${lastSkip}）`, POOL_EXHAUSTED_CODE,
    );
  }

  /** 成功：清零该 Key 的连续失败计数并解除冷却。 */
  recordSuccess(route, keyId) {
    const { poolId } = this.poolOf(route);
    const state = this.keyStates.get(`${poolId}/${keyId}`);
    if (state === undefined) return;
    state.failureCount = 0;
    state.cooldownUntil = 0;
    this.providerFailures.delete(poolId);
    this.lastFailures.delete(poolId);
  }

  /**
   * 失败：按 failure.js 决策表处置。
   * @param {string} route pool-* route
   * @param {string} keyId 本次流实际使用的 Key
   * @param {string} code 稳定失败 code
   * @param {{ retryAfterMs?: number }} [hints]
   */
  recordFailure(route, keyId, code, hints = {}) {
    const { poolId, pool } = this.poolOf(route);
    const decision = decideFailureAction(code);
    if (decision.action === 'ignore') return decision.action;
    this.lastFailures.set(poolId, { code, at: this.now() });
    if (decision.action === 'count') {
      this.providerFailures.set(poolId, (this.providerFailures.get(poolId) ?? 0) + 1);
      return decision.action;
    }
    const state = this.keyStates.get(`${poolId}/${keyId}`);
    if (state === undefined) return decision.action;
    if (decision.action === 'disable') {
      state.disabled = true;
      state.cooldownUntil = 0;
      state.failureCount += 1;
      return decision.action;
    }
    state.failureCount += 1;
    state.cooldownUntil = this.now() + nextCooldownMs({
      failureCount: state.failureCount,
      cooldownMs: pool.cooldownMs,
      maxCooldownMs: pool.maxCooldownMs,
      retryAfterMs: hints.retryAfterMs,
      useRetryAfter: decision.useRetryAfter,
      longCooldown: decision.longCooldown,
    });
    return decision.action;
  }

  /** 手动重置冷却/禁用（Web 管理操作）；keyId 省略时重置整个池。 */
  resetCooldown(route, keyId) {
    const { poolId, pool } = this.poolOf(route);
    const targets = keyId === undefined ? pool.keyIds : [keyId];
    for (const id of targets) {
      const state = this.keyStates.get(`${poolId}/${id}`);
      if (state !== undefined) {
        state.failureCount = 0;
        state.cooldownUntil = 0;
        state.disabled = false;
      }
    }
    this.providerFailures.delete(poolId);
  }

  /** 健康快照（脱敏：只有 keyId 与状态，无 Key 值）。 */
  healthSnapshot() {
    const t = this.now();
    const pools = {};
    for (const [poolId, pool] of Object.entries(this.config.pools)) {
      pools[poolId] = {
        route: routeOf(poolId),
        displayName: pool.displayName,
        enabled: pool.enabled,
        selection: pool.selection,
        keyCount: pool.keyIds.length,
        providerFailures: this.providerFailures.get(poolId) ?? 0,
        lastFailure: this.lastFailures.get(poolId) ?? null,
        keys: pool.keyIds.map((keyId) => {
          const state = this.keyStates.get(`${poolId}/${keyId}`) ?? keyState();
          return {
            keyId,
            state: state.disabled ? 'disabled' : state.cooldownUntil > t ? 'cooling' : 'ready',
            cooldownRemainingMs: state.disabled ? 0 : Math.max(0, state.cooldownUntil - t),
            failureCount: state.failureCount,
          };
        }),
      };
    }
    return { pools, generatedAt: t };
  }
}
