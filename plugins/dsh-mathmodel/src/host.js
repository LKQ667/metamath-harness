import Schema from '@deepseek-ai/schemastery';
import { Remote, TypertRemoteService } from '@deepseek-ai/dsh-typert-protocol';
import { CardRegistry, SkillHelpCatalog } from './cards/registry.js';
import { MathModelCardsRemote } from './cards/remote.js';
import { PreflightService } from './preflight.js';
import { CredentialFacade } from './security/credentials.js';
import { DEFAULT_PROVIDER_SETTINGS, ProviderSettingsFacade } from './security/provider-settings.js';
import { IMAGE_CONNECTIONS_SCHEMA_TAG, validateImageConnections } from './security/image-connections.js';
import { ImageConnectionCredentialStore } from './security/image-credentials.js';
import { ManualVisionService, VisionService } from './vision.js';
import { ImageGenerationService } from './image/service.js';
import { ImageConnectionService } from './image/connections.js';
import { OpenCodeRtService, OpenCodeRtSettingsSchema } from './opencode-rt.js';
import { StoredKeyModelDiscoveryService } from './model-discovery.js';

export const PROVIDER_SETTINGS_NAMESPACE = 'mathmodel-providers';
export const IMAGE_CONNECTIONS_NAMESPACE = 'mathmodel-image-connections';

export const ProviderSettingsSchema = Schema.object({
  providerOrder: Schema.array(Schema.union(['dashscope', 'openai', 'gemini', 'custom'].map(Schema.const))).default([...DEFAULT_PROVIDER_SETTINGS.providerOrder])
    .description('生图供应商尝试顺序（v1 兼容；仅用于 v1→v2 迁移源）'),
  dashscopeModel: Schema.string().default(DEFAULT_PROVIDER_SETTINGS.dashscopeModel).description('百炼生图模型（v1 兼容）'),
  openaiModel: Schema.string().default(DEFAULT_PROVIDER_SETTINGS.openaiModel).description('OpenAI 生图模型（v1 兼容）'),
  geminiModel: Schema.string().default(DEFAULT_PROVIDER_SETTINGS.geminiModel).description('Gemini 生图模型（v1 兼容）'),
  customBaseUrl: Schema.string().default('').description('自定义供应商 HTTPS Base URL（v1 兼容）'),
  customModel: Schema.string().default('').description('自定义供应商模型（v1 兼容）'),
});

const VerificationSchema = Schema.object({
  status: Schema.string().default(''),
  protocol: Schema.string().default(''),
  model: Schema.string().default(''),
  template: Schema.string().default(''),
  baseUrlFingerprint: Schema.string().default(''),
  keyFingerprint: Schema.string().default(''),
  verifiedAt: Schema.string().default(''),
  message: Schema.string().default(''),
});

export const ImageConnectionsSchema = Schema.object({
  schema: Schema.const(IMAGE_CONNECTIONS_SCHEMA_TAG),
  activeConnectionId: Schema.string().default(''),
  connections: Schema.array(Schema.object({
    id: Schema.string().default(''),
    name: Schema.string().default(''),
    template: Schema.string().default(''),
    adapter: Schema.string().default(''),
    model: Schema.string().default(''),
    baseUrl: Schema.string().default(''),
    credentialRef: Schema.string().default(''),
    createdAt: Schema.string().default(''),
    updatedAt: Schema.string().default(''),
    legacyProvider: Schema.string().default(''),
    verification: VerificationSchema,
  })).default([]),
}).default({
  schema: IMAGE_CONNECTIONS_SCHEMA_TAG,
  activeConnectionId: '',
  connections: [],
});

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

export class MathmodelCardsGateway extends TypertRemoteService {
  constructor(ctx, service) {
    super(ctx, 'mathmodelCards');
    this.service = service;
    initializeRemotes(this, MathmodelCardsGateway);
  }
  async list() { return await this.service.list(); }
  async help() { return await this.service.help(); }
  async render(skill, values) { return await this.service.render(skill, values); }
}
remote(MathmodelCardsGateway, 'list');
remote(MathmodelCardsGateway, 'help');
remote(MathmodelCardsGateway, 'render');

export class MathmodelCredentialsGateway extends TypertRemoteService {
  constructor(ctx, service) {
    super(ctx, 'mathmodelCredentials');
    this.service = service;
    initializeRemotes(this, MathmodelCredentialsGateway);
  }
  async describe(ref) { return await this.service.describe(ref); }
  async set(ref, value) { return await this.service.set(ref, value); }
  async unset(ref) { return await this.service.unset(ref); }
}
remote(MathmodelCredentialsGateway, 'describe');
remote(MathmodelCredentialsGateway, 'set');
remote(MathmodelCredentialsGateway, 'unset');

export class MathmodelPreflightGateway extends TypertRemoteService {
  constructor(ctx, service) {
    super(ctx, 'mathmodelPreflight');
    this.service = service;
    initializeRemotes(this, MathmodelPreflightGateway);
  }
  async run() { return await this.service.run(); }
}
remote(MathmodelPreflightGateway, 'run');

/** 只读 v1 Remote：仅供新客户端识别尚未重载的旧 Host，不再暴露写入口。 */
export class MathmodelProvidersGateway extends TypertRemoteService {
  constructor(ctx, settings, credentials) {
    super(ctx, 'mathmodelProviders');
    this.settings = settings;
    this.credentials = credentials;
    initializeRemotes(this, MathmodelProvidersGateway);
  }
  async status() {
    const credentials = await this.credentials.describeAll();
    return { schema: 'dsh.mathmodel.providers/v1', connectionsV2: true, settings: new ProviderSettingsFacade(this.settings).describe(), credentials };
  }
}
remote(MathmodelProvidersGateway, 'status');

