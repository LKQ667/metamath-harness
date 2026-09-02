/**
 * dsh-api-key-pool 浏览器 bundle：Settings → Plugins 中的「API Key 号池」卡片。
 * - 通过官方 keyed slot（settings.plugin.item，key=api-key-pool）注册，与 Host namespace 同名
 * - 填写方式对齐原生「设置 → 模型」：主字段是一个只写的「API 密钥」输入框，端点／协议／
 *   模型收在折叠的「自定义设置」里，一张卡片填完即可保存。唯一差异是同一张卡片可以
 *   填入多枚 Key（一次粘贴多行即拆成多枚），已存储的 Key 以脱敏行展示其轮询状态
 * - 全部数据经 Typert Remote（apiKeyPool.list/upsertPool/addKey/removeKey/resetCooldown/probe）
 *   获取，Host 侧输出已递归脱敏（masked/fingerprint/keyId），本卡片永不显示/复制完整 Key
 * - 输入的新 Key 只上行一次（addKey），不落地 localStorage/sessionStorage
 */
(() => {
  if (typeof window === 'undefined' || !window.__ModuleLoader__) return;

  window.__ModuleLoader__.load({
    id: '@deepseek-harness/dsh-api-key-pool',
    factory: (require) => {
      const module = { exports: {} };
      const React = require('react');

      const STYLE_ID = 'dsh-api-key-pool-card-style';
      if (!document.getElementById(STYLE_ID)) {
        const style = document.createElement('style');
        style.id = STYLE_ID;
        style.textContent = [
          '.akp-card{border:1px solid var(--dsw-alias-border-l2);background:var(--dsw-alias-bg-layer-3);border-radius:8px;min-width:0;list-style:none;transition:border-color .16s,background .16s;overflow:hidden;margin-bottom:8px}',
          '.akp-cardOpen{background:var(--dsw-alias-bg-layer-2);border-color:var(--dsw-alias-label-dimmed)}',
          '.akp-header{width:100%;color:inherit;cursor:pointer;text-align:left;font:inherit;background:0 0;border:0;align-items:center;gap:8px;padding:10px 14px;display:flex}',
          '.akp-header:hover:not(:disabled){background:var(--dsw-alias-interactive-bg-hover)}',
          '.akp-headText{flex-direction:column;flex:1;gap:2px;min-width:0;display:flex;overflow:hidden}',
          '.akp-name{color:var(--dsw-alias-label-primary);white-space:nowrap;text-overflow:ellipsis;font-weight:600;overflow:hidden}',
          '.akp-description{color:var(--dsw-alias-label-tertiary);white-space:nowrap;text-overflow:ellipsis;font-size:12px;overflow:hidden}',
          '.akp-chevron{color:var(--dsw-alias-label-tertiary);flex:none;font-size:13px;transition:transform .12s}',
          '.akp-chevronOpen{transform:rotate(180deg)}',
          '.akp-body{flex-direction:column;gap:10px;padding:0 14px 14px;display:flex}',
          '.akp-error{color:var(--dsw-alias-state-error-primary);margin:0;font-size:12px}',
          '.akp-hint{color:var(--dsw-alias-label-secondary);margin:0;font-size:12px}',
          '.akp-pool{border:1px solid var(--dsw-alias-border-l2);background:var(--dsw-alias-bg-layer-3);border-radius:8px;overflow:hidden}',
          '.akp-poolHead{align-items:center;gap:8px;padding:9px 12px;display:flex}',
          '.akp-rowToggle{flex:1;min-width:0;color:inherit;cursor:pointer;text-align:left;font:inherit;background:0 0;border:0;align-items:center;gap:8px;display:flex}',
          '.akp-poolName{color:var(--dsw-alias-label-primary);font-weight:600;font-size:13px;flex:1;min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}',
          '.akp-badge{white-space:nowrap;border-radius:999px;flex:none;padding:1px 6px;font-size:11px}',
          '.akp-badgeOn{background:rgba(80,200,120,.15);color:#7ddb9c;border:1px solid rgba(80,200,120,.3)}',
          '.akp-badgeOff{background:rgba(240,170,80,.15);color:#f0b060;border:1px solid rgba(240,170,80,.3)}',
          '.akp-badgeState{background:var(--dsw-alias-interactive-bg-hover-accent);color:var(--dsw-alias-state-business-primary);border:1px solid transparent}',
          '.akp-badgeStateBad{background:rgba(240,170,80,.15);color:#f0b060;border:1px solid rgba(240,170,80,.3)}',
          '.akp-dot{flex:none;width:8px;height:8px;border-radius:50%;background:var(--dsw-alias-label-dimmed)}',
          '.akp-dotOk{background:#4fbd7a}',
          '.akp-dotWarn{background:#f0b060}',
          '.akp-dotMiss{background:#e06c6c}',
          '.akp-editorBody{border-top:1px solid var(--dsw-alias-border-l2);flex-direction:column;gap:10px;padding:12px;display:flex}',
          '.akp-field{flex-direction:column;gap:4px;min-width:0;display:flex}',
          '.akp-fieldLabel{color:var(--dsw-alias-label-secondary);font-size:12px}',
          '.akp-select,.akp-input{border:1px solid var(--dsw-alias-border-l2);font:inherit;font-variant-numeric:tabular-nums;color:var(--dsw-alias-label-primary);background:var(--dsw-specific-input-major);border-radius:6px;padding:6px 8px;font-size:13px;transition:border-color .13s,box-shadow .13s}',
          '.akp-select{color-scheme:light dark}',
          '.akp-input{width:100%;min-width:0;box-sizing:border-box}',
          '.akp-input:disabled{color:var(--dsw-alias-label-tertiary);cursor:default}',
          '.akp-input:focus-visible,.akp-select:focus-visible{outline:2px solid var(--dsw-alias-state-business-primary);outline-offset:1px}',
          '.akp-keyInputRow{align-items:center;gap:8px;display:flex}',
          '.akp-keyInputRow .akp-input{flex:1}',
          '.akp-chips{flex-wrap:wrap;gap:6px;display:flex}',
          '.akp-chip{align-items:center;gap:6px;border:1px solid var(--dsw-alias-border-l2);border-radius:999px;background:var(--dsw-alias-interactive-bg-hover-accent);color:var(--dsw-alias-label-primary);font-family:ui-monospace,Consolas,monospace;font-size:12px;padding:2px 4px 2px 9px;display:flex}',
          '.akp-chipBtn{cursor:pointer;color:inherit;background:0 0;border:0;border-radius:50%;width:18px;height:18px;line-height:1;font-size:13px;display:grid;place-items:center}',
          '.akp-chipBtn:hover{background:rgba(240,100,100,.18);color:#f28b8b}',
          '.akp-keys{flex-direction:column;gap:4px;display:flex}',
          '.akp-keysTitle{color:var(--dsw-alias-label-tertiary);font-size:12px}',
          '.akp-keyRow{border:1px solid var(--dsw-alias-border-l2);border-radius:6px;align-items:center;gap:8px;padding:4px 8px;display:flex;flex-wrap:wrap;font-size:12px;min-width:0}',
          '.akp-keyRow .akp-masked{font-family:ui-monospace,Consolas,monospace;color:var(--dsw-alias-label-primary)}',
          '.akp-keyRow .akp-meta{color:var(--dsw-alias-label-tertiary)}',
          '.akp-keyRow .akp-spacer{flex:1}',
          '.akp-keyRowMarked{border-color:rgba(240,100,100,.35);background:rgba(240,100,100,.07)}',
          '.akp-keyRowMarked .akp-masked{text-decoration:line-through;color:var(--dsw-alias-label-tertiary)}',
          '.akp-btn{font:inherit;cursor:pointer;border-radius:6px;padding:3px 10px;font-size:12px;white-space:nowrap;transition:background-color .13s,border-color .13s,color .13s;border:1px solid var(--dsw-alias-border-l2);background:transparent;color:var(--dsw-alias-label-secondary)}',
          '.akp-btn:hover:not(:disabled){background:var(--dsw-alias-interactive-bg-hover);color:var(--dsw-alias-label-primary)}',
          '.akp-btn:disabled{opacity:.5;cursor:default}',
          '.akp-danger:hover:not(:disabled){background:rgba(240,100,100,.12);color:#f28b8b;border-color:rgba(240,100,100,.35)}',
          '.akp-adv{border:1px solid var(--dsw-alias-border-l2);border-radius:8px;overflow:hidden}',
          '.akp-advHead{width:100%;color:inherit;font:inherit;cursor:pointer;text-align:left;background:0 0;border:0;align-items:center;gap:6px;padding:7px 10px;display:flex;font-size:12px}',
          '.akp-advHead:hover{background:var(--dsw-alias-interactive-bg-hover);color:var(--dsw-alias-label-primary)}',
          '.akp-grid{grid-template-columns:repeat(auto-fit,minmax(210px,1fr));gap:10px;padding:10px;display:grid}',
          '.akp-catalog{border-top:1px solid var(--dsw-alias-border-l2);flex-direction:column;gap:6px;padding:10px;display:flex}',
          '.akp-catalogHead{align-items:baseline;gap:8px;display:flex}',
          '.akp-catalogTitle{color:var(--dsw-alias-label-secondary);font-size:12px}',
          '.akp-catalogMeta{color:var(--dsw-alias-label-tertiary);font-size:12px}',
          '.akp-modelRow{align-items:center;gap:6px;display:flex}',
          '.akp-modelRow .akp-input{flex:1;min-width:0}',
          '.akp-iconBtn{cursor:pointer;color:var(--dsw-alias-label-secondary);background:transparent;border:1px solid var(--dsw-alias-border-l2);border-radius:6px;flex:none;width:28px;height:28px;display:grid;place-items:center}',
          '.akp-iconBtn:hover:not(:disabled){background:var(--dsw-alias-interactive-bg-hover);color:var(--dsw-alias-label-primary)}',
          '.akp-iconBtn:disabled{opacity:.5;cursor:default}',
          '.akp-iconBtnDanger:hover:not(:disabled){background:rgba(240,100,100,.12);color:#f28b8b;border-color:rgba(240,100,100,.35)}',
          '.akp-modelAdvanced{grid-template-columns:repeat(auto-fit,minmax(170px,1fr));border:1px dashed var(--dsw-alias-border-l2);border-radius:6px;gap:8px;padding:8px;display:grid}',
          '.akp-modelField{flex-direction:column;gap:4px;min-width:0;display:flex}',
          '.akp-modelFieldLabel{color:var(--dsw-alias-label-tertiary);font-size:12px}',
          '.akp-check{align-items:center;gap:6px;font-size:12px;color:var(--dsw-alias-label-secondary);display:flex}',
          '.akp-footer{border-top:1px solid var(--dsw-alias-border-l2);align-items:center;gap:8px;padding-top:10px;display:flex}',
          '.akp-footer .akp-spacer{flex:1}',
          '.akp-save{border:1px solid var(--dsw-alias-button-info-fill);background:var(--dsw-alias-button-info-fill);color:var(--dsw-alias-label-primary-foreground)}',
          '.akp-save:hover:not(:disabled){border-color:var(--dsw-alias-button-info-hover);background:var(--dsw-alias-button-info-hover)}',
          '.akp-save:disabled{opacity:.5;cursor:default}',
          '.akp-orphans{border:1px solid var(--dsw-alias-border-l2);border-radius:8px;color:var(--dsw-alias-state-warn-primary);font-size:12px;align-items:center;gap:8px;padding:8px 10px;display:flex}',
          '.akp-orphans .akp-spacer{flex:1}',
        ].join('');
        document.head.appendChild(style);
      }

      const pass = Object.freeze({ parse: (value) => value });
      const codec = Object.freeze({ mode: 'strict', typeSymbol: 'api-key-pool#json', schema: pass });
      const param = (name) => ({ name, wire: name, source: 'json', codec });
      const descriptor = (service, method, parameters = []) => ({
        id: `@deepseek-harness/dsh-api-key-pool#${service}/${method}`,
        service, namespace: service, method, invocation: { kind: 'direct' }, parameters, result: codec,
      });
      const TYPERT_REMOTE = Object.freeze({
        package: '@deepseek-harness/dsh-api-key-pool',
        descriptors: [
          descriptor('apiKeyPool', 'list'),
          descriptor('apiKeyPool', 'upsertPool', [param('pool')]),
          descriptor('apiKeyPool', 'deletePool', [param('poolId')]),
          descriptor('apiKeyPool', 'addKey', [param('value'), param('poolId')]),
          descriptor('apiKeyPool', 'removeKey', [param('keyId')]),
          descriptor('apiKeyPool', 'resetCooldown', [param('route'), param('keyId')]),
          descriptor('apiKeyPool', 'probe', [param('poolId')]),
        ],
      });

      const STATE_LABELS = { ready: '就绪', cooling: '冷却中', disabled: '已禁用' };
      const SUPPORTED_APIS = ['openai-completions', 'openai-responses', 'anthropic-messages'];
      const POOL_ID_PATTERN = /^[a-z][a-z0-9-]{0,38}[a-z0-9]$/;
      /** 与原生「模型」页同一把尺子：HTTP 头所能承载的可打印 ASCII。 */
      const LEGAL_KEY_PATTERN = /^[\x21-\x7E]+$/;
      const ENV_ASSIGNMENT_PATTERN = /^[A-Za-z_][A-Za-z0-9_]*\s*=/;

      const COPY = {
        keyInput: 'API 密钥',
        keyPlaceholder: '输入 API 密钥',
        keyStored: '已配置——输入新值可添加',
        keyBlank: '请输入 API 密钥。',
        keyIllegalCharacters: '该 API 密钥格式错误，请检查。',
        customized: '自定义设置',
        customRoute: 'Provider ID',
        customRouteHint: '以小写字母开头的标识，唯一标识该号池并派生 pool-* 路由名；创建后不可更改。',
        customRouteInvalid: 'Provider ID 需以小写字母开头，只含小写字母、数字与连字符，且以字母或数字结尾。',
        customRouteTaken: '该 Provider ID 已存在，请换一个。',
        customDisplayName: '显示名称',
        baseUrl: 'API 地址',
        baseUrlRequired: '请输入 API 地址。',
        baseUrlHttp: 'API 地址必须以 https:// 开头。',
        customApi: 'API 协议',
        models: '模型目录',
        modelsHint: '号池把每个模型 ID 注册到该池的 pool-* 路由下，至少一个。',
        modelsRequired: '请至少添加一个模型。',
        modelId: '模型 ID',
        modelName: '显示名称',
        modelNamePlaceholder: '留空时使用模型 ID',
        modelAdvanced: '容量',
        addModel: '添加模型',
        removeModel: '删除模型',
        modelContextWindow: '上下文窗口',
        modelMaxTokens: '最大输出 token',
        modelVision: '识图（图片输入）',
        modelVisionHint: '勾选即声明该模型支持图片输入；未勾选则继承提供方默认（通常仅文本）。',
        modelIdRequired: '模型 ID 不能为空。',
        modelIdDuplicate: '模型 ID 不能重复。',
        modelNameInvalid: '显示名称不能为空。',
        modelCapacityInvalid: '容量需为数字，可加 K 或 M 后缀。',
        modelContextInvalid: '上下文窗口必须是正整数，例如 131072、256K 或 1M。',
        modelMaxTokensInvalid: '最大输出 token 数必须是正整数，例如 8192、64K 或 1M。',
        apply: '保存',
        applying: '保存中…',
        cancel: '取消',
        add: '添加号池',
        remove: '删除',
        advancedHint: '冷却、重试等其余字段在 settings.yaml 的 api-key-pool 段，请直接编辑。',
      };

      function fmtDuration(ms) {
        if (!Number.isFinite(ms) || ms <= 0) return '';
        const s = Math.ceil(ms / 1000);
        if (s < 60) return `${s}s`;
        const m = Math.ceil(s / 60);
        if (m < 60) return `${m}m`;
        return `${Math.ceil(m / 60)}h`;
      }

      const messageOf = (err) => (err instanceof Error ? err.message : String(err));

      /** 脱敏预览：与 Host maskKey 同形，界面状态里从不留完整 Key。 */
      function maskPreview(value) {
        if (typeof value !== 'string' || value.length <= 12) return '…';
        return `${value.slice(0, 3)}…${value.slice(-4)}`;
      }

      /** 原生 apiKeyFailure 的镜像：空字段不是失败，纯空白与非法字符才是。 */
      function keyFailure(raw) {
        if (typeof raw !== 'string' || raw.length === 0) return undefined;
        const value = raw.trim();
        if (value.length === 0) return 'keyBlank';
        if (ENV_ASSIGNMENT_PATTERN.test(value)) return 'keyIllegalCharacters';
        const quoted = value.length >= 2
          && ((value.startsWith('"') && value.endsWith('"')) || (value.startsWith("'") && value.endsWith("'")));
        if (quoted) return 'keyIllegalCharacters';
        return LEGAL_KEY_PATTERN.test(value) ? undefined : 'keyIllegalCharacters';
      }

      /** 一次粘贴多枚：按换行／空白／逗号切分；只有一段时按原生单枚规则判定。 */
      function splitKeys(raw) {
        const value = String(raw ?? '').trim();
        if (value.length === 0) return [];
        const parts = value.split(/[\s,，;；]+/).map((part) => part.trim()).filter(Boolean);
        return parts.length > 1 ? parts : [value];
      }

      function slugify(raw) {
        return String(raw ?? '')
          .toLowerCase()
          .replace(/[^a-z0-9]+/g, '-')
          .replace(/^-+/, '')
          .replace(/-+$/, '')
          .slice(0, 38)
          .replace(/-+$/, '');
      }

      function hostOf(rawURL) {
        try {
          return new URL(String(rawURL).trim()).hostname;
        } catch {
          return '';
        }
      }

      /** 派生一个合法且未被占用的池 id：显示名优先，其次端点主机名。 */
      function suggestPoolId(preferred, takenIds) {
        let base = slugify(preferred);
        if (base.length === 0) base = 'pool';
        if (!/^[a-z]/.test(base)) base = `pool-${base}`.slice(0, 38).replace(/-+$/, '');
        if (base.length === 1) base = `${base}-1`;
        if (!POOL_ID_PATTERN.test(base)) base = 'pool-1';
        const taken = new Set(takenIds ?? []);
        if (!taken.has(base)) return base;
        for (let n = 2; n < 1000; n += 1) {
          const candidate = `${base}-${n}`;
          if (!taken.has(candidate)) return candidate;
        }
        return `pool-${Date.now()}`.slice(0, 38);
      }

      function statusOf(pool) {
        if (!pool.enabled) return { dot: 'akp-dot', text: '停用' };
        if (pool.keys.length === 0) return { dot: 'akp-dot akp-dotMiss', text: '无 Key' };
        const ready = pool.keys.filter((key) => key.state === 'ready').length;
        if (ready === 0) return { dot: 'akp-dot akp-dotWarn', text: '全部不可用' };
        return { dot: 'akp-dot akp-dotOk', text: `${ready}/${pool.keys.length} 就绪` };
      }

      /**
       * 原生「模型目录」同款容量词表：十进制数加可选 K/M 后缀（1M = 1000K），
       * 存储仍是纯 token 数；留空由 Host 回落到 schema 默认值。
       */
      const CAPACITY_PATTERN = /^(\d+(?:\.\d+)?)([km])?$/i;
      const CAPACITY_SCALE = { k: 1e3, m: 1e6 };
      const CAPACITY_HINT = { contextWindow: '256K', maxTokens: '32K' };
      /** 与 schema.js 的 fallback 一致：等于默认值时按「未填」显示，回写结果不变。 */
      const CAPACITY_DEFAULT = { contextWindow: 262144, maxTokens: 32768 };
      /** 原生勾选「识图」写入的模态集合：始终补齐 text，取消勾选即整字段清空。 */
      const VISION_INPUT = Object.freeze(['text', 'image']);
      const hasVision = (model) => Array.isArray(model?.input) && model.input.includes('image');

      function parseCapacity(text) {
        const trimmed = String(text ?? '').trim();
        if (trimmed.length === 0) return undefined;
        const match = CAPACITY_PATTERN.exec(trimmed);
        if (match === null) return NaN;
        const suffix = match[2] ? match[2].toLowerCase() : undefined;
        const scale = suffix === undefined ? 1 : CAPACITY_SCALE[suffix];
        const scaled = Number(match[1]) * scale;
        const rounded = Math.round(scaled);
        return Math.abs(scaled - rounded) < 1e-6 ? rounded : scaled;
      }

      function formatCapacity(value) {
        if (!Number.isInteger(value) || value <= 0) return String(value);
        if (value % CAPACITY_SCALE.m === 0) return `${value / CAPACITY_SCALE.m}M`;
        if (value % CAPACITY_SCALE.k === 0) return `${value / CAPACITY_SCALE.k}K`;
        return String(value);
      }

      /** 已存池 → 编辑行：只把「非默认」容量显式回填，其余留空显示占位提示。 */
      function modelRowsOf(models) {
        return (models ?? []).map((model) => ({
          id: typeof model.id === 'string' ? model.id : '',
          ...(typeof model.name === 'string' && model.name.length > 0 && model.name !== model.id
            ? { name: model.name } : {}),
          ...(Number.isInteger(model.contextWindow) && model.contextWindow !== CAPACITY_DEFAULT.contextWindow
            ? { contextWindow: model.contextWindow } : {}),
          ...(Number.isInteger(model.maxTokens) && model.maxTokens !== CAPACITY_DEFAULT.maxTokens
            ? { maxTokens: model.maxTokens } : {}),
          ...(hasVision(model) ? { input: [...VISION_INPUT] } : {}),
        }));
      }

      /** 编辑行 → 上行载荷：裁剪文本、只带用户真正填过的容量。 */
      function modelPayloadOf(rows) {
        return rows.map((row) => ({
          id: String(row.id ?? '').trim(),
          ...(typeof row.name === 'string' && row.name.trim().length > 0 ? { name: row.name.trim() } : {}),
          ...(Number.isInteger(row.contextWindow) ? { contextWindow: row.contextWindow } : {}),
          ...(Number.isInteger(row.maxTokens) ? { maxTokens: row.maxTokens } : {}),
          ...(hasVision(row) ? { input: [...VISION_INPUT] } : {}),
        }));
      }

      /** 原生 validateDeepSeekModels 的号池等价物：任何一行不合法都拒绝写入。 */
      function modelRowsFailure(rows) {
        const seen = new Set();
        for (const row of rows) {
          if (row.id.length === 0) return 'modelIdRequired';
          if (seen.has(row.id)) return 'modelIdDuplicate';
          seen.add(row.id);
          if (row.name !== undefined && row.name.trim().length === 0) return 'modelNameInvalid';
          for (const field of ['contextWindow', 'maxTokens']) {
            const value = row[field];
            if (value === undefined) continue;
            if (typeof value !== 'number' || !Number.isFinite(value)) return 'modelCapacityInvalid';
            if (!Number.isInteger(value) || value <= 0) {
              return field === 'contextWindow' ? 'modelContextInvalid' : 'modelMaxTokensInvalid';
            }
          }
        }
        return undefined;
      }

      /** 行折叠箭头与删除图标：沿用原生模型页的字形，不引入新图标库。 */
      function IconChevron({ open }) {
        return React.createElement('svg', {
          width: 14, height: 14, viewBox: '0 0 16 16', fill: 'none', 'aria-hidden': true,
          style: { transform: open ? 'rotate(90deg)' : undefined, transition: 'transform 120ms ease' },
        }, React.createElement('path', {
          d: 'M6 3.5L10.5 8L6 12.5', stroke: 'currentColor', strokeWidth: 1.5,
          strokeLinecap: 'round', strokeLinejoin: 'round',
        }));
      }

      function IconTrash() {
        return React.createElement('svg', {
          width: 14, height: 14, viewBox: '0 0 16 16', fill: 'none', 'aria-hidden': true,
        }, React.createElement('path', {
          d: 'M2.5 4h11M6.5 4V2.5h3V4M4 4l.7 9a1 1 0 001 .9h4.6a1 1 0 001-.9L12 4M6.5 6.8v4.4M9.5 6.8v4.4',
          stroke: 'currentColor', strokeWidth: 1.3, strokeLinecap: 'round', strokeLinejoin: 'round',
        }));
      }

      /**
       * 模型目录编辑器：与原生一致，一行一个模型（模型 ID + 显示名称 + 容量折叠 + 删除），
       * 底部「添加模型」逐行新增；不再用逗号把多个模型挤进一个输入框。
       */
      function ModelListEditor({ models, disabled, onChange }) {
        const [expanded, setExpanded] = React.useState(() => new Set());
        const [buffer, setBuffer] = React.useState(() => new Map());
        const bufferKey = (index, field) => `${index}:${field}`;
        const textOf = (model, key) => (typeof model[key] === 'string' ? model[key] : '');

        const patch = (index, next) => onChange(models.map((model, at) => {
          if (at !== index) return model;
          const cleared = new Set(Object.entries(next)
            .filter(([, value]) => value === undefined || value === '')
            .map(([key]) => key));
          return Object.fromEntries(Object.entries({ ...model, ...next })
            .filter(([key]) => !cleared.has(key)));
        }));

        const editCapacity = (index, field, text) => {
          setBuffer((current) => new Map(current).set(bufferKey(index, field), text));
          patch(index, { [field]: parseCapacity(text) });
        };

        const capacityText = (model, index, field) => {
          const typed = buffer.get(bufferKey(index, field));
          if (typed !== undefined) return typed;
          const value = model[field];
          return typeof value === 'number' ? formatCapacity(value) : '';
        };

        const toggleExpanded = (index) => setExpanded((current) => {
          const next = new Set(current);
          if (!next.delete(index)) next.add(index);
          return next;
        });

        const removeRow = (index) => {
          onChange(models.filter((_, at) => at !== index));
          setExpanded((current) => {
            const next = new Set();
            for (const at of current) {
              if (at < index) next.add(at);
              else if (at > index) next.add(at - 1);
            }
            return next;
          });
          setBuffer((current) => {
            const next = new Map();
            for (const [key, value] of current) {
              const at = Number(key.slice(0, key.indexOf(':')));
              if (at === index) continue;
              next.set(at > index ? key.replace(/^\d+/, String(at - 1)) : key, value);
            }
            return next;
          });
        };

        return React.createElement('section', { className: 'akp-catalog', 'aria-label': COPY.models },
          React.createElement('div', { className: 'akp-catalogHead' },
            React.createElement('span', { className: 'akp-catalogTitle' }, COPY.models),
            React.createElement('span', { className: 'akp-catalogMeta' },
              models.length === 0 ? COPY.modelsRequired : `${models.length} 个模型`),
          ),
          models.map((model, index) => React.createElement('div', { key: index },
            React.createElement('div', { className: 'akp-modelRow' },
              React.createElement('input', {
                className: 'akp-input', type: 'text', value: textOf(model, 'id'),
                placeholder: COPY.modelId, disabled, spellCheck: false,
                'aria-label': `${COPY.modelId} ${index + 1}`,
                onChange: (event) => patch(index, { id: event.target.value }),
              }),
              React.createElement('input', {
                className: 'akp-input', type: 'text', value: textOf(model, 'name'),
                placeholder: COPY.modelNamePlaceholder, disabled,
                'aria-label': `${COPY.modelName} ${index + 1}`,
                onChange: (event) => patch(index, { name: event.target.value }),
              }),
              React.createElement('button', {
                type: 'button', className: 'akp-iconBtn', disabled,
                title: COPY.modelAdvanced, 'aria-expanded': expanded.has(index),
                'aria-label': `${COPY.modelAdvanced} ${index + 1}`,
                onClick: () => toggleExpanded(index),
              }, React.createElement(IconChevron, { open: expanded.has(index) })),
              React.createElement('button', {
                type: 'button', className: 'akp-iconBtn akp-iconBtnDanger', disabled,
                title: COPY.removeModel, 'aria-label': `${COPY.removeModel} ${index + 1}`,
                onClick: () => removeRow(index),
              }, React.createElement(IconTrash, {})),
            ),
            expanded.has(index) ? React.createElement('div', { className: 'akp-modelAdvanced' },
              React.createElement('label', { className: 'akp-modelField' },
                React.createElement('span', { className: 'akp-modelFieldLabel' }, COPY.modelContextWindow),
                React.createElement('input', {
                  className: 'akp-input', type: 'text', inputMode: 'numeric',
                  value: capacityText(model, index, 'contextWindow'),
                  placeholder: CAPACITY_HINT.contextWindow, disabled,
                  'aria-label': `${COPY.modelContextWindow} ${index + 1}`,
                  onChange: (event) => editCapacity(index, 'contextWindow', event.target.value),
                }),
              ),
              React.createElement('label', { className: 'akp-modelField' },
                React.createElement('span', { className: 'akp-modelFieldLabel' }, COPY.modelMaxTokens),
                React.createElement('input', {
                  className: 'akp-input', type: 'text', inputMode: 'numeric',
                  value: capacityText(model, index, 'maxTokens'),
                  placeholder: CAPACITY_HINT.maxTokens, disabled,
                  'aria-label': `${COPY.modelMaxTokens} ${index + 1}`,
                  onChange: (event) => editCapacity(index, 'maxTokens', event.target.value),
                }),
              ),
              React.createElement('label', { className: 'akp-modelField' },
                React.createElement('span', { className: 'akp-modelFieldLabel' }, COPY.modelVision),
                React.createElement('input', {
                  type: 'checkbox', checked: hasVision(model), disabled,
                  title: COPY.modelVisionHint,
                  'aria-label': `${COPY.modelVision} ${index + 1}`,
                  onChange: (event) => patch(index, {
                    input: event.target.checked ? [...VISION_INPUT] : undefined,
                  }),
                }),
              ),
            ) : null,
          )),
          React.createElement('div', { className: 'akp-modelRow' },
            React.createElement('button', {
              type: 'button', className: 'akp-btn', disabled,
              onClick: () => onChange([...models, { id: '' }]),
            }, COPY.addModel),
            React.createElement('span', { className: 'akp-catalogMeta' }, COPY.modelsHint),
          ),
        );
      }

      /** 已存储 Key 的一行：脱敏值 + 轮询状态 + 重置／待移除。 */
      function StoredKeyRow({ route, entry, busy, marked, onReset, onToggleMark }) {
        return React.createElement('div', {
          className: 'akp-keyRow' + (marked ? ' akp-keyRowMarked' : ''),
        },
          React.createElement('span', {
            className: 'akp-badge ' + (entry.state === 'ready' ? 'akp-badgeState' : 'akp-badgeStateBad'),
          }, STATE_LABELS[entry.state] ?? entry.state),
          React.createElement('span', { className: 'akp-masked' }, entry.masked),
          React.createElement('span', { className: 'akp-meta' },
            `指纹 ${entry.fingerprint || '—'} · 失败 ${entry.failureCount}` +
            (entry.cooldownRemainingMs > 0 ? ` · 冷却余 ${fmtDuration(entry.cooldownRemainingMs)}` : '')),
          React.createElement('span', { className: 'akp-spacer' }),
          entry.state === 'ready' ? null : React.createElement('button', {
            type: 'button', className: 'akp-btn', disabled: busy,
            onClick: () => onReset(route, entry.keyId),
          }, '重置'),
          React.createElement('button', {
            type: 'button', className: 'akp-btn' + (marked ? '' : ' akp-danger'), disabled: busy,
            onClick: () => onToggleMark(entry.keyId),
          }, marked ? '撤销移除' : '移除'),
        );
      }

      /**
       * 一张号池卡片对应原生的一张提供方卡片：主字段只写 API 密钥，端点／协议／模型
       * 收在折叠的自定义设置里；多枚 Key 在同一字段连续填入，保存时一次提交。
       */
      function PoolEditor({ pool, takenIds, busy, onCommit, onCancel, onResetKey, onProbe, probeResult }) {
        const creating = pool === null;
        const takenKey = takenIds.join('|');
        const [draft, setDraft] = React.useState(() => ({
          id: creating ? suggestPoolId('', takenIds) : pool.id,
          displayName: creating ? '' : (pool.displayName === pool.id ? '' : pool.displayName),
          api: creating ? SUPPORTED_APIS[0] : (pool.api ?? SUPPORTED_APIS[0]),
          baseURL: creating ? '' : (pool.baseURL ?? ''),
          models: creating ? [{ id: '' }] : modelRowsOf(pool.models),
          enabled: creating ? true : pool.enabled,
        }));
        const [idTouched, setIdTouched] = React.useState(!creating);
        const [keyDraft, setKeyDraft] = React.useState('');
        const [pendingKeys, setPendingKeys] = React.useState([]);
        const [removals, setRemovals] = React.useState([]);
        const [advOpen, setAdvOpen] = React.useState(creating);
        const [keyFailureKey, setKeyFailureKey] = React.useState(undefined);
        const [error, setError] = React.useState(undefined);
        const [notice, setNotice] = React.useState(undefined);

        // 创建中且用户没有亲自改过 id 时，随显示名／API 地址实时派生建议值
        React.useEffect(() => {
          if (!creating || idTouched) return;
          const preferred = draft.displayName.trim().length > 0
            ? (slugify(draft.displayName) || slugify(hostOf(draft.baseURL)))
            : slugify(hostOf(draft.baseURL));
          const next = suggestPoolId(preferred, takenKey.split('|'));
          setDraft((current) => (current.id === next ? current : { ...current, id: next }));
        }, [creating, idTouched, draft.displayName, draft.baseURL, takenKey]);

        const set = (field) => (event) => {
          const next = event.target.type === 'checkbox' ? event.target.checked : event.target.value;
          setDraft((current) => ({ ...current, [field]: next }));
        };

        /** 逐枚判定格式后放入待发队列；是否真的重复由 Host 按指纹判定。 */
        const stageParts = (parts) => {
          const bad = parts.find((part) => keyFailure(part) !== undefined);
          if (bad !== undefined) {
            setKeyFailureKey(keyFailure(bad));
            return false;
          }
          setPendingKeys((current) => [...current, ...parts.filter((part) => !current.includes(part))]);
          return true;
        };

        const stageKeys = () => {
          const parts = splitKeys(keyDraft);
          if (parts.length === 0) {
            setKeyFailureKey(keyFailure(keyDraft) ?? 'keyBlank');
            return false;
          }
          if (!stageParts(parts)) return false;
          setKeyDraft('');
          setKeyFailureKey(undefined);
          return true;
        };

        /**
         * 一次粘贴多枚：单行输入框会吞掉剪贴板里的换行（浏览器把多行拼成一串），
         * 所以在 paste 事件里直接读剪贴板原文拆分；只有一枚时不拦截，行为与原生一致。
         */
        const onPasteKeys = (event) => {
          const text = event.clipboardData?.getData('text') ?? '';
          const parts = splitKeys(text);
          if (parts.length < 2) return;
          event.preventDefault();
          stageParts(parts);
        };

        const storedIds = new Set((pool?.keys ?? []).map((entry) => entry.keyId));
        const storedCount = pool?.keys.length ?? 0;
        const submitModels = modelPayloadOf(draft.models);

        const submit = async () => {
          setError(undefined);
          setNotice(undefined);
          const id = draft.id.trim();
          if (!POOL_ID_PATTERN.test(id)) {
            setError(COPY.customRouteInvalid);
            setAdvOpen(true);
            return;
          }
          if (creating && takenIds.includes(id)) {
            setError(COPY.customRouteTaken);
            setAdvOpen(true);
            return;
          }
          if (draft.baseURL.trim().length === 0) {
            setError(COPY.baseUrlRequired);
            setAdvOpen(true);
            return;
          }
          if (!/^https:\/\//i.test(draft.baseURL.trim())) {
            setError(COPY.baseUrlHttp);
            setAdvOpen(true);
            return;
          }
          if (submitModels.length === 0) {
            setError(COPY.modelsRequired);
            setAdvOpen(true);
            return;
          }
          const rowsFailure = modelRowsFailure(submitModels);
          if (rowsFailure !== undefined) {
            setError(COPY[rowsFailure]);
            setAdvOpen(true);
            return;
          }
          // 输入框里还留着没点「添加密钥」的内容：先校验，失败就停在字段上
          let staged = pendingKeys;
          if (keyDraft.trim().length > 0) {
            if (!stageKeys()) return;
            staged = [...pendingKeys, ...splitKeys(keyDraft)];
          }
          try {
            const result = await onCommit({
              pool: {
                id,
                displayName: draft.displayName.trim() || undefined,
                api: draft.api,
                baseURL: draft.baseURL.trim(),
                models: submitModels,
                enabled: draft.enabled,
              },
              addKeys: [...new Set(staged)],
              removeKeyIds: removals.filter((keyId) => storedIds.has(keyId)),
            });
            setNotice(`号池 ${result.poolId} 已保存；上方统计已刷新。`);
            setPendingKeys([]);
            setRemovals([]);
            if (result.failures.length > 0) setError(result.failures.join('；'));
          } catch (err) {
            setError(messageOf(err));
          }
        };

        return React.createElement('div', { className: 'akp-editorBody' },
          React.createElement('div', { className: 'akp-field' },
            React.createElement('span', { className: 'akp-fieldLabel' }, COPY.keyInput),
            React.createElement('div', { className: 'akp-keyInputRow' },
              React.createElement('input', {
                className: 'akp-input',
                type: 'password',
                autoComplete: 'off',
                spellCheck: false,
                disabled: busy,
                value: keyDraft,
                placeholder: storedCount > 0 ? COPY.keyStored : COPY.keyPlaceholder,
                'aria-label': COPY.keyInput,
                'aria-invalid': keyFailureKey !== undefined,
                onPaste: onPasteKeys,
                onChange: (event) => {
                  setKeyDraft(event.target.value);
                  setKeyFailureKey(undefined);
                },
                onKeyDown: (event) => {
                  if (event.key === 'Enter') {
                    event.preventDefault();
                    stageKeys();
                  }
                },
              }),
              React.createElement('button', {
                type: 'button', className: 'akp-btn', disabled: busy, onClick: stageKeys,
              }, '添加密钥'),
            ),
            keyFailureKey === undefined ? null : React.createElement('p', { className: 'akp-error' },
              COPY[keyFailureKey] ?? keyFailureKey),
            pendingKeys.length === 0 ? null : React.createElement('div', { className: 'akp-chips' },
              pendingKeys.map((value, index) => React.createElement('span', {
                className: 'akp-chip', key: `${index}-${maskPreview(value)}`,
              },
                maskPreview(value),
                React.createElement('button', {
                  type: 'button', className: 'akp-chipBtn', title: '取消填入这枚密钥', disabled: busy,
                  onClick: () => setPendingKeys((current) => current.filter((_, i) => i !== index)),
                }, '×'),
              ))),
            React.createElement('p', { className: 'akp-hint' },
              '一枚一枚填即可，多枚会自动排队；一次粘贴多行也会自动拆开。完整 Key 只在保存时上行一次，界面与日志只显示脱敏值。'),
          ),
          storedCount === 0
            ? React.createElement('p', { className: 'akp-hint' }, '该号池还没有 Key。')
            : React.createElement('div', { className: 'akp-keys' },
                React.createElement('span', { className: 'akp-keysTitle' }, `已存储 ${storedCount} 枚`),
                pool.keys.map((entry) => React.createElement(StoredKeyRow, {
                  key: entry.keyId,
                  route: pool.route,
                  entry,
                  busy,
                  marked: removals.includes(entry.keyId),
                  onReset: onResetKey,
                  onToggleMark: (keyId) => setRemovals((current) => (
                    current.includes(keyId) ? current.filter((item) => item !== keyId) : [...current, keyId]
                  )),
                })),
                pool.providerFailures > 0
                  ? React.createElement('p', { className: 'akp-hint' }, `Provider 级连续失败：${pool.providerFailures}`)
                  : null,
                pool.lastFailure
                  ? React.createElement('p', { className: 'akp-hint' },
                      `最近失败：${pool.lastFailure.code}（${new Date(pool.lastFailure.at).toLocaleTimeString()}）`)
                  : null,
              ),
          React.createElement('div', { className: 'akp-adv' },
            React.createElement('button', {
              type: 'button', className: 'akp-advHead', onClick: () => setAdvOpen(!advOpen),
              'aria-expanded': advOpen,
            },
              React.createElement('span', { className: 'akp-chevron' + (advOpen ? ' akp-chevronOpen' : '') }, '▸'),
              React.createElement('span', {}, COPY.customized),
            ),
            advOpen ? React.createElement(React.Fragment, null,
              React.createElement('div', { className: 'akp-grid' },
              React.createElement('div', { className: 'akp-field' },
                React.createElement('span', { className: 'akp-fieldLabel' }, COPY.customRoute),
                React.createElement('input', {
                  className: 'akp-input', type: 'text', value: draft.id, disabled: !creating,
                  placeholder: 'deepseek-gateway', 'aria-label': COPY.customRoute, spellCheck: false,
                  onChange: (event) => {
                    setIdTouched(true);
                    const value = event.target.value;
                    setDraft((current) => ({ ...current, id: value }));
                  },
                }),
                React.createElement('span', { className: 'akp-hint' }, COPY.customRouteHint),
              ),
              React.createElement('div', { className: 'akp-field' },
                React.createElement('span', { className: 'akp-fieldLabel' }, COPY.customDisplayName),
                React.createElement('input', {
                  className: 'akp-input', type: 'text', value: draft.displayName, disabled: busy,
                  placeholder: draft.id || '留空时使用 Provider ID', 'aria-label': COPY.customDisplayName,
                  onChange: set('displayName'),
                }),
              ),
              React.createElement('div', { className: 'akp-field' },
                React.createElement('span', { className: 'akp-fieldLabel' }, COPY.baseUrl),
                React.createElement('input', {
                  className: 'akp-input', type: 'text', value: draft.baseURL, disabled: busy,
                  placeholder: 'https://gateway.example/v1', 'aria-label': COPY.baseUrl, spellCheck: false,
                  onChange: set('baseURL'),
                }),
              ),
              React.createElement('div', { className: 'akp-field' },
                React.createElement('span', { className: 'akp-fieldLabel' }, COPY.customApi),
                React.createElement('select', {
                  className: 'akp-select', value: draft.api, disabled: busy,
                  'aria-label': COPY.customApi, onChange: set('api'),
                }, SUPPORTED_APIS.map((value) => React.createElement('option', { key: value, value }, value))),
              ),
              React.createElement('div', { className: 'akp-field' },
                React.createElement('span', { className: 'akp-fieldLabel' }, '状态'),
                React.createElement('label', { className: 'akp-check' },
                  React.createElement('input', {
                    type: 'checkbox', checked: draft.enabled, disabled: busy, onChange: set('enabled'),
                  }), ' 启用该号池'),
              ),
              React.createElement('p', { className: 'akp-hint' }, COPY.advancedHint),
              ),
              React.createElement(ModelListEditor, {
                models: draft.models,
                disabled: busy,
                onChange: (rows) => setDraft((current) => ({ ...current, models: rows })),
              }),
            ) : null,
          ),
          probeResult ? React.createElement('p', { className: 'akp-hint', role: 'status' },
            `探测：${probeResult.ok ? `HTTP ${probeResult.status}` : `失败（${probeResult.error ?? probeResult.status ?? '未知'}）`} · ${probeResult.latencyMs ?? '—'}ms`)
            : null,
          error ? React.createElement('p', { className: 'akp-error', role: 'alert' }, error) : null,
          notice ? React.createElement('p', { className: 'akp-hint', role: 'status' }, notice) : null,
          React.createElement('div', { className: 'akp-footer' },
            React.createElement('span', { className: 'akp-spacer' }),
            creating ? null : React.createElement('button', {
              type: 'button', className: 'akp-btn', disabled: busy, onClick: onProbe,
            }, '探测'),
            React.createElement('button', {
              type: 'button', className: 'akp-btn', disabled: busy, onClick: onCancel,
            }, COPY.cancel),
            React.createElement('button', {
              type: 'button', className: 'akp-btn akp-save', disabled: busy, onClick: submit,
            }, busy ? COPY.applying : COPY.apply),
          ),
        );
      }

      // Typert Remote 调用返回 {ok, value|error} 信封（与 dsh-mathmodel 客户端一致），
      // 必须显式解包：ok 时取 value，失败时抛带 code 的 Error。
      const unwrapRemote = (result) => {
        if (result !== null && typeof result === 'object' && ('ok' in result)) {
          if (result.ok === true) return result.value;
          const err = new Error(result?.error?.message ?? 'remote 调用失败');
          err.code = result?.error?.code;
          throw err;
        }
        return result;
      };

      function ApiKeyPoolCard({ remote }) {
        const [open, setOpen] = React.useState(false);
        const [data, setData] = React.useState(null);
        const [error, setError] = React.useState(null);
        const [busy, setBusy] = React.useState(false);
        const [editing, setEditing] = React.useState(null);
        const [probes, setProbes] = React.useState({});

        const refresh = React.useCallback(async () => {
          try {
            const result = unwrapRemote(await remote.list());
            setData(result);
            setError(null);
          } catch (err) {
            setError(messageOf(err));
          }
        }, [remote]);

        React.useEffect(() => {
          if (!open) return undefined;
          refresh();
          const timer = setInterval(refresh, 5000);
          return () => clearInterval(timer);
        }, [open, refresh]);

        const pools = data?.pools ?? [];
        const takenIds = pools.map((pool) => pool.id);
        const keyTotal = pools.reduce((sum, pool) => sum + pool.keyCount, 0);

        /** 一次「保存」= 写池配置 + 存入新 Key + 摘除待移除 Key，末尾统一刷新一次。 */
        const commit = async ({ pool, addKeys, removeKeyIds }) => {
          setBusy(true);
          try {
            const created = unwrapRemote(await remote.upsertPool(pool));
            const failures = [];
            for (const value of addKeys) {
              try {
                unwrapRemote(await remote.addKey(value, created.poolId));
              } catch (err) {
                failures.push(`${maskPreview(value)} 未能入库：${messageOf(err)}`);
              }
            }
            for (const keyId of removeKeyIds) {
              try {
                unwrapRemote(await remote.removeKey(keyId));
              } catch (err) {
                failures.push(`已存储密钥未能移除：${messageOf(err)}`);
              }
            }
            await refresh();
            // 新建成功后把「新建号池」卡片换成该池的编辑卡片，界面即已保存的证据
            if (created.created === true) setEditing({ mode: 'edit', id: created.poolId });
            return { ...created, failures };
          } finally {
            setBusy(false);
          }
        };

        const resetKey = async (route, keyId) => {
          setBusy(true);
          try {
            unwrapRemote(await remote.resetCooldown(route, keyId));
            await refresh();
          } catch (err) {
            setError(messageOf(err));
          } finally {
            setBusy(false);
          }
        };

        const deletePool = async (poolId) => {
          setBusy(true);
          try {
            unwrapRemote(await remote.deletePool(poolId));
            if (editing?.id === poolId) setEditing(null);
            await refresh();
          } catch (err) {
            setError(messageOf(err));
          } finally {
            setBusy(false);
          }
        };

        const probe = async (poolId) => {
          if (!window.confirm(`将用号池 "${poolId}" 的第一枚 Key 向上游发起一次真实请求（可能产生费用），确认继续？`)) return;
          setBusy(true);
          try {
            const result = unwrapRemote(await remote.probe(poolId));
            setProbes({ ...probes, [poolId]: result });
          } catch (err) {
            setProbes({ ...probes, [poolId]: { ok: false, error: messageOf(err) } });
          } finally {
            setBusy(false);
          }
        };

        const cleanOrphans = async () => {
          const orphans = data?.orphans ?? [];
          if (orphans.length === 0) return;
          if (!window.confirm(`删除 ${orphans.length} 枚未挂池的 Key 记录？该操作不可撤销。`)) return;
          setBusy(true);
          try {
            for (const keyId of orphans) unwrapRemote(await remote.removeKey(keyId));
            await refresh();
          } catch (err) {
            setError(messageOf(err));
          } finally {
            setBusy(false);
          }
        };

        const editingPool = editing === null || editing.mode === 'create'
          ? null
          : pools.find((pool) => pool.id === editing.id) ?? null;
        // 正在编辑的池被别处删除时不渲染陈旧卡片
        const showEditor = editing !== null && (editing.mode === 'create' || editingPool !== null);

        return React.createElement('li', { className: 'akp-card' + (open ? ' akp-cardOpen' : '') },
          React.createElement('button', {
            type: 'button', className: 'akp-header',
            onClick: () => setOpen(!open),
            'aria-expanded': open,
          },
            React.createElement('span', { className: 'akp-headText' },
              React.createElement('span', { className: 'akp-name' }, 'API Key 号池'),
              React.createElement('span', { className: 'akp-description' },
                `${pools.length} 个池 · ${keyTotal} 枚 Key · 多 Key 轮询与失败切换`),
            ),
            React.createElement('span', { className: 'akp-chevron' + (open ? ' akp-chevronOpen' : '') }, '▾'),
          ),
          open ? React.createElement('div', { className: 'akp-body' },
            error ? React.createElement('div', { className: 'akp-error', role: 'alert' },
              `号池服务不可用：${error}`) : null,
            data === null && !error ? React.createElement('div', { className: 'akp-hint' }, '加载中…') : null,
            data !== null
              ? React.createElement('p', { className: 'akp-hint' },
                  '填入各号池的 API 密钥即可使用其模型；一个号池可填多枚 Key，轮询与失败切换自动进行。')
              : null,
            pools.map((pool) => {
              const status = statusOf(pool);
              const expanded = editing?.mode === 'edit' && editing.id === pool.id;
              return React.createElement('div', { className: 'akp-pool', key: pool.id },
                React.createElement('div', { className: 'akp-poolHead' },
                  React.createElement('button', {
                    type: 'button', className: 'akp-rowToggle',
                    onClick: () => setEditing(expanded ? null : { mode: 'edit', id: pool.id }),
                    'aria-expanded': expanded,
                  },
                    React.createElement('span', { className: status.dot }),
                    React.createElement('span', { className: 'akp-poolName' },
                      `${pool.displayName}（${pool.route}）`),
                    React.createElement('span', {
                      className: 'akp-badge ' + (pool.enabled ? 'akp-badgeOn' : 'akp-badgeOff'),
                    }, pool.enabled ? '启用' : '停用'),
                    React.createElement('span', { className: 'akp-badge akp-badgeState' }, status.text),
                    React.createElement('span', {
                      className: 'akp-chevron' + (expanded ? ' akp-chevronOpen' : ''),
                    }, '▾'),
                  ),
                  React.createElement('button', {
                    type: 'button', className: 'akp-btn akp-danger', disabled: busy,
                    onClick: () => {
                      if (window.confirm(`删除号池 "${pool.id}"？已存储的 Key 记录会保留为未挂池状态，不会被删除。`)) {
                        deletePool(pool.id);
                      }
                    },
                  }, COPY.remove),
                ),
                expanded
                  ? React.createElement(PoolEditor, {
                      key: pool.id,
                      pool,
                      takenIds,
                      busy,
                      onCommit: commit,
                      onResetKey: resetKey,
                      onProbe: () => probe(pool.id),
                      probeResult: probes[pool.id],
                      onCancel: () => setEditing(null),
                    })
                  : null,
              );
            }),
            showEditor && editing.mode === 'create'
              ? React.createElement('div', { className: 'akp-pool' },
                  React.createElement('div', { className: 'akp-poolHead' },
                    React.createElement('span', { className: 'akp-poolName' }, '新建号池')),
                  React.createElement(PoolEditor, {
                    key: 'create',
                    pool: null,
                    takenIds,
                    busy,
                    onCommit: commit,
                    onResetKey: resetKey,
                    onProbe: () => undefined,
                    probeResult: undefined,
                    onCancel: () => setEditing(null),
                  }))
              : null,
            (data?.orphans ?? []).length > 0
              ? React.createElement('div', { className: 'akp-orphans' },
                  React.createElement('span', {}, `未挂池的 Key 记录 ${data.orphans.length} 枚`),
                  React.createElement('span', { className: 'akp-spacer' }),
                  React.createElement('button', {
                    type: 'button', className: 'akp-btn akp-danger', disabled: busy, onClick: cleanOrphans,
                  }, '清理'))
              : null,
            data !== null && editing?.mode !== 'create'
              ? React.createElement('button', {
                  type: 'button', className: 'akp-btn', disabled: busy,
                  onClick: () => setEditing({ mode: 'create', id: null }),
                }, COPY.add)
              : null,
          ) : null,
        );
      }

      const inject = ['slots', 'remote'];

      async function apply(ctx) {
        const disposeRemote = await ctx.remote.$mount(TYPERT_REMOTE);
        const remote = ctx.get('remote.apiKeyPool');
        if (remote === undefined || remote === null) {
          await disposeRemote();
          throw new Error('dsh-api-key-pool: Remote 挂载后不可用');
        }

        ctx.slots.inject('settings.plugin.item', () =>
          ctx.slots.register(
            {
              name: 'settings.plugin.item',
              key: 'api-key-pool',
              id: '@deepseek-harness/dsh-api-key-pool',
              order: 130,
              inject: () => ({ remote }),
            },
            ApiKeyPoolCard,
          ),
        );

        return async () => { await disposeRemote(); };
      }

      module.exports.apply = apply;
      module.exports.inject = inject;
      return module.exports;
    },
  });
})();
