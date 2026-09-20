/**
 * 碎碎念生成（host 半侧）：用 DSH 的 LLM 统一抽象层（ctx.llm）按当前对话用的
 * provider/model 生成一句话。与余额不同：不自己拼各服务商端点、不碰凭证——
 * ctx.llm 已接管适配器路由/模型解析/凭据，天然与对话页完全一致。
 *
 * 设计：
 * - provider/model 直接取 agentDefaultModel.currentSelection()（与余额同源）；
 * - system = 用户配置的 whisperPrompt（人设），user = 一个极简的"说句话"请求；
 * - reasoningEffort: 'off' —— 统一关闭深度思考：碎碎念只求随口一句，不开推理（省时省 token）；
 * - 流式收集 + BlockAssembler 拼装文本；生成失败显式返回结构化原因，不伪造文案；
 * - 短超时（LLM 冷启动/慢响应时快速放弃，不留挂起请求）。
 */
/** 生成失败原因（与 shared/whisper.ts 的 WhisperState 失败分支同构） */
export type WhisperGenerateResult = {
    ok: true;
    text: string;
} | {
    ok: false;
    reason: 'provider-missing' | 'generate-error';
    message?: string;
};
/**
 * 用当前对话的 provider/model 生成一句碎碎念。
 * @param ctx 宿主上下文（注入 agentDefaultModel / llm）
 * @param system 人设提示词（whisperPrompt）
 * @returns 生成的文本，或结构化失败（provider 缺失 / 生成错误）
 */
export declare function generateWhisper(ctx: {
    agentDefaultModel: {
        currentSelection(): {
            provider: string;
            model: string;
        };
    };
    llm?: unknown;
}, system: string): Promise<WhisperGenerateResult>;
