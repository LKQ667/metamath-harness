import Schema from '@deepseek-ai/schemastery';
import { assertCompatibleHarnessVersion, detectHarnessVersion } from './version.js';
import { installApiKeyPoolHost } from './host.js';

export const name = 'api-key-pool';

export const inject = ['credentials', 'settings'];

/** 插件配置：共存模式默认开启；独立号池 Profile 可显式启用独占路由。 */
export const Config = Schema.object({
  profileLabel: Schema.string().description('健康端点返回的 profile 标签（如 web 或 web-key-pool）；留空则返回 null'),
  exclusivePoolRoutes: Schema.boolean().default(false)
    .description('独占号池路由：拒绝所有非 pool-* 请求；仅独立号池 Profile 启用'),
});

/** Host 分面入口；版本门通过后才注册服务与 Remote。 */
export function apply(ctx, config) {
  assertCompatibleHarnessVersion(detectHarnessVersion(ctx?.baseUrl ?? import.meta.url));
  return installApiKeyPoolHost(ctx, config);
}

export {
  assertCompatibleHarnessVersion, detectHarnessVersion, SUPPORTED_DSH_VERSION,
} from './version.js';
export { ApiKeyPoolService, ApiKeyPoolGateway, installApiKeyPoolHost, makeHealthRoutes, recursiveSecretScan } from './host.js';
export { ApiKeyPoolSchema, API_KEY_POOL_NAMESPACE, routeOf, isPoolRoute, validatePoolConfig } from './schema.js';
export { CredentialFacade, CREDENTIAL_SCOPE } from './credentials.js';
export { KeyPoolRuntime, POOL_EXHAUSTED_CODE } from './pools.js';
export { PoolPiAiAdapter, resolvePoolProfiles, keySession } from './adapter.js';
export { decideFailureAction, nextCooldownMs } from './failure.js';
export { API_KEY_POOL_INVOCATIONS, API_KEY_POOL_SERVICE } from './typert-shared.js';
