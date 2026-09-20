window.__ModuleLoader__.load({
	id: "dsh-cline-key-card",
	factory: (require) => {
		var module = { exports: {} };
		var exports = module.exports;
		Object.defineProperty(exports, Symbol.toStringTag, { value: "Module" });
		let react = require("react");
		const { useState, useEffect, useCallback } = react;
		const h = react.createElement;

		//#region 常量
		const LEGACY_REF = "CLINE_API_KEY";
		const POOL_REF_BASE = "CLINE_API_KEY_";
		const POOL_SCAN_MAX = 32;
		const KEY_HELP_URL = "https://app.cline.bot/dashboard/account?tab=api-keys";
		//#endregion

		//#region 托管集合与分阶段结果（GOAL-84 / M04、M05）
		// 本卡片允许管理的凭据 ref 全集：旧单 Key ref、固定扫描范围 1..N、
		// 以及当前池配置里引用的本插件 ref（兼容旧代码保存的超限 ref）。
		// 绝不扫描或清除其他插件的 ref。
		function settingsValue(settingsScope) {
			const snapshot = settingsScope?.getSnapshot?.();
			if (snapshot?.status !== 'ready' || !snapshot.writable || snapshot.mode !== 'host') {
				throw new Error('配置尚未就绪或不可写，请稍后重试；本次不修改凭据。');
			}
			return snapshot.value || {};
		}
		function poolConfigRefs(settingsScope) {
			const value = settingsValue(settingsScope);
			return [value.apiKeyEnvPool, value.apiKeyCleanupRefs].flatMap(pool =>
				Array.isArray(pool) ? pool.filter(item => typeof item === 'string'
					&& (item === LEGACY_REF || /^CLINE_API_KEY_[1-9]\d*$/.test(item))) : []);
		}
		async function writeSetting(settingsScope, field, value) {
			const result = await settingsScope.set(field, value);
			if (result?.ok === false) throw new Error('配置写入未确认');
		}
		function managedRefs(settingsScope) {
			const refs = new Set([LEGACY_REF]);
			for (let i = 1; i <= POOL_SCAN_MAX; i++) refs.add(POOL_REF_BASE + i);
			for (const ref of poolConfigRefs(settingsScope)) refs.add(ref);
			return [...refs];
		}
		//#endregion

		//#region 样式（外框类名与 dsh-connect-trae 家族同款，仅本卡片私有类名带 ckc- 前缀）
		const CARD_CSS = `
.dsm-plugin-card{border:1px solid var(--dsw-alias-border-l2,#36373b);background:var(--dsw-alias-bg-layer-3,#202126);border-radius:12px;list-style:none;transition:border-color .16s,background .16s}
.dsm-plugin-card:hover{border-color:var(--dsw-alias-label-dimmed,#777)}
.dsm-plugin-card-open{background:var(--dsw-alias-bg-layer-2,#25262b);border-color:var(--dsw-alias-label-dimmed,#777)}
.dsm-plugin-card-header{appearance:none;width:100%;font:inherit;color:inherit;text-align:left;cursor:pointer;background:transparent;border:0;border-radius:12px;align-items:center;gap:12px;padding:14px 16px;display:flex}
.dsm-plugin-card-header:focus-visible{outline:2px solid var(--dsw-alias-brand-primary,#5686fe);outline-offset:-2px}
.dsm-plugin-card-head{flex-direction:column;flex:1;gap:4px;min-width:0;display:flex}
.dsm-plugin-card-title{color:var(--dsw-alias-label-primary,#e6e6e6);font-size:15px;font-weight:600;line-height:1.4}
.dsm-plugin-card-description{color:var(--dsw-alias-label-tertiary,#999);font-size:13px;line-height:1.5}
.dsm-plugin-card-chevron{color:var(--dsw-alias-label-tertiary,#999);flex:none;display:inline-flex;transition:transform .16s}
.dsm-plugin-card-chevron-open{transform:rotate(180deg)}
.dsm-plugin-card-body{border-top:1px solid var(--dsw-alias-border-l2,#36373b);margin:0 16px;padding:0 0 8px}
.dsm-plugin-card-icon{width:32px;height:32px;flex:none;border-radius:7px}
.dsm-btn{appearance:none;font:inherit;cursor:pointer;border:1px solid transparent;border-radius:8px;padding:5px 14px;font-size:13px;line-height:1.5}
.dsm-btn:focus-visible{outline:2px solid var(--dsw-alias-brand-primary,#5686fe);outline-offset:1px}
.dsm-btn:disabled{opacity:.4;cursor:default}
.dsm-btn-outline{border-color:var(--dsw-alias-border-l2);color:var(--dsw-alias-label-secondary);background:transparent;font-weight:500}
.dsm-btn-outline:hover:not(:disabled){color:var(--dsw-alias-label-primary);border-color:var(--dsw-alias-label-dimmed);background:rgba(255,255,255,.04)}
.dsm-btn-primary{background:var(--dsw-alias-label-primary);color:var(--dsw-alias-bg-layer-3)}
.dsm-btn-primary:hover:not(:disabled){opacity:.9}
.dsm-btn-danger{border-color:var(--dsw-alias-state-error-primary,#ef4444);color:var(--dsw-alias-state-error-primary,#ef4444);background:transparent}
.dsm-btn-danger:hover:not(:disabled){background:rgba(239,68,68,.08)}
.ckc-body{display:flex;flex-direction:column;gap:12px;margin:0;padding:16px 0 8px}
.ckc-status{display:flex;align-items:center;gap:10px;font-size:14px;font-weight:500;color:var(--dsw-alias-label-primary,#e6e6e6)}
.ckc-dot{width:9px;height:9px;border-radius:50%;flex:0 0 auto}
.ckc-dot-ok{background:var(--dsw-alias-state-success-primary,#3f8d60)}
.ckc-dot-missing{background:var(--dsw-alias-state-error-primary,#ef4444)}
.ckc-row{display:flex;gap:8px;align-items:center;justify-content:flex-end}
.ckc-textarea{box-sizing:border-box;width:100%;min-height:88px;font:inherit;font-size:13px;line-height:1.6;color:var(--dsw-alias-label-primary,#e6e6e6);background:var(--dsw-alias-bg-layer-3,#2a2c33);border:1px solid var(--dsw-alias-border-l2,#3a3d45);border-radius:10px;padding:10px 12px;resize:vertical;font-family:ui-monospace,SFMono-Regular,Menlo,monospace;transition:border-color .15s,box-shadow .15s}
.ckc-textarea:focus-visible{outline:none;border-color:var(--dsw-alias-brand-primary,#5686fe);box-shadow:0 0 0 3px rgba(86,134,254,.22)}
.ckc-textarea::placeholder{color:var(--dsw-alias-label-dimmed,#666);font-family:inherit}
.ckc-hint{margin:0;font-size:12px;line-height:18px;color:var(--dsw-alias-label-tertiary,#9aa0a8)}
.ckc-hint a{color:var(--dsw-alias-label-secondary,#b8b8b8);text-underline-offset:2px}
.ckc-msg{margin:0;font-size:12px;line-height:18px;color:var(--dsw-alias-state-success-primary,#3f8d60)}
.ckc-err{margin:0;font-size:12px;line-height:18px;color:var(--dsw-alias-state-error-primary,#ef4444)}
`;
		const PLUGIN_ICON = "data:image/svg+xml," + encodeURIComponent(
			'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32">' +
			'<rect width="32" height="32" rx="7" fill="#1f2430"/>' +
			'<circle cx="13" cy="16" r="4.2" fill="none" stroke="url(#g)" stroke-width="2.4"/>' +
			'<path d="M17.2 16h8M22 16v3.4M25.2 16v2.2" stroke="url(#g)" stroke-width="2.4" stroke-linecap="round"/>' +
			'<defs><linearGradient id="g" x1="0" y1="0" x2="32" y2="32">' +
			'<stop stop-color="#ffb84d"/><stop offset="1" stop-color="#ff7a45"/></linearGradient></defs></svg>'
		);
		const CHEVRON = "data:image/svg+xml," + encodeURIComponent(
			'<svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 14 14" fill="none">' +
			'<path d="M3 5l4 4 4-4" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/></svg>'
		);
		//#endregion

		if (typeof document !== 'undefined') {
			const cssId = 'dsh-cline-key-card/client.css';
			if (!document.querySelector(`style[data-plugin-css="${cssId}"]`)) {
				const styleTag = document.createElement('style');
				styleTag.dataset.plugin = 'dsh-cline-key-card';
				styleTag.dataset.pluginCss = cssId;
				styleTag.textContent = CARD_CSS;
				document.head.appendChild(styleTag);
			}
		}

		//#region 卡片组件
		function ClineKeyCard({ remote, settingsScope }) {
			const [open, setOpen] = useState(false);
			const [draft, setDraft] = useState('');
			const [busyKind, setBusyKind] = useState(null);   // null | 'save' | 'clear'
			const [legacy, setLegacy] = useState(null);       // 旧单 Key ref 是否配置
			const [poolConfigured, setPoolConfigured] = useState(null); // 池内已配置的 Key 数
			const [message, setMessage] = useState(null);     // { kind: 'ok' | 'error', text }
			const busy = busyKind !== null;

			const refresh = useCallback(async () => {
				try {
					const refs = managedRefs(settingsScope);
					const response = await remote.credentials.describe(refs);
					if (!response.ok) {
						setLegacy(null);
						setPoolConfigured(null);
						return;
					}
					const value = response.value || {};
					setLegacy(Boolean(value[LEGACY_REF] && value[LEGACY_REF].configured));
					let count = 0;
					for (const ref of refs) {
						if (ref !== LEGACY_REF && value[ref] && value[ref].configured) count++;
					}
					setPoolConfigured(count);
				} catch {
					setLegacy(null);
					setPoolConfigured(null);
				}
			}, [remote, settingsScope]);

			useEffect(() => {
				void refresh();
				return settingsScope?.subscribe?.(() => { void refresh(); });
			}, [refresh, settingsScope]);

			// 清理一个不再使用的旧池位：probe + unset，且检查每一步实际返回。
			// 返回 null 表示成功，字符串表示失败或状态未知原因。
			const clearOneRef = useCallback(async (ref) => {
				try {
					const probe = await remote.credentials.describe([ref]);
					if (!probe.ok) return `${ref}: 状态未知（describe 失败），无法确认清除`;
					if (!(probe.value && probe.value[ref] && probe.value[ref].configured)) return null;
					const result = await remote.credentials.unset(ref);
					if (result && result.ok === false) {
						return `${ref}: ${result.error && result.error.message ? result.error.message : '清除未确认'}`;
					}
					return null;
				} catch (error) {
					return `${ref}: ${String(error)}`;
				}
			}, [remote]);

			const save = useCallback(async () => {
				if (busy) return;
				const keys = [...new Set(draft.split('\n').map(line => line.trim()).filter(line => line.length > 0))];
				if (keys.length === 0) {
					setMessage({ kind: 'error', text: '请先粘贴至少一把 Key（每行一把）。' });
					return;
				}
				if (keys.length > POOL_SCAN_MAX) {
					setMessage({ kind: 'error', text: `最多保存 ${POOL_SCAN_MAX} 把 Key（去重后当前 ${keys.length} 把）。请删减后重试；本次未写入任何凭据。` });
					return;
				}
				setBusyKind('save');
				setMessage(null);
				try {
					const previousRefs = managedRefs(settingsScope);
					const newRefs = keys.map((_, i) => POOL_REF_BASE + (i + 1));
					const pendingRefs = previousRefs.filter(ref => ref !== LEGACY_REF && !newRefs.includes(ref));
					// 阶段 1：逐把写入池 refs（CLINE_API_KEY_1..N）。任何失败都不再
					// 进入后续阶段（不删旧位、不下发池配置），保留编辑输入。
					const writeFailures = [];
					for (let i = 0; i < keys.length; i++) {
						const ref = POOL_REF_BASE + (i + 1);
						const response = await remote.credentials.set(ref, keys[i]);
						if (!response.ok) writeFailures.push(`${ref}: ${response.error && response.error.message ? response.error.message : '未知错误'}`);
					}
					if (writeFailures.length > 0) {
						setMessage({ kind: 'error', text: `保存未完成：${keys.length - writeFailures.length}/${keys.length} 把 Key 已写入；失败项：${writeFailures.join('；')}。旧配置未改动，编辑内容已保留，可修改后重试。` });
						await refresh();
						return;
					}
					// 阶段 2：下发池配置（provider onChange 重建 profiles）。
					let configOk = true;
					if (settingsScope !== undefined) {
						try {
							// 先持久化旧ref，避免配置切换后丢失超限项；不存Key内容。
							await writeSetting(settingsScope, 'apiKeyCleanupRefs', pendingRefs);
							await writeSetting(settingsScope, 'apiKeyEnvPool', newRefs);
						} catch {
							configOk = false;
						}
					}
					if (!configOk) {
						setMessage({ kind: 'error', text: `已写入 ${keys.length} 把 Key，但轮询池配置未确认生效；旧池位未清理。请重试保存。` });
						await refresh();
						return;
					}
					// 阶段 3：清理本次未用到的旧池位（含旧代码可能残留的超限 ref）。
					// 旧单 Key ref（CLINE_API_KEY）仍出现在 provider 的 poolRefs 里，
					// 不算“不再使用”，只在“全部清除”时移除。
					const cleanupFailures = [];
					const failedRefs = [];
					for (const ref of pendingRefs) {
						const failure = await clearOneRef(ref);
						if (failure !== null) { cleanupFailures.push(failure); failedRefs.push(ref); }
					}
					await writeSetting(settingsScope, 'apiKeyCleanupRefs', failedRefs);
					setDraft('');
					if (cleanupFailures.length > 0) {
						setMessage({ kind: 'error', text: `已保存 ${keys.length} 把 Key，新配置已生效；旧项清理未完成：${cleanupFailures.join('；')}。待清理项已保留，可重新粘贴后保存或点击全部清除重试。` });
					} else {
						setMessage({ kind: 'ok', text: `已保存 ${keys.length} 把 Key（轮询 + 失败自动切换）。新 Key 最迟约 1 分钟内进入轮询。` });
					}
					await refresh();
				} catch (error) {
					setMessage({ kind: 'error', text: `保存失败：${String(error)}` });
				} finally {
					setBusyKind(null);
				}
			}, [draft, busy, remote, settingsScope, refresh, clearOneRef]);

			const clearAll = useCallback(async () => {
				if (busy) return;
				setBusyKind('clear');
				setMessage(null);
				try {
					// 阶段 1：清理全部本插件托管 ref（旧单 Key、固定范围、池配置引用）。
					const failures = [];
					for (const ref of managedRefs(settingsScope)) {
						const failure = await clearOneRef(ref);
						if (failure !== null) failures.push(failure);
					}
					if (failures.length > 0) {
						await refresh();
						setMessage({ kind: 'error', text: `清除未全部完成，失败项：${failures.join('；')}。原池配置与待清理列表已保留，请重试。` });
						return;
					}
					// 阶段 2：仅在凭据均已清除后停用配置。
					let configOk = true;
					if (settingsScope !== undefined) {
						try {
							await writeSetting(settingsScope, 'apiKeyEnvPool', []);
							await writeSetting(settingsScope, 'apiKeyCleanupRefs', []);
						} catch {
							configOk = false;
						}
					}
					await refresh();
					if (!configOk) {
						setMessage({ kind: 'error', text: '凭据已清除，但轮询池配置停用未确认成功；请重试清除。' });
						return;
					}
					setMessage({ kind: 'ok', text: '已清除全部 Cline Key 并停用轮询池。' });
				} catch (error) {
					setMessage({ kind: 'error', text: `清除失败：${String(error)}` });
				} finally {
					setBusyKind(null);
				}
			}, [busy, remote, settingsScope, refresh, clearOneRef]);

			const total = (legacy ? 1 : 0) + (poolConfigured ?? 0);
			const statusText = poolConfigured === null && legacy === null
				? '状态未知'
				: total > 0
					? `已配置 ${total} 把 Key${(poolConfigured ?? 0) > 1 ? '（轮询池已启用）' : ''}`
					: '未配置';
			return h('li', { className: `dsm-plugin-card${open ? ' dsm-plugin-card-open' : ''}` },
				h('button', {
					type: 'button',
					className: 'dsm-plugin-card-header',
					'aria-expanded': open,
					onClick: () => setOpen(!open),
				},
					h('img', { className: 'dsm-plugin-card-icon', src: PLUGIN_ICON, alt: '' }),
					h('span', { className: 'dsm-plugin-card-head' },
						h('span', { className: 'dsm-plugin-card-title' }, 'Cline Free API Key'),
						h('span', { className: 'dsm-plugin-card-description' }, '为 Cline 免费模型接入（dsh-cline-free-provider）填写 API Key，支持多 Key 轮询。'),
					),
					h('span', {
						'aria-hidden': 'true',
						className: `dsm-plugin-card-chevron${open ? ' dsm-plugin-card-chevron-open' : ''}`,
					}, h('img', { src: CHEVRON, alt: '', width: 14, height: 14 })),
				),
				open ? h('div', { className: 'dsm-plugin-card-body' },
					h('div', { className: 'ckc-body' },
						h('div', { className: 'ckc-status', role: 'status' },
							h('span', { 'aria-hidden': 'true', className: `ckc-dot ${total > 0 ? 'ckc-dot-ok' : 'ckc-dot-missing'}` }),
							h('span', null, `Cline Key：${statusText}`),
						),
						h('textarea', {
							className: 'ckc-textarea',
							autoComplete: 'off',
							spellCheck: false,
							placeholder: `每行一把 Cline API Key（最多 ${POOL_SCAN_MAX} 把，自动轮询与失败切换）\nsk-xxxxxxxx\nsk-yyyyyyyy`,
							'aria-label': 'Cline API Key 列表',
							value: draft,
							disabled: busy,
							onChange: (event) => setDraft(event.target.value),
						}),
						h('div', { className: 'ckc-row' },
							(total > 0 || poolConfigured === null) ? h('button', {
								type: 'button',
								className: 'dsm-btn dsm-btn-danger',
								disabled: busy,
								onClick: () => { void clearAll(); },
							}, busyKind === 'clear' ? '清除中…' : '全部清除') : null,
							h('button', {
								type: 'button',
								className: 'dsm-btn dsm-btn-primary',
								disabled: busy || draft.trim().length === 0,
								onClick: () => { void save(); },
							}, busyKind === 'save' ? '保存中…' : '保存'),
						),
						message ? h('p', { className: message.kind === 'ok' ? 'ckc-msg' : 'ckc-err' }, message.text) : null,
						h('p', { className: 'ckc-hint' },
							'Key 逐把保存在 DSH 凭据服务（', h('code', null, 'CLINE_API_KEY_N'), `，最多 ${POOL_SCAN_MAX} 把），不会写入会话或日志。调度语义：每请求轮询一把，遇到 401/403/429 自动冷却该 Key 并换下一把重放；已产出内容后的失败不重放，下一轮自动避开。获取 Key：`,
							h('a', { href: KEY_HELP_URL, target: '_blank', rel: 'noreferrer' }, 'Cline Dashboard → API Keys'),
							'。',
						),
					),
				) : null,
			);
		}
		//#endregion

		//#region 客户端入口
		const name = 'dsh-cline-key-card-client';
		const inject = ['remote', 'remote.credentials', 'settingsScope', 'slots'];

		function apply(ctx) {
			try {
				const remote = ctx.remote
				const settingsScope = ctx.settingsScope.bind({ namespace: 'cline-free-provider' })
				// 插件页按 settings 命名空间派发卡片（entryKey = ns），本卡编辑的是
				// dsh-cline-free-provider 安装的 cline-free-provider 命名空间。
				ctx.slots.inject('settings.plugin.item', () => ctx.slots.register({
					name: 'settings.plugin.item',
					key: 'cline-free-provider',
					priority: 30,
					inject: () => ({ remote, settingsScope }),
				}, ClineKeyCard));
			} catch (error) {
				console.error('[dsh-cline-key-card] client card failed to load:', error);
			}
		}
		//#endregion

		exports.apply = apply;
		exports.inject = inject;
		exports.name = name;
		return module.exports;
	}
});
