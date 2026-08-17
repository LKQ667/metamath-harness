(() => {
function createCardFlow({ renderDraft, insertDraft, setBlock, notify }) {
  const listeners = new Set();
  let state = Object.freeze({ open: false, busy: false, error: null });
  const publish = (next) => {
    state = Object.freeze(next);
    for (const listener of [...listeners]) listener();
  };
  const close = () => {
    if (state.open) setBlock(state.sessionId, undefined);
    publish({
      open: false,
      busy: false,
      error: null,
      activeCard: state.activeCard,
      activeSessionId: state.activeSessionId,
      status: state.status,
    });
  };
  return {
    getSnapshot: () => state,
    subscribe(listener) {
      listeners.add(listener);
      return () => listeners.delete(listener);
    },
    open({ sessionId, span, card }) {
      if (state.open) setBlock(state.sessionId, undefined);
      const values = Object.fromEntries(card.fields.filter((field) => field.default !== undefined).map((field) => [field.id, field.default]));
      setBlock(sessionId, { reason: `正在配置 ${card.title}，确认或取消后恢复输入` });
      publish({ ...state, open: true, busy: false, error: null, sessionId, span, card, values, activeCard: card, activeSessionId: sessionId });
    },
    setValue(id, value) {
      if (!state.open || state.busy) return;
      publish({ ...state, values: { ...state.values, [id]: value }, error: null });
    },
    cancel: close,
    setStatus(status) {
      publish({ ...state, status: { ...state.status, ...status } });
    },
    async confirm() {
      if (!state.open || state.busy) return false;
      const attempt = state;
      publish({ ...attempt, busy: true, error: null });
      try {
        const result = await renderDraft(attempt.card.skill, attempt.values);
        const applied = await insertDraft(attempt.sessionId, attempt.span, result.text);
        if (!applied) {
          notify(attempt.sessionId, 'error', '草稿已变化，未覆盖你的新内容；请重新打开卡片。');
          close();
          return false;
        }
        close();
        return true;
      } catch (error) {
        publish({ ...attempt, busy: false, error: error instanceof Error ? error.message : String(error) });
        return false;
      }
    },
  };
}

function panelSections(card, status = {}) {
  const help = card?.help;
  return [
    ['用途', help?.purpose ? [help.purpose] : ['从 / 菜单选择 Skill 后填写卡片，只生成可编辑草稿。']],
    ['输入', help?.inputs ?? ['赛题、数据或待处理文本']],
    ['输出', help?.outputs ?? ['结构化 Prompt 草稿']],
    ['限制', help?.limits ?? ['不会自动发送；不会替用户确认付费调用']],
    ['依赖', help?.dependencies ?? ['请运行依赖预检']],
    ['环境状态', [status.preflight?.status === 'ready' ? '本机依赖已就绪' : status.preflight ? '部分依赖需要处理' : '尚未完成预检']],
    ['供应商状态', [status.imageConnections?.summary ?? status.providers?.summary ?? '生图连接尚未配置或未检测']],
  ];
}

function createCredentialActions(remote, flow) {
  const refs = {
    dashscope_key_status: 'DASHSCOPE_API_KEY',
    openai_key_status: 'OPENAI_API_KEY',
    gemini_key_status: 'GEMINI_API_KEY',
    custom_image_key_status: 'CUSTOM_IMAGE_API_KEY',
  };
  const refFor = (fieldId) => {
    const ref = refs[fieldId];
    if (!ref) throw new TypeError(`未知凭据状态字段：${fieldId}`);
    return ref;
  };
  const publish = (fieldId, info) => {
    const text = info.configured ? `已配置（${info.source ?? '受管存储'}）` : '未配置';
    flow.setValue(fieldId, text);
    return info;
  };
  return {
    describe: async (fieldId) => publish(fieldId, await remote.describe(refFor(fieldId))),
    set: async (fieldId, value) => publish(fieldId, await remote.set(refFor(fieldId), value)),
    unset: async (fieldId) => publish(fieldId, await remote.unset(refFor(fieldId))),
  };
}

const IMAGE_TEMPLATE_META = Object.freeze([
  Object.freeze({ id: 'dashscope', name: '百炼', baseUrlEditable: false, defaultBaseUrl: '', defaultModel: 'wan2.7-image-pro', adapters: ['dashscope-async'], capability: 'official-known', hint: '官方固定接口，仅配置模型与受管 Key。' }),
  Object.freeze({ id: 'openai', name: 'OpenAI', baseUrlEditable: false, defaultBaseUrl: '', defaultModel: 'gpt-image-1', adapters: ['openai-images'], capability: 'official-known', hint: '官方固定接口，仅配置模型与受管 Key。' }),
  Object.freeze({ id: 'gemini', name: 'Gemini', baseUrlEditable: false, defaultBaseUrl: '', defaultModel: 'gemini-3.1-flash-image', adapters: ['gemini-content'], capability: 'official-known', hint: '官方固定接口，仅配置模型与受管 Key。' }),
  Object.freeze({ id: 'volcengine-ark', name: '火山引擎 Ark', baseUrlEditable: true, defaultBaseUrl: 'https://ark.cn-beijing.volces.com/api/v3', defaultModel: 'doubao-seedream-5.0-lite', adapters: ['openai-images'], capability: 'pending', hint: '图片专用 Images API；模型可填官方模型 ID 或火山推理接入点 ID。' }),
  Object.freeze({ id: 'sub2api', name: 'Sub2API', baseUrlEditable: true, defaultBaseUrl: 'http://localhost:8080/v1', defaultModel: '', adapters: ['sub2api-async-images', 'openai-images'], capability: 'pending', hint: '默认使用异步 Images API；不预置“必然可用”模型。' }),
  Object.freeze({ id: 'cliproxyapi', name: 'CLIProxyAPI', baseUrlEditable: true, defaultBaseUrl: 'http://127.0.0.1:8317/v1', defaultModel: '', adapters: ['openai-images'], capability: 'pending', hint: '仅提示 gpt-image-2 候选，请按实际服务填写。' }),
  Object.freeze({ id: 'openai-compatible', name: '自定义 OpenAI 兼容', baseUrlEditable: true, defaultBaseUrl: '', defaultModel: '', adapters: ['openai-images', 'openai-chat-image'], capability: 'pending', hint: '通用兼容网关；真实测试可确认是否改用 openai-chat-image 协议。' }),
]);

const ADAPTER_LABELS = Object.freeze({
  'dashscope-async': '百炼异步',
  'openai-images': 'OpenAI Images',
  'gemini-content': 'Gemini Content',
  'sub2api-async-images': 'Sub2API 异步 Images',
  'openai-chat-image': 'OpenAI Chat 图片',
});

const CAPABILITY_LABELS = Object.freeze({
  ready: '就绪', pending: '待验证', missing_key: '缺少 Key', failed: '验证失败',
});

function templateMeta(id) {
  return IMAGE_TEMPLATE_META.find((item) => item.id === id) ?? null;
}

function capabilityLabel(capability) {
  return CAPABILITY_LABELS[capability] ?? '未知';
}

function createImageConnectionActions(remote) {
  const legacyFallback = (legacy) => {
    const credentials = Object.fromEntries((legacy.credentials ?? []).map((item) => [item.ref, item]));
    const legacyConnections = [
      ['dashscope', '百炼', 'DASHSCOPE_API_KEY', 'dashscopeModel'], ['openai', 'OpenAI', 'OPENAI_API_KEY', 'openaiModel'], ['gemini', 'Gemini', 'GEMINI_API_KEY', 'geminiModel'],
    ].map(([template, name, credentialRef, modelKey]) => ({ id: `legacy_${template}`, name, template, adapter: templateMeta(template)?.defaultAdapter ?? '', model: legacy.settings?.[modelKey] ?? '', baseUrl: '', credentialRef, capability: credentials[credentialRef]?.configured ? 'pending' : 'missing_key', credential: credentials[credentialRef] ?? { configured: false, writable: false } }));
    if (legacy.settings?.customBaseUrl && legacy.settings?.customModel) legacyConnections.push({ id: 'legacy_custom', name: '自定义', template: 'openai-compatible', adapter: 'openai-images', model: legacy.settings.customModel, baseUrl: legacy.settings.customBaseUrl, credentialRef: 'CUSTOM_IMAGE_API_KEY', capability: credentials.CUSTOM_IMAGE_API_KEY?.configured ? 'pending' : 'missing_key', credential: credentials.CUSTOM_IMAGE_API_KEY ?? { configured: false, writable: false } });
    return { schema: 'dsh.mathmodel.image-connections/legacy-fallback', activeConnectionId: '', connections: legacyConnections, legacyFallback: true, summary: '当前 Web 服务仍是旧版本；重启 Harness 后启用多连接配置。' };
  };
  return {
    load: async () => {
      if (remote.legacyStatus) {
        const legacy = await remote.legacyStatus();
        if (legacy?.connectionsV2 !== true) return legacyFallback(legacy);
      }
      try { return await remote.list(); }
      catch (error) {
        if (!remote.legacyStatus || !/HTTP 404|not found/i.test(String(error?.message ?? error))) throw error;
        return legacyFallback(await remote.legacyStatus());
      }
    },
    save: async (draft, id) => await remote.upsert(draft, id),
    setKey: async (id, value) => await remote.setKey(id, value),
    clearKey: async (id) => await remote.clearKey(id),
    discover: async (id) => await remote.discoverModels(id),
    verify: async (id) => await remote.verify(id, true),
    setActive: async (id) => await remote.setActive(id),
    remove: async (id, clearCredential) => await remote.deleteConnection(id, clearCredential),
  };
}

function createOpenCodeRtActions(remote) {
  return {
    configure: async (apiKey) => await remote.configure(apiKey),
    refresh: async () => await remote.refresh(),
  };
}

function createStoredKeyModelDiscoveryActions(remote) {
  return {
    discover: async (provider) => await remote.discover(provider),
  };
}

function appendStagedImagesDraft(draft, files) {
  if (!Array.isArray(files) || files.length === 0) throw new TypeError('附图结果为空');
  const body = files.map((file, index) => {
    const name = String(file?.name ?? `图片 ${index + 1}`).replace(/[\r\n]/g, ' ').trim() || `图片 ${index + 1}`;
    const path = String(file?.path ?? '').trim();
    if (!path) throw new TypeError('附图结果缺少文件路径');
    return `图片 ${index + 1}（${name}）：${path}`;
  }).join('\n');
  const prefix = String(draft ?? '').trimEnd();
  return `${prefix}${prefix ? '\n\n' : ''}[已附图片（claude-vision-skill）——请用 vision_analyze 工具查看原图]\n${body}\n[/已附图片]`;
}

async function browserDraftPayload(file) {
  const bytes = new Uint8Array(await file.arrayBuffer());
  let binary = '';
  for (let offset = 0; offset < bytes.length; offset += 32768) binary += String.fromCharCode(...bytes.subarray(offset, offset + 32768));
  return { mediaType: file.type, data: btoa(binary), ...(file.name ? { name: file.name } : {}) };
}

function currentInputState(input) {
  const state = input?.state?.getSnapshot?.();
  if (!state || !Array.isArray(state.imageIds)) throw new Error('输入草稿已不可用，请重试');
  return state;
}

function createManualVisionActions({ stage, workspaceOf, draftImages, releaseDraftImages, inputForSession, notify, encodeImage = browserDraftPayload }) {
  return {
    notify,
    async stageToDraft({ sessionId, imageIds }) {
      if (!Array.isArray(imageIds) || imageIds.length === 0) throw new Error('请先添加至少一张图片');
      const workspace = workspaceOf(sessionId);
      if (!workspace) throw new Error('当前会话未绑定工作区，无法附图');
      const input = inputForSession(sessionId);
      const attachments = draftImages(imageIds);
      if (attachments.length !== imageIds.length) throw new Error('图片草稿已变更，请重试');
      const result = await stage(await Promise.all(attachments.map((attachment) => encodeImage(attachment.file))), workspace);
      const latest = currentInputState(input);
      const liveImageIds = new Set(latest.imageIds);
      if (!imageIds.every((id) => liveImageIds.has(id))) throw new Error('图片草稿已变更，未写入附图结果');
      input.setDraft(appendStagedImagesDraft(latest.draft, result?.files));
      for (const id of imageIds) input.removeImage(id);
      releaseDraftImages(attachments);
      input.notify?.('info', `已附图 ${result.files.length} 张；发送后模型将调用视觉工具查看原图。`);
      return result;
    },
  };
}

function createSkillSource({ fetchCatalog, flow, cardsForSession }) {
  return {
    trigger: '/',
    name: 'skill',
    order: 2,
    async candidates(session, { query, signal }) {
      const skills = await fetchCatalog(session.sessionId);
      if (signal.aborted) return [];
      const cards = cardsForSession(session.sessionId);
      return skills.filter((skill) => skill.name.startsWith(query)).map((skill) => {
        const card = cards.get(skill.name);
        return {
          name: skill.name,
          description: card?.summary ?? (skill.modelInvocable ? skill.description : `仅手动 · ${skill.description}`),
          ...(card ? { hint: card.category } : {}),
        };
      });
    },
    warm(session) {
      fetchCatalog(session.sessionId).catch(() => {});
    },
    lexicon(session) {
      return cardsForSession(session.sessionId).catalog?.map((skill) => skill.name);
    },
    onPick({ candidate, session, span }) {
      const card = cardsForSession(session.sessionId).get(candidate.name);
      if (!card) return { text: `/${candidate.name} ` };
      flow.open({ sessionId: session.sessionId, span, card });
      return 'handled';
    },
  };
}

if (typeof module !== 'undefined') module.exports = { appendStagedImagesDraft, browserDraftPayload, createCardFlow, createCredentialActions, createImageConnectionActions, createManualVisionActions, createOpenCodeRtActions, createStoredKeyModelDiscoveryActions, createSkillSource, panelSections, IMAGE_TEMPLATE_META, capabilityLabel };

if (typeof window !== 'undefined' && window.__ModuleLoader__) {
  window.__ModuleLoader__.load({
    id: '@deepseek-harness/dsh-mathmodel',
    factory: (require) => {
      const module = { exports: {} };
      const React = require('react');
      const ReactDOM = require('react-dom');
      const metaMathBrandMark = 'data:image/png;base64,__METAMATH_BRAND_MARK__';
      const metaMathHeroMark = 'data:image/png;base64,__METAMATH_HERO_MARK__';
      const metaMathHeroTitle = 'data:image/png;base64,__METAMATH_HERO_TITLE__';

      const styleId = 'dsh-mathmodel-card-style';
      if (!document.getElementById(styleId)) {
        const style = document.createElement('style');
        style.id = styleId;
        style.textContent = `
          .dsh-mm-overlay{position:fixed;z-index:40;inset:68px 24px 140px;display:flex;align-items:flex-end;justify-content:center;pointer-events:none}
          .dsh-mm-card{box-sizing:border-box;width:min(680px,100%);max-height:100%;overflow:auto;pointer-events:auto;border:1px solid color-mix(in srgb,var(--dsw-alias-border-l1) 82%,transparent);border-radius:18px;background:var(--dsw-alias-bg-base);box-shadow:0 20px 54px rgba(15,23,42,.16);padding:20px 22px 0;scrollbar-width:thin;overscroll-behavior:contain}
          .dsh-mm-head{display:flex;gap:12px;align-items:flex-start}.dsh-mm-title{margin:0;flex:1;font-size:17px;line-height:1.35;font-weight:650;letter-spacing:-.01em}.dsh-mm-summary{margin:5px 0 16px;color:var(--dsw-alias-label-secondary);font-size:12px;line-height:1.5}
          .dsh-mm-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));align-items:start;column-gap:18px;row-gap:12px}.dsh-mm-field{display:flex;min-width:0;flex-direction:column;gap:6px;color:var(--dsw-alias-label-secondary);font-size:12px;font-weight:550;line-height:1.35}.dsh-mm-field[data-wide=true]{grid-column:1/-1}
          .dsh-mm-field input,.dsh-mm-field select,.dsh-mm-field textarea{box-sizing:border-box;width:100%;min-height:38px;border:1px solid var(--dsw-alias-border-l2);border-radius:9px;outline:0;background:color-mix(in srgb,var(--dsw-alias-bg-base) 96%,var(--dsw-alias-label-primary));color:var(--dsw-alias-label-primary);padding:0 11px;font:inherit;font-size:13px;font-weight:400;transition:border-color .16s ease,box-shadow .16s ease,background .16s ease}.dsh-mm-field textarea{min-height:68px;padding:10px 11px;resize:vertical}.dsh-mm-field input:hover,.dsh-mm-field select:hover,.dsh-mm-field textarea:hover{border-color:var(--dsw-alias-label-tertiary)}.dsh-mm-field input:focus-visible,.dsh-mm-field select:focus-visible,.dsh-mm-field textarea:focus-visible{border-color:var(--dsw-alias-state-business-primary);box-shadow:0 0 0 3px color-mix(in srgb,var(--dsw-alias-state-business-primary) 14%,transparent);background:var(--dsw-alias-bg-base)}
          .dsh-mm-field small{color:var(--dsw-alias-label-tertiary);font-size:11px;font-weight:400;line-height:1.4}.dsh-mm-field[data-type=boolean]{min-height:38px;box-sizing:border-box;align-self:start;flex-direction:row;align-items:center;gap:9px;margin-top:22px;border:1px solid var(--dsw-alias-border-l2);border-radius:9px;padding:0 11px;color:var(--dsw-alias-label-primary);font-size:13px;font-weight:400;cursor:pointer}.dsh-mm-field[data-type=boolean]:hover{background:var(--dsw-alias-interactive-bg-hover)}.dsh-mm-field[data-type=boolean] input{order:-1;width:16px;min-height:16px;height:16px;margin:0;accent-color:var(--dsw-alias-state-business-primary)}
          .dsh-mm-actions{position:sticky;bottom:0;display:flex;justify-content:flex-end;gap:8px;margin:18px -22px 0;padding:13px 22px 16px;border-top:1px solid var(--dsw-alias-border-l1);background:var(--dsw-alias-bg-base)}.dsh-mm-actions button{min-height:36px;border:1px solid var(--dsw-alias-border-l2);border-radius:9px;background:transparent;color:var(--dsw-alias-label-primary);padding:0 14px;font-size:12px;font-weight:550;cursor:pointer}.dsh-mm-actions button:hover{background:var(--dsw-alias-interactive-bg-hover)}.dsh-mm-actions button:focus-visible{outline:2px solid var(--dsw-alias-state-business-primary);outline-offset:2px}.dsh-mm-primary{border-color:var(--dsw-alias-state-business-primary)!important;background:var(--dsw-alias-state-business-primary)!important;color:white!important}.dsh-mm-error{color:var(--dsw-alias-state-error-primary);font-size:12px;margin-top:10px}
          .dsh-mm-model-picker{display:flex;max-height:250px;flex-direction:column;gap:6px;overflow:auto;margin:0 -4px;padding:2px 4px}.dsh-mm-model-picker-row{display:flex;align-items:center;gap:9px;min-height:34px;border:1px solid var(--dsw-alias-border-l1);border-radius:9px;padding:0 10px;font-size:12px;cursor:pointer}.dsh-mm-model-picker-row input{accent-color:var(--dsw-alias-state-business-primary)}.dsh-mm-model-picker-row span{overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.dsh-mm-model-picker-row small{margin-left:auto;color:var(--dsw-alias-label-tertiary)}.dsh-mm-model-picker-empty{padding:20px 0;color:var(--dsw-alias-label-tertiary);font-size:12px;text-align:center}
          .dsh-mm-settings-overlay{z-index:1000;inset:24px}
          .dsh-mm-vision-draft{height:28px;max-width:132px;overflow:hidden;border:1px solid var(--dsw-alias-border-l2);border-radius:8px;background:transparent;color:var(--dsw-alias-label-secondary);padding:0 9px;text-overflow:ellipsis;white-space:nowrap;font-size:12px;font-weight:550;cursor:pointer}.dsh-mm-vision-draft:hover:not(:disabled){background:var(--dsw-alias-interactive-bg-hover);color:var(--dsw-alias-label-primary)}.dsh-mm-vision-draft:focus-visible{outline:2px solid var(--dsw-alias-state-business-primary);outline-offset:2px}.dsh-mm-vision-draft:disabled{cursor:default;opacity:.6}
          @media(max-width:760px){.dsh-mm-overlay{inset:52px 10px 116px}.dsh-mm-card{padding:18px 16px 0;border-radius:15px}.dsh-mm-grid{grid-template-columns:1fr;row-gap:11px}.dsh-mm-field{grid-column:1}.dsh-mm-field[data-type=boolean]{margin-top:0}.dsh-mm-actions{margin:16px -16px 0;padding:12px 16px 14px}}
           .dsh-mm-info-button{border:0;background:transparent;color:var(--dsw-alias-label-secondary);border-radius:9px;padding:6px 10px;cursor:pointer;font-size:12px;font-weight:550}.dsh-mm-info-button:hover{background:var(--dsw-alias-interactive-bg-hover);color:var(--dsw-alias-label-primary)}.dsh-mm-info-button:focus-visible{outline:2px solid var(--dsw-alias-label-tertiary);outline-offset:2px}
           .dsh-mm-hero-mark{width:34px;height:34px;border-radius:9px;object-fit:contain;display:inline-block;vertical-align:middle}
          .dsh-mm-hero-title{display:inline-flex;align-items:center}
          .dsh-mm-hero-title-img{height:34px;width:auto;display:block}
          .hHd-Xa_logoRow>.hHd-Xa_brand[data-dsh-metamath-brand=true]>svg{display:none!important}.dsh-mm-brand-lockup{display:inline-flex;align-items:center;gap:7px;color:#16181d}.dsh-mm-brand-mark{width:28px;height:28px;flex:none;border-radius:8px;object-fit:contain}.dsh-mm-brand-word{font-size:18px;font-weight:650;letter-spacing:-.04em;line-height:1}.dsh-mm-brand-chip{border-radius:4px;background:#181a20;color:#fff;padding:3px 5px 2px;font-size:9px;font-weight:750;letter-spacing:.065em;line-height:1}
          .dsh-mm-info-launcher{position:fixed;z-index:89;top:12px;right:72px;display:inline-flex;width:36px;height:36px;min-height:36px;box-sizing:border-box;align-items:center;justify-content:center;border:0;border-radius:12px;background:transparent;box-shadow:none;padding:0;line-height:1}.dsh-mm-info-launcher:hover,.dsh-mm-info-launcher[aria-expanded=true]{background:var(--dsw-alias-interactive-bg-hover);color:var(--dsw-alias-label-primary)}.dsh-mm-info-launcher svg{width:19px;height:19px}
          [data-slot="conversation.session.header.utilities"]>button[class*="_sessionLogButton"]{width:36px!important;height:36px!important;min-width:36px!important;box-sizing:border-box!important;justify-content:center!important;gap:0!important;border-radius:12px!important;padding:0!important}[data-slot="conversation.session.header.utilities"]>button[class*="_sessionLogButton"]>span{position:absolute!important;width:1px!important;height:1px!important;overflow:hidden!important;clip:rect(0 0 0 0)!important;clip-path:inset(50%)!important;white-space:nowrap!important}[data-slot="conversation.session.header.utilities"]>button[class*="_sessionLogButton"]>svg{width:16px!important;height:16px!important}
          .dsh-mm-info{position:fixed;z-index:90;top:56px;right:12px;bottom:12px;display:flex;width:min(400px,calc(100vw - 24px));box-sizing:border-box;flex-direction:column;overflow:hidden;pointer-events:auto;border:1px solid var(--dsw-alias-border-l1);border-radius:16px;background:var(--dsw-alias-bg-base);box-shadow:0 20px 52px rgba(15,23,42,.18)}
          .dsh-mm-info-head{display:flex;align-items:flex-start;gap:12px;padding:18px 18px 13px}.dsh-mm-info-heading{min-width:0;flex:1}.dsh-mm-info-heading h2{font-size:16px;line-height:1.35;margin:0;font-weight:650;letter-spacing:-.01em}.dsh-mm-info-heading p{margin:4px 0 0;color:var(--dsw-alias-label-tertiary);font-size:11px}.dsh-mm-info-close{border:0;border-radius:8px;background:transparent;color:var(--dsw-alias-label-secondary);cursor:pointer;padding:5px 7px;font-size:11px}.dsh-mm-info-close:hover{background:var(--dsw-alias-interactive-bg-hover);color:var(--dsw-alias-label-primary)}
          .dsh-mm-info-search{padding:0 18px 12px}.dsh-mm-info-search input{box-sizing:border-box;width:100%;height:36px;border:1px solid var(--dsw-alias-border-l2);border-radius:9px;outline:0;background:color-mix(in srgb,var(--dsw-alias-bg-base) 96%,var(--dsw-alias-label-primary));color:var(--dsw-alias-label-primary);padding:0 11px;font-size:12px}.dsh-mm-info-search input:focus-visible{border-color:var(--dsw-alias-state-business-primary);box-shadow:0 0 0 3px color-mix(in srgb,var(--dsw-alias-state-business-primary) 12%,transparent)}
          .dsh-mm-info-body{min-height:0;flex:1;overflow:auto;border-top:1px solid var(--dsw-alias-border-l1);padding:10px;scrollbar-width:thin}.dsh-mm-info-list-head{display:flex;justify-content:space-between;align-items:center;padding:2px 8px 8px;color:var(--dsw-alias-label-tertiary);font-size:11px}.dsh-mm-skill-list{display:flex;flex-direction:column;gap:4px}.dsh-mm-skill-item{border:1px solid transparent;border-radius:11px;background:transparent}.dsh-mm-skill-item[data-selected=true]{border-color:var(--dsw-alias-border-l1);background:color-mix(in srgb,var(--dsw-alias-interactive-bg-hover) 65%,transparent)}.dsh-mm-skill-row{display:block;width:100%;box-sizing:border-box;border:0;border-radius:10px;background:transparent;color:inherit;padding:10px;text-align:left;cursor:pointer}.dsh-mm-skill-row:hover{background:var(--dsw-alias-interactive-bg-hover)}.dsh-mm-skill-row:focus-visible{outline:2px solid var(--dsw-alias-state-business-primary);outline-offset:-2px}.dsh-mm-skill-title{display:flex;align-items:center;gap:7px}.dsh-mm-skill-title strong{min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;font-size:13px;font-weight:620}.dsh-mm-skill-current{flex:none;border-radius:999px;background:var(--dsw-alias-state-business-primary);color:white;padding:2px 6px;font-size:9px;font-weight:650}.dsh-mm-skill-name{display:block;margin-top:2px;color:var(--dsw-alias-label-tertiary);font-family:ui-monospace,SFMono-Regular,Consolas,monospace;font-size:10px}.dsh-mm-skill-summary{margin:6px 0 0;color:var(--dsw-alias-label-secondary);font-size:12px;line-height:1.48}.dsh-mm-skill-detail{display:grid;grid-template-columns:44px 1fr;gap:5px 8px;margin:0 10px 10px;padding:10px;border-top:1px solid var(--dsw-alias-border-l1);font-size:11px;line-height:1.45}.dsh-mm-skill-detail dt{color:var(--dsw-alias-label-tertiary)}.dsh-mm-skill-detail dd{margin:0;color:var(--dsw-alias-label-secondary)}.dsh-mm-info-empty{padding:36px 16px;text-align:center;color:var(--dsw-alias-label-tertiary);font-size:12px}.dsh-mm-info-status{display:grid;grid-template-columns:1fr 1fr;gap:8px;border-top:1px solid var(--dsw-alias-border-l1);padding:10px 18px;color:var(--dsw-alias-label-tertiary);font-size:10px}.dsh-mm-info-status span{overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.dsh-mm-info-status span:last-child{text-align:right}
          .dsh-mm-image-settings{margin-top:34px;padding-top:28px;border-top:1px solid var(--dsw-alias-border-l1)}.dsh-mm-image-settings-head{display:flex;align-items:flex-start;justify-content:space-between;gap:16px;margin-bottom:18px}.dsh-mm-image-settings-title{margin:0;color:var(--dsw-alias-label-primary);font-size:20px;line-height:1.4;font-weight:600}.dsh-mm-image-settings-intro{margin:6px 0 0;color:var(--dsw-alias-label-secondary);font-size:14px;line-height:1.65}.dsh-mm-active-selector{position:relative;display:flex;min-width:180px;max-width:360px;flex-direction:column;gap:5px;color:var(--dsw-alias-label-secondary);font-size:11px}.dsh-mm-active-trigger,.dsh-mm-image-provider-field select{box-sizing:border-box;width:100%;height:36px;border:1px solid var(--dsw-alias-border-l2);border-radius:9px;background:var(--dsw-alias-bg-base);color:var(--dsw-alias-label-primary);padding:0 10px;font:inherit;font-size:12px;text-align:left;cursor:pointer}.dsh-mm-active-trigger:after{content:'⌄';float:right;color:var(--dsw-alias-label-tertiary);font-size:14px}.dsh-mm-active-menu{position:absolute;z-index:1002;right:0;top:calc(100% + 6px);display:flex;width:min(360px,calc(100vw - 48px));max-height:260px;flex-direction:column;gap:4px;overflow:auto;border:1px solid var(--dsw-alias-border-l1);border-radius:12px;background:var(--dsw-alias-bg-base);box-shadow:0 12px 32px rgba(15,23,42,.16);padding:6px}.dsh-mm-active-option{min-height:34px;border:0;border-radius:8px;background:transparent;color:var(--dsw-alias-label-primary);padding:0 10px;text-align:left;font:inherit;font-size:12px;cursor:pointer}.dsh-mm-active-option:hover,.dsh-mm-active-option[aria-checked=true]{background:var(--dsw-alias-interactive-bg-hover)}.dsh-mm-active-empty{margin:8px;color:var(--dsw-alias-label-tertiary);font-size:12px}.dsh-mm-image-provider-list{display:flex;flex-direction:column;gap:12px}.dsh-mm-image-provider{overflow:hidden;border:1px solid var(--dsw-alias-border-l1);border-radius:14px;background:var(--dsw-alias-bg-base)}.dsh-mm-image-provider[data-active=true]{border-color:color-mix(in srgb,var(--dsw-alias-state-business-primary) 54%,var(--dsw-alias-border-l1))}.dsh-mm-image-provider-head{display:flex;min-height:58px;align-items:center;gap:12px;padding:0 18px}.dsh-mm-image-provider-name{font-size:15px;font-weight:560}.dsh-mm-image-provider-meta{display:flex;min-width:0;flex:1;align-items:center;gap:8px;color:var(--dsw-alias-label-tertiary);font-size:12px}.dsh-mm-image-provider-model{overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.dsh-mm-image-provider-dot{width:8px;height:8px;flex:none;border-radius:50%;background:var(--dsw-alias-label-tertiary)}.dsh-mm-image-provider-dot[data-ready=true]{background:#20b96b}.dsh-mm-image-current{border-radius:999px;background:color-mix(in srgb,var(--dsw-alias-state-business-primary) 12%,transparent);color:var(--dsw-alias-state-business-primary);padding:3px 8px;font-size:11px}.dsh-mm-image-provider-edit,.dsh-mm-image-provider-button{min-height:34px;border:1px solid var(--dsw-alias-border-l2);border-radius:9px;background:transparent;color:var(--dsw-alias-label-primary);padding:0 13px;font-size:12px;cursor:pointer}.dsh-mm-image-provider-edit:hover,.dsh-mm-image-provider-button:hover{background:var(--dsw-alias-interactive-bg-hover)}.dsh-mm-image-provider-button:disabled{cursor:not-allowed;opacity:.5}.dsh-mm-image-card-actions{display:flex;gap:8px;padding:0 18px 14px}.dsh-mm-image-provider-editor{display:grid;grid-template-columns:1fr 1fr;gap:14px 16px;border-top:1px solid var(--dsw-alias-border-l1);padding:18px}.dsh-mm-image-provider-field{display:flex;min-width:0;flex-direction:column;gap:6px;color:var(--dsw-alias-label-secondary);font-size:12px}.dsh-mm-image-provider-field[data-wide=true]{grid-column:1/-1}.dsh-mm-image-provider-field input{box-sizing:border-box;width:100%;height:38px;border:1px solid var(--dsw-alias-border-l2);border-radius:9px;outline:0;background:var(--dsw-alias-bg-base);color:var(--dsw-alias-label-primary);padding:0 11px;font-size:13px}.dsh-mm-image-provider-field input:focus-visible,.dsh-mm-image-provider-field select:focus-visible,.dsh-mm-active-trigger:focus-visible,.dsh-mm-active-option:focus-visible{border-color:var(--dsw-alias-state-business-primary);box-shadow:0 0 0 3px color-mix(in srgb,var(--dsw-alias-state-business-primary) 12%,transparent)}.dsh-mm-image-provider-hint,.dsh-mm-image-provider-verify-note{grid-column:1/-1;margin:-4px 0 0;color:var(--dsw-alias-label-tertiary);font-size:11px;line-height:1.5}.dsh-mm-image-provider-actions{display:flex;grid-column:1/-1;justify-content:flex-end;gap:8px}.dsh-mm-image-provider-button[data-primary=true]{border-color:var(--dsw-alias-state-business-primary);background:var(--dsw-alias-state-business-primary);color:#fff}.dsh-mm-image-provider-message{grid-column:1/-1;margin:0;color:var(--dsw-alias-label-secondary);font-size:12px}.dsh-mm-image-settings-state{padding:24px 0;color:var(--dsw-alias-label-secondary);font-size:13px}.dsh-mm-image-settings-state[data-error=true]{color:var(--dsw-alias-state-error-primary)}.dsh-mm-image-add{align-self:flex-start}.dsh-mm-image-confirm{position:fixed;z-index:1010;left:50%;top:50%;width:min(420px,calc(100vw - 32px));transform:translate(-50%,-50%);border:1px solid var(--dsw-alias-border-l1);border-radius:14px;background:var(--dsw-alias-bg-base);box-shadow:0 18px 52px rgba(15,23,42,.24);padding:18px}.dsh-mm-image-confirm p{margin:9px 0 16px;color:var(--dsw-alias-label-secondary);font-size:12px;line-height:1.6}.dsh-mm-image-confirm .dsh-mm-image-provider-actions{display:flex}.dsh-mm-model-picker{display:flex;max-height:240px;flex-direction:column;gap:7px;overflow:auto;margin-bottom:14px}
          @media(max-width:760px){.dsh-mm-info{top:56px;right:6px;bottom:6px;width:calc(100vw - 12px)}.dsh-mm-info-status{grid-template-columns:1fr}.dsh-mm-info-status span:last-child{text-align:left}}
          .dsh-mm-active-selector{position:relative;flex:none;min-width:0;max-width:360px}.dsh-mm-active-selector-button{display:inline-flex;align-items:center;gap:7px;width:100%;min-height:34px;box-sizing:border-box;border:1px solid var(--dsw-alias-border-l2);border-radius:9px;background:transparent;color:var(--dsw-alias-label-primary);padding:0 11px;font-size:12px;cursor:pointer;overflow:hidden}.dsh-mm-active-selector-button:hover{background:var(--dsw-alias-interactive-bg-hover)}.dsh-mm-active-selector-button:focus-visible{outline:2px solid var(--dsw-alias-state-business-primary);outline-offset:2px}.dsh-mm-active-selector-dot{width:8px;height:8px;flex:none;border-radius:50%;background:var(--dsw-alias-label-tertiary)}.dsh-mm-active-selector-dot[data-ready=true]{background:#20b96b}.dsh-mm-active-selector-label{overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.dsh-mm-active-selector-caret{flex:none;color:var(--dsw-alias-label-tertiary)}.dsh-mm-active-menu{position:fixed;z-index:1200;display:flex;width:min(360px,calc(100vw - 24px));max-height:min(320px,60vh);flex-direction:column;gap:4px;overflow:auto;box-sizing:border-box;border:1px solid var(--dsw-alias-border-l1);border-radius:12px;background:var(--dsw-alias-bg-base);box-shadow:0 18px 46px rgba(15,23,42,.18);padding:8px;scrollbar-width:thin}.dsh-mm-active-menu-option{display:flex;align-items:center;gap:8px;min-height:36px;border:0;border-radius:9px;background:transparent;color:var(--dsw-alias-label-primary);padding:0 10px;font-size:12px;text-align:left;cursor:pointer}.dsh-mm-active-menu-option:hover,.dsh-mm-active-menu-option[aria-selected=true]{background:var(--dsw-alias-interactive-bg-hover)}.dsh-mm-active-menu-option:focus-visible{outline:2px solid var(--dsw-alias-state-business-primary);outline-offset:-2px}.dsh-mm-active-menu-name{overflow:hidden;text-overflow:ellipsis;white-space:nowrap;font-weight:550}.dsh-mm-active-menu-meta{margin-left:auto;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;color:var(--dsw-alias-label-tertiary);font-size:11px}.dsh-mm-active-menu-check{flex:none;color:var(--dsw-alias-state-business-primary);font-weight:700}.dsh-mm-active-menu-empty{padding:16px 10px;color:var(--dsw-alias-label-tertiary);font-size:12px;text-align:center}.dsh-mm-image-add{display:block;width:100%;box-sizing:border-box;min-height:40px;margin-top:12px;border:1px dashed var(--dsw-alias-border-l2);border-radius:12px;background:transparent;color:var(--dsw-alias-label-secondary);font-size:13px;font-weight:550;cursor:pointer}.dsh-mm-image-add:hover{background:var(--dsw-alias-interactive-bg-hover);color:var(--dsw-alias-label-primary)}.dsh-mm-image-provider-capability{display:inline-flex;align-items:center;gap:6px;color:var(--dsw-alias-label-secondary);font-size:12px}.dsh-mm-image-provider-capability[data-capability=ready]{color:#1a8f56}.dsh-mm-image-provider-active{flex:none;border-radius:999px;background:var(--dsw-alias-state-business-primary);color:white;padding:3px 8px;font-size:11px;font-weight:600}.dsh-mm-image-provider-field select{box-sizing:border-box;width:100%;height:38px;border:1px solid var(--dsw-alias-border-l2);border-radius:9px;outline:0;background:var(--dsw-alias-bg-base);color:var(--dsw-alias-label-primary);padding:0 9px;font-size:13px}.dsh-mm-image-provider-field select:focus-visible{border-color:var(--dsw-alias-state-business-primary);box-shadow:0 0 0 3px color-mix(in srgb,var(--dsw-alias-state-business-primary) 12%,transparent)}.dsh-mm-image-provider-verify-note{grid-column:1/-1;margin:0;color:#b45309;font-size:11px;line-height:1.5}.dsh-mm-image-confirm{border-top:1px solid var(--dsw-alias-border-l1);padding:14px 18px;display:flex;flex-direction:column;gap:10px;align-items:flex-start;color:var(--dsw-alias-label-secondary);font-size:12px}.dsh-mm-image-confirm-actions{display:flex;flex-wrap:wrap;gap:8px}.dsh-mm-image-danger{border-color:var(--dsw-alias-state-error-primary)!important;color:var(--dsw-alias-state-error-primary)!important}.dsh-mm-image-provider-message[data-error=true]{color:var(--dsw-alias-state-error-primary)}
          @media(max-width:700px){.dsh-mm-image-settings{margin-top:26px;padding-top:22px}.dsh-mm-image-settings-head{display:block}.dsh-mm-image-provider-head{padding:0 14px}.dsh-mm-image-provider-meta{display:none}.dsh-mm-image-provider-editor{grid-template-columns:1fr;padding:14px}.dsh-mm-image-provider-field,.dsh-mm-image-provider-field[data-wide=true],.dsh-mm-image-provider-actions{grid-column:1}.dsh-mm-active-selector{max-width:none;margin-top:14px}.dsh-mm-active-menu{position:fixed;left:12px!important;right:12px!important;top:auto!important;bottom:12px;width:auto;max-height:70vh;border-radius:16px}.dsh-mm-image-confirm{padding:12px 14px}}
        `;
        document.head.appendChild(style);
      }

      function installMetaMathBrand() {
        const brand = document.querySelector('.hHd-Xa_logoRow > button.hHd-Xa_brand.hHd-Xa_wide');
        if (!brand || brand.dataset.dshMetamathBrand === 'true') return;
        const officialMark = brand.querySelector('svg[width="182"][height="24"]');
        if (!officialMark) return;
        const lockup = document.createElement('span');
        lockup.className = 'dsh-mm-brand-lockup';
        lockup.setAttribute('aria-hidden', 'true');
        const mark = document.createElement('img');
        mark.className = 'dsh-mm-brand-mark';
        mark.src = metaMathBrandMark;
        mark.alt = '';
        const word = document.createElement('span');
        word.className = 'dsh-mm-brand-word';
        word.textContent = 'MetaMath';
        const chip = document.createElement('span');
        chip.className = 'dsh-mm-brand-chip';
        chip.textContent = 'HARNESS';
        lockup.append(mark, word, chip);
        brand.appendChild(lockup);
        brand.dataset.dshMetamathBrand = 'true';
      }
      installMetaMathBrand();
      new MutationObserver(installMetaMathBrand).observe(document.documentElement, { childList: true, subtree: true });

      // 中央主视觉（hero）鲸鱼图标替换为 MetaMath 四象限鲸鱼标记（GOAL-19 同款运行时覆盖思路）
      function installMetaMathHeroMark() {
        const hitbox = document.querySelector('span[class*="_fishHitbox"]');
        if (!hitbox || hitbox.dataset.dshMetamathHero === 'true') return;
        const officialFish = hitbox.querySelector('svg');
        if (!officialFish) return;
        officialFish.style.display = 'none';
        const mark = document.createElement('img');
        mark.className = 'dsh-mm-hero-mark';
        mark.src = metaMathHeroMark;
        mark.alt = '';
        mark.setAttribute('aria-hidden', 'true');
        hitbox.appendChild(mark);
        hitbox.dataset.dshMetamathHero = 'true';
      }
      installMetaMathHeroMark();
      new MutationObserver(installMetaMathHeroMark).observe(document.documentElement, { childList: true, subtree: true });

      // 中央主标题替换为“大道至简”金属艺术字图（透明底），并移除“预览版”徽章（GOAL-33）
      function installMetaMathHeroTitle() {
        const headline = document.querySelector('span[class*="_headlineText"]');
        if (headline && headline.dataset.dshMetamathTitle !== 'true') {
          headline.textContent = '';
          headline.classList.add('dsh-mm-hero-title');
          const titleImg = document.createElement('img');
          titleImg.className = 'dsh-mm-hero-title-img';
          titleImg.src = metaMathHeroTitle;
          titleImg.alt = '大道至简';
          headline.appendChild(titleImg);
          headline.dataset.dshMetamathTitle = 'true';
          const row = headline.parentElement;
          if (row && row.dataset.dshMetamathTitleRow !== 'true') {
            row.style.gridTemplateColumns = '34px auto';
            row.dataset.dshMetamathTitleRow = 'true';
          }
        }
        const badge = document.querySelector('span[class*="_previewBadge"]');
        if (badge && badge.dataset.dshMetamathBadge !== 'true') {
          badge.style.display = 'none';
          badge.dataset.dshMetamathBadge = 'true';
        }
      }
      installMetaMathHeroTitle();
      new MutationObserver(installMetaMathHeroTitle).observe(document.documentElement, { childList: true, subtree: true });

      function MathmodelInfo({ flow, sessionId, loadSkillHelp, floating = false }) {
        const state = React.useSyncExternalStore(flow.subscribe, flow.getSnapshot, flow.getSnapshot);
        const [open, setOpen] = React.useState(false);
        const [skills, setSkills] = React.useState([]);
        const [query, setQuery] = React.useState('');
        const [selectedSkill, setSelectedSkill] = React.useState(null);
        const [loadState, setLoadState] = React.useState('idle');
        const buttonRef = React.useRef(null);
        const card = state.activeSessionId === sessionId ? state.activeCard : null;
        const activeSkill = card?.skill ?? null;
        const panelId = `dsh-mm-info-${sessionId}`;
        const closePanel = () => {
          setOpen(false);
          queueMicrotask(() => buttonRef.current?.focus());
        };
        React.useEffect(() => {
          if (!open) return undefined;
          const onKeyDown = (event) => {
            if (event.key === 'Escape') {
              event.preventDefault();
              closePanel();
            }
          };
          document.addEventListener('keydown', onKeyDown);
          return () => document.removeEventListener('keydown', onKeyDown);
        }, [open]);
        React.useEffect(() => {
          if (!open || typeof loadSkillHelp !== 'function') return undefined;
          let active = true;
          setLoadState('loading');
          loadSkillHelp().then((result) => {
            if (!active) return;
            setSkills(result.skills);
            setSelectedSkill((current) => activeSkill ?? current ?? result.skills[0]?.skill ?? null);
            setLoadState('ready');
          }).catch(() => { if (active) setLoadState('error'); });
          return () => { active = false; };
        }, [open, loadSkillHelp, activeSkill]);
        React.useEffect(() => { if (activeSkill) setSelectedSkill(activeSkill); }, [activeSkill]);
        React.useEffect(() => {
          if (!floating) return undefined;
          const button = document.querySelector('[data-slot="conversation.session.header.utilities"] > button[class*="_sessionLogButton"]');
          if (!button) return undefined;
          const previousLabel = button.getAttribute('aria-label');
          const previousTitle = button.getAttribute('title');
          button.setAttribute('aria-label', '下载会话日志');
          button.setAttribute('title', '下载会话日志');
          return () => {
            if (previousLabel === null) button.removeAttribute('aria-label'); else button.setAttribute('aria-label', previousLabel);
            if (previousTitle === null) button.removeAttribute('title'); else button.setAttribute('title', previousTitle);
          };
        }, [floating, sessionId]);
        const normalizedQuery = query.trim().toLocaleLowerCase('zh-CN');
        const visibleSkills = skills.filter((skill) => !normalizedQuery || [skill.skill, skill.title, skill.summary, skill.category]
          .some((value) => value.toLocaleLowerCase('zh-CN').includes(normalizedQuery)))
          .sort((left, right) => Number(right.skill === activeSkill) - Number(left.skill === activeSkill));
        const environment = state.status?.preflight?.status === 'ready' ? '环境已就绪' : state.status?.preflight ? '环境需检查' : '环境未检测';
        const providers = state.status?.providers?.summary ?? '生图凭据未检测';
        const panel = open ? ReactDOM.createPortal(React.createElement('aside', {
          id: panelId, className: 'dsh-mm-info', role: 'complementary', 'aria-labelledby': `${panelId}-title`,
        },
        React.createElement('div', { className: 'dsh-mm-info-head' },
          React.createElement('div', { className: 'dsh-mm-info-heading' },
            React.createElement('h2', { id: `${panelId}-title` }, '技能说明'),
            React.createElement('p', null, `${skills.length || 15} 个 Skill · 点击查看简单说明`),
          ),
          React.createElement('button', { type: 'button', className: 'dsh-mm-info-close', 'aria-label': '收起 Skill 说明', onClick: closePanel }, '收起'),
        ),
        React.createElement('div', { className: 'dsh-mm-info-search' }, React.createElement('input', {
          type: 'search', value: query, 'aria-label': '搜索 Skill', placeholder: '搜索 Skill 名称或用途', onChange: (event) => setQuery(event.target.value),
        })),
        React.createElement('div', { className: 'dsh-mm-info-body' },
          React.createElement('div', { className: 'dsh-mm-info-list-head' },
            React.createElement('span', null, normalizedQuery ? '搜索结果' : '全部 Skill'),
            React.createElement('span', null, `${visibleSkills.length} 项`),
          ),
          loadState === 'loading' ? React.createElement('div', { className: 'dsh-mm-info-empty', role: 'status' }, '正在读取 Skill…') : null,
          loadState === 'error' ? React.createElement('div', { className: 'dsh-mm-info-empty', role: 'alert' }, '暂时无法读取 Skill 说明，请稍后重试。') : null,
          loadState === 'ready' && visibleSkills.length === 0 ? React.createElement('div', { className: 'dsh-mm-info-empty' }, '没有找到匹配的 Skill。') : null,
          React.createElement('div', { className: 'dsh-mm-skill-list' }, visibleSkills.map((skill) => {
            const selected = skill.skill === selectedSkill;
            return React.createElement('article', { className: 'dsh-mm-skill-item', 'data-selected': selected, key: skill.skill },
              React.createElement('button', { type: 'button', className: 'dsh-mm-skill-row', 'aria-expanded': selected, onClick: () => setSelectedSkill(selected ? null : skill.skill) },
                React.createElement('span', { className: 'dsh-mm-skill-title' },
                  React.createElement('strong', null, skill.title),
                  skill.skill === activeSkill ? React.createElement('span', { className: 'dsh-mm-skill-current' }, '当前') : null,
                ),
                React.createElement('span', { className: 'dsh-mm-skill-name' }, `/${skill.skill}`),
                React.createElement('p', { className: 'dsh-mm-skill-summary' }, skill.summary),
              ),
              selected ? React.createElement('dl', { className: 'dsh-mm-skill-detail' },
                React.createElement('dt', null, '适合'), React.createElement('dd', null, skill.useWhen),
                React.createElement('dt', null, '得到'), React.createElement('dd', null, skill.output),
              ) : null,
            );
          })),
        ),
        React.createElement('div', { className: 'dsh-mm-info-status' }, React.createElement('span', null, environment), React.createElement('span', null, providers)),
        ), document.body) : null;
        return React.createElement(React.Fragment, null,
          React.createElement('button', {
            ref: buttonRef, type: 'button', className: `dsh-mm-info-button${floating ? ' dsh-mm-info-launcher' : ''}`, 'aria-expanded': open, 'aria-controls': panelId,
            onClick: () => setOpen((value) => !value), title: '技能说明', 'aria-label': '技能说明',
          }, floating ? React.createElement('svg', { viewBox: '0 0 20 20', fill: 'none', 'aria-hidden': 'true' },
            React.createElement('circle', { cx: '4.5', cy: '5', r: '1.7', stroke: 'currentColor', strokeWidth: '1.5' }),
            React.createElement('circle', { cx: '4.5', cy: '10', r: '1.7', stroke: 'currentColor', strokeWidth: '1.5' }),
            React.createElement('circle', { cx: '4.5', cy: '15', r: '1.7', stroke: 'currentColor', strokeWidth: '1.5' }),
            React.createElement('path', { d: 'M9 5h7M9 10h7M9 15h7', stroke: 'currentColor', strokeWidth: '1.5', strokeLinecap: 'round' }),
          ) : '技能说明'),
          panel,
        );
      }

      function CredentialField({ field, value, actions }) {
        const [secret, setSecret] = React.useState('');
        const [message, setMessage] = React.useState('');
        React.useEffect(() => {
          let active = true;
          actions.describe(field.id).catch((error) => { if (active) setMessage(error instanceof Error ? error.message : String(error)); });
          return () => { active = false; };
        }, [actions, field.id]);
        const save = async () => {
          setMessage('');
          try {
            await actions.set(field.id, secret);
            setSecret('');
            setMessage('配置已保存，卡片其他内容保持不变。');
          } catch (error) { setMessage(error instanceof Error ? error.message : String(error)); }
        };
        return React.createElement('div', null,
          React.createElement('div', { role: 'status', 'aria-live': 'polite' }, value || '未检测'),
          React.createElement('input', { type: 'password', value: secret, autoComplete: 'new-password', placeholder: '输入 Key（不会写入 Prompt）', onChange: (event) => setSecret(event.target.value) }),
          React.createElement('div', { className: 'dsh-mm-actions' },
            React.createElement('button', { type: 'button', disabled: !secret, onClick: save }, '安全保存'),
            React.createElement('button', { type: 'button', onClick: () => actions.unset(field.id) }, '清除受管 Key'),
          ),
          message ? React.createElement('small', { role: 'status' }, message) : null,
        );
      }

      function useModelsSettingsHost() {
        const [host, setHost] = React.useState(null);
        React.useEffect(() => {
          const locate = () => {
            const dialog = document.querySelector('[role="dialog"][aria-modal="true"]');
            const title = dialog && [...dialog.querySelectorAll('h2')].find((node) => ['模型', 'Models'].includes(node.textContent?.trim()));
            const section = title?.parentElement;
            if (!section) return null;
            let mount = section.querySelector(':scope > [data-dsh-mathmodel-image-settings]');
            if (!mount) {
              mount = document.createElement('div');
              mount.dataset.dshMathmodelImageSettings = 'true';
              section.appendChild(mount);
            }
            return mount;
          };
          const sync = () => setHost((current) => locate() ?? (current?.isConnected ? current : null));
          sync();
          const observer = new MutationObserver(sync);
          observer.observe(document.body, { childList: true, subtree: true });
          return () => { observer.disconnect(); document.querySelector('[data-dsh-mathmodel-image-settings]')?.remove(); };
        }, []);
        return host;
      }

      function ImageConnectionSettings({ actions }) {
        const host = useModelsSettingsHost();
        const [state, setState] = React.useState({ status: 'idle', data: null, error: '' });
        const [editing, setEditing] = React.useState(null);
        const [confirmRemove, setConfirmRemove] = React.useState(null);
        const [verifyTarget, setVerifyTarget] = React.useState(null);
        const [discover, setDiscover] = React.useState(null);
        const [busy, setBusy] = React.useState(false);
        const [message, setMessage] = React.useState('');
        const [pickerOpen, setPickerOpen] = React.useState(false);
        const pickerButtonRef = React.useRef(null);
        const load = React.useCallback(async () => {
          setState((current) => ({ ...current, status: 'loading', error: '' }));
          try { setState({ status: 'ready', data: await actions.load(), error: '' }); }
          catch (error) { setState({ status: 'error', data: null, error: error instanceof Error ? error.message : String(error) }); }
        }, [actions]);
        React.useEffect(() => { if (host && state.status === 'idle') load(); }, [host, state.status, load]);
        if (!host) return null;
        const refresh = async () => {
          const data = await actions.load();
          setState({ status: 'ready', data, error: '' });
          return data;
        };
        const run = async (task, successMessage) => {
          setBusy(true); setMessage('');
          try {
            await task();
            if (successMessage) setMessage(successMessage);
          } catch (error) { setMessage(error instanceof Error ? error.message : String(error)); }
          finally { setBusy(false); }
        };
        const emptyDraft = (templateId) => {
          const meta = templateMeta(templateId) ?? IMAGE_TEMPLATE_META[0];
          return { name: '', template: meta.id, adapter: meta.defaultAdapter, model: meta.defaultModel, baseUrl: meta.defaultBaseUrl ?? '', secret: '' };
        };
        const openCreate = () => { setMessage(''); setEditing({ id: null, draft: emptyDraft('openai-compatible') }); };
        const openEdit = (item) => {
          setMessage('');
          setEditing({ id: item.id, draft: { name: item.name, template: item.template, adapter: item.adapter, model: item.model, baseUrl: item.baseUrl, secret: '' } });
        };
        const openCopy = (item) => {
          setMessage('');
          setEditing({ id: null, draft: { name: `${item.name}（副本）`, template: item.template, adapter: item.adapter, model: item.model, baseUrl: item.baseUrl, secret: '' } });
        };
        const patchDraft = (patch) => setEditing((current) => current ? { ...current, draft: { ...current.draft, ...patch } } : current);
        const changeTemplate = (templateId) => {
          const meta = templateMeta(templateId);
          setEditing((current) => {
            if (!current) return current;
            const previous = templateMeta(current.draft.template);
            const draft = {
              ...current.draft,
              template: templateId,
              adapter: meta.adapters.includes(current.draft.adapter) ? current.draft.adapter : meta.defaultAdapter,
              model: current.draft.model || meta.defaultModel,
              baseUrl: meta.baseUrlEditable ? (current.draft.baseUrl === '' || (previous?.baseUrlEditable && current.draft.baseUrl === previous.defaultBaseUrl) ? meta.defaultBaseUrl ?? '' : current.draft.baseUrl) : '',
            };
            return { ...current, draft };
          });
        };
        const save = async () => {
          if (!editing) return;
          const { id, draft } = editing;
          const meta = templateMeta(draft.template);
          const payload = { name: String(draft.name ?? '').trim(), template: draft.template, adapter: draft.adapter, model: String(draft.model ?? '').trim() };
          if (meta.baseUrlEditable) payload.baseUrl = String(draft.baseUrl ?? '').trim();
          await run(async () => {
            const saved = await actions.save(payload, id);
            if (String(draft.secret ?? '').trim()) await actions.setKey(saved.id, String(draft.secret).trim());
            await refresh();
            setEditing(null);
          }, '连接已保存。');
        };
        const doVerify = async (id) => {
          setVerifyTarget(null);
          await run(async () => { await actions.verify(id); await refresh(); }, '真实测试完成，已更新验证状态。');
        };
        const doSetActive = async (id) => {
          await run(async () => { await actions.setActive(id); await refresh(); }, '已切换当前生图连接。');
        };
        const doRemove = async (id, clearCredential) => {
          setConfirmRemove(null);
          await run(async () => { await actions.remove(id, clearCredential); await refresh(); }, clearCredential ? '连接已删除，Key 已清除。' : '连接已删除（Key 已保留）。');
        };
        const doClearKey = async (id) => {
          await run(async () => { await actions.clearKey(id); await refresh(); }, '该连接受管 Key 已清除，验证状态已失效。');
        };
        const doDiscover = async (id, name) => {
          setDiscover({ id, name, status: 'loading', models: [], error: '' });
          try {
            const result = await actions.discover(id);
            setDiscover((current) => current?.id === id ? { ...current, status: 'ready', models: result.models ?? [], error: '' } : current);
          } catch (error) {
            setDiscover((current) => current?.id === id ? { ...current, status: 'error', error: error instanceof Error ? error.message : String(error) } : current);
          }
        };
        const editorMarkup = editing ? (() => {
          const meta = templateMeta(editing.draft.template);
          const existing = state.data?.connections?.find((item) => item.id === editing.id);
          const configured = existing?.credential?.configured === true;
          const editable = !busy;
          return React.createElement('div', { className: 'dsh-mm-image-provider-editor', role: 'group', 'aria-label': '编辑生图连接' },
            React.createElement('label', { className: 'dsh-mm-image-provider-field', 'data-wide': true }, React.createElement('span', null, '显示名称'), React.createElement('input', { value: editing.draft.name, maxLength: 64, placeholder: '例如：火山正式 / Sub2API 测试', onChange: (event) => patchDraft({ name: event.target.value }) })),
            React.createElement('label', { className: 'dsh-mm-image-provider-field' }, React.createElement('span', null, '供应商模板'), React.createElement('select', { value: editing.draft.template, onChange: (event) => changeTemplate(event.target.value) }, IMAGE_TEMPLATE_META.map((item) => React.createElement('option', { key: item.id, value: item.id }, item.name)))),
            React.createElement('label', { className: 'dsh-mm-image-provider-field' }, React.createElement('span', null, '接口格式'), React.createElement('select', { value: editing.draft.adapter, onChange: (event) => patchDraft({ adapter: event.target.value }) }, meta.adapters.map((adapter) => React.createElement('option', { key: adapter, value: adapter }, ADAPTER_LABELS[adapter] ?? adapter)))),
            React.createElement('label', { className: 'dsh-mm-image-provider-field', 'data-wide': meta.baseUrlEditable }, React.createElement('span', null, '模型'), React.createElement('input', { value: editing.draft.model, maxLength: 160, placeholder: meta.defaultModel || '模型 ID', onChange: (event) => patchDraft({ model: event.target.value }) })),
            meta.baseUrlEditable ? React.createElement('label', { className: 'dsh-mm-image-provider-field', 'data-wide': true }, React.createElement('span', null, 'Base URL'), React.createElement('input', { type: 'url', value: editing.draft.baseUrl, maxLength: 2048, placeholder: 'https://example.com/v1', onChange: (event) => patchDraft({ baseUrl: event.target.value }) })) : null,
            React.createElement('label', { className: 'dsh-mm-image-provider-field', 'data-wide': true }, React.createElement('span', null, configured ? 'API Key（留空保持原 Key）' : 'API Key'), React.createElement('input', { type: 'password', autoComplete: 'new-password', value: editing.draft.secret, placeholder: configured ? '留空保持原 Key' : '输入 Key（只写入受管存储）', onChange: (event) => patchDraft({ secret: event.target.value }) })),
            React.createElement('p', { className: 'dsh-mm-image-provider-hint' }, meta.hint),
            React.createElement('p', { className: 'dsh-mm-image-provider-verify-note' }, '“真实测试”会发送一次最小生图请求，可能产生供应商费用；只有测试成功后才能设为当前，测试结果不会写入工作区。'),
            message ? React.createElement('p', { className: 'dsh-mm-image-provider-message', role: 'status' }, message) : null,
            React.createElement('div', { className: 'dsh-mm-image-provider-actions' },
              editing.id ? React.createElement('button', { type: 'button', className: 'dsh-mm-image-provider-button', disabled: !editable, onClick: () => doDiscover(editing.id, editing.draft.name || '该连接') }, '获取可用模型') : null,
              configured && editing.id ? React.createElement('button', { type: 'button', className: 'dsh-mm-image-provider-button', disabled: !editable, onClick: () => doClearKey(editing.id) }, '清除 Key') : null,
              React.createElement('button', { type: 'button', className: 'dsh-mm-image-provider-button', disabled: !editable, onClick: () => setEditing(null) }, '取消'),
              React.createElement('button', { type: 'button', className: 'dsh-mm-image-provider-button', 'data-primary': true, disabled: !editable, onClick: save }, busy ? '保存中…' : '保存')),
          );
        })() : null;
        const connections = state.data?.connections ?? [];
        const activeId = state.data?.activeConnectionId ?? '';
        const legacyFallback = state.data?.legacyFallback === true;
        const selected = connections.find((item) => item.id === activeId);
        const connectionCard = (item) => {
          const isActive = item.id === activeId;
          const isEditing = editing?.id === item.id;
          const canActivate = item.capability === 'ready';
          return React.createElement('article', { className: 'dsh-mm-image-provider', key: item.id, 'data-active': isActive },
            React.createElement('div', { className: 'dsh-mm-image-provider-head' },
              React.createElement('span', { className: 'dsh-mm-image-provider-name' }, item.name),
              React.createElement('span', { className: 'dsh-mm-image-provider-meta' },
                React.createElement('span', { className: 'dsh-mm-image-provider-dot', 'data-ready': canActivate, 'aria-label': capabilityLabel(item.capability), title: capabilityLabel(item.capability) }),
                React.createElement('span', { className: 'dsh-mm-image-provider-model' }, `${item.model} · ${templateMeta(item.template)?.name ?? item.template} · ${capabilityLabel(item.capability)}`)),
              isActive ? React.createElement('span', { className: 'dsh-mm-image-current' }, '当前') : null,
              React.createElement('button', { type: 'button', className: 'dsh-mm-image-provider-edit', disabled: legacyFallback, 'aria-expanded': isEditing, onClick: () => openEdit(item) }, isEditing ? '收起' : '编辑')),
            React.createElement('div', { className: 'dsh-mm-image-card-actions' },
              !isActive ? React.createElement('button', { type: 'button', className: 'dsh-mm-image-provider-button', disabled: legacyFallback || busy || !canActivate, title: canActivate ? '设为当前生图连接' : '需先保存 Key 并通过真实测试', onClick: () => doSetActive(item.id) }, '设为当前') : null,
              React.createElement('button', { type: 'button', className: 'dsh-mm-image-provider-button', disabled: legacyFallback || busy || !item.credential?.configured, onClick: () => setVerifyTarget(item), title: '将发送一次最小真实生图请求，可能产生费用' }, '真实测试'),
              React.createElement('button', { type: 'button', className: 'dsh-mm-image-provider-button', disabled: legacyFallback || busy, onClick: () => openCopy(item) }, '复制'),
              React.createElement('button', { type: 'button', className: 'dsh-mm-image-provider-button', disabled: legacyFallback || busy, onClick: () => setConfirmRemove(item) }, '删除')),
            isEditing ? editorMarkup : null);
        };
        const readyConnections = connections.filter((item) => item.capability === 'ready');
        const pickerId = 'dsh-mm-active-connection-menu';
        const closePicker = () => { setPickerOpen(false); pickerButtonRef.current?.focus(); };
        const selectConnection = (id) => { setPickerOpen(false); doSetActive(id); };
        const pickerKeyDown = (event) => {
          if (event.key === 'Escape') { event.preventDefault(); closePicker(); }
          if (['Enter', ' '].includes(event.key)) { event.preventDefault(); setPickerOpen((open) => !open); }
          if (event.key === 'ArrowDown' || event.key === 'ArrowUp') { event.preventDefault(); setPickerOpen(true); }
        };
        const picker = React.createElement('div', { className: 'dsh-mm-active-selector' },
          React.createElement('span', { id: 'dsh-mm-active-connection-label' }, '当前连接'),
          React.createElement('button', { ref: pickerButtonRef, type: 'button', className: 'dsh-mm-active-trigger', disabled: legacyFallback || busy, 'aria-labelledby': 'dsh-mm-active-connection-label', 'aria-expanded': pickerOpen, 'aria-controls': pickerId, onClick: () => setPickerOpen((open) => !open), onKeyDown: pickerKeyDown }, selected?.name ?? '选择已验证连接'),
          pickerOpen ? React.createElement('div', { id: pickerId, className: 'dsh-mm-active-menu', role: 'radiogroup', 'aria-label': '选择当前生图连接', onKeyDown: (event) => { if (event.key === 'Escape') { event.preventDefault(); closePicker(); } } },
            readyConnections.length ? readyConnections.map((item) => React.createElement('button', { type: 'button', role: 'radio', key: item.id, className: 'dsh-mm-active-option', 'aria-checked': item.id === activeId, onClick: () => selectConnection(item.id), onKeyDown: (event) => { if (['Enter', ' '].includes(event.key)) { event.preventDefault(); selectConnection(item.id); } } }, `${item.name}${item.id === activeId ? '（当前）' : ''}`)) : React.createElement('p', { className: 'dsh-mm-active-empty' }, '先完成配置并验证')) : null);
        const confirmation = verifyTarget ? React.createElement('div', { className: 'dsh-mm-image-confirm', role: 'dialog', 'aria-modal': true, 'aria-label': '确认真实测试' },
          React.createElement('strong', null, `测试“${verifyTarget.name}”`),
          React.createElement('p', null, '将发送一次最小真实生图请求，可能产生供应商费用。测试不会写入工作区。'),
          React.createElement('div', { className: 'dsh-mm-image-provider-actions' },
            React.createElement('button', { type: 'button', className: 'dsh-mm-image-provider-button', onClick: () => setVerifyTarget(null) }, '取消'),
            React.createElement('button', { type: 'button', className: 'dsh-mm-image-provider-button', 'data-primary': true, onClick: () => doVerify(verifyTarget.id) }, '确认测试'))) : null;
        const removal = confirmRemove ? React.createElement('div', { className: 'dsh-mm-image-confirm', role: 'dialog', 'aria-modal': true, 'aria-label': '确认删除生图连接' },
          React.createElement('strong', null, `删除“${confirmRemove.name}”`),
          React.createElement('p', null, '默认仅删除连接，保留受管 Key，方便日后重新添加。'),
          React.createElement('div', { className: 'dsh-mm-image-provider-actions' },
            React.createElement('button', { type: 'button', className: 'dsh-mm-image-provider-button', onClick: () => setConfirmRemove(null) }, '取消'),
            React.createElement('button', { type: 'button', className: 'dsh-mm-image-provider-button', onClick: () => doRemove(confirmRemove.id, false) }, '仅删除连接'),
            React.createElement('button', { type: 'button', className: 'dsh-mm-image-provider-button', 'data-primary': true, onClick: () => doRemove(confirmRemove.id, true) }, '删除并清除 Key'))) : null;
        const discovered = discover ? React.createElement('div', { className: 'dsh-mm-image-confirm', role: 'dialog', 'aria-modal': true, 'aria-label': '可用模型' },
          React.createElement('strong', null, `${discover.name} 的可用模型`),
          discover.status === 'loading' ? React.createElement('p', null, '正在获取模型…') : null,
          discover.status === 'error' ? React.createElement('p', { role: 'alert' }, discover.error) : null,
          discover.status === 'ready' ? React.createElement('div', { className: 'dsh-mm-model-picker' }, discover.models.length ? discover.models.map((model) => React.createElement('button', { type: 'button', className: 'dsh-mm-image-provider-button', key: model.id, onClick: () => { patchDraft({ model: model.id }); setDiscover(null); } }, model.name ? `${model.name} (${model.id})` : model.id)) : React.createElement('p', null, '接口未返回可用模型；可继续手动填写模型。')) : null,
          React.createElement('div', { className: 'dsh-mm-image-provider-actions' }, React.createElement('button', { type: 'button', className: 'dsh-mm-image-provider-button', onClick: () => setDiscover(null) }, '关闭'))) : null;
        return ReactDOM.createPortal(React.createElement('section', { className: 'dsh-mm-image-settings', 'aria-labelledby': 'dsh-mm-image-settings-title' },
          React.createElement('div', { className: 'dsh-mm-image-settings-head' },
            React.createElement('div', null, React.createElement('h2', { id: 'dsh-mm-image-settings-title', className: 'dsh-mm-image-settings-title' }, '生图模型'), React.createElement('p', { className: 'dsh-mm-image-settings-intro' }, '独立于对话模型，所有模式均可通过 /ai-draw-skills 或 image_generate 使用。')),
            picker),
          ['idle', 'loading'].includes(state.status) ? React.createElement('div', { className: 'dsh-mm-image-settings-state', role: 'status' }, '正在读取生图配置…') : null,
          state.status === 'error' ? React.createElement('div', { className: 'dsh-mm-image-settings-state', 'data-error': true, role: 'alert' }, state.error) : null,
          state.status === 'ready' ? React.createElement('div', { className: 'dsh-mm-image-provider-list' },
            legacyFallback ? React.createElement('p', { className: 'dsh-mm-image-provider-message', role: 'status' }, state.data.summary) : null,
            connections.map(connectionCard),
            editing?.id === null ? React.createElement('article', { className: 'dsh-mm-image-provider' }, editorMarkup) : null,
            React.createElement('button', { type: 'button', className: 'dsh-mm-image-provider-button dsh-mm-image-add', disabled: legacyFallback || busy, onClick: openCreate }, '＋ 添加生图连接'),
            message ? React.createElement('p', { className: 'dsh-mm-image-provider-message', role: 'status' }, message) : null) : null,
          confirmation, removal, discovered), host);
      }

      function OpenCodeRtAddProvider({ actions }) {
        const [host, setHost] = React.useState(null);
        const [open, setOpen] = React.useState(false);
        const [apiKey, setApiKey] = React.useState('');
        const [busy, setBusy] = React.useState(false);
        const [message, setMessage] = React.useState('');
        const selectRef = React.useRef(null);
        React.useEffect(() => {
          const locate = () => {
            const dialog = document.querySelector('[role="dialog"][aria-modal="true"]');
            const title = dialog && [...dialog.querySelectorAll('h2')].find((node) => ['模型', 'Models'].includes(node.textContent?.trim()));
            const section = title?.parentElement;
            const select = section?.querySelector('select[aria-label="提供方"], select[aria-label="Provider"]');
            if (!select) return null;
            if (![...select.options].some((option) => option.value === 'opencode-rt')) {
              const option = document.createElement('option');
              option.value = 'opencode-rt'; option.textContent = 'OpenCode RT'; option.dataset.dshMathmodelOpenCodeRt = 'true'; select.appendChild(option);
            }
            selectRef.current = select;
            // 官方 CSS Modules 会把 addCard 编译为哈希类名；选项标签的父级再上一层才是整张添加卡片。
            return select.parentElement?.parentElement ?? select.parentElement;
          };
          const sync = () => setHost(locate());
          const onChange = (event) => {
            if (event.target !== selectRef.current || event.target.value !== 'opencode-rt') return;
            event.stopPropagation(); setMessage(''); setOpen(true);
          };
          sync(); document.addEventListener('change', onChange, true);
          const observer = new MutationObserver(sync);
          observer.observe(document.body, { childList: true, subtree: true });
          return () => { observer.disconnect(); document.removeEventListener('change', onChange, true); };
        }, []);
        React.useEffect(() => {
          if (!host) return;
          for (const child of host.children) if (child.dataset.dshMathmodelOpencodeRtAdd !== 'true') child.style.display = open ? 'none' : '';
          return () => { for (const child of host.children) child.style.display = ''; };
        }, [host, open]);
        if (!host || !open) return null;
        const cancel = () => {
          const select = selectRef.current;
          const fallback = [...(select?.options ?? [])].find((option) => option.value !== 'opencode-rt');
          if (select && fallback) { select.value = fallback.value; select.dispatchEvent(new Event('change', { bubbles: true })); }
          setApiKey(''); setMessage(''); setOpen(false);
        };
        const save = async () => {
          setBusy(true); setMessage('正在保存并从官方接口同步模型…');
          try { const result = await actions.configure(apiKey); setApiKey(''); setMessage(`已保存：同步 ${result.configuredModels.length} 个兼容模型。关闭后重新打开“模型”即可看到 OpenCode RT。`); }
          catch (error) { setMessage(error instanceof Error ? error.message : String(error)); }
          finally { setBusy(false); }
        };
        return ReactDOM.createPortal(React.createElement('div', { 'data-dsh-mathmodel-opencode-rt-add': 'true', className: 'dsh-mm-image-provider-editor' },
          React.createElement('label', { className: 'dsh-mm-image-provider-field', 'data-wide': true }, React.createElement('span', null, '提供方'), React.createElement('input', { value: 'OpenCode RT', readOnly: true, 'aria-label': '提供方：OpenCode RT' })),
          React.createElement('p', { className: 'dsh-mm-image-provider-hint' }, 'OpenCode RT 会使用 OpenCode 官方最新模型列表；已知支持图片的模型会自动启用识图。'),
          React.createElement('label', { className: 'dsh-mm-image-provider-field', 'data-wide': true }, React.createElement('span', null, 'API Key（留空复用 opencode-go）'), React.createElement('input', { type: 'password', autoComplete: 'new-password', value: apiKey, placeholder: '输入新 Key，或留空复用已有 Key', onChange: (event) => setApiKey(event.target.value) })),
          message ? React.createElement('p', { className: 'dsh-mm-image-provider-message', role: 'status' }, message) : null,
          React.createElement('div', { className: 'dsh-mm-image-provider-actions' }, React.createElement('button', { type: 'button', className: 'dsh-mm-image-provider-button', disabled: busy, onClick: cancel }, '取消'), React.createElement('button', { type: 'button', className: 'dsh-mm-image-provider-button', 'data-primary': true, disabled: busy, onClick: save }, busy ? '保存中…' : '保存')),
        ), host);
      }

      function setNativeInputValue(input, value) {
        const setter = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value')?.set;
        if (!setter) throw new Error('浏览器无法更新模型草稿');
        setter.call(input, value);
        input.dispatchEvent(new Event('input', { bubbles: true }));
        input.dispatchEvent(new Event('change', { bubbles: true }));
      }

      const nextFrame = () => new Promise((resolve) => requestAnimationFrame(resolve));

      async function appendModelsToNativeDraft(editor, models) {
        const catalog = editor?.querySelector('[aria-label="模型目录"], [aria-label="Model catalog"]');
        if (!catalog) throw new Error('未找到当前模型草稿，请关闭后重新编辑供应商');
        const ids = () => [...catalog.querySelectorAll('input[aria-label^="模型 ID"], input[aria-label^="Model ID"]')];
        const existing = new Set(ids().map((input) => input.value.trim()).filter(Boolean));
        for (const model of models) {
          if (existing.has(model.id)) continue;
          const add = [...catalog.querySelectorAll('button')].find((button) => ['添加模型', 'Add model'].includes(button.textContent?.trim()));
          if (!add) throw new Error('未找到“添加模型”控件，请关闭后重新编辑供应商');
          const before = ids().length;
          add.click();
          await nextFrame();
          const added = ids()[before];
          if (!added) throw new Error('无法向当前模型草稿添加模型');
          setNativeInputValue(added, model.id);
          const nameInput = added.parentElement?.querySelector('input[aria-label^="显示名称"], input[aria-label^="Display name"]');
          if (nameInput && model.name) setNativeInputValue(nameInput, model.name);
          existing.add(model.id);
          await nextFrame();
        }
      }

      function providerFromEditor(editor) {
        const row = editor?.closest('li');
        const label = row?.querySelector('button[aria-label^="编辑"], button[aria-label^="Edit"]')?.getAttribute('aria-label') ?? '';
        const named = label.match(/\(([^()]+)\)\s*$/)?.[1];
        const plain = label.replace(/^(编辑|Edit)\s+/, '').trim();
        const provider = (named ?? plain).trim();
        return /^[a-z0-9][a-z0-9-]*$/.test(provider) ? provider : null;
      }

      function StoredKeyModelDiscovery({ actions }) {
        const [picker, setPicker] = React.useState(null);
        const open = React.useCallback((provider, editor) => {
          setPicker({ provider, editor, status: 'loading', models: [], selected: new Set(), error: '' });
          if (provider === 'opencode-rt') {
            actions.refreshOpenCodeRt().then((result) => {
              setPicker((current) => current?.provider === provider ? { ...current, status: 'notice', message: `已安全同步 ${result.configuredModels.length} 个兼容模型。关闭后重新打开此供应商即可查看。` } : current);
            }, (error) => {
              setPicker((current) => current?.provider === provider ? { ...current, status: 'error', error: error instanceof Error ? error.message : String(error) } : current);
            });
            return;
          }
          actions.discover(provider).then((result) => {
            const existing = new Set([...editor.querySelectorAll('input[aria-label^="模型 ID"], input[aria-label^="Model ID"]')].map((input) => input.value.trim()));
            setPicker((current) => current?.provider === provider ? { ...current, status: 'ready', models: result.models, selected: new Set(result.models.filter((model) => !existing.has(model.id)).map((model) => model.id)) } : current);
          }, (error) => {
            setPicker((current) => current?.provider === provider ? { ...current, status: 'error', error: error instanceof Error ? error.message : String(error) } : current);
          });
        }, [actions]);
        React.useEffect(() => {
          const onClick = (event) => {
            const target = event.target instanceof Element ? event.target.closest('button') : null;
            if (!target || !['获取可用模型', 'Fetch available models'].includes(target.textContent?.trim())) return;
            const editor = target.closest('li')?.querySelector('[aria-label="模型目录"], [aria-label="Model catalog"]')?.closest('div')?.parentElement;
            const provider = providerFromEditor(target.closest('li'));
            if (!editor || !provider) return;
            event.preventDefault(); event.stopImmediatePropagation(); open(provider, target.closest('li'));
          };
          document.addEventListener('click', onClick, true);
          return () => document.removeEventListener('click', onClick, true);
        }, [open]);
        if (!picker) return null;
        const toggle = (id) => setPicker((current) => {
          const selected = new Set(current.selected);
          if (!selected.delete(id)) selected.add(id);
          return { ...current, selected };
        });
        const append = async () => {
          setPicker((current) => ({ ...current, status: 'applying', error: '' }));
          try {
            const selected = picker.models.filter((model) => picker.selected.has(model.id));
            await appendModelsToNativeDraft(picker.editor, selected);
            setPicker(null);
          } catch (error) {
            setPicker((current) => ({ ...current, status: 'ready', error: error instanceof Error ? error.message : String(error) }));
          }
        };
        const busy = ['loading', 'applying'].includes(picker.status);
        return ReactDOM.createPortal(React.createElement('div', { className: 'dsh-mm-overlay dsh-mm-settings-overlay' }, React.createElement('section', { className: 'dsh-mm-card', role: 'dialog', 'aria-modal': 'true', 'aria-labelledby': 'dsh-mm-model-discovery-title' },
          React.createElement('div', { className: 'dsh-mm-head' }, React.createElement('h2', { id: 'dsh-mm-model-discovery-title', className: 'dsh-mm-title' }, '获取可用模型')),
          React.createElement('p', { className: 'dsh-mm-summary' }, `将复用“${picker.provider}”已保存的受管 API Key。选中的模型仅加入当前草稿，仍需点击页面“保存”才会生效。`),
          picker.status === 'loading' ? React.createElement('p', { className: 'dsh-mm-summary', role: 'status' }, '正在获取模型列表…') : null,
          picker.status === 'notice' ? React.createElement('p', { className: 'dsh-mm-summary', role: 'status' }, picker.message) : null,
          picker.status === 'ready' ? React.createElement('div', { className: 'dsh-mm-model-picker' }, picker.models.length ? picker.models.map((model) => React.createElement('label', { key: model.id, className: 'dsh-mm-model-picker-row' }, React.createElement('input', { type: 'checkbox', checked: picker.selected.has(model.id), onChange: () => toggle(model.id) }), React.createElement('span', null, model.id), model.name && model.name !== model.id ? React.createElement('small', null, model.name) : null)) : React.createElement('p', { className: 'dsh-mm-model-picker-empty' }, '该供应商没有返回模型；你仍可手动添加模型。')) : null,
          picker.error ? React.createElement('p', { className: 'dsh-mm-error', role: 'alert' }, picker.error) : null,
          React.createElement('div', { className: 'dsh-mm-actions' }, React.createElement('button', { type: 'button', disabled: busy, onClick: () => setPicker(null) }, picker.status === 'notice' ? '关闭' : '取消'), picker.status === 'notice' ? null : React.createElement('button', { type: 'button', className: 'dsh-mm-primary', disabled: picker.status !== 'ready' || picker.selected.size === 0, onClick: append }, picker.status === 'applying' ? '加入中…' : '加入当前草稿')),
        )), document.body);
      }

      function ManualVisionDraftButton({ input, sessionId, actions }) {
        const [busy, setBusy] = React.useState(false);
        const imageIds = input?.imageIds ?? [];
        if (imageIds.length === 0) return null;
        const stage = async () => {
          setBusy(true);
          try { await actions.stageToDraft({ sessionId, imageIds: [...imageIds] }); }
          catch (error) { actions.notify(sessionId, error instanceof Error ? error.message : String(error)); }
          finally { setBusy(false); }
        };
        return React.createElement('button', {
          type: 'button', className: 'dsh-mm-vision-draft', disabled: busy,
          title: '保存图片到工作区；发送后模型将通过 vision_analyze 工具查看原图',
          'aria-label': `附图给模型分析 ${imageIds.length} 张图片`, onClick: stage,
        }, busy ? `附图中 ${imageIds.length} 张…` : `附图分析（${imageIds.length} 张）`);
      }

      function fieldControl(field, value, setValue, credentialActions) {
        const common = { id: `dsh-mm-${field.id}`, disabled: false, 'aria-required': field.required || undefined };
        if (field.type === 'credential-status') return React.createElement(CredentialField, { field, value, actions: credentialActions });
        if (field.type === 'boolean') return React.createElement('input', { ...common, type: 'checkbox', checked: Boolean(value), onChange: (event) => setValue(event.target.checked) });
        if (field.type === 'select') return React.createElement('select', { ...common, value: value ?? '', onChange: (event) => setValue(event.target.value) }, field.options.map((option) => React.createElement('option', { key: option, value: option }, option)));
        if (field.type === 'multiselect') return React.createElement('select', { ...common, multiple: true, value: value ?? [], onChange: (event) => setValue([...event.target.selectedOptions].map((option) => option.value)) }, field.options.map((option) => React.createElement('option', { key: option, value: option }, option)));
        if (field.type === 'text') return React.createElement('textarea', { ...common, value: value ?? '', placeholder: field.placeholder, onChange: (event) => setValue(event.target.value) });
        return React.createElement('input', { ...common, type: field.type === 'number' ? 'number' : 'text', value: value ?? '', min: field.min, max: field.max, placeholder: field.placeholder, onChange: (event) => setValue(field.type === 'number' ? Number(event.target.value) : event.target.value) });
      }

      function CardOverlay({ flow, sessionId, credentialActions, loadSkillHelp }) {
        const state = React.useSyncExternalStore(flow.subscribe, flow.getSnapshot, flow.getSnapshot);
        const isActive = state.activeSessionId === sessionId && state.activeCard;
        const info = React.createElement(MathmodelInfo, { flow, sessionId, loadSkillHelp, floating: true });
        if (!isActive) return info;
        if (!state.open || state.sessionId !== sessionId) return info;
        return React.createElement(React.Fragment, null, React.createElement('div', { className: 'dsh-mm-overlay' }, React.createElement('section', { className: 'dsh-mm-card', role: 'dialog', 'aria-modal': 'true', 'aria-labelledby': 'dsh-mm-title' },
          React.createElement('div', { className: 'dsh-mm-head' }, React.createElement('h2', { className: 'dsh-mm-title', id: 'dsh-mm-title' }, state.card.title)),
          React.createElement('p', { className: 'dsh-mm-summary' }, state.card.summary),
          React.createElement('div', { className: 'dsh-mm-grid' }, state.card.fields.map((field) => React.createElement('label', { className: 'dsh-mm-field', 'data-type': field.type, 'data-wide': ['text', 'path'].includes(field.type), key: field.id, htmlFor: `dsh-mm-${field.id}` },
            React.createElement('span', null, field.label, field.required ? ' *' : ''),
            fieldControl(field, state.values[field.id], (value) => flow.setValue(field.id, value), credentialActions),
            field.description ? React.createElement('small', null, field.description) : null,
          ))),
          state.error ? React.createElement('div', { className: 'dsh-mm-error', role: 'alert' }, state.error) : null,
          React.createElement('div', { className: 'dsh-mm-actions' },
            React.createElement('button', { type: 'button', disabled: state.busy, onClick: flow.cancel }, '取消'),
            React.createElement('button', { type: 'button', className: 'dsh-mm-primary', disabled: state.busy, onClick: () => flow.confirm() }, state.busy ? '生成中…' : '确定（仅写入草稿）'),
          ),
        )), info);
      }

      const inject = [
        'inputTriggers',
        'connection',
        'sessions',
        'slots',
        'remote',
        'conversation',
      ];
      const pass = Object.freeze({ parse: (value) => value });
      const codec = Object.freeze({ mode: 'strict', typeSymbol: 'mathmodel#json', schema: pass });
      const param = (name) => ({ name, wire: name, source: 'json', codec });
      const descriptor = (service, method, parameters = []) => ({
        id: `@deepseek-harness/dsh-mathmodel#${service}/${method}`,
        service, namespace: service, method, invocation: { kind: 'direct' }, parameters, result: codec,
      });
      const TYPERT_REMOTE = Object.freeze({
        package: '@deepseek-harness/dsh-mathmodel',
        descriptors: [
          descriptor('mathmodelCards', 'list'),
          descriptor('mathmodelCards', 'help'),
          descriptor('mathmodelCards', 'render', [param('skill'), param('values')]),
          descriptor('mathmodelCredentials', 'describe', [param('ref')]),
          descriptor('mathmodelCredentials', 'set', [param('ref'), param('value')]),
          descriptor('mathmodelCredentials', 'unset', [param('ref')]),
          descriptor('mathmodelPreflight', 'run'),
          descriptor('mathmodelProviders', 'status'),
          descriptor('mathmodelImageConnections', 'list'),
          descriptor('mathmodelImageConnections', 'upsert', [param('draft'), param('id')]),
          descriptor('mathmodelImageConnections', 'setKey', [param('id'), param('value')]),
          descriptor('mathmodelImageConnections', 'clearKey', [param('id')]),
          descriptor('mathmodelImageConnections', 'discoverModels', [param('id')]),
          descriptor('mathmodelImageConnections', 'verify', [param('id'), param('authorizePaid')]),
          descriptor('mathmodelImageConnections', 'setActive', [param('id')]),
          descriptor('mathmodelImageConnections', 'deleteConnection', [param('id'), param('clearCredential')]),
          descriptor('mathmodelOpenCodeRt', 'configure', [param('apiKey')]),
          descriptor('mathmodelOpenCodeRt', 'refresh'),
          descriptor('mathmodelStoredKeyModelDiscovery', 'discover', [param('provider')]),
          descriptor('mathmodelManualVision', 'stage', [param('images'), param('workspace')]),
        ],
      });
      async function unwrapRemote(promise, endpoint) {
        const result = await promise;
        if (result?.ok === true) return result.value;
        const code = result?.error?.code ?? 'internal';
        const message = result?.error?.message ?? '远程调用失败';
        const error = new Error(`${endpoint}: ${message} (${code})`);
        error.code = code;
        throw error;
      }
      async function apply(ctx) {
        const disposeRemote = await ctx.remote.$mount(TYPERT_REMOTE);
        const mathmodelCards = ctx.get('remote.mathmodelCards');
        const mathmodelCredentials = ctx.get('remote.mathmodelCredentials');
        const mathmodelPreflight = ctx.get('remote.mathmodelPreflight');
        const mathmodelProviders = ctx.get('remote.mathmodelProviders');
        const mathmodelImageConnections = ctx.get('remote.mathmodelImageConnections');
        const mathmodelOpenCodeRt = ctx.get('remote.mathmodelOpenCodeRt');
        const mathmodelStoredKeyModelDiscovery = ctx.get('remote.mathmodelStoredKeyModelDiscovery');
        const mathmodelManualVision = ctx.get('remote.mathmodelManualVision');
        if (!mathmodelCards || !mathmodelCredentials || !mathmodelPreflight || !mathmodelProviders || !mathmodelImageConnections || !mathmodelOpenCodeRt || !mathmodelStoredKeyModelDiscovery || !mathmodelManualVision) {
          throw new Error('mathmodel Remote 挂载后不可用');
        }
        const sessions = ctx.get('sessions');
        const conversation = ctx.get('conversation');
        const skillsApi = ctx.get('connection').api.skills;
        const cache = new Map();
        const catalogTtlMs = 2_000;
        const loadSkillHelp = () => unwrapRemote(mathmodelCards.help(), 'mathmodelCards/help');
        const cardsForSession = (sessionId) => cache.get(sessionId)?.cards ?? new Map();
        const fetchCatalog = (sessionId) => {
          if (sessions.subagentAddress(sessionId) !== undefined) return Promise.resolve([]);
          const current = cache.get(sessionId);
          if (current?.promise && Date.now() - current.fetchedAt < catalogTtlMs) return current.promise;
          current?.abort.abort();
          const abort = new AbortController();
          const promise = (async () => {
            const [{ result }, cardsResult] = await Promise.all([
              skillsApi.list({ sessionId }, abort.signal),
              unwrapRemote(mathmodelCards.list(), 'mathmodelCards/list'),
            ]);
            if (!result.ok) throw new Error(`skill.list failed: ${result.error.code}`);
            const cards = new Map(cardsResult.cards.map((card) => [card.skill, card]));
            cards.catalog = result.value.skills;
            cache.set(sessionId, { promise, abort, cards, fetchedAt: Date.now() });
            return result.value.skills;
          })();
          cache.set(sessionId, { promise, abort, cards: new Map(), fetchedAt: Date.now() });
          promise.catch(() => { if (cache.get(sessionId)?.promise === promise) cache.delete(sessionId); });
          return promise;
        };
        const flow = createCardFlow({
          renderDraft: (skill, values) => unwrapRemote(
            mathmodelCards.render(skill, values),
            'mathmodelCards/render',
          ),
          insertDraft: (sessionId, span, text) => {
            const actx = sessions.scope(sessionId);
            return actx?.bail(actx, 'slash/input-insert-text', { text, span }) === true;
          },
          setBlock: (sessionId, block) => conversation.blocks.set(sessionId, block),
          notify: (sessionId, level, text) => {
            const actx = sessions.scope(sessionId);
            if (actx) conversation.input.for(actx).notify(level, text);
          },
        });
        const credentialActions = createCredentialActions({
          describe: (ref) => unwrapRemote(mathmodelCredentials.describe(ref), 'mathmodelCredentials/describe'),
          set: (ref, value) => unwrapRemote(mathmodelCredentials.set(ref, value), 'mathmodelCredentials/set'),
          unset: (ref) => unwrapRemote(mathmodelCredentials.unset(ref), 'mathmodelCredentials/unset'),
        }, flow);
        const imageConnectionActions = createImageConnectionActions({
          list: () => unwrapRemote(mathmodelImageConnections.list(), 'mathmodelImageConnections/list'),
          upsert: (draft, id) => unwrapRemote(mathmodelImageConnections.upsert(draft, id), 'mathmodelImageConnections/upsert'),
          setKey: (id, value) => unwrapRemote(mathmodelImageConnections.setKey(id, value), 'mathmodelImageConnections/setKey'),
          clearKey: (id) => unwrapRemote(mathmodelImageConnections.clearKey(id), 'mathmodelImageConnections/clearKey'),
          discoverModels: (id) => unwrapRemote(mathmodelImageConnections.discoverModels(id), 'mathmodelImageConnections/discoverModels'),
          verify: (id, authorizePaid) => unwrapRemote(mathmodelImageConnections.verify(id, authorizePaid), 'mathmodelImageConnections/verify'),
          setActive: (id) => unwrapRemote(mathmodelImageConnections.setActive(id), 'mathmodelImageConnections/setActive'),
          deleteConnection: (id, clearCredential) => unwrapRemote(mathmodelImageConnections.deleteConnection(id, clearCredential), 'mathmodelImageConnections/deleteConnection'),
          legacyStatus: () => unwrapRemote(mathmodelProviders.status(), 'mathmodelProviders/status'),
        });
        const openCodeRtActions = createOpenCodeRtActions({
          configure: (apiKey) => unwrapRemote(mathmodelOpenCodeRt.configure(apiKey), 'mathmodelOpenCodeRt/configure'),
          refresh: () => unwrapRemote(mathmodelOpenCodeRt.refresh(), 'mathmodelOpenCodeRt/refresh'),
        });
        const storedKeyModelDiscoveryActions = createStoredKeyModelDiscoveryActions({
          discover: (provider) => unwrapRemote(mathmodelStoredKeyModelDiscovery.discover(provider), 'mathmodelStoredKeyModelDiscovery/discover'),
        });
        const manualVisionActions = createManualVisionActions({
          stage: (images, workspace) => unwrapRemote(mathmodelManualVision.stage(images, workspace), 'mathmodelManualVision/stage'),
          workspaceOf: (sessionId) => sessions.list?.getSnapshot?.().byId[sessionId]?.cwd,
          draftImages: (imageIds) => conversation.draftImages(imageIds),
          releaseDraftImages: (attachments) => conversation.releaseDraftImages(attachments),
          inputForSession: (sessionId) => {
            const actx = sessions.scope(sessionId);
            if (!actx) throw new Error('当前会话已不可用，请重试');
            return conversation.input.for(actx);
          },
          notify: (sessionId, text) => {
            const actx = sessions.scope(sessionId);
            if (actx) conversation.input.for(actx).notify('error', text);
          },
        });
        Promise.resolve().then(async () => {
          const [preflight, imageConnections] = await Promise.allSettled([
            unwrapRemote(mathmodelPreflight.run(), 'mathmodelPreflight/run'),
            imageConnectionActions.load(),
          ]);
          flow.setStatus({
            ...(preflight.status === 'fulfilled' ? { preflight: preflight.value } : {}),
            ...(imageConnections.status === 'fulfilled' ? { imageConnections: imageConnections.value } : {}),
          });
        });
        const source = createSkillSource({ fetchCatalog, flow, cardsForSession });
        ctx.effect(() => ctx.get('inputTriggers').registerSource(source), 'dsh-mathmodel: skill source');
        ctx.slots.inject('conversation.input.overlay', () => ctx.slots.register({
          name: 'conversation.input.overlay', id: 'mathmodel-card', order: -20,
          inject: (sessionId) => ({ flow, sessionId, credentialActions, loadSkillHelp }),
        }, CardOverlay));
        ctx.slots.inject('conversation.input.overlay', () => ctx.slots.register({
          name: 'conversation.input.overlay', id: 'mathmodel-image-connection-settings', order: -19,
          inject: () => ({ actions: imageConnectionActions }),
        }, ImageConnectionSettings));
        ctx.slots.inject('conversation.input.overlay', () => ctx.slots.register({
          name: 'conversation.input.overlay', id: 'mathmodel-opencode-rt-add-provider', order: -18,
          inject: () => ({ actions: openCodeRtActions }),
        }, OpenCodeRtAddProvider));
        ctx.slots.inject('conversation.input.overlay', () => ctx.slots.register({
          name: 'conversation.input.overlay', id: 'mathmodel-stored-key-model-discovery', order: -17,
          inject: () => ({ actions: { ...storedKeyModelDiscoveryActions, refreshOpenCodeRt: openCodeRtActions.refresh } }),
        }, StoredKeyModelDiscovery));
        ctx.slots.inject('conversation.input.right', () => ctx.slots.register({
          name: 'conversation.input.right', id: 'mathmodel-manual-vision-draft', order: -20,
          inject: () => ({ actions: manualVisionActions }),
        }, ManualVisionDraftButton));
        const invalidate = (sessionId) => {
          const entry = cache.get(sessionId);
          entry?.abort.abort();
          cache.delete(sessionId);
        };
        ctx.remote.$on('agent-preset/selected', invalidate);
        ctx.on('connection/reset', () => { for (const id of [...cache.keys()]) invalidate(id); });
        return async () => {
          for (const id of [...cache.keys()]) invalidate(id);
          await disposeRemote();
        };
      }
      module.exports.apply = apply;
      module.exports.inject = inject;
      return module.exports;
    },
  });
}
})();
