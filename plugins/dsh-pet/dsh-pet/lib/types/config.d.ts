/** 配置路径集（宿主组装好后传入，单一事实来源） */
export interface ConfigPaths {
    /** 包内 assets/config.jsonc（内置默认，绝对正确） */
    defaultFile: string;
    /** ~/.dsh/dsh-pet/main-config.json（用户主配置，可编辑层） */
    userFile: string;
    /** ~/.dsh/dsh-pet/pet（文件宠物目录） */
    petDir: string;
}
/**
 * 唯一读取函数：内置默认 + 用户主配置 + 文件宠物逐字段合并后的完成品聚合。
 * 返回 { main: {...}, test1: {...}, ... } —— 每个条目都是原文件结构且所有字段已填满，
 * 消费端直接读，不做任何校验/兜底。每次调用重新读文件：修改配置刷新/重启即生效。
 */
export declare function readAllConfig(paths: ConfigPaths): Record<string, Record<string, unknown>>;
/** 拍平全部条目的 pets 为单列表（host 消费端用：桌面宠物列表 / 命令 / 当前桌宠解析） */
export declare function flattenPetList(merged: Record<string, Record<string, unknown>>): Record<string, unknown>[];
/** 在完成品聚合里按实例 id 定位宠物及其所属条目（host 内部消费索引）：
 *  条目 key 即素材根（assetRoot）；条目级字段（whisperPrompt/chatMemoryRounds/animations）随条目取。 */
export declare function findPetInstance(merged: Record<string, Record<string, unknown>>, petId: string): {
    entry: string;
    conf: Record<string, unknown>;
    pet: Record<string, unknown>;
} | undefined;
/** 持久切换文件宠物显示状态；只写扫描到的配置文件，不接受调用方提供路径。 */
export declare function setFilePetVisibility(paths: ConfigPaths, petId: string, visible: boolean): Promise<{
    display: string;
} | null>;
/**
 * 保存用户层（PUT /config）：更新 main-config.json，接受可编辑字段（pets + notificationsEnabled）。
 * 编辑语义：**非白名单顶层字段（physics / whisperPrompt / chatMemoryRounds / eventsRefreshSec 等）
 * 从 `existing`（当前磁盘上的用户文件原对象）原样透传保留**——
 * 用户手动编辑的精调配置不会被设置页保存抹掉（旧实现是纯白名单重建，会整体覆盖丢失）。
 * 非法 → 返回 null（宿主回 400）。与读取分离——文件宠物永不回写、不在本模式内。
 */
export declare function saveUserConfig(raw: unknown, existing?: Record<string, unknown>): {
    pets: unknown[];
    notificationsEnabled?: boolean;
    [key: string]: unknown;
} | null;
