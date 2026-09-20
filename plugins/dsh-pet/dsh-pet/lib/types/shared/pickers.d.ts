import type { Category, Weights } from './types';
/** 从字符串池里等概率随机抽一个；exclude 排除某个名字（避免连续重复） */
export declare const pick: <T>(pool: T[], exclude?: T) => T;
/** 生成 [min, max) 区间内的随机整数 */
export declare const randomBetween: (min: number, max: number) => number;
/**
 * 按权重在分类池中选一个分类；noMirror 分类在镜像(facing=right)时被排除，
 * 剩余权重自动归一化。分类池为空时返回 null。
 */
export declare const pickWeightedCategory: (categories: Category[], facing: string) => Category | null;
/** 掷骰结果类别 */
export type RollKind = 'idle' | 'turn' | 'move' | 'action';
/**
 * 按权重掷骰：roll ∈ [0,1) → 下一个动画类别（纯函数，可单测）。
 * topEnd = (idle+turn+move)/100：三档权重占比之和，剩余概率归入 'action'。
 */
export declare const rollKind: (roll: number, w: Weights) => RollKind;
/** 从分类池选一个动作；无可用分类时回退 idle 池（返回 {id, name}，纯函数）。
 * facing 用于 noMirror 镜像过滤；current 用于避免连续重复（pick 的 exclude）。 */
export declare const pickCategoryAction: (categories: Category[], idlePool: string[], facing: string, current: string) => {
    id: string;
    name: string;
};
