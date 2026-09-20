/** /dsh-pet-7340/whisper 响应（与 host/whisper.ts 同构；两端按此结构校验） */
export interface RawWhisperResult {
    ok: boolean;
    text?: string;
    ts?: number;
    reason?: string;
    message?: string;
}
/** 已解析的碎碎念结果：成功（一句话 + 生成时间戳）/ 失败（显式原因，不伪造文本） */
export type WhisperState = {
    ok: true;
    text: string;
    ts: number;
} | {
    ok: false;
    reason: 'provider-missing' | 'generate-error';
    message?: string;
};
/** 拉取当前碎碎念文本；解析/网络失败显式抛错（上层决定报错方式，绝不静默伪造文案） */
export declare function fetchWhisperState(baseUrl?: string): Promise<WhisperState>;
/** 手动触发一次碎碎念（右键菜单「碎碎念」项用）：host 强制立即新生成一句并更新缓存
 *  （绕过节流——周期内的轮询端下次拉取看到新 ts 也会跟着展示，与 /balance/trigger 同语义）。 */
export declare function fetchWhisperTrigger(baseUrl?: string): Promise<WhisperState>;
/** 碎碎念气泡行数据：一句话（role:'label' 单行，复用余额气泡的通用行渲染） */
export type WhisperBubbleRow = {
    role: 'label';
    text: string;
};
/** 碎碎念文本 → 气泡行（两端共用同一份行数据；纯函数，不碰 DOM/React） */
export declare function whisperBubbleView(state: WhisperState): WhisperBubbleRow[];
