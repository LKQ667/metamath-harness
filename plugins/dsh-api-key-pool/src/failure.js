/**
 * 稳定失败 code → Key 处置决策（纯函数，无 I/O，便于测试）。
 * 输入使用 dsh-llm 的 provider-neutral 稳定 code（AUTH/QUOTA/RATE_LIMIT/…），
 * 绝不解析 message 文本做路由。
 */

/** 处置动作：
 *  - cooldown     指数冷却该 Key（RATE_LIMIT 受 Retry-After 抬升，QUOTA 直接长冷却）
 *  - disable     禁用该 Key（INVALID_CREDENTIAL：每次尝试都同样失败，修 Key 才有意义）
 *  - count       provider 级计数（TIMEOUT/TRANSPORT/SERVER/EMPTY_RESPONSE：不罚 Key）
 *  - ignore      透传不动健康（INVALID_REQUEST、CONTEXT_WINDOW_EXCEEDED 等请求侧失败）
 */
export const FAILURE_ACTIONS = Object.freeze({
  AUTH: 'cooldown',
  RATE_LIMIT: 'cooldown',
  QUOTA: 'cooldown',
  INVALID_CREDENTIAL: 'disable',
  TIMEOUT: 'count',
  TRANSPORT: 'count',
  SERVER: 'count',
  EMPTY_RESPONSE: 'count',
});

/** 长冷却 code：QUOTA 表示账户额度耗尽，直接进入池配置的冷却上限。 */
const LONG_COOLDOWN_CODES = new Set(['QUOTA']);
/** 受 Retry-After 抬升的 code。 */
const RETRY_AFTER_CODES = new Set(['RATE_LIMIT']);
/** 请求侧失败：与 Key 健康无关，透传。 */
const IGNORED_CODES = new Set([
  'INVALID_REQUEST',
  'CONTEXT_WINDOW_EXCEEDED',
  'MISSING_CREDENTIAL',
  'UNSUPPORTED_OPTION',
  'UNSUPPORTED_CONTENT',
  'UNKNOWN_MODEL',
  'NO_ADAPTER',
  'ABORTED',
]);

/**
 * @param {string} code 稳定失败 code
 * @returns {{
 *   action: 'cooldown'|'disable'|'count'|'ignore',
 *   useRetryAfter: boolean,
 *   longCooldown: boolean,
 * }} 不可变决策
 */
export function decideFailureAction(code) {
  if (typeof code !== 'string' || code.length === 0) return { action: 'ignore', useRetryAfter: false, longCooldown: false };
  const action = FAILURE_ACTIONS[code];
  if (action === undefined) return { action: 'ignore', useRetryAfter: false, longCooldown: false };
  return Object.freeze({
    action,
    useRetryAfter: RETRY_AFTER_CODES.has(code),
    longCooldown: LONG_COOLDOWN_CODES.has(code),
  });
}

/**
 * 计算下一次冷却毫秒数。
 * - 基础指数退避：cooldownMs * 2^(failureCount-1)，封顶 maxCooldownMs。
 * - longCooldown（QUOTA）：直接 maxCooldownMs。
 * - useRetryAfter（RATE_LIMIT）：max(retryAfterMs, 上述结果)。
 * @returns {number} 冷却毫秒数（>= 0）
 */
export function nextCooldownMs({ failureCount, cooldownMs, maxCooldownMs, retryAfterMs, useRetryAfter = false, longCooldown = false }) {
  const base = Number.isFinite(cooldownMs) && cooldownMs > 0 ? cooldownMs : 30_000;
  const cap = Number.isFinite(maxCooldownMs) && maxCooldownMs > 0 ? maxCooldownMs : 3_600_000;
  const safeCap = Math.max(cap, base);
  if (longCooldown) return safeCap;
  const n = Number.isInteger(failureCount) && failureCount > 0 ? failureCount : 1;
  let ms = base;
  for (let i = 1; i < n; i += 1) {
    ms *= 2;
    if (ms >= safeCap) return useRetryAfter ? Math.max(safeCap, retryAfterMs ?? 0) : safeCap;
  }
  ms = Math.min(ms, safeCap);
  if (useRetryAfter && Number.isFinite(retryAfterMs) && retryAfterMs > 0) {
    ms = Math.max(ms, retryAfterMs);
  }
  return Math.round(ms);
}
