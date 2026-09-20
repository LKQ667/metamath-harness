import { createReadStream, existsSync, mkdirSync, readFileSync, readdirSync } from "node:fs";
import { mkdir, readFile, rename, rm, stat, writeFile } from "node:fs/promises";
import { homedir } from "node:os";
import { basename, dirname, join, normalize, resolve, sep } from "node:path";
import { fileURLToPath } from "node:url";
import { resolveDshHome } from "@deepseek-ai/dsh-home-paths";
import { credentialRef } from "@deepseek-ai/dsh-credentials";
import { BlockAssembler, ReasoningEffortId, createAssistantMessage, createUserMessage } from "@deepseek-ai/dsh-llm";
import { spawn } from "node:child_process";
import { createRequire } from "node:module";
import { downloadArtifact } from "@electron/get";
import extract from "@electron-internal/extract-zip";
import { randomUUID } from "node:crypto";

//#region src/host/balance.ts
/**
* 余额查询（host 半侧）：把「当前服务商」映射到对应的余额/用量接口并抓取。
*
* 设计：
* - 数据源按「服务商 provider id」寻址（来源 = agentDefaultModel.currentSelection().provider）；
* - 只登记有公开查询接口的服务商；未登记（如 opencode/Zen 暂无官方余额 API）→ 显式
*   `unsupported`，由上层决定不显示，绝不静默伪造 0 余额；
* - key 由调用方经 DSH 官方 credentialRef 解析后注入（不直接读 .credentials.yaml）；
* - 网络超时 + 重试（实测该环境对境外端点间歇性超时）。
*/
/** 抓取超时（ms） */
const FETCH_TIMEOUT_MS = 2e4;
/** 单次抓取失败后的重试次数（失败间隔 0.8s 线性退避） */
const RETRIES = 3;
const BALANCE_PROVIDERS = [{
	ids: ["opencode-go"],
	ref: "OPENCODE_GO_API_KEY",
	kind: "opencode"
}, {
	ids: ["deepseek-official"],
	ref: "DEEPSEEK_API_KEY",
	kind: "deepseek"
}];
function matchBalanceProvider(provider) {
	return BALANCE_PROVIDERS.find((p) => p.ids.includes(provider));
}
/** fetch 一次，带超时；失败抛错（调用方决定是否重试） */
async function fetchOnce(url, key) {
	return fetch(url, {
		headers: {
			Authorization: "Bearer " + key,
			"User-Agent": "dsh-pet-balance"
		},
		signal: AbortSignal.timeout(FETCH_TIMEOUT_MS)
	});
}
/** fetch + 重试；全败抛最后错误 */
async function fetchWithRetry(url, key) {
	let last;
	for (let i = 0; i <= RETRIES; i++) try {
		return await fetchOnce(url, key);
	} catch (e) {
		last = e;
		if (i < RETRIES) await new Promise((r) => setTimeout(r, 800));
	}
	throw last instanceof Error ? last : new Error(String(last));
}
/** 数字兜底校验：数值化失败或非有限数 → throw（数据异常显式报错，不静默当 0） */
function num(value, what) {
	const n = Number(value);
	if (!Number.isFinite(n)) throw new Error("dsh-pet: 余额数据非法字段 " + what);
	return n;
}
/** 字符串兜底校验：非空字符串，否则 throw */
function str(value, what) {
	if (typeof value !== "string" || value.length === 0) throw new Error("dsh-pet: 余额数据非法字段 " + what);
	return value;
}
/** 抓取 OpenCode Go 用量（/zen/go/v1/usage） */
async function fetchOpencode(key, provider) {
	const res = await fetchWithRetry("https://opencode.ai/zen/go/v1/usage", key);
	if (!res.ok) throw new Error("opencode usage HTTP " + res.status);
	const body = await res.json();
	const usage = body?.usage;
	if (!usage || typeof usage !== "object") throw new Error("dsh-pet: opencode usage 响应缺少 usage");
	const u = usage;
	const rolling = u.rolling, weekly = u.weekly, monthly = u.monthly;
	if (!rolling || !weekly || !monthly) throw new Error("dsh-pet: opencode usage 响应缺少窗口");
	return {
		ok: true,
		provider,
		kind: "opencode",
		data: {
			rolling: num(rolling.percent, "rolling.percent"),
			weekly: num(weekly.percent, "weekly.percent"),
			monthly: num(monthly.percent, "monthly.percent"),
			rollingResetsAt: str(rolling.resetsAt, "rolling.resetsAt"),
			weeklyResetsAt: str(weekly.resetsAt, "weekly.resetsAt"),
			monthlyResetsAt: str(monthly.resetsAt, "monthly.resetsAt")
		}
	};
}
/** 抓取 DeepSeek 余额（/user/balance） */
async function fetchDeepseek(key, provider) {
	const res = await fetchWithRetry("https://api.deepseek.com/user/balance", key);
	if (!res.ok) throw new Error("deepseek balance HTTP " + res.status);
	const body = await res.json();
	const infos = body?.balance_infos;
	if (!Array.isArray(infos) || infos.length === 0) throw new Error("dsh-pet: deepseek balance 响应缺少 balance_infos");
	const first = infos[0];
	return {
		ok: true,
		provider,
		kind: "deepseek",
		data: {
			currency: str(first.currency, "currency"),
			total: str(first.total_balance, "total_balance"),
			granted: str(first.granted_balance, "granted_balance"),
			toppedUp: str(first.topped_up_balance, "topped_up_balance")
		}
	};
}
async function queryBalance(provider, resolveKey) {
	const match = matchBalanceProvider(provider);
	if (!match) return {
		ok: false,
		provider,
		reason: "unsupported"
	};
	const rc = await resolveKey(match.ref);
	if (!rc) return {
		ok: false,
		provider,
		reason: "credential-missing",
		message: "缺少凭证 " + match.ref
	};
	try {
		return match.kind === "opencode" ? await fetchOpencode(rc, provider) : await fetchDeepseek(rc, provider);
	} catch (e) {
		return {
			ok: false,
			provider,
			reason: "fetch-error",
			message: e instanceof Error ? e.message : String(e)
		};
	}
}

//#endregion
//#region src/host/llm-reasoning.ts
async function supportsReasoningOff(ctx, provider, model) {
	const llm = ctx.llm;
	if (!llm || typeof llm.resolveModelInfo !== "function") return false;
	try {
		const info = await llm.resolveModelInfo(provider, model);
		return info?.reasoning?.efforts?.some((e) => e.id === "off") ?? false;
	} catch {
		return false;
	}
}

//#endregion
//#region src/host/whisper.ts
/** 单次生成超时（ms）：骈骈念不需要长输出，30s 足够 */
const TIMEOUT_MS$1 = 3e4;
/** 碎碎念指令：纯文本（原行为） */
const USER_TEXT = "随便说一句日常碎碎念，一句就好，20 字以内。";
/**
* 碎碎念指令：带表情包（用户开启 whisperImageEnabled 时）——要求模型配合作画说一句。
* 明确「正文仍是一句话」：图是配图，不是让模型描述画面本身。
*/
function userTextWithMeme(meme) {
	return "随便说一句日常碎碎念，一句就好，20 字以内。\n这次会配一张表情包一起显示，图的内容是：" + meme.name + "（" + meme.desc + "）。\n请让这句话和这张图的情绪/场景自然契合，像是配合画面说出来的；不要描述画面本身。";
}
async function generateWhisper(ctx, system, meme) {
	let sel;
	try {
		sel = ctx.agentDefaultModel.currentSelection();
	} catch {
		return {
			ok: false,
			reason: "provider-missing",
			message: "当前对话未配置模型"
		};
	}
	if (!sel?.provider || !sel?.model) return {
		ok: false,
		reason: "provider-missing",
		message: "当前对话未配置模型"
	};
	const llm = ctx.llm;
	if (!llm || typeof llm.stream !== "function") return {
		ok: false,
		reason: "generate-error",
		message: "LLM 服务不可用"
	};
	const deadline = AbortSignal.timeout(TIMEOUT_MS$1);
	const supportsOff = await supportsReasoningOff(ctx, sel.provider, sel.model);
	const options = {
		provider: sel.provider,
		model: sel.model,
		messages: [createUserMessage({
			content: [{
				type: "text",
				text: meme ? userTextWithMeme(meme) : USER_TEXT
			}],
			source: {
				kind: "plugin",
				plugin: "dsh-pet"
			}
		})],
		system,
		temperature: 1,
		...supportsOff ? { reasoningEffort: ReasoningEffortId("off") } : {},
		signal: deadline
	};
	const assembler = new BlockAssembler();
	try {
		for await (const chunk of llm.stream(options)) assembler.push(chunk);
	} catch (e) {
		return {
			ok: false,
			reason: "generate-error",
			message: e instanceof Error ? e.message : String(e)
		};
	}
	const text = assembler.blocks().filter((b) => b.type === "text").map((b) => "text" in b ? b.text : "").join("").trim();
	if (!text) return {
		ok: false,
		reason: "generate-error",
		message: "模型未返回文本"
	};
	return meme ? {
		ok: true,
		text,
		image: meme.name
	} : {
		ok: true,
		text
	};
}

//#endregion
//#region src/host/memes.ts
const MEMES_DIR = "memes";
function readMemePool(memes, assetsRoot) {
	if (!memes || typeof memes !== "object" || Array.isArray(memes)) return [];
	const dir = join(assetsRoot, MEMES_DIR);
	const out = [];
	for (const [name$1, desc] of Object.entries(memes)) {
		const text = typeof desc === "string" ? desc.trim() : "";
		if (!name$1 || !text) continue;
		if (!existsSync(join(dir, name$1 + ".png"))) continue;
		out.push({
			name: name$1,
			desc: text
		});
	}
	return out.sort((a, b) => a.name.localeCompare(b.name, "zh"));
}
function pickMeme(pool, random = Math.random) {
	if (pool.length === 0) return void 0;
	const idx = Math.floor(random() * pool.length) % pool.length;
	return pool[idx];
}
function matchMeme(pool, name$1) {
	const key = String(name$1 ?? "").trim();
	return key ? pool.find((m) => m.name === key) : void 0;
}
/** 配图选择标记：`[图:名称]` 附在回复末尾（容忍全角冒号与前后空白） */
const IMG_TAG = /\[图[:：]\s*([^\]\n]+?)\s*\]\s*$/;
function extractChatImage(text, pool) {
	const m = IMG_TAG.exec(text);
	if (!m) return { text };
	const hit = matchMeme(pool, m[1] ?? "");
	const body = text.slice(0, m.index).trim();
	if (!hit || !body) return { text };
	return {
		text: body,
		image: hit.name
	};
}
function memeCatalog(pool) {
	return pool.map((m) => "- " + m.name + "：" + m.desc).join("\n");
}

//#endregion
//#region src/host/chat.ts
/** 单次生成超时（ms）：对话等 LLM 回复，60s 足够 */
const TIMEOUT_MS = 6e4;
/** 配图指令：附在 user 正文之后（紧邻回答位置，模型更容易遵守） */
function imageInstruction(pool) {
	return "\n\n[配图] 回复结尾可选附一张表情包给用户看，从下列清单里挑最贴合当前语境的：\n" + memeCatalog(pool) + "\n挑中就在回复最后另起一行写 [图:名称]（名称原样照抄）；没有合适的就完全不要写这个标记。";
}
async function generateChat(ctx, system, history, userText, pool = []) {
	let sel;
	try {
		sel = ctx.agentDefaultModel.currentSelection();
	} catch {
		return {
			ok: false,
			reason: "provider-missing",
			message: "当前对话未配置模型"
		};
	}
	if (!sel?.provider || !sel?.model) return {
		ok: false,
		reason: "provider-missing",
		message: "当前对话未配置模型"
	};
	const llm = ctx.llm;
	if (!llm || typeof llm.stream !== "function") return {
		ok: false,
		reason: "generate-error",
		message: "LLM 服务不可用"
	};
	const historyMessages = history.map((m) => m.role === "user" ? createUserMessage({
		content: [{
			type: "text",
			text: m.content
		}],
		source: {
			kind: "plugin",
			plugin: "dsh-pet"
		}
	}) : createAssistantMessage({
		content: [{
			type: "text",
			text: m.content
		}],
		source: {
			provider: sel.provider,
			model: sel.model
		}
	}));
	const deadline = AbortSignal.timeout(TIMEOUT_MS);
	const supportsOff = await supportsReasoningOff(ctx, sel.provider, sel.model);
	const wantImage = pool.length > 0;
	const options = {
		provider: sel.provider,
		model: sel.model,
		messages: [...historyMessages, createUserMessage({
			content: [{
				type: "text",
				text: wantImage ? userText + imageInstruction(pool) : userText
			}],
			source: {
				kind: "plugin",
				plugin: "dsh-pet"
			}
		})],
		system,
		temperature: 1,
		...supportsOff ? { reasoningEffort: ReasoningEffortId("off") } : {},
		signal: deadline
	};
	const assembler = new BlockAssembler();
	try {
		for await (const chunk of llm.stream(options)) assembler.push(chunk);
	} catch (e) {
		return {
			ok: false,
			reason: "generate-error",
			message: e instanceof Error ? e.message : String(e)
		};
	}
	const text = assembler.blocks().filter((b) => b.type === "text").map((b) => "text" in b ? b.text : "").join("").trim();
	if (!text) return {
		ok: false,
		reason: "generate-error",
		message: "模型未返回文本"
	};
	if (!wantImage) return {
		ok: true,
		text
	};
	const picked = extractChatImage(text, pool);
	return picked.image ? {
		ok: true,
		text: picked.text,
		image: picked.image
	} : {
		ok: true,
		text: picked.text
	};
}

