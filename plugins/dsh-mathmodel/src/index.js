import { assertCompatibleHarnessVersion, detectHarnessVersion } from './version.js';
import { installMathmodelHost } from './host.js';

export const name = 'dsh-mathmodel';

export const inject = ['credentials', 'settings'];

/** Host 分面入口；仅在版本门通过后注册服务与 Remote。 */
export function apply(ctx, config) {
  assertCompatibleHarnessVersion(detectHarnessVersion(ctx?.baseUrl ?? import.meta.url));
  return installMathmodelHost(ctx, config);
}

export { assertCompatibleHarnessVersion, detectHarnessVersion, SUPPORTED_DSH_VERSION } from './version.js';
export { CardRegistry, SkillHelpCatalog, SKILL_HELP_OVERRIDES } from './cards/registry.js';
export { MathModelCardsRemote } from './cards/remote.js';
export { parseAndValidateCard, validateCard } from './cards/schema.js';
export { renderCardPrompt } from './cards/prompt.js';
export { locateExecutable, PreflightService, runReadonlyProcess } from './preflight.js';
export { CredentialFacade, CREDENTIAL_ALLOWLIST } from './security/credentials.js';
export { DEFAULT_PROVIDER_SETTINGS, PROVIDERS, ProviderSettingsFacade, validateProviderSettings } from './security/provider-settings.js';
export {
  CONNECTION_ID_PATTERN, EMPTY_IMAGE_CONNECTIONS, IMAGE_CONNECTIONS_SCHEMA_TAG, IMAGE_TEMPLATES,
  ImageConnectionsFacade, LEGACY_PROVIDERS, MAX_CONNECTIONS, adapterIds, capabilityOf,
  generateConnectionId, isValidConnectionId, migrateFromV1, templateById, validateBaseUrl,
  validateConnectionDraft, validateImageConnections,
} from './security/image-connections.js';
export { ImageConnectionCredentialStore } from './security/image-credentials.js';
export { redactText, safeError } from './security/redact.js';
export {
  CODEX_CREDENTIAL_KEY, describeCodexCredential, resolveCodexSession,
} from './image/codex-auth.js';
export {
  GROK_CREDENTIAL_KEY, describeGrokCredential, resolveGrokSession,
} from './image/grok-auth.js';
export { codexImagesAdapter, grokImagesAdapter } from './image/adapters.js';
export { ManualVisionService, VisionError, VISION_MODELS, VisionService, MANUAL_VISION_LIMITS, MANUAL_VISION_PROMPT } from './vision.js';
export { ADAPTER_BY_ID, IMAGE_ADAPTERS, customAdapter, dashscopeAdapter, geminiAdapter, openaiAdapter, openaiChatImageAdapter, openaiImagesAdapter, sub2apiAsyncImagesAdapter } from './image/adapters.js';
export { decodeImageAsset, downloadImage, mimeForPath, requestError } from './image/assets.js';
export { classifyVerifyError, shouldTryChatImage, verificationIdentity, verifyConnection } from './image/verify.js';
export { ImageConnectionService } from './image/connections.js';
export { ImageGenerationService } from './image/service.js';
export { createToolExecutors, IMAGE_GENERATE_TOOL, VISION_ANALYZE_TOOL } from './tool-contracts.js';
export { OPENCODE_RT_CREDENTIAL, OPENCODE_RT_ENDPOINT, OPENCODE_RT_MODELS_ENDPOINT, OPENCODE_RT_PROVIDER, OpenCodeRtService, OpenCodeRtSettingsSchema, buildOpenCodeRtProfile, parseOpenCodeModels } from './opencode-rt.js';
export { StoredKeyModelDiscoveryService, parseStoredKeyModels } from './model-discovery.js';
export { ImageConnectionsSchema, IMAGE_CONNECTIONS_NAMESPACE, installMathmodelHost, ProviderSettingsSchema, PROVIDER_SETTINGS_NAMESPACE } from './host.js';
