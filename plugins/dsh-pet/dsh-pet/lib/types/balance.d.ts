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
/** 一个 service provider 的余额查询定义 */
export interface BalanceProvider {
    /** 可命中的 provider id（agentDefaultModel 报告的 id） */
    ids: string[];
    /** 凭证引用名（credentialRef），如 OPENCODE_GO_API_KEY */
    ref: string;
    /** 展示类型：余额 vs 用量 */
    kind: 'opencode' | 'deepseek';
}
/** 已知可查询余额的服务商（只登记有公开 API 的；opencode/Zen 暂无官方余额 API，不在此表） */
export declare const BALANCE_PROVIDERS: BalanceProvider[];
/** provider id → 唯一匹配定义；未匹配返回 undefined（= 不支持查询） */
export declare function matchBalanceProvider(provider: string): BalanceProvider | undefined;
/** 重构后的响应（client 端与 host 端同构使用） */
export type BalanceResult = {
    ok: true;
    provider: string;
    kind: 'opencode';
    data: {
        rolling: number;
        weekly: number;
        monthly: number;
        rollingResetsAt: string;
        weeklyResetsAt: string;
        monthlyResetsAt: string;
    };
} | {
    ok: true;
    provider: string;
    kind: 'deepseek';
    data: {
        currency: string;
        total: string;
        granted: string;
        toppedUp: string;
    };
} | {
    ok: false;
    provider: string;
    reason: 'unsupported' | 'credential-missing' | 'fetch-error';
    message?: string;
};
/**
 * 按当前服务商查询余额。
 * @param provider agentDefaultModel.currentSelection().provider
 * @param resolveKey 凭证解析：ref 名 → key（由调用方注入 ctx.credentials.resolve）
 * @returns 结构化结果：成功 / 不支持 / 缺凭证 / 抓取失败（失败带 message，绝不返回伪造数字）
 */
export declare function queryBalance(provider: string, resolveKey: (ref: string) => Promise<string | undefined>): Promise<BalanceResult>;