export class MathmodelImageConnectionsGateway extends TypertRemoteService {
  constructor(ctx, service) {
    super(ctx, 'mathmodelImageConnections');
    this.service = service;
    initializeRemotes(this, MathmodelImageConnectionsGateway);
  }
  async list() { return await this.service.list(); }
  async upsert(draft, id) { return await this.service.upsert(draft, id); }
  async setKey(id, value) { return await this.service.setKey(id, value); }
  async clearKey(id) { return await this.service.clearKey(id); }
  async discoverModels(id) { return await this.service.discoverModels(id); }
  async verify(id, authorizePaid) { return await this.service.verify(id, authorizePaid); }
  async setActive(id) { return await this.service.setActive(id); }
  async deleteConnection(id, clearCredential) { return await this.service.remove(id, { clearCredential }); }
}
remote(MathmodelImageConnectionsGateway, 'list');
remote(MathmodelImageConnectionsGateway, 'upsert');
remote(MathmodelImageConnectionsGateway, 'setKey');
remote(MathmodelImageConnectionsGateway, 'clearKey');
remote(MathmodelImageConnectionsGateway, 'discoverModels');
remote(MathmodelImageConnectionsGateway, 'verify');
remote(MathmodelImageConnectionsGateway, 'setActive');
remote(MathmodelImageConnectionsGateway, 'deleteConnection');

export class MathmodelOpenCodeRtGateway extends TypertRemoteService {
  constructor(ctx, service) {
    super(ctx, 'mathmodelOpenCodeRt');
    this.service = service;
    initializeRemotes(this, MathmodelOpenCodeRtGateway);
  }
  async status() { return this.service.status(); }
  async configure(apiKey) { return await this.service.configure(apiKey); }
  async refresh() { return await this.service.refresh(); }
  async verifyVision(model) { return await this.service.verifyVision(model); }
}
remote(MathmodelOpenCodeRtGateway, 'configure');
remote(MathmodelOpenCodeRtGateway, 'refresh');

export class MathmodelStoredKeyModelDiscoveryGateway extends TypertRemoteService {
  constructor(ctx, service) {
    super(ctx, 'mathmodelStoredKeyModelDiscovery');
    this.service = service;
    initializeRemotes(this, MathmodelStoredKeyModelDiscoveryGateway);
  }
  async discover(provider) { return await this.service.discover(provider); }
}
remote(MathmodelStoredKeyModelDiscoveryGateway, 'discover');

export class MathmodelManualVisionGateway extends TypertRemoteService {
  constructor(ctx, service) {
    super(ctx, 'mathmodelManualVision');
    this.service = service;
    initializeRemotes(this, MathmodelManualVisionGateway);
  }
  async stage(images, workspace) { return await this.service.stageDraftImages({ images, workspace }); }
}
remote(MathmodelManualVisionGateway, 'stage');

export function installMathmodelHost(ctx, config = {}) {
  const skillRoot = config.skillRoot;
  const settingsScope = ctx.settings.register(PROVIDER_SETTINGS_NAMESPACE, ProviderSettingsSchema, {
    applies: 'live',
    validate: (value) => new ProviderSettingsFacade({ get: () => value }).describe(),
  });
  const imageConnectionsScope = ctx.settings.register(IMAGE_CONNECTIONS_NAMESPACE, ImageConnectionsSchema, {
    applies: 'live',
    validate: (value) => { validateImageConnections(value); },
  });
  ctx.settings.register('mathmodel-opencode-rt', OpenCodeRtSettingsSchema, { applies: 'live' });
  const credentials = new CredentialFacade(ctx.credentials);
  const cards = new MathModelCardsRemote(new CardRegistry(skillRoot), new SkillHelpCatalog(skillRoot));
  const preflight = new PreflightService();
  const credentialStore = new ImageConnectionCredentialStore(ctx.credentials);
  const imageConnections = new ImageConnectionService({
    settings: imageConnectionsScope,
    legacySettings: settingsScope,
    credentialStore,
    credentialProvider: ctx.credentials,
    hasV2UserSection: () => {
      try {
        const descriptor = ctx.settings.describe({ redactSecrets: true }).find((entry) => entry.ns === IMAGE_CONNECTIONS_NAMESPACE);
        return descriptor?.user !== undefined;
      } catch {
        return false;
      }
    },
  });
  const runtime = Object.freeze({
    vision: new VisionService({ credentials: ctx.credentials }),
    image: new ImageGenerationService({ connections: imageConnections }),
  });
  const openCodeRt = new OpenCodeRtService({ settings: ctx.settings, credentials: ctx.credentials });
  const storedKeyModelDiscovery = new StoredKeyModelDiscoveryService({ settings: ctx.settings, credentials: ctx.credentials });

  ctx.effect(() => ctx.reflect.provide('mathmodelRuntime', runtime), 'dsh-mathmodel: runtime');
  new MathmodelCardsGateway(ctx, cards);
  new MathmodelCredentialsGateway(ctx, credentials);
  new MathmodelPreflightGateway(ctx, preflight);
  new MathmodelProvidersGateway(ctx, settingsScope, credentials);
  new MathmodelImageConnectionsGateway(ctx, imageConnections);
  new MathmodelOpenCodeRtGateway(ctx, openCodeRt);
  new MathmodelStoredKeyModelDiscoveryGateway(ctx, storedKeyModelDiscovery);
  new MathmodelManualVisionGateway(ctx, new ManualVisionService());
  return runtime;
}
