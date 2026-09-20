// 碎碎念数据层与展示视图（src/shared 纯逻辑，浏览器 bundle 与桌面 shared-core 共用）：
// 拉取 /dsh-pet-7340/whisper → 解析 → 生成文本 → 气泡行数据。
// 不依赖 React/DOM；host/whisper.ts 的生成结果与本模块的 RawWhisperResult 同构
// （HTTP 契约两端各自声明，host 无需 import 本目录——DSH 单文件加载约束）。
//
// 触发语义（与余额一致）：容器按 eventsRefreshSec.whisper 周期拉取一次，成功且
// 新文本（ts 变化）时递增 whisperTick 触发各宠物播碎碎念动画 + 显示一句话气泡。

/** /dsh-pet-7340/whisper 响应（与 host/whisper.ts 同构；两端按此结构校验） */
export interface RawWhisperResult {
  ok: boolean;
  text?: string;
  /** 配图名称（= 配置 memes 的键，即 assets/memes/<名称>.png）；未开配图或该次未配图时缺省 */
  image?: string;
  ts?: number;
  reason?: string;
  message?: string;
}

/** 已解析的碎碎念结果：成功（一句话 + 可选配图 + 生成时间戳）/ 失败（显式原因，不伪造文本） */
export type WhisperState =
  | { ok: true; text: string; image?: string; ts: number }
  | { ok: false; reason: 'provider-missing' | 'generate-error'; message?: string };

const TIMEOUT_MS = 30000;
const RETRIES = 2;

/** 带超时 + 重试的 GET（host 生成 LLM 调用可能较慢，超时放宽；桌面 file:// 页面需绝对 URL） */
async function getWithRetry(url: string): Promise<Response> {
  let last: unknown;
  for (let i = 0; i <= RETRIES; i++) {
    try {
      const res = await fetch(url, { signal: AbortSignal.timeout(TIMEOUT_MS) });
      if (res.ok) return res;
      last = new Error('HTTP ' + res.status);
    } catch (e) {
      last = e;
    }
    if (i < RETRIES) await new Promise((r) => setTimeout(r, 800));
  }
  throw last instanceof Error ? last : new Error(String(last));
}

/** 拉取当前碎碎念文本；解析/网络失败显式抛错（上层决定报错方式，绝不静默伪造文案） */
export async function fetchWhisperState(baseUrl: string = '/dsh-pet-7340/whisper'): Promise<WhisperState> {
  const res = await getWithRetry(baseUrl);
  const raw: RawWhisperResult = await res.json().catch(() => null);
  if (!raw || typeof raw !== 'object') throw new Error('dsh-pet: 碎碎念响应非法');
  if (raw.ok !== true) {
    return {
      ok: false,
      reason: raw.reason === 'provider-missing' ? 'provider-missing' : 'generate-error',
      message: typeof raw.message === 'string' ? raw.message : undefined,
    };
  }
  const text = typeof raw.text === 'string' ? raw.text.trim() : '';
  const ts = Number(raw.ts);
  if (!text || !Number.isFinite(ts)) throw new Error('dsh-pet: 碎碎念数据非法');
  const image = typeof raw.image === 'string' && raw.image.trim() ? raw.image.trim() : undefined;
  return image ? { ok: true, text, image, ts } : { ok: true, text, ts };
}

/**
 * 表情包图片 URL —— 与视频（/thumb）、字体（/font）、光标（/pic）**完全同一套拼法**：
 * `<base>/pic/memes/<名称>.png`，名称含中文需编码。
 *
 * base 语义 = 各端的「已含 /dsh-pet-7340 前缀的宿主基址」（**与视频的 assetBase 一致**）：
 *   - 浏览器：缺省 `/dsh-pet-7340`（页面就在宿主 origin 上，相对路径即可）；
 *   - 桌面：传 `BASE`（`http://127.0.0.1:<port>/dsh-pet-7340` 或 bridge 的
 *     `dsh-pet-bridge://dsh-pet/dsh-pet-7340`）——桌面页面是 file:// 加载的，
 *     相对路径会被解析成 file:///… 而必然失败；且 bridge 模式必须走自定义 scheme。
 *
 * 注意：base 已含 `/dsh-pet-7340`，函数内**不得**再拼一次（否则出现
 * `…/dsh-pet-7340/dsh-pet-7340/…` 而 404——桌面端图裂的成因）。
 */
