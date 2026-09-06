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
  ts?: number;
  reason?: string;
  message?: string;
}

/** 已解析的碎碎念结果：成功（一句话 + 生成时间戳）/ 失败（显式原因，不伪造文本） */
export type WhisperState =
  | { ok: true; text: string; ts: number }
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
  return { ok: true, text, ts };
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
