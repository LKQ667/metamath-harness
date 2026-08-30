import { fail } from '../security/image-connections.js';

export const GROK_CREDENTIAL_KEY = 'grok';
const SOURCE = 'subscriptions-auth';

function serviceOf(value) {
  const service = typeof value === 'function' ? value() : value;
  return service && typeof service === 'object' ? service : undefined;
}

/** 通过 dsh-plugin-subscriptions 的 Host-only 服务解析 Grok 会话。 */
export async function resolveGrokSession({ subscriptionSessions, force = false, signal } = {}) {
  const service = serviceOf(subscriptionSessions);
  if (typeof service?.resolve !== 'function') {
    throw fail('subscription_service_unavailable', '订阅插件尚未就绪；请确认 dsh-plugin-subscriptions 已启用后重试');
  }
  const session = await service.resolve('grok', { force, signal });
  if (typeof session?.accessToken !== 'string' || session.accessToken.length === 0) {
    throw fail('subscription_session_invalid', 'Grok 订阅会话缺少必要字段；请到“设置 → 订阅”重新登录 Grok');
  }
  return Object.freeze({ accessToken: session.accessToken });
}

/** 返回脱敏登录状态；服务未加载或状态查询失败时按未就绪处理。 */
export async function describeGrokCredential(subscriptionSessions) {
  const service = serviceOf(subscriptionSessions);
  let configured = false;
  try {
    configured = typeof service?.describe === 'function' && (await service.describe('grok'))?.configured === true;
  } catch {
    configured = false;
  }
  return Object.freeze({ ref: SOURCE, configured, writable: false, source: SOURCE });
}