export function memeImageUrl(name: string, base = '/dsh-pet-7340'): string {
  return base + '/pic/memes/' + encodeURIComponent(name) + '.png';
}

/** 气泡配图 class（两端共用，样式见 MEME_BUBBLE_CSS） */
export const MEME_IMG_CLASS = 'pet-bub-img';
/** 带图气泡 class：取消 min-width，让气泡贴合图片宽度（否则图旁留大片空白） */
export const MEME_BUBBLE_CLASS = 'has-img';

/** 气泡配图样式 —— 两端注入同一份（与 SCORE_POPUP_CSS / MENU_CSS 同理，避免两处各写一遍）。
 * 尺寸取宠物宽度变量：浏览器用 --dsh-pet-size、桌面用 --pet-size（既有差异），
 * 这里用 CSS 变量回退同时兼容两者，调用方无需传尺寸。 */
export const MEME_BUBBLE_CSS = [
  '.pet-bub-img{display:block;width:calc(var(--dsh-pet-size,var(--pet-size,462px))*0.34);height:auto;',
  'border-radius:calc(var(--dsh-pet-size,var(--pet-size,462px))*0.026);',
  'margin:0 auto calc(var(--dsh-pet-size,var(--pet-size,462px))*0.017);object-fit:cover;',
  'pointer-events:none;user-select:none}',
  '.pet-bubble.has-img,.dsh-pet-bubble.has-img{min-width:0}',
].join('');

/** 只注入一次（两端共用；页面已有同一标记则跳过） */
let memeCssInjected = false;
export function injectMemeBubbleCss(): void {
  if (memeCssInjected || typeof document === 'undefined') return;
  memeCssInjected = true;
  if (document.querySelector('style[data-plugin-css="dsh-pet/meme-bubble"]') !== null) return;
  const tag = document.createElement('style');
  tag.dataset.plugin = 'dsh-pet';
  tag.dataset.pluginCss = 'dsh-pet/meme-bubble';
  tag.textContent = MEME_BUBBLE_CSS;
  document.head.appendChild(tag);
}

/**
 * 生成气泡配图节点（两端共用同一份渲染：浏览器 React 壳与桌面 DOM 壳都调它）。
 * 返回 null 表示「本次不配图」——调用方据此走纯文本路径（老行为不变）。
 * @param name 配图名称（配置 memes 的键）；缺省/空白 → null
 * @param base 已含 /dsh-pet-7340 的宿主基址（与视频同规则）：浏览器缺省，桌面传 BASE
 */
export function createMemeImage(name?: string, base = '/dsh-pet-7340'): HTMLImageElement | null {
  const key = String(name ?? '').trim();
  if (!key) return null;
  injectMemeBubbleCss();
  const img = document.createElement('img');
  img.className = MEME_IMG_CLASS;
  img.src = memeImageUrl(key, base);
  img.alt = key;
  return img;
}

/** 手动触发一次碎碎念（右键菜单「碎碎念」项用）：host 强制立即新生成一句并更新缓存
 *  （绕过节流——周期内的轮询端下次拉取看到新 ts 也会跟着展示，与 /balance/trigger 同语义）。 */
export function fetchWhisperTrigger(baseUrl: string = '/dsh-pet-7340/whisper/trigger'): Promise<WhisperState> {
  return fetchWhisperState(baseUrl);
}

/** 碎碎念气泡行数据：一句话（role:'label' 单行，复用余额气泡的通用行渲染） */
export type WhisperBubbleRow = { role: 'label'; text: string };

/** 碎碎念文本 → 气泡行（两端共用同一份行数据；纯函数，不碰 DOM/React） */
export function whisperBubbleView(state: WhisperState): WhisperBubbleRow[] {
  if (state.ok) return [{ role: 'label', text: state.text }];
  const msg =
    state.reason === 'provider-missing'
      ? '当前对话未配置模型，碎碎念不可用'
      : '碎碎念生成失败' + (state.message ? '：' + state.message : '');
  return [{ role: 'label', text: msg }];
}