//#endregion
//#region src/host/config.ts
/** 位置角落白名单 */
const CORNERS = [
	"top-left",
	"top-right",
	"bottom-left",
	"bottom-right"
];
const CORNER_SET = new Set(CORNERS);
/** display 白名单 */
const PET_DISPLAYS = [
	"web",
	"desktop",
	"both",
	"none"
];
const PET_DISPLAY_SET = new Set(PET_DISPLAYS);
/** id 禁用的字符（Windows 文件名保留符 + 控制字符，防配置值逃逸文件路径） */
const ID_FORBIDDEN = /[\\/:\x00-\x1f]/;
/** 已告警过的 文件:字段（进程内去重：同一问题只告警一次，避免每请求刷屏；重启重置） */
const warnedKeys = new Set();
function warnOnce(key, message) {
	if (warnedKeys.has(key)) return;
	warnedKeys.add(key);
	console.warn("dsh-pet: " + message);
}
/** 剥除 JSONC 注释（行注释 // 与块注释）得到纯 JSON */
function stripJsonc$1(src) {
	return src.replace(/\/\*[\s\S]*?\*\//g, "").replace(/(^|[^\\:])\/\/.*$/gm, "$1").trim();
}
/** 读取并解析 JSONC 文件；不存在/解析失败 → undefined（调用方决定处理） */
function readJsonc(path) {
	try {
		const raw = JSON.parse(stripJsonc$1(readFileSync(path, "utf8")));
		return raw && typeof raw === "object" ? raw : void 0;
	} catch {
		return void 0;
	}
}
/** 扫描 pet/ 目录：<名>-config.(json|jsonc) → 条目（按文件名排序） */
function scanPetFiles(petDir) {
	let entries;
	try {
		entries = readdirSync(petDir, { withFileTypes: true });
	} catch {
		return [];
	}
	return entries.filter((e) => e.isFile()).map((e) => e.name).filter((name$1) => /^.+?-config\.(json|jsonc)$/.test(name$1)).sort().map((name$1) => ({
		prefix: name$1.replace(/-config\.(json|jsonc)$/, ""),
		path: join(petDir, name$1)
	}));
}
/** animations 段完整性校验（与旧 assertAnimationsHost 同一套规则；不 throw，非法返回 false） */
function animationsValid(a) {
	if (!a || typeof a !== "object") return false;
	const anims = a;
	for (const key of [
		"idle",
		"turn",
		"drag",
		"clicks"
	]) if (!Array.isArray(anims[key])) return false;
	const moves = anims.moves;
	if (!moves || typeof moves !== "object" || typeof moves.default !== "object" || moves.default === null || !Array.isArray(moves.actions)) return false;
	if (!Array.isArray(anims.categories)) return false;
	const ev = anims.events;
	if (!ev || typeof ev !== "object" || Array.isArray(ev)) return false;
	const evEntries = ev;
	for (const pool of Object.values(evEntries)) {
		if (!Array.isArray(pool) || pool.length === 0) return false;
		for (const slot of pool) if (typeof slot === "string") {
			if (slot.length === 0) return false;
		} else if (Array.isArray(slot)) {
			if (slot.length === 0) return false;
			for (const name$1 of slot) if (typeof name$1 !== "string" || name$1.length === 0) return false;
		} else return false;
	}
	return true;
}
/** animationWeights 段校验（idle/turn/move 三个非负数字） */
function weightsValid(w) {
	if (!w || typeof w !== "object") return false;
	const weights = w;
	for (const key of [
		"idle",
		"turn",
		"move"
	]) {
		const v = Number(weights[key]);
		if (!Number.isFinite(v) || v < 0) return false;
	}
	return true;
}
/** physics 段校验：gravity ≥ 0（0 = 无重力，合法）、restitution ∈ [0,1]、groundFriction ≥ 0（均为有限数字）、
*  ceilingBounce 为布尔、throwPower > 0（有限数字）、petCollision 为布尔 */
function physicsValid(value) {
	if (!value || typeof value !== "object") return false;
	const p = value;
	const g = Number(p.gravity);
	const r = Number(p.restitution);
	const f = Number(p.groundFriction);
	const tp = Number(p.throwPower);
	return Number.isFinite(g) && g >= 0 && Number.isFinite(r) && r >= 0 && r <= 1 && Number.isFinite(f) && f >= 0 && typeof p.ceilingBounce === "boolean" && Number.isFinite(tp) && tp > 0 && typeof p.petCollision === "boolean";
}
/** workStatusTexts 段校验：二维数组——外层每项都是非空字符串数组（档位文案，每档可多句随机）；空数组不可用 */
function workStatusTextsValid(value) {
	if (!Array.isArray(value) || value.length === 0) return false;
	for (const group of value) {
		if (!Array.isArray(group) || group.length === 0) return false;
		for (const text of group) if (typeof text !== "string" || text.length === 0) return false;
	}
	return true;
}
/** 顶层标量字段的合法性（非法与缺失同处理：取默认值 + 告警） */
function topFieldValid(key, value) {
	switch (key) {
		case "whisperPrompt": return typeof value === "string" && value.length > 0;
		case "chatMemoryRounds": {
			const n = Number(value);
			return Number.isFinite(n) && n >= 0;
		}
		case "notificationsEnabled": return typeof value === "boolean";
		case "whisperImageEnabled": return typeof value === "boolean";
		case "chatImageEnabled": return typeof value === "boolean";
		case "animations": return animationsValid(value);
		case "animationWeights": return weightsValid(value);
		case "physics": return physicsValid(value);
		case "workStatusTexts": return workStatusTextsValid(value);
		default: return true;
	}
}
/** eventsRefreshSec 段：深度合并——每个事件键都要有正数秒值；缺子键 → 静默取默认，显式写但非法 → 告警 + 默认 */
function mergeEventsRefreshSec(base, overlay, label) {
	const baseErs = base && typeof base === "object" ? base : {};
	const out = {};
	for (const [eventName, baseSec] of Object.entries(baseErs)) {
		const own = overlay && typeof overlay === "object" ? overlay[eventName] : void 0;
		if (own === void 0) {
			out[eventName] = Number(baseSec);
			continue;
		}
		const n = Number(own);
		if (!Number.isFinite(n) || n <= 0) {
			warnOnce(`${label}:eventsRefreshSec.${eventName}`, `「${label}」的 eventsRefreshSec.${eventName} 非法，已取默认值`);
			out[eventName] = Number(baseSec);
			continue;
		}
		out[eventName] = n;
	}
	return out;
}
/** 一个覆盖文件 → 完整条目：顶层逐字段合并（没写/非法 → 内置默认 + 告警），pets 逐实例 */
function mergeEntry(base, overlay, label, basePets, seenIds) {
	const out = {};
	for (const key of Object.keys(base)) {
		if (key === "pets") {
			out.pets = mergePets(basePets, overlay?.[key], label, seenIds);
			continue;
		}
		if (key === "eventsRefreshSec") {
			out[key] = mergeEventsRefreshSec(base[key], overlay?.[key], label);
			continue;
		}
		const own = overlay ? overlay[key] : void 0;
		if (own === void 0) {
			out[key] = base[key];
			continue;
		}
		if (!topFieldValid(key, own)) {
			warnOnce(`${label}:${key}`, `「${label}」的 ${key} 非法，已取默认值`);
			out[key] = base[key];
			continue;
		}
		out[key] = own;
	}
	return out;
}
/** pets 数组合并：文件没写/空 → 默认列表；逐实例合并（缺字段 → 内置默认 pets[0]，静默）。 */
function mergePets(basePets, raw, label, seenIds) {
	const basePet = basePets[0] ?? {};
	if (!Array.isArray(raw) || raw.length === 0) {
		warnOnce(`${label}:pets`, `「${label}」的 pets 缺失或为空，已取默认宠物列表`);
		return basePets;
	}
	const out = [];
	for (const item of raw) {
		const pet = mergePet(basePet, item, label, seenIds);
		if (pet) out.push(pet);
	}
	if (out.length === 0) {
		warnOnce(`${label}:pets`, `「${label}」的 pets 全部被跳过（id 非法/重复/冲突），已取默认宠物列表`);
		return basePets;
	}
	return out;
}
/** 宠物实例字段取数字；缺失 → 静默取默认（结构性常态）；显式写但非法 → 告警 + 默认 */
function petNumber(own, def, min, label, field, id) {
	const n = Number(own);
	if (own !== void 0 && own !== null && Number.isFinite(n) && n >= min) return n;
	if (own !== void 0 && own !== null) warnOnce(`${label}:${field}:${id}`, `宠物「${id}」的 ${field} 非法，已取默认值`);
	return Number(def);
}
/** 宠物实例字段取布尔；缺失 → 静默取默认；显式写但非法 → 告警 + 默认 */
function petBool(own, def, label, field, id) {
	if (typeof own === "boolean") return own;
	if (own !== void 0 && own !== null) warnOnce(`${label}:${field}:${id}`, `宠物「${id}」的 ${field} 非法，已取默认值`);
	return Boolean(def);
}
/** 宠物实例字段取白名单枚举；缺失 → 静默取默认；显式写但非法 → 告警 + 默认 */
function petEnum(own, set, def, label, field, id) {
	if (typeof own === "string" && set.has(own)) return own;
	if (own !== void 0 && own !== null) warnOnce(`${label}:${field}:${id}`, `宠物「${id}」的 ${field} 非法，已取默认值`);
	return typeof def === "string" ? def : "";
}
/** 一只实例 → 完成品实例（id 必须自己的且全局唯一；其余字段没写/非法 → 默认 + 告警） */
function mergePet(base, raw, label, seenIds) {
	const p = raw && typeof raw === "object" ? raw : {};
	const id = typeof p.id === "string" ? p.id.trim() : "";
	if (!id || id.length > 64 || ID_FORBIDDEN.test(id) || seenIds.has(id)) {
		warnOnce(`${label}:id:${id || "(空)"}`, `「${label}」的宠物 id「${id || "(空)"}」非法、重复或已存在，已跳过该实例`);
		return null;
	}
	seenIds.add(id);
	const rawName = typeof p.name === "string" ? p.name.trim() : "";
	const name$1 = rawName || id;
	if (!rawName) warnOnce(`${label}:name:${id}`, `宠物「${id}」缺少 name，已按 id 处理`);
	const basePos = base.position && typeof base.position === "object" ? base.position : {};
	const ownPos = p.position && typeof p.position === "object" ? p.position : {};
	return {
		id,
		name: name$1,
		size: petNumber(p.size, base.size, 1, label, "size", id),
		balanceEnabled: petBool(p.balanceEnabled, base.balanceEnabled, label, "balanceEnabled", id),
		whisperEnabled: petBool(p.whisperEnabled, base.whisperEnabled, label, "whisperEnabled", id),
		workStatusEnabled: petBool(p.workStatusEnabled, base.workStatusEnabled, label, "workStatusEnabled", id),
		display: petEnum(p.display, PET_DISPLAY_SET, base.display, label, "display", id),
		position: {
			corner: petEnum(ownPos.corner, CORNER_SET, basePos.corner, label, "position.corner", id),
			marginX: petNumber(ownPos.marginX, basePos.marginX, -Infinity, label, "position.marginX", id),
			marginY: petNumber(ownPos.marginY, basePos.marginY, -Infinity, label, "position.marginY", id)
		}
	};
}
function readAllConfig(paths) {
	const base = readJsonc(paths.defaultFile);
	if (!base) throw new Error("dsh-pet: 内置默认配置缺失或解析失败（安装损坏）：" + paths.defaultFile);
	const basePets = Array.isArray(base.pets) ? base.pets : [];
	const seenIds = new Set();
	const out = {};
	const mainOverlay = readJsonc(paths.userFile);
	if (existsSync(paths.userFile) && !mainOverlay) warnOnce("file:" + paths.userFile, "用户主配置解析失败，已按无用户配置处理：" + paths.userFile);
	out.main = mergeEntry(base, mainOverlay, "main-config.json", basePets, seenIds);
	for (const file of scanPetFiles(paths.petDir)) {
		const parsed = readJsonc(file.path);
		if (!parsed) {
			warnOnce("file:" + file.path, "文件宠物配置解析失败，已跳过：" + file.path);
			continue;
		}
		out[file.prefix] = mergeEntry(base, parsed, file.prefix + "-config.json", basePets, seenIds);
	}
	return out;
}
function flattenPetList(merged) {
	const out = [];
	for (const conf of Object.values(merged)) if (Array.isArray(conf?.pets)) out.push(...conf.pets);
	return out;
}
function findPetInstance(merged, petId) {
	for (const [entry, conf] of Object.entries(merged)) {
		const pets = Array.isArray(conf?.pets) ? conf.pets : [];
		const found = pets.find((p) => String(p.id) === petId);
		if (found) return {
			entry,
			conf,
			pet: found
		};
	}
	return void 0;
}
async function setFilePetVisibility(paths, petId, visible) {
	for (const file of scanPetFiles(paths.petDir)) {
		const parsed = readJsonc(file.path);
		const pets = Array.isArray(parsed?.pets) ? parsed.pets : [];
		const pet = pets.find((candidate) => String(candidate.id ?? "") === petId);
		if (!pet) continue;
		const current = typeof pet.display === "string" && PET_DISPLAY_SET.has(pet.display) ? pet.display : "web";
		if (visible) {
			const previous = typeof pet.dshPetDisplayBeforeClose === "string" && PET_DISPLAY_SET.has(pet.dshPetDisplayBeforeClose) && pet.dshPetDisplayBeforeClose !== "none" ? pet.dshPetDisplayBeforeClose : "web";
			pet.display = previous;
			delete pet.dshPetDisplayBeforeClose;
		} else {
			if (current !== "none") pet.dshPetDisplayBeforeClose = current;
			pet.display = "none";
		}
		await writeFile(file.path, JSON.stringify(parsed, null, 2) + "\n", "utf8");
		return { display: String(pet.display) };
	}
	return null;
}
function saveUserConfig(raw, existing) {
	const o = raw && typeof raw === "object" ? raw : {};
	const arr = Array.isArray(o.pets) ? o.pets : null;
	if (!arr || !arr.length) return null;
	const out = [];
	for (const p of arr) {
		if (!p || typeof p !== "object") return null;
		const pp = p;
		const id = String(pp.id ?? "");
		if (!id || id.length > 64 || ID_FORBIDDEN.test(id)) return null;
		const size = Number(pp.size);
		if (!Number.isFinite(size) || size <= 0) return null;
		let name$1 = typeof pp.name === "string" ? pp.name.trim() : "";
		if (!name$1) {
			console.warn(`dsh-pet: pet「${id}」缺少 name，已按默认 ${id}（宠物 id）处理`);
			name$1 = id;
		}
		const balanceEnabled = pp.balanceEnabled;
		if (typeof balanceEnabled !== "boolean") return null;
		const whisperEnabled = pp.whisperEnabled;
		if (whisperEnabled !== void 0 && typeof whisperEnabled !== "boolean") return null;
		const workStatusEnabled = pp.workStatusEnabled;
		if (workStatusEnabled !== void 0 && typeof workStatusEnabled !== "boolean") return null;
		const display = String(pp.display ?? "");
		if (!PET_DISPLAY_SET.has(display)) return null;
		const pos = pp.position && typeof pp.position === "object" ? pp.position : {};
		const corner = String(pos.corner ?? "");
		if (!CORNER_SET.has(corner)) return null;
		const marginX = Number(pos.marginX);
		const marginY = Number(pos.marginY);
		if (!Number.isFinite(marginX) || !Number.isFinite(marginY)) return null;
		out.push({
			id,
			name: name$1,
			size,
			balanceEnabled,
			whisperEnabled,
			workStatusEnabled,
			display,
			position: {
				corner,
				marginX,
				marginY
			}
		});
	}
	const ne = o.notificationsEnabled;
	if (ne !== void 0 && typeof ne !== "boolean") return null;
	const wie = o.whisperImageEnabled;
	if (wie !== void 0 && typeof wie !== "boolean") return null;
	const cie = o.chatImageEnabled;
	if (cie !== void 0 && typeof cie !== "boolean") return null;
	const outConfig = { pets: out };
	if (ne !== void 0) outConfig.notificationsEnabled = ne;
	if (wie !== void 0) outConfig.whisperImageEnabled = wie;
	if (cie !== void 0) outConfig.chatImageEnabled = cie;
	const bodyOwned = new Set(["pets"]);
	if (ne !== void 0) bodyOwned.add("notificationsEnabled");
	if (wie !== void 0) bodyOwned.add("whisperImageEnabled");
	if (cie !== void 0) bodyOwned.add("chatImageEnabled");
	if (existing && typeof existing === "object") for (const key of Object.keys(existing)) {
		if (bodyOwned.has(key)) continue;
		outConfig[key] = existing[key];
	}
	return outConfig;
}

//#endregion
//#region src/host/work-status.ts
/**
* turn/end reason.kind → 状态：
*   completed → success、错误系（error/max-tokens/timeout）→ error、blocked → waiting（回合被阻塞，等用户确认）；
*   其余（aborted 等）→ null＝该会话回合已结束，由调用方清理会话回空闲——绝不残留上一档
*   （否则回合被打断后会永远卡在 working，即当年"这一步正在进行中哦"挂死的根因）。
*/
function turnEndState(kind) {
	if (kind === "completed") return "success";
	if (kind === "error" || kind === "max-tokens" || kind === "timeout") return "error";
	if (kind === "blocked") return "waiting";
	return null;
}
/** ask_user_question 工具名：模型在等用户选择题答复 → 归为 waiting（等待确认）而非普通工作 */
const USER_QUESTION_TOOL$1 = "ask_user_question";
const GOAL_UPDATE_TOOL = "update_goal";
function goalUpdateAction(args) {
	try {
		const o = JSON.parse(args);
		const action = String(o?.action ?? "");
		if (action === "complete" || action === "blocked") return action;
	} catch {}
	return null;
}
function completedState(turn) {
	if (!turn?.goalRound) return "success";
	if (turn.closing === "blocked") return "error";
	if (turn.closing === "complete") return "success";
	return "result";
}
function reduceWorkStatus(event, turn) {
	switch (event?.type) {
		case "turn/start": return "thinking";
		case "tool/call": {
			if (String(event?.data?.name ?? "") === USER_QUESTION_TOOL$1) return "waiting";
			return "working";
		}
		case "tool/result": return "result";
		case "approval/asked": return "waiting";
		case "turn/end": {
			const reason = turnEndState(String(event?.data?.reason?.kind ?? ""));
			if (reason === "success") return completedState(turn);
			return reason;
		}
		default: return null;
	}
}
function currentTaskFromTodo(event) {
	const todos = Array.isArray(event?.data?.todos) ? event.data.todos : [];
	const current = todos.find((t) => t?.status === "in_progress") ?? todos.find((t) => t?.status === "pending");
	const content = String(current?.content ?? "").trim();
	return content || null;
}

//#endregion
//#region src/host/notify-events.ts
function turnEndNotifyKind(kind) {
	if (kind === "completed") return "completed";
	if (kind === "error" || kind === "max-tokens") return kind;
	return null;
}
/** ask_user_question 工具名（与 work-status.ts 同源；该工具触发时模型在等用户选择题答复） */
const USER_QUESTION_TOOL = "ask_user_question";
function parseToolQuestions(args) {
	if (typeof args !== "string") return null;
	try {
		const parsed = JSON.parse(args);
		const questions = parsed?.questions;
		if (!Array.isArray(questions)) return null;
		return questions;
	} catch {
		return null;
	}
}
function reduceNotifyFrame(event) {
	if (!event?.type) return null;
	switch (event.type) {
		case "turn/end": {
			const reason = event.data?.reason;
			const kind = turnEndNotifyKind(reason?.kind);
			if (!kind) return null;
			return {
				type: "session/event",
				event: {
					type: "turn/end",
					data: { reason }
				}
			};
		}
		case "approval/asked": {
			const data = event.data ?? {};
			return {
				type: "approval/requested",
				...typeof data.toolName === "string" && data.toolName ? { toolName: data.toolName } : {},
				...typeof data.reason === "string" && data.reason ? { reason: data.reason } : {}
			};
		}
		case "tool/call": {
			if (String(event.data?.name ?? "") !== USER_QUESTION_TOOL) return null;
			const questions = parseToolQuestions(event.data?.arguments);
			if (!questions || questions.length === 0) return null;
			return {
				type: "question/requested",
				questions
			};
		}
		default: return null;
	}
}
function agentErrorFrame(error) {
	const message = typeof error === "string" ? error : error instanceof Error ? error.message : String(error ?? "");
	return {
		type: "host/agent-error",
		message
	};
}

//#endregion
//#region src/host/storage-paths.ts
const DESKTOP_APP_NAME = "dsh-pet-electron-helper";
/** Electron 下载缓存的应用名（@electron/get 写死 env-paths('electron')，与插件名无关） */
const ELECTRON_PATHS_NAME = "electron";
/**
* 桌面端 userData 目录（Electron app.getPath('userData') 的等价推导）。
*
* 与 Electron 的口径逐平台对齐：
*   win32  = %APPDATA%\<name>（appData 在 Windows 就是 Roaming）
*   darwin = ~/Library/Application Support/<name>
*   linux  = $XDG_CONFIG_HOME/<name>，未设则 ~/.config/<name>
*/
function desktopUserDataDir(input) {
	const { home, env = process.env, platform = process.platform } = input;
	if (platform === "win32") return join(env.APPDATA || join(home, "AppData", "Roaming"), DESKTOP_APP_NAME);
	if (platform === "darwin") return join(home, "Library", "Application Support", DESKTOP_APP_NAME);
	return join(env.XDG_CONFIG_HOME || join(home, ".config"), DESKTOP_APP_NAME);
}
/**
* Electron 安装包下载缓存目录（@electron/get 默认 cacheRoot = env-paths('electron').cache）。
*
* env-paths 的口径：win32 在 LOCALAPPDATA 下多一层 Cache，macOS 用 ~/Library/Caches，
* Linux 用 $XDG_CACHE_HOME（默认 ~/.cache）——都是「应用名单独一层」。
* 该目录与其它用 @electron/get 的工具共用，删掉只是下次重新下载。
*/
function electronCacheDir(input) {
	const { home, env = process.env, platform = process.platform } = input;
	if (platform === "win32") return join(env.LOCALAPPDATA || join(home, "AppData", "Local"), ELECTRON_PATHS_NAME, "Cache");
	if (platform === "darwin") return join(home, "Library", "Caches", ELECTRON_PATHS_NAME);
	return join(env.XDG_CACHE_HOME || join(home, ".cache"), ELECTRON_PATHS_NAME);
}
function storageEntries(input) {
	const items = [
		{
			key: "userData",
			path: input.userDataRoot
		},
		{
			key: "electron",
			path: input.electronDir
		},
		{
			key: "desktopCache",
			path: desktopUserDataDir(input)
		},
		{
			key: "electronCache",
			path: electronCacheDir(input)
		},
		{
			key: "package",
			path: input.packageRoot
		}
	];
	return items.map((it) => ({
		...it,
		exists: existsSync(it.path)
	}));
}
function profileNameFrom(packageRoot$1) {
	const m = /[\\/]profiles[\\/]([^\\/]+)[\\/]node_modules[\\/][^\\/]+[\\/]?$/.exec(packageRoot$1);
	return m?.[1];
}

//#endregion
//#region src/host/helper-process.ts
const require = createRequire(import.meta.url);
const here = dirname(fileURLToPath(import.meta.url));
const packageRoot = resolve(here, "..");
const defaultHelperMain = resolve(packageRoot, "runtime", "electron-helper", "main.js");
const BRIDGE_PREFIX = "dsh-pet-bridge:";
function resolveElectronPath(candidates = []) {
	const seen = new Set();
	const list = [];
	const push = (value) => {
		if (!value || seen.has(value)) return;
		seen.add(value);
		list.push(value);
	};
	for (const value of candidates) push(value);
	if (process.env.DSH_PET_ELECTRON_PATH) push(process.env.DSH_PET_ELECTRON_PATH);
	try {
		const resolved = require("electron");
		if (typeof resolved === "string" && resolved) push(resolved);
	} catch {}
	push(defaultElectronExe());
	return list.find((value) => existsSync(value));
}
function hasGraphicalDisplay() {
	if (process.platform !== "linux") return true;
	if (process.env.DSH_PET_DESKTOP_FORCE === "1") return true;
	return Boolean(process.env.DISPLAY || process.env.WAYLAND_DISPLAY);
}
function dshHomeDir() {
	const userProfile = process.env.USERPROFILE || process.env.HOME || "";
	return process.env.DSH_HOME || join(userProfile, ".dsh");
}
/** 当前平台标识（win32 / darwin / linux） */
const PLAT = process.platform;
/** $DSH_HOME/electron 落地目录下，可执行文件的相对路径（按平台） */
const ELECTRON_REL = PLAT === "win32" ? "electron.exe" : PLAT === "darwin" ? join("Electron.app", "Contents", "MacOS", "Electron") : "electron";
function electronLandingDir() {
	return join(dshHomeDir(), "electron");
}
function defaultElectronExe() {
	return join(electronLandingDir(), ELECTRON_REL);
}
async function ensureElectronDownload(options = {}) {
	const version = options.version || process.env.DSH_PET_ELECTRON_VERSION || "43.3.0";
	const mirror = options.mirror || process.env.DSH_PET_ELECTRON_MIRROR || "https://npmmirror.com/mirrors/electron/";
	const timeoutMs = options.timeoutMs ?? 10 * 60 * 1e3;
	const targetDir = electronLandingDir();
	const exe = defaultElectronExe();
	if (existsSync(exe)) return exe;
	const log = (message) => console.log(`[dsh-pet] ${message}`);
	const warn = (message) => console.warn(`[dsh-pet] ${message}`);
	const startedAt = Date.now();
	log(`Electron not found, downloading v${version} (${PLAT}-${process.arch}) ...`);
	mkdirSync(targetDir, { recursive: true });
	try {
		const controller = new AbortController();
		const timer = setTimeout(() => controller.abort(new Error(`Electron download timed out after ${timeoutMs}ms`)), timeoutMs);
		timer.unref?.();
		let nextLogAt = Date.now() + 3e3;
		try {
			const zipPath = await downloadArtifact({
				version: `v${version}`,
				artifactName: "electron",
				mirrorOptions: { mirror: mirror.replace(/\/$/, "") + "/" },
				downloadOptions: {
					signal: controller.signal,
					quiet: true,
					getProgressCallback: async (progress) => {
						const now = Date.now();
						if (!progress.total || now < nextLogAt) return;
						nextLogAt = now + 3e3;
						log(`downloading ${(progress.transferred / 1024 / 1024).toFixed(1)}MB / ${(progress.total / 1024 / 1024).toFixed(1)}MB`);
					}
				}
			});
			const seconds = ((Date.now() - startedAt) / 1e3).toFixed(1);
			log(`download complete (${seconds}s), extracting to ${targetDir} ...`);
			await extract(zipPath, { dir: targetDir });
			if (!existsSync(exe)) throw new Error(`Electron zip extracted, but ${ELECTRON_REL} not found`);
			const readySeconds = ((Date.now() - startedAt) / 1e3).toFixed(1);
			log(`ready in ${readySeconds}s: ${exe}`);
			return exe;
		} finally {
			clearTimeout(timer);
		}
	} catch (error) {
		warn(`ensure failed: ${error instanceof Error ? error.message : String(error)}`);
		warn("desktop pet unavailable. Set DSH_PET_ELECTRON_PATH to an existing Electron, or retry later.");
		return void 0;
	}
}
function defaultLaunch(options = {}) {
	const electronPath = resolveElectronPath([options.electronPath]);
	if (!electronPath) throw new Error("dsh-pet: cannot resolve Electron executable. Set DSH_PET_ELECTRON_PATH or install electron.");
	const helperPath = options.helperPath || defaultHelperMain;
	return {
		command: electronPath,
		args: [helperPath]
	};
}
var HelperProcess = class {
	constructor(options = {}, logger = console) {
		this.options = options;
		this.logger = logger;
		this.child = void 0;
		this.stopping = false;
		this.restartSuppressed = false;
		this.restartTimer = void 0;
		this.restartFailures = 0;
		this.lastStartAt = 0;
		this.stdoutBuffer = "";
	}
	start() {
		if (this.child || this.stopping || this.restartSuppressed) return this.child;
		this.lastStartAt = Date.now();
		const helperPath = this.options.helperPath || defaultHelperMain;
		const launch = this.options.command ? {
			command: this.options.command,
			args: this.options.args || [helperPath]
		} : defaultLaunch(this.options);
		const command = launch.command;
		const args = this.options.args || launch.args;
		const child = spawn(command, args, {
			cwd: this.options.cwd || packageRoot,
			env: {
				...process.env,
				...this.options.env
			},
			stdio: [
				"pipe",
				"pipe",
				"pipe"
			],
			windowsHide: true
		});
		this.child = child;
		child.once("error", (error) => {
			this.logger.error?.(`dsh-pet desktop helper failed to start: ${error.message}`);
		});
		child.once("exit", (code, signal) => {
			if (this.child !== child) return;
			this.child = void 0;
			if (!this.stopping && !this.restartSuppressed) {
				this.logger.warn?.(`dsh-pet desktop helper exited (code=${String(code)}, signal=${String(signal)}); restarting`);
				this.scheduleRestart();
			}
		});
		child.stdout.on("data", (chunk) => {
			this.onStdoutChunk(String(chunk));
		});
		child.stderr.on("data", (chunk) => {
			const line = String(chunk).trim();
			if (line) this.logger.warn?.(`[dsh-pet desktop helper] ${line}`);
		});
		child.stdin?.on("error", () => {});
		return child;
	}
	/** stdout 按行缓冲：`dsh-pet-bridge:` 前缀整行 = 协议请求，其余 = 日志行 */
	onStdoutChunk(chunk) {
		this.stdoutBuffer += chunk;
		let nl;
		while ((nl = this.stdoutBuffer.indexOf("\n")) >= 0) {
			const line = this.stdoutBuffer.slice(0, nl);
			this.stdoutBuffer = this.stdoutBuffer.slice(nl + 1);
			const trimmed = line.trim();
			if (!trimmed) continue;
			if (trimmed.startsWith(BRIDGE_PREFIX)) {
				this.handleBridgeLine(trimmed);
				continue;
			}
			this.logger.debug?.(`[dsh-pet desktop helper] ${trimmed}`);
		}
	}
	/** 处理一条协议请求：交给宿主 bridgeHandler，结果按 id POST 回 main.js 的回调服务器
	*  （cb 由请求行携带；不走 stdin —— Electron 主进程收不到 piped stdin） */
	async handleBridgeLine(line) {
		const child = this.child;
		if (!child?.stdin || !this.options.bridgeHandler) return;
		let req;
		try {
			req = JSON.parse(line.slice(BRIDGE_PREFIX.length));
		} catch {
			this.logger.warn?.("[dsh-pet desktop helper] bridge 协议行非法，已忽略");
			return;
		}
		if (typeof req.id !== "number") return;
		try {
			const resp = await this.options.bridgeHandler(req);
			this.sendBridgeResponse(req, resp);
		} catch (e) {
			this.sendBridgeResponse(req, {
				id: req.id,
				status: 500,
				contentType: "application/json; charset=utf-8",
				body: JSON.stringify({ error: `bridge handler error: ${e instanceof Error ? e.message : String(e)}` })
			});
		}
	}
	/** 把应答发回 main.js：优先 POST 到请求行携带的 cb（本地回调服务器）；无 cb 时回写 stdin（低版本兼容） */
	sendBridgeResponse(req, resp) {
		const cb = typeof req.cb === "string" && /^https?:[/][/]/.test(req.cb) ? req.cb : "";
		if (cb) {
			fetch(cb, {
				method: "POST",
				headers: { "content-type": "application/json" },
				body: JSON.stringify(resp)
			}).catch(() => {});
			return;
		}
		const child = this.child;
		if (!child?.stdin || child.stdin.destroyed) return;
		try {
			child.stdin.write(BRIDGE_PREFIX + JSON.stringify(resp) + "\n");
		} catch {}
	}
	stop(reason = "plugin-disposed") {
		this.stopping = true;
		if (this.restartTimer) clearTimeout(this.restartTimer);
		this.restartTimer = void 0;
		this.logger.debug?.(`dsh-pet desktop helper stopping (${reason})`);
		const child = this.child;
		if (!child) return;
		child.kill();
	}
	scheduleRestart() {
		if (this.restartTimer || this.stopping || this.restartSuppressed) return;
		if (helperRunIsStable(Date.now() - this.lastStartAt)) this.restartFailures = 0;
		else this.restartFailures += 1;
		if (shouldCircuitBreak(this.restartFailures, this.resolveMaxFailures())) {
			this.logger.error?.(`dsh-pet desktop helper crashed ${this.restartFailures} consecutive times; circuit breaker tripped, no more restarts. Fix the environment (e.g. DISPLAY/headless) or set DSH_PET_RESTART_MAX_FAILURES to raise the limit.`);
			return;
		}
		const base = this.resolveRestartBaseMs();
		const delay = restartBackoffDelayMs(this.restartFailures, base);
		this.logger.warn?.(`dsh-pet desktop helper exited; restarting in ${Math.round(delay)}ms (attempt ${this.restartFailures}, consecutive-crash limit ${this.resolveMaxFailures()})`);
		this.restartTimer = setTimeout(() => {
			this.restartTimer = void 0;
			this.start();
		}, delay);
		this.restartTimer.unref?.();
	}
	/** 退避基值：DSH_PET_RESTART_BASE_MS（ms，>0）可调，默认 750。 */
	resolveRestartBaseMs() {
		return envPositiveInt(process.env.DSH_PET_RESTART_BASE_MS, RESTART_BASE_MS_DEFAULT);
	}
	/** 熔断阈值：DSH_PET_RESTART_MAX_FAILURES（次，>0）可调，默认 12。 */
	resolveMaxFailures() {
		return envPositiveInt(process.env.DSH_PET_RESTART_MAX_FAILURES, RESTART_MAX_FAILURES_DEFAULT);
	}
};
const HELPER_STABLE_MS = 3 * 60 * 1e3;
function restartBackoffDelayMs(consecutiveFailures, baseMs = 750) {
	const MAX = 3e4;
	const raw = baseMs * 2 ** Math.max(0, consecutiveFailures);
	return Math.min(raw, MAX);
}
function shouldCircuitBreak(consecutiveFailures, limit = 12) {
	return consecutiveFailures >= limit;
}
function helperRunIsStable(elapsedMs) {
	return elapsedMs >= HELPER_STABLE_MS;
}
/** 退避基值（ms）：默认 750 与旧版首延一致，DSH_PET_RESTART_BASE_MS 可调。 */
const RESTART_BASE_MS_DEFAULT = 750;
/** 熔断阈值（连续崩溃次数）：默认 12，DSH_PET_RESTART_MAX_FAILURES 可调。 */
const RESTART_MAX_FAILURES_DEFAULT = 12;
/** 非负整数 env 解析（非法/未设回落默认），供重启参数读取共用。 */
function envPositiveInt(value, fallback) {
	const parsed = Number.parseInt(String(value ?? ""), 10);
	return Number.isFinite(parsed) && parsed > 0 ? parsed : fallback;
}

//#endregion
//#region src/host/pet-pack-import.ts
const MAX_FILES = 256;
const MAX_FILE_BYTES = 64 * 1024 * 1024;
const MAX_TOTAL_BYTES = 192 * 1024 * 1024;
const MAX_CONFIG_BYTES = 1024 * 1024;
const CONFIG_RE = /^(.+)-config\.(json|jsonc)$/;
const importErrorStatuses = new WeakMap();
var PetPackImportError = class extends Error {
	constructor(message, status = 400) {
		super(message);
		importErrorStatuses.set(this, status);
	}
	get status() {
		return importErrorStatuses.get(this) ?? 400;
	}
};
function stripJsonc(text) {
	let out = "";
	let inString = false;
	let escaped = false;
	for (let i = 0; i < text.length; i++) {
		const ch = text[i];
		const next = text[i + 1];
		if (inString) {
			out += ch;
			if (escaped) escaped = false;
			else if (ch === "\\") escaped = true;
			else if (ch === "\"") inString = false;
			continue;
		}
		if (ch === "\"") {
			inString = true;
			out += ch;
		} else if (ch === "/" && next === "/") {
			i += 2;
			while (i < text.length && text[i] !== "\n" && text[i] !== "\r") i++;
			i--;
		} else if (ch === "/" && next === "*") {
			const end = text.indexOf("*/", i + 2);
			if (end < 0) throw new PetPackImportError("配置文件的块注释未闭合");
			i = end + 1;
		} else out += ch;
	}
	return out;
}
function safeSegment(segment) {
	const hasControlCharacter = [...segment].some((character) => character.charCodeAt(0) <= 31);
	return segment.length > 0 && segment.length <= 120 && segment !== "." && segment !== ".." && !segment.startsWith(".") && !/[<>:"/\\|?*]/.test(segment) && !hasControlCharacter;
}
function normalizeUploadPaths(files) {
	const parsed = files.map((file) => {
		if (!file || typeof file.path !== "string" || typeof file.data !== "string") throw new PetPackImportError("上传文件条目无效");
		if (file.path.startsWith("/") || /^[A-Za-z]:/.test(file.path) || file.path.includes("\\")) throw new PetPackImportError("上传路径必须是文件夹内的相对路径");
		const parts = file.path.split("/");
		if (parts.length < 1 || parts.some((part) => !safeSegment(part))) throw new PetPackImportError("上传路径包含非法文件名或路径段");
		return {
			...file,
			parts
		};
	});
	const first = parsed[0]?.parts[0];
	const hasCommonPickerRoot = !!first && parsed.every((file) => file.parts.length >= 2 && file.parts[0] === first);
	return parsed.map((file) => ({
		...file,
		parts: hasCommonPickerRoot ? file.parts.slice(1) : file.parts
	}));
}
function decodeBase64(value) {
	if (value.length === 0 || value.length % 4 !== 0 || !/^[A-Za-z0-9+/]*={0,2}$/.test(value)) throw new PetPackImportError("上传文件内容不是有效的 base64");
	const data = Buffer.from(value, "base64");
	if (data.length === 0 || data.length > MAX_FILE_BYTES) throw new PetPackImportError(`单个文件必须大于 0 且不超过 ${MAX_FILE_BYTES / 1024 / 1024} MiB`);
	return data;
}
function stringArray(value, label) {
	if (!Array.isArray(value) || !value.every((item) => typeof item === "string" && item.length > 0)) throw new PetPackImportError(`${label} 必须是字符串数组`);
	return value;
}
function validateConfig(configBytes, existingPetIds) {
	if (configBytes.length > MAX_CONFIG_BYTES) throw new PetPackImportError("配置文件不得超过 1 MiB");
	let config;
	try {
		const parsed = JSON.parse(stripJsonc(configBytes.toString("utf8")));
		if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) throw new Error("root");
		config = parsed;
	} catch (error) {
		if (error instanceof PetPackImportError) throw error;
		throw new PetPackImportError("配置文件不是有效的 JSON/JSONC 对象");
	}
	if (!Array.isArray(config.pets) || config.pets.length === 0) throw new PetPackImportError("配置 pets 必须是非空数组");
	const localIds = new Set();
	for (const pet of config.pets) {
		const id = pet && typeof pet === "object" ? pet.id : void 0;
		if (typeof id !== "string" || !safeSegment(id)) throw new PetPackImportError("每个 pets[] 必须有安全且非空的 id");
		if (localIds.has(id)) throw new PetPackImportError(`配置内宠物 id 重复：${id}`);
		if (existingPetIds.has(id)) throw new PetPackImportError(`宠物 id 已存在：${id}`, 409);
		localIds.add(id);
	}
	const animations = config.animations;
	if (!animations || typeof animations !== "object" || Array.isArray(animations)) throw new PetPackImportError("配置 animations 必须是对象");
	const a = animations;
	const referenced = new Set();
	for (const key of [
		"idle",
		"turn",
		"drag",
		"clicks"
	]) for (const name$1 of stringArray(a[key], `animations.${key}`)) referenced.add(name$1);
	const moves = a.moves;
	if (!moves || typeof moves !== "object" || Array.isArray(moves)) throw new PetPackImportError("animations.moves 必须是对象");
	const moveRecord = moves;
	if (!moveRecord.default || typeof moveRecord.default !== "object" || !Array.isArray(moveRecord.actions)) throw new PetPackImportError("animations.moves.default/actions 不完整");
	for (const action of moveRecord.actions) {
		const name$1 = action && typeof action === "object" ? action.name : void 0;
		if (typeof name$1 !== "string" || name$1.length === 0) throw new PetPackImportError("animations.moves.actions[].name 无效");
		referenced.add(name$1);
	}
	if (!Array.isArray(a.categories)) throw new PetPackImportError("animations.categories 必须是数组");
	let categoryWeight = 0;
	for (const category of a.categories) {
		if (!category || typeof category !== "object") throw new PetPackImportError("animations.categories[] 无效");
		const record = category;
		if (typeof record.weight !== "number" || record.weight < 0) throw new PetPackImportError("分类 weight 必须是非负数");
		categoryWeight += record.weight;
		for (const name$1 of stringArray(record.actions, "animations.categories[].actions")) referenced.add(name$1);
	}
	if (!a.events || typeof a.events !== "object" || Array.isArray(a.events)) throw new PetPackImportError("animations.events 必须是对象");
	for (const [event, pool] of Object.entries(a.events)) for (const name$1 of stringArray(pool, `animations.events.${event}`)) referenced.add(name$1);
	const weights = config.animationWeights;
	if (!weights || typeof weights !== "object" || Array.isArray(weights)) throw new PetPackImportError("animationWeights 必须是对象");
	const weightRecord = weights;
	const topWeights = [
		"idle",
		"turn",
		"move"
	].map((key) => weightRecord[key]);
	if (!topWeights.every((value) => typeof value === "number" && value >= 0)) throw new PetPackImportError("animationWeights 必须包含非负的 idle/turn/move");
	const totalWeight = topWeights.reduce((sum, value) => sum + value, 0) + categoryWeight;
	if (Math.abs(totalWeight - 100) > Number.EPSILON) throw new PetPackImportError(`动画权重总和必须为 100，当前为 ${totalWeight}`);
	if (referenced.size === 0) throw new PetPackImportError("配置至少需要引用一个动画");
	for (const name$1 of referenced) if (!safeSegment(name$1)) throw new PetPackImportError(`动画名不安全：${name$1}`);
	return {
		petCount: config.pets.length,
		referenced
	};
}
async function pathExists(path) {
	try {
		await stat(path);
		return true;
	} catch {
		return false;
	}
}
async function importPetPack(payload, options) {
	if (!Array.isArray(payload?.files) || payload.files.length < 2 || payload.files.length > MAX_FILES) throw new PetPackImportError(`宠物包文件数必须在 2 到 ${MAX_FILES} 之间`);
	const files = normalizeUploadPaths(payload.files);
	const configs = files.filter((file) => file.parts.length === 1 && CONFIG_RE.test(file.parts[0]));
	if (configs.length !== 1) throw new PetPackImportError("文件夹根目录必须恰好包含一个 <名称>-config.json 或 .jsonc");
	const configName = configs[0].parts[0];
	const match = CONFIG_RE.exec(configName);
	const prefix = match?.[1] ?? "";
	if (!safeSegment(prefix)) throw new PetPackImportError("宠物包名称包含非法字符");
	const animationDirName = `${prefix}-animation`;
	const animationFiles = files.filter((file) => file.parts.length === 2 && file.parts[0] === animationDirName && file.parts[1].toLowerCase().endsWith(".webm"));
	if (animationFiles.length === 0 || animationFiles.length !== files.length - 1) throw new PetPackImportError(`除配置外只允许 ${animationDirName} 目录中的 .webm 文件`);
	const decoded = new Map();
	let totalBytes = 0;
	for (const file of files) {
		const key = file.parts.join("/");
		if (decoded.has(key)) throw new PetPackImportError(`上传路径重复：${key}`);
		const bytes = decodeBase64(file.data);
		totalBytes += bytes.length;
		if (totalBytes > MAX_TOTAL_BYTES) throw new PetPackImportError("宠物包原始文件总大小不得超过 192 MiB");
		decoded.set(key, bytes);
	}
	const configBytes = decoded.get(configName);
	if (!configBytes) throw new PetPackImportError("配置文件内容缺失");
	const { petCount, referenced } = validateConfig(configBytes, options.existingPetIds);
	const available = new Set(animationFiles.map((file) => basename(file.parts[1], ".webm")));
	for (const name$1 of referenced) if (!available.has(name$1)) throw new PetPackImportError(`配置引用的动画不存在：${name$1}.webm`);
	await mkdir(options.petDir, { recursive: true });
	const targetConfig = join(options.petDir, configName);
	const targetAnimations = join(options.petDir, animationDirName);
	if (await pathExists(targetConfig) || await pathExists(targetAnimations)) throw new PetPackImportError(`宠物包已存在：${prefix}`, 409);
	const staging = join(options.petDir, `.import-${randomUUID()}`);
	const stagingAnimations = join(staging, animationDirName);
	await mkdir(stagingAnimations, { recursive: true });
	try {
		await writeFile(join(staging, configName), configBytes, { flag: "wx" });
		for (const file of animationFiles) {
			const bytes = decoded.get(file.parts.join("/"));
			if (!bytes) throw new PetPackImportError(`动画文件内容缺失：${file.parts[1]}`);
			await writeFile(join(stagingAnimations, file.parts[1]), bytes, { flag: "wx" });
		}
		await rename(stagingAnimations, targetAnimations);
		try {
			await rename(join(staging, configName), targetConfig);
		} catch (error) {
			await rename(targetAnimations, stagingAnimations).catch(() => void 0);
			throw error;
		}
		return {
			prefix,
			petCount,
			animationCount: animationFiles.length
		};
	} finally {
		await rm(staging, {
			recursive: true,
			force: true
		});
	}
}

//#endregion
//#region src/host/index.ts
const name = "pet";
const inject = [
	"webServer",
	"agentDefaultModel",
	"credentials",
	"llm",
	"commands"
];
/** 本包目录：宿主构建产物位于 lib/，其上一级即包根。 */
const PACKAGE_ROOT = resolve(fileURLToPath(new URL("..", import.meta.url)));
/** 包内 assets 根（表情包池解析用：assets/memes/<名称>.png） */
const PACKAGE_ROOT_ASSETS = join(PACKAGE_ROOT, "assets");
/** 路由前缀 */
const ROUTE_PREFIX = "/dsh-pet-7340";
/** 不同扩展名对应的 Content-Type 映射 */
const MIME = {
	".webm": "video/webm",
	".mov": "video/quicktime",
	".mp4": "video/mp4",
	".png": "image/png",
	".json": "application/json; charset=utf-8",
	".jsonc": "application/json; charset=utf-8",
	".ttf": "font/ttf",
	".woff": "font/woff",
	".woff2": "font/woff2"
};
/**
* 规范化并校验请求路径，确保它在 assets 根目录内（防路径穿越）。
* @returns 规范化后的绝对文件路径；非法（穿越）时返回 undefined
*/
function resolveAsset(root, rel) {
	if (rel.length === 0) return void 0;
	const candidate = normalize(join(root, rel));
	const rootWithSep = root.endsWith(sep) ? root : root + sep;
	if (candidate !== root && !candidate.startsWith(rootWithSep)) return void 0;
	return candidate;
}
/** 在 root 下解析并确认实体存在；非法（穿越）或不存在时返回 undefined */
function resolveExisting(root, rel) {
	const candidate = resolveAsset(root, rel);
	return candidate && existsSync(candidate) ? candidate : void 0;
}
/** 流式返回一个文件（带 Content-Type / 长度 / 缓存头）。 */
async function sendFile(res, file, contentType) {
	const { size } = await stat(file);
	res.writeHead(200, {
		"content-type": contentType,
		"content-length": size,
		"cache-control": "public, max-age=3600"
	});
	const stream = createReadStream(file);
	stream.on("error", () => res.destroy());
	stream.pipe(res);
}
/** 该宠物是否参与桌面模式（Electron 透明窗） */
const isDesktopVisible = (display) => display === "desktop" || display === "both";
/** 发送 JSON 响应（headers 可选：如 no-cache 触发计数） */
function sendJson(res, status, obj, headers = {}) {
	const body = JSON.stringify(obj);
	res.writeHead(status, {
		"content-type": "application/json; charset=utf-8",
		"content-length": Buffer.byteLength(body),
		...headers
	});
	res.end(body);
}
/** 发送纯文本响应（素材 404/400 等显式错误文案） */
function sendText(res, status, body) {
	res.writeHead(status, { "content-type": "text/plain; charset=utf-8" });
	res.end(body);
}
/** 收集请求体（文本）；pet pack 使用 base64 JSON，因此显式限制请求体，避免本地页面耗尽 Host 内存。 */
function readBody(req, maxBytes = 260 * 1024 * 1024) {
	return new Promise((resolve2, reject) => {
		const chunks = [];
		let total = 0;
		let tooLarge = false;
		req.on("data", (c) => {
			total += c.length;
			if (total > maxBytes) {
				tooLarge = true;
				chunks.length = 0;
			} else if (!tooLarge) chunks.push(c);
		});
		req.on("end", () => {
			if (tooLarge) reject(new PetPackImportError("上传请求不得超过 260 MiB", 413));
			else resolve2(Buffer.concat(chunks).toString("utf8"));
		});
		req.on("error", reject);
	});
}
function apply(ctx) {
	const dshHome = resolveDshHome();
	const userRoot = join(dshHome, "dsh-pet");
	const userConfigPath = join(userRoot, "main-config.json");
	const petConfigDir = join(userRoot, "pet");
	const configPaths = {
		defaultFile: join(PACKAGE_ROOT, "assets", "config.jsonc"),
		userFile: userConfigPath,
		petDir: petConfigDir
	};
	const thumbUserRoot = join(userRoot, "main-animation");
	let balanceTriggerCount = 0;
	const workStatus = {
		state: null,
		task: null,
		ts: 0
	};
	const notifyFrames = [];
	let notifySeq = 0;
	const NOTIFY_QUEUE_MAX = 100;
	const pushNotifyFrame = (frame) => {
		notifySeq += 1;
		notifyFrames.push({
			seq: notifySeq,
			frame
		});
		if (notifyFrames.length > NOTIFY_QUEUE_MAX) notifyFrames.shift();
	};
	/** 每会话最近状态（会话 id → 状态），多会话时取优先级最高的作展示（与 better-dsh-pet 同思路） */
	const workStatusBySession = new Map();
	/** 每会话 turn 级标志（goal 续跑轮判定；不参与展示，仅修正 turn/end 终局语义） */
	const turnFlags = new Map();
	/** 终态（success/error）展示窗口定时器：约 60s 后清掉该会话条目，陈旧完成态不再浮上来（Bug 2/3） */
	const terminalTimers = new Map();
	const TERMINAL_KEEP_MS = 60 * 1e3;
	/** 排一个终态清理定时器（每会话一个，已排则跳过） */
	const scheduleTerminalCleanup = (sessionId) => {
		if (terminalTimers.has(sessionId)) return;
		const t = setTimeout(() => {
			terminalTimers.delete(sessionId);
			const entry = workStatusBySession.get(sessionId);
			if (entry && (entry.state === "success" || entry.state === "error")) {
				workStatusBySession.delete(sessionId);
				turnFlags.delete(sessionId);
				refreshWorkStatus();
			}
		}, TERMINAL_KEEP_MS);
		terminalTimers.set(sessionId, t);
	};
	/** 展示优先级：waiting > error > working > thinking > result > success
	*  （result 高于 success：任何会话的进行中过渡态都不被别处已完成态压过，防中途庆祝；同档按最近更新优先） */
	const WORK_STATUS_PRIORITY = {
		waiting: 60,
		error: 50,
		working: 40,
		thinking: 30,
		result: 25,
		success: 20
	};
	/** 重算当前展示状态：所有会话里优先级最高者（同优先级取最近 seq），无活动会话 → 空闲 */
	const refreshWorkStatus = () => {
		let best;
		for (const entry of workStatusBySession.values()) if (!best || WORK_STATUS_PRIORITY[entry.state] > WORK_STATUS_PRIORITY[best.state] || WORK_STATUS_PRIORITY[entry.state] === WORK_STATUS_PRIORITY[best.state] && entry.seq > best.seq) best = entry;
		const next = best?.state ?? null;
		if (next === workStatus.state) return;
		workStatus.state = next;
		workStatus.ts = Date.now();
	};
	let activePetId = "";
	const broadcastCache = new Map();
	const whisperCache = new Map();
	const memoryPath = join(userRoot, "memory.json");
	let chatQueue = Promise.resolve();
	/** 读记忆文件：不存在 → 空；损坏 → 显式报错 + 备份原始文件（绝不静默丢数据）+ 重建空记忆 */
	const readMemory = async () => {
		let raw;
		try {
			raw = await readFile(memoryPath, "utf8");
		} catch {
			return {};
		}
		try {
			const parsed = JSON.parse(raw);
			if (!parsed || typeof parsed !== "object") throw new Error("not an object");
			return parsed;
		} catch (e) {
			console.error(`dsh-pet: 记忆文件损坏已备份（对话将从头开始）：${memoryPath}（${e instanceof Error ? e.message : String(e)}）`);
			try {
				await mkdir(userRoot, { recursive: true });
				await writeFile(`${memoryPath}.bak-${Date.now()}`, raw, "utf8");
			} catch {}
			return {};
		}
	};
	const writeMemory = async (mem) => {
		await mkdir(userRoot, { recursive: true });
		await writeFile(memoryPath, JSON.stringify(mem, null, 2), "utf8");
	};
	/** 把一次读写封进串行队列（同进程内防交错），返回 fn 的结果 */
	const withMemoryLock = (fn) => {
		const run = chatQueue.then(fn, fn);
		chatQueue = run.then(() => void 0, () => void 0);
		return run;
	};
	/** 某宠物的最终人设 system：所属条目（非文件宠物 → main 条目）的 whisperPrompt（合并器已填默认）
	*  + 无条件追加一句名字声明（name，缺失已按 id）——碎碎念与对话共用同一拼装。 */
	const petSystemPrompt = (petId, cfg) => {
		const found = findPetInstance(cfg, petId);
		const conf = found ? found.conf : cfg.main ?? {};
		const prompt = typeof conf.whisperPrompt === "string" ? conf.whisperPrompt : "";
		const name$1 = found ? String(found.pet.name || found.pet.id || petId) : petId;
		const nameLine = "你的名字是“" + name$1 + "”。";
		return prompt ? prompt + "\n" + nameLine : nameLine;
	};
	/** 对话记忆轮数（1 轮 = 1 问 1 答）：所属条目/主条目的 chatMemoryRounds（合并器已填默认非负数字） */
	const memoryRounds = (petId, cfg) => {
		const found = findPetInstance(cfg, petId);
		const v = Number(found?.conf.chatMemoryRounds ?? cfg.main?.chatMemoryRounds);
		return Number.isFinite(v) && v >= 0 ? Math.floor(v) : 5;
	};
	/** 生成/返回某宠物的一句碎碎念（周期 GET 与菜单手动触发共用的同一逻辑）：
	*  每只宠物独立生成（所属条目的人设），缓存按 pet 分开；
	*  force=false 走周期节流（缓存期内返回同一句 ts），force=true 强制新生成并刷新缓存
	*  （右键菜单「碎碎念」手动触发：绕过节流立即新出一句，同宠多端下次轮询看到新 ts 一起展示）。
	*  配图（whisperImageEnabled 开启时）：从表情包池**随机抽 1 张**，把描述注入指令并随文本带回；
	*  连图带句一起进缓存——周期内多端轮询看到的是同一张图（同 ts 同图，语义与文本一致）。 */
	const serveWhisper = async (petId, force) => {
		const cfg = readAllConfig(configPaths);
		const found = findPetInstance(cfg, petId);
		const conf = found ? found.conf : cfg.main ?? {};
		const ers = conf.eventsRefreshSec;
		const intervalSec = ers && typeof ers.whisper === "number" ? ers.whisper : 3600;
		const system = petSystemPrompt(petId, cfg);
		const now = Date.now();
		const cached = whisperCache.get(petId);
		if (!force && cached && now - cached.ts < intervalSec * 1e3) return {
			ok: true,
			text: cached.text,
			image: cached.image,
			ts: cached.ts
		};
		const meme = conf.whisperImageEnabled === true ? pickMeme(readMemePool(conf.memes, PACKAGE_ROOT_ASSETS)) : void 0;
		const result = await generateWhisper(ctx, system, meme);
		if (!result.ok) return {
			ok: false,
			reason: result.reason,
			message: result.message
		};
		whisperCache.set(petId, {
			text: result.text,
			image: result.image,
			ts: now
		});
		return {
			ok: true,
			text: result.text,
			image: result.image,
			ts: now
		};
	};
	/** 与某只宠物对话：截取最近记忆 → 生成回复 → 写入记忆 → 返回 {reply,ts}。
	*  供 /chat 端点（POST）与 /chat 命令共用同一条路径（锁内读写，防两端交错写盘）。
	*  配图（chatImageEnabled 开启时）：把表情包清单交给模型按语境选一张，命中池内才随回复带回。 */
	const chatWithPet = async (petId, text) => withMemoryLock(async () => {
		const cfg = readAllConfig(configPaths);
		const rounds = memoryRounds(petId, cfg);
		const conf = (findPetInstance(cfg, petId) ?? { conf: cfg.main ?? {} }).conf;
		const system = petSystemPrompt(petId, cfg);
		const pool = conf.chatImageEnabled === true ? readMemePool(conf.memes, PACKAGE_ROOT_ASSETS) : [];
		const mem = await readMemory();
		const bucketKey = findPetInstance(cfg, petId)?.entry ?? petId;
		const bucket = mem[bucketKey] ?? (mem[bucketKey] = {});
		const entry = bucket[petId] ?? (bucket[petId] = { messages: [] });
		const list = entry.messages.slice().slice(-rounds * 2);
		const generated = await generateChat(ctx, system, list, text, pool);
		if (!generated.ok) return generated;
		const now = Date.now();
		entry.messages.push({
			role: "user",
			content: text,
			ts: now
		});
		entry.messages.push({
			role: "assistant",
			content: generated.text,
			ts: now
		});
		await writeMemory(mem);
		return generated.image ? {
			ok: true,
			reply: generated.text,
			image: generated.image,
			ts: now
		} : {
			ok: true,
			reply: generated.text,
			ts: now
		};
	});
	/**
	* 当前生效宠物列表 = readAllConfig 成品拍平（main + 文件宠物全部条目；合并器已保证 id 唯一、
	* 字段填满），命令与桌面模式都从这里取。
	*/
	const effectivePetList = () => flattenPetList(readAllConfig(configPaths));
	/** 命令触发的展示气泡：/chat 命令写入（两端 1s 轮询 /broadcast 拉取展示）；覆盖手动触发场景。
	*  image：配图名称（碎碎念/对话配图开关开启时由 host 抽定或模型选定），随文本一起进缓存——
	*  与 /whisper 的 serveWhisper 契约对齐，否则命令这条路会把图丢掉（只剩文字气泡）。 */
	const broadcastTo = (petId, text, image) => {
		broadcastCache.set(petId, {
			text,
			image,
			ts: Date.now()
		});
	};
	/** 当前交互桌宠 id：/pet 已选且仍存在 → 该宠物；未选/已失效 → 有效宠物列表第一只（进程内，重启回默认） */
	const resolveActivePetId = () => {
		try {
			const eff = effectivePetList();
			if (eff.length === 0) return "";
			if (activePetId && eff.some((p) => String(p.id) === activePetId)) return activePetId;
			return String(eff[0].id);
		} catch {
			return activePetId;
		}
	};
	/** 宠物的显示名（name，缺失回落 id）——命令文案用 */
	const petDisplayName = (pet) => {
		const n = String(pet.name ?? "").trim();
		return n || String(pet.id ?? "");
	};
	let hasDesktopPet = false;
	const refreshDesktop = () => {
		hasDesktopPet = false;
		try {
			hasDesktopPet = effectivePetList().some((p) => isDesktopVisible(p.display));
		} catch (e) {
			ctx.logger?.warn?.(`[dsh-pet] 宠物配置非法，桌面模式已跳过：${e instanceof Error ? e.message : String(e)}`);
		}
	};
	refreshDesktop();
	/** 桌面可见宠物列表（[{id,size}]）：透传 Helper 决定创建几个局部窗口（每宠物一个）。 */
	const desktopPetList = () => {
		try {
			return effectivePetList().filter((p) => isDesktopVisible(p.display)).map((p) => ({
				id: String(p.id),
				size: Number(p.size)
			}));
		} catch {
			return [];
		}
	};
	let helper;
	let startRetryTimer;
	let electronEnsure;
	let disposed = false;
	/** 「无图形环境」提示只在进程生命周期内打一次，避免守护循环刷屏 */
	let displayWarned = false;
	/** 用已确认存在的 Electron 路径拉起桌面 Helper（每只桌面宠物一个局部小窗口）。 */
	const launchHelper = (electronPath) => {
		if (helper || disposed) return;
		if (!hasDesktopPet) return;
		const port = typeof ctx.webServer?.port === "number" ? ctx.webServer.port : 0;
		if (!port || port <= 0) {
			if (!startRetryTimer) {
				startRetryTimer = setTimeout(() => {
					startRetryTimer = void 0;
					launchHelper(electronPath);
				}, 500);
				startRetryTimer.unref?.();
			}
			return;
		}
		const origin = `http://127.0.0.1:${port}`;
		const configUrl = `${origin}${ROUTE_PREFIX}/config`;
		helper = new HelperProcess({
			electronPath,
			env: {
				DSH_PET_CONFIG_URL: configUrl,
				DSH_PET_SCALE: "1",
				DSH_PET_BRIDGE: "1",
				DSH_PET_PETS: JSON.stringify(desktopPetList())
			},
			bridgeHandler: async (req) => {
				const result = await handlePetRoute(req.url ?? "/", req.method ?? "GET", req.body);
				if (result.kind === "file") return {
					id: req.id,
					status: 200,
					contentType: result.contentType,
					file: result.file
				};
				if (result.kind === "text") return {
					id: req.id,
					status: result.status,
					contentType: "text/plain; charset=utf-8",
					body: result.body
				};
				return {
					id: req.id,
					status: result.status,
					contentType: "application/json; charset=utf-8",
					body: JSON.stringify(result.obj)
				};
			}
		}, ctx.logger ?? console);
		try {
			helper.start();
			ctx.logger?.info?.(`dsh-pet desktop helper started (config: ${configUrl})`);
		} catch (e) {
			ctx.logger?.warn?.(`dsh-pet desktop helper start failed: ${e instanceof Error ? e.message : String(e)}`);
			helper = void 0;
		}
	};
	/** 拉起桌面 Helper：先探测本机 Electron；缺失时进程内异步下载
	*  （不 spawn 子进程，CLI node 与 DSH Desktop 均适用），下载完成后自动拉起。 */
	const startHelper = () => {
		if (helper || electronEnsure || disposed) return;
		if (!hasDesktopPet) return;
		if (!hasGraphicalDisplay()) {
			if (!displayWarned) {
				displayWarned = true;
				ctx.logger?.warn?.("[dsh-pet] 未检测到图形显示环境（DISPLAY/WAYLAND_DISPLAY 均为空），已跳过桌面宠物。浏览器内宠物不受影响；如需在服务器上启用桌面模式，请配置 Xvfb 后设置 DSH_PET_DESKTOP_FORCE=1。");
			}
			return;
		}
		const found = resolveElectronPath();
		if (found) {
			launchHelper(found);
			return;
		}
		console.warn(`[dsh-pet] Electron not found, downloading to ${defaultElectronExe()} ...`);
		electronEnsure = ensureElectronDownload().then((path) => {
			if (path) launchHelper(path);
			else console.warn("[dsh-pet] Electron download failed; desktop pet unavailable. Set DSH_PET_ELECTRON_PATH and restart, or retry later.");
		}).finally(() => {
			electronEnsure = void 0;
		});
	};
	/** 停止桌面 Helper（保留配置，可再次拉起）。 */
	const stopHelper = (reason = "settings-change") => {
		if (startRetryTimer) {
			clearTimeout(startRetryTimer);
			startRetryTimer = void 0;
		}
		helper?.stop(reason);
		helper = void 0;
	};
	/** 宠物配置（display 等）变更后：重解析桌面宠物并按需重启 Helper。 */
	const syncDesktop = () => {
		refreshDesktop();
		stopHelper("desktop-config-change");
		startHelper();
	};
	/** 扩展名 → 素材子目录名（webm → webm/，mov → mov/；其余落在动画目录平级放行） */
	const animSubdirFor = (ext) => ext === ".mov" ? "mov" : "webm";
	/** 包内动画素材根：按扩展名取子目录（webm/ 随包发布；mov/ 不存在时为 404 兜底，仅 macOS 自维护）。 */
	const assetRootFor = (ext) => join(PACKAGE_ROOT, "assets", animSubdirFor(ext));
	/** 用户动画根：按扩展名取子目录（main-animation/webm 或 main-animation/mov）。 */
	const userRootFor = (ext) => join(thumbUserRoot, animSubdirFor(ext));
	/** 单次业务路由(WebServer 注册 → HTTP 落盘 / 桌面 Helper 管道 → scheme 应答,共用同一份实现):
	*  输入只需 rawUrl(/dsh-pet-7340/... + 查询) + method + body 文本;返回 RouteResult(JSON/文本/文件),
	*  消费方各自落盘——业务逻辑只有一份,两端天然一致(硬契约:浏览器/桌面行为严格对齐)。 */
	const handlePetRoute = async (rawUrl, method, body) => {
		const url = new URL(rawUrl, "http://localhost");
		const rest = decodeURIComponent(url.pathname.slice(ROUTE_PREFIX.length + 1));
		if (rest === "pet-pack/import") {
			if (method !== "POST") return {
				kind: "json",
				status: 405,
				obj: { error: "method not allowed" }
			};
			try {
				const payload = JSON.parse(body ?? "");
				const existingPetIds = new Set(flattenPetList(readAllConfig(configPaths)).map((pet) => String(pet.id ?? "")).filter(Boolean));
				const result = await importPetPack(payload, {
					petDir: petConfigDir,
					existingPetIds
				});
				syncDesktop();
				return {
					kind: "json",
					status: 200,
					obj: {
						ok: true,
						...result
					}
				};
			} catch (error) {
				if (error instanceof PetPackImportError) return {
					kind: "json",
					status: error.status,
					obj: { error: error.message }
				};
				return {
					kind: "json",
					status: 500,
					obj: { error: error instanceof Error ? error.message : String(error) }
				};
			}
		}
		if (rest === "pet/visibility") {
			if (method !== "POST") return {
				kind: "json",
				status: 405,
				obj: { error: "method not allowed" }
			};
			try {
				const payload = JSON.parse(body ?? "");
				if (typeof payload.petId !== "string" || typeof payload.visible !== "boolean") return {
					kind: "json",
					status: 400,
					obj: { error: "invalid pet visibility payload" }
				};
				const result = await setFilePetVisibility(configPaths, payload.petId, payload.visible);
				if (!result) return {
					kind: "json",
					status: 404,
					obj: { error: "file pet not found" }
				};
				syncDesktop();
				return {
					kind: "json",
					status: 200,
					obj: {
						ok: true,
						...result
					}
				};
			} catch (error) {
				return {
					kind: "json",
					status: 500,
					obj: { error: error instanceof Error ? error.message : String(error) }
				};
			}
		}
		if (rest === "config") {
			if (method === "GET") try {
				return {
					kind: "json",
					status: 200,
					obj: readAllConfig(configPaths)
				};
			} catch (e) {
				return {
					kind: "json",
					status: 500,
					obj: { error: e instanceof Error ? e.message : String(e) }
				};
			}
			if (method === "PUT") try {
				const parsed = JSON.parse(body ?? "");
				let existing;
				try {
					existing = JSON.parse(await readFile(userConfigPath, "utf8"));
				} catch {}
				const clean = saveUserConfig(parsed, existing);
				if (!clean) return {
					kind: "json",
					status: 400,
					obj: { error: "invalid pet config: expected { pets:[{name?,id,size,balanceEnabled,display,position:{corner,marginX,marginY}}] }（display 为 web/desktop/both/none 之一；可选顶层 notificationsEnabled / whisperImageEnabled / chatImageEnabled 布尔）" }
				};
				await mkdir(userRoot, { recursive: true });
				await writeFile(userConfigPath, JSON.stringify(clean, null, 2), "utf8");
				syncDesktop();
				return {
					kind: "json",
					status: 200,
					obj: { ok: true }
				};
			} catch {
				return {
					kind: "json",
					status: 400,
					obj: { error: "invalid JSON body" }
				};
			}
			if (method === "DELETE") {
				try {
					await rm(userConfigPath, { force: true });
				} catch {}
				syncDesktop();
				return {
					kind: "json",
					status: 200,
					obj: { ok: true }
				};
			}
			return {
				kind: "json",
				status: 405,
				obj: { error: "method not allowed" }
			};
		}
		if (rest === "config/meta") return {
			kind: "json",
			status: 200,
			obj: {
				user: userConfigPath,
				default: join(PACKAGE_ROOT, "assets", "config.jsonc"),
				animations: thumbUserRoot,
				storage: storageEntries({
					userDataRoot: userRoot,
					electronDir: electronLandingDir(),
					home: homedir(),
					packageRoot: PACKAGE_ROOT
				}),
				profile: profileNameFrom(PACKAGE_ROOT) ?? ""
			}
		};
		if (rest === "balance") {
			if (method !== "GET") return {
				kind: "json",
				status: 405,
				obj: { error: "method not allowed" }
			};
			try {
				const sel = ctx.agentDefaultModel.currentSelection();
				const result = await queryBalance(sel.provider, async (ref) => {
					const rc = await ctx.credentials.resolve(credentialRef(ref));
					return rc?.value;
				});
				return {
					kind: "json",
					status: 200,
					obj: result
				};
			} catch (e) {
				return {
					kind: "json",
					status: 500,
					obj: {
						ok: false,
						provider: "unknown",
						reason: "fetch-error",
						message: e instanceof Error ? e.message : String(e)
					}
				};
			}
		}
		if (rest === "balance/trigger") return {
			kind: "json",
			status: 200,
			obj: { count: balanceTriggerCount },
			headers: { "cache-control": "no-cache, no-store" }
		};
		if (rest === "whisper") {
			if (method !== "GET") return {
				kind: "json",
				status: 405,
				obj: { error: "method not allowed" }
			};
			try {
				const petId$1 = String(url.searchParams.get("pet") ?? "");
				return {
					kind: "json",
					status: 200,
					obj: await serveWhisper(petId$1, false)
				};
			} catch (e) {
				return {
					kind: "json",
					status: 200,
					obj: {
						ok: false,
						reason: "generate-error",
						message: e instanceof Error ? e.message : String(e)
					}
				};
			}
		}
		if (rest === "whisper/trigger") {
			if (method !== "GET") return {
				kind: "json",
				status: 405,
				obj: { error: "method not allowed" }
			};
			try {
				const petId$1 = String(url.searchParams.get("pet") ?? "");
				return {
					kind: "json",
					status: 200,
					obj: await serveWhisper(petId$1, true)
				};
			} catch (e) {
				return {
					kind: "json",
					status: 200,
					obj: {
						ok: false,
						reason: "generate-error",
						message: e instanceof Error ? e.message : String(e)
					}
				};
			}
		}
		if (rest === "chat") {
			const petId$1 = String(url.searchParams.get("pet") ?? "");
			try {
				if (method === "GET") {
					const cfg = readAllConfig(configPaths);
					const mem = await readMemory();
					const bucket = mem[findPetInstance(cfg, petId$1)?.entry ?? petId$1] ?? {};
					const list = (bucket[petId$1]?.messages ?? []).slice();
					const rounds = memoryRounds(petId$1, cfg);
					return {
						kind: "json",
						status: 200,
						obj: {
							ok: true,
							messages: list.slice(-rounds * 2),
							rounds
						}
					};
				}
				if (method === "POST") {
					const parsed = JSON.parse(body ?? "null") ?? {};
					const text = typeof parsed.text === "string" ? parsed.text.trim() : "";
					if (!text) return {
						kind: "json",
						status: 200,
						obj: {
							ok: false,
							reason: "bad-request",
							message: "消息为空"
						}
					};
					if (text.length > 2e3) return {
						kind: "json",
						status: 200,
						obj: {
							ok: false,
							reason: "bad-request",
							message: "消息过长（限 2000 字）"
						}
					};
					const result = await chatWithPet(petId$1, text);
					return {
						kind: "json",
						status: 200,
						obj: result
					};
				}
				return {
					kind: "json",
					status: 405,
					obj: { error: "method not allowed" }
				};
			} catch (e) {
				return {
					kind: "json",
					status: 200,
					obj: {
						ok: false,
						reason: "generate-error",
						message: e instanceof Error ? e.message : String(e)
					}
				};
			}
		}
		if (rest === "broadcast") {
			if (method !== "GET") return {
				kind: "json",
				status: 405,
				obj: { error: "method not allowed" }
			};
			const petId$1 = String(url.searchParams.get("pet") ?? "");
			const hit = broadcastCache.get(petId$1);
			return {
				kind: "json",
				status: 200,
				obj: {
					ok: true,
					text: hit?.text ?? "",
					image: hit?.image,
					ts: hit?.ts ?? 0
				},
				headers: { "cache-control": "no-cache, no-store" }
			};
		}
		if (rest === "work-status") {
			if (method !== "GET") return {
				kind: "json",
				status: 405,
				obj: { error: "method not allowed" }
			};
			return {
				kind: "json",
				status: 200,
				obj: workStatus,
				headers: { "cache-control": "no-cache, no-store" }
			};
		}
		if (rest === "notify") {
			if (method !== "GET") return {
				kind: "json",
				status: 405,
				obj: { error: "method not allowed" }
			};
			const since = Number(url.searchParams.get("since") ?? "0");
			const frames = notifyFrames.filter((f) => f.seq > since).map((f) => f.frame);
			return {
				kind: "json",
				status: 200,
				obj: {
					ok: true,
					seq: notifySeq,
					frames
				},
				headers: { "cache-control": "no-cache, no-store" }
			};
		}
		const [scope, ...restParts] = rest.split("/");
		if (scope === "font") {
			const fontRoot = join(PACKAGE_ROOT, "assets", "fonts");
			const fontFile = resolveExisting(fontRoot, restParts.join("/"));
			if (fontFile === void 0) return {
				kind: "text",
				status: 404,
				body: "dsh-pet: font not found"
			};
			const ext$1 = fontFile.slice(fontFile.lastIndexOf(".")).toLowerCase();
			return {
				kind: "file",
				file: fontFile,
				contentType: MIME[ext$1] ?? "application/octet-stream"
			};
		}
		if (scope === "pic") {
			const isMeme = restParts[0] === "memes";
			const picRoot = join(PACKAGE_ROOT, "assets", isMeme ? "memes" : "pic");
			const picFile = resolveExisting(picRoot, (isMeme ? restParts.slice(1) : restParts).join("/"));
			if (picFile === void 0) return {
				kind: "text",
				status: 404,
				body: "dsh-pet: pic not found"
			};
			const ext$1 = picFile.slice(picFile.lastIndexOf(".")).toLowerCase();
			return {
				kind: "file",
				file: picFile,
				contentType: MIME[ext$1] ?? "application/octet-stream"
			};
		}
		if (scope !== "thumb") return {
			kind: "text",
			status: 400,
			body: "dsh-pet: expected /dsh-pet-7340/thumb/<petId>/<file>"
		};
		const [petId, ...nameParts] = restParts;
		if (!petId || nameParts.length === 0) return {
			kind: "text",
			status: 400,
			body: "dsh-pet: expected /dsh-pet-7340/thumb/<petId>/<file>"
		};
		const fileName = nameParts.join("/");
		const ext = fileName.slice(fileName.lastIndexOf(".")).toLowerCase();
		if (ext !== ".webm" && ext !== ".mov") return {
			kind: "text",
			status: 400,
			body: "dsh-pet: unsupported animation format (expected .webm or .mov)"
		};
		const extraAnimDir = resolveAsset(petConfigDir, petId + "-animation");
		const file = extraAnimDir !== void 0 && existsSync(extraAnimDir) ? resolveExisting(extraAnimDir, fileName) : resolveExisting(userRootFor(ext), fileName) ?? resolveExisting(assetRootFor(ext), fileName);
		if (file === void 0) return {
			kind: "text",
			status: 404,
			body: "dsh-pet: asset not found"
		};
		return {
			kind: "file",
			file,
			contentType: MIME[ext] ?? "application/octet-stream"
		};
	};
	ctx.effect(() => ctx.webServer.register({
		kind: "prefix",
		path: ROUTE_PREFIX,
		handler: async (req, res) => {
			try {
				const body = req.method === "PUT" || req.method === "POST" ? await readBody(req) : void 0;
				const result = await handlePetRoute(req.url ?? "/", req.method ?? "GET", body);
				if (result.kind === "json") sendJson(res, result.status, result.obj, result.headers);
				else if (result.kind === "text") sendText(res, result.status, result.body);
				else await sendFile(res, result.file, result.contentType);
			} catch (e) {
				const status = e instanceof PetPackImportError ? e.status : 500;
				sendJson(res, status, { error: e instanceof Error ? e.message : String(e) });
			}
		}
	}), "dsh-pet: /dsh-pet-7340 asset route");
	ctx.effect(() => {
		const dispose = ctx.on("session/event", (session, event) => {
			const type = event?.type;
			if (!type) return;
			const sessionId = String(session?.header?.id ?? session?.id ?? "unknown");
			if (type === "todo/write") {
				if (workStatusBySession.has(sessionId)) {
					const task = currentTaskFromTodo(event);
					if (task !== workStatus.task) {
						workStatus.task = task;
						workStatus.ts = Date.now();
					}
				}
				return;
			}
			if (type === "user/message") {
				const source = event?.data?.source;
				if (source?.kind === "goal") {
					const flags = turnFlags.get(sessionId) ?? {
						goalRound: false,
						closing: null
					};
					flags.goalRound = true;
					turnFlags.set(sessionId, flags);
				}
				return;
			}
			if (type === "turn/start") turnFlags.set(sessionId, {
				goalRound: false,
				closing: null
			});
			if (type === "tool/call" && String(event?.data?.name ?? "") === GOAL_UPDATE_TOOL) {
				const action = goalUpdateAction(String(event?.data?.arguments ?? ""));
				if (action) {
					const flags = turnFlags.get(sessionId) ?? {
						goalRound: false,
						closing: null
					};
					flags.closing = action;
					turnFlags.set(sessionId, flags);
				}
			}
			const next = reduceWorkStatus(event, turnFlags.get(sessionId));
			if (!next) {
				if (type === "turn/end") {
					turnFlags.delete(sessionId);
					if (workStatusBySession.delete(sessionId)) refreshWorkStatus();
				}
				return;
			}
			const seq = Number(event.seq ?? 0);
			const prev = workStatusBySession.get(sessionId);
			if (prev?.state === next && (prev?.seq ?? -1) >= seq) return;
			workStatusBySession.set(sessionId, {
				state: next,
				seq
			});
			refreshWorkStatus();
			if (next === "success" || next === "error") scheduleTerminalCleanup(sessionId);
		});
		return () => {
			dispose();
			for (const t of terminalTimers.values()) clearTimeout(t);
			terminalTimers.clear();
		};
	}, "dsh-pet: work-status session events");
	ctx.effect(() => {
		const sessionDispose = ctx.on(
			"session/event",
			// eslint-disable-next-line @typescript-eslint/no-explicit-any
			(_session, event) => {
				const frame = reduceNotifyFrame(event);
				if (frame) pushNotifyFrame(frame);
			}
);
		const errorDispose = ctx.on(
			"agent/error",
			// eslint-disable-next-line @typescript-eslint/no-explicit-any
			(payload) => {
				pushNotifyFrame(agentErrorFrame(payload?.error));
			}
);
		return () => {
			sessionDispose();
			errorDispose();
		};
	}, "dsh-pet: notify frames");
	ctx.effect(() => ctx.commands.register({
		name: "balance",
		description: "手动触发桌宠余额动画（立即显示余额气泡）",
		handler: () => {
			balanceTriggerCount += 1;
			return {
				kind: "success",
				text: "已触发桌宠余额动画"
			};
		}
	}), "dsh-pet: /balance command");
	ctx.effect(() => ctx.commands.register({
		name: "pet",
		description: "选择桌宠（/chat 对话的目标；支持选择框或手输 id/名字）",
		input: { hint: "[宠物 id 或名字]（留空查看当前）" },
		handler: ({ rawInput }) => {
			const arg = rawInput.trim();
			let eff;
			try {
				eff = effectivePetList();
			} catch {
				eff = [];
			}
			if (!arg) {
				const cur = resolveActivePetId();
				const found = eff.find((p) => String(p.id) === cur);
				return {
					kind: "success",
					text: "当前桌宠：" + (found ? petDisplayName(found) : cur || "（无可交互桌宠）")
				};
			}
			const byId = eff.find((p) => String(p.id) === arg);
			if (byId) {
				activePetId = String(byId.id);
				return {
					kind: "success",
					text: "已选择桌宠：" + petDisplayName(byId)
				};
			}
			const byName = eff.filter((p) => petDisplayName(p) === arg);
			if (byName.length === 1) {
				activePetId = String(byName[0].id);
				return {
					kind: "success",
					text: "已选择桌宠：" + petDisplayName(byName[0])
				};
			}
			if (byName.length > 1) return {
				kind: "error",
				text: "「" + arg + "」有 " + byName.length + " 只桌宠（id：" + byName.map((p) => String(p.id)).join("、") + "），请用 id 指定"
			};
			return {
				kind: "error",
				text: "找不到桌宠「" + arg + "」（id 或名字都行；/pet 回车可打开选择框）"
			};
		}
	}), "dsh-pet: /pet command");
	ctx.effect(() => ctx.commands.register({
		name: "chat",
		description: "与桌宠对话：留空 = 碎碎念一句；输入消息 = 正常对话",
		input: { hint: "[消息]（留空 = 碎碎念）" },
		handler: async ({ rawInput }) => {
			const petId = resolveActivePetId();
			if (!petId) return {
				kind: "error",
				text: "没有可交互的桌宠"
			};
			const text = rawInput.trim();
			try {
				if (!text) {
					const w = await serveWhisper(petId, true);
					if (!w.ok) return {
						kind: "error",
						text: "碎碎念生成失败" + (w.message ? "：" + w.message : "")
					};
					broadcastTo(petId, w.text ?? "", w.image);
					return {
						kind: "success",
						text: w.text ?? ""
					};
				}
				if (text.length > 2e3) return {
					kind: "error",
					text: "消息过长（限 2000 字）"
				};
				const r = await chatWithPet(petId, text);
				if (!r.ok) return {
					kind: "error",
					text: "对话失败" + (r.message ? "：" + r.message : "")
				};
				broadcastTo(petId, r.reply, r.image);
				return {
					kind: "success",
					text: r.reply
				};
			} catch (e) {
				return {
					kind: "error",
					text: "对话失败：" + (e instanceof Error ? e.message : String(e))
				};
			}
		}
	}), "dsh-pet: /chat command");
	ctx.effect(() => () => {
		disposed = true;
		stopHelper("dsh-host-stop");
	});
	startHelper();
}

//#endregion
export { apply, inject, name };