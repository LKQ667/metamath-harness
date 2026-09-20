/** /dsh-pet-7340/balance 响应（与 host/balance.ts 同构；两端按此结构校验） */
export interface RawBalanceResult {
    ok: boolean;
    provider?: string;
    kind?: 'opencode' | 'deepseek';
    reason?: string;
    message?: string;
    data?: {
        rolling?: unknown;
        weekly?: unknown;
        monthly?: unknown;
        rollingResetsAt?: unknown;
        weeklyResetsAt?: unknown;
        monthlyResetsAt?: unknown;
        currency?: unknown;
        total?: unknown;
        granted?: unknown;
        toppedUp?: unknown;
    };
}
/** 已解析的余额视图（展示 + 档位计算用） */
export interface BalanceView {
    provider: string;
    kind: 'opencode' | 'deepseek';
    ok: true;
    /** opencode：三窗口用量（0-100 数字）+ 各自的重置时间 */
    rolling?: number;
    weekly?: number;
    monthly?: number;
    rollingResetsAt?: string;
    weeklyResetsAt?: string;
    monthlyResetsAt?: string;
    /** deepseek：余额金额（字符串，与接口一致） */
    currency?: string;
    total?: string;
    granted?: string;
    toppedUp?: string;
}
/** 无效（不支持/缺凭证/抓取失败）：显式标记，不静默 */
export interface BalanceUnavailable {
    provider: string;
    ok: false;
    reason: 'unsupported' | 'credential-missing' | 'fetch-error';
    message?: string;
}
export type BalanceState = BalanceView | BalanceUnavailable;
/** 拉取当前状态的余额；网络/解析失败显式抛错（上层决定报错方式，绝不静默 0） */
export declare function fetchBalanceState(baseUrl?: string): Promise<BalanceState>;
/** 手动触发计数（/balance 命令 +1；两个平台同样的 1s 轻量轮询语义）。 */
export declare function fetchTriggerCount(baseUrl?: string): Promise<number>;
/** DeepSeek 满额基准（¥）：余额 ≥ 该值视为 100%（未消耗），余额按比例折算为已用百分比 */
export declare const DEEPSEEK_FULL_BALANCE_CNY = 20;
/**
 * 事件档位百分比（已用百分比语义：0 = 未消耗，100 = 耗尽）：
 * - opencode：取三窗口最大（风险最高者为准）
 * - deepseek：余额按 DEEPSEEK_FULL_BALANCE_CNY（¥20 = 100%）折算为已用百分比
 *   （余额 20 元 → 0%，10 元 → 50%，0 元 → 100%）
 */
export declare function balancePercent(v: BalanceView): number | undefined;
/**
 * 余额事件档位索引（与 assets/config.jsonc 注释一致）：
 * index = p === 100 ? 5 : Math.floor(p / 20)
 */
export declare function balanceEventIndex(p: number): number;
/** OpenCode 各窗口满额度金额（USD）。业务常量：12 = 5h（5 小时滚动窗口）、30 = 周、60 = 月 */
export declare const OPENCODE_QUOTA_USD: {
    readonly rolling: 12;
    readonly weekly: 30;
    readonly monthly: 60;
};
/** 窗口展示名（联想框文案用）：5h = 5 小时额度窗口、周、月 */
export declare const WINDOW_LABELS: {
    readonly rolling: "5h";
    readonly weekly: "周";
    readonly monthly: "月";
};
export type OpenCodeWindow = keyof typeof OPENCODE_QUOTA_USD;
/** 一个窗口的额度概况（用于联想框一句话判定） */
export interface WindowUsage {
    label: string;
    percent: number;
    quotaUsd: number;
    /** 剩余额度（USD）= 满额度 × (100 − percent) / 100 */
    remainingUsd: number;
    resetsAt?: string;
}
/** 取三窗口剩余额度最少的那个（最先到达满额度/最先用完） */
export declare function urgentWindow(v: BalanceView): WindowUsage | undefined;
/**
 * 重置时间 → 相对文案（保留 1 位小数）：
 * - 距重置 ≥ 4 天 → 「N.x 天」
 * - 距重置 < 4 天 → 「N.x 小时」
 * - 已过重置点 → 「已重置」；未知时间 → 空串
 */
export declare function resetInText(iso?: string): string;
/**
 * DeepSeek 峰谷计价档位（北京时间）：
 * - 高峰：工作日 9:00–12:00、14:00–18:00；其余为空闲（低谷）
 * - 周六/周日全天按低谷价计费（自 2026-08-23 起，周末不再区分峰谷）
 */
export type PricingTier = 'peak' | 'idle';
/** 当前时刻的 DeepSeek 计价档位（按北京时间 Asia/Shanghai，UTC+8 无夏令时） */
export declare function deepseekPricingTier(now?: Date): PricingTier;
/** 气泡行数据：role 决定两端的样式类（浏览器 React span；桌面 DOM div）；tier 用于峰谷着色 */
export type BalanceBubbleRow = {
    role: 'label';
    text: string;
} | {
    role: 'sub';
    text: string;
} | {
    role: 'error';
    text: string;
} | {
    role: 'tier';
    tier: PricingTier;
    text: string;
};
/**
 * 把 BalanceState 渲染成气泡行数据（纯函数，不碰 DOM/React）：
 * - opencode：两行 —— 「5h/周/月」额度已用 N% + 重置倒计时
 * - deepseek：一行 —— 余额（峰/谷）¥x.xx（峰红/谷绿由 role:'tier' 表达）
 * - 无效：显式展示不可用原因，绝不伪造数字
 */
export declare function balanceBubbleView(state: BalanceState): BalanceBubbleRow[];
