import type { Corner } from './types';
/** 一次移动的几何参数（比例坐标） */
export interface MovePlan {
    startRatio: number;
    startYRatio: number;
    targetRatio: number;
    totalRatio: number;
}
/** 计算一次移动的起点/终点比例坐标；目标越出视口边缘（含边距）时返回 null。
 *  sideAllow = 左右透明边余量（视频画布内宠物身体居中、两侧透明）：边界按"身体"贴边而不是
 *  按"整个视频盒"贴边——宠物能走到屏幕边缘，但身体永不越界（不会漫游到屏幕外丢失）。 */
export declare const planMove: (o: {
    cx: number;
    cy: number;
    W: number;
    H: number;
    dir: 1 | -1;
    minDist: number;
    maxDist: number;
    margin: number;
    halfW: number;
    /** 可选：身体相对视频盒左/右各留多少像素（默认 0 = 旧行为，按视频盒贴边） */
    sideAllow?: number;
}) => MovePlan | null;
/**
 * 角落 + 边距 → 宠物根节点左上角像素坐标。
 * 与浏览器 overlay 的 CSS 角落语义一致：
 *   top-left     = left:marginX, top:marginY
 *   top-right    = right:marginX, top:marginY
 *   bottom-left  = left:marginX, bottom:marginY
 *   bottom-right = right:marginX, bottom:marginY
 * 桌面模式用同一套几何摆放宠物（根节点 = 舞台）。
 */
export declare const anchorPixel: (o: {
    corner: Corner;
    marginX: number;
    marginY: number;
    size: number;
    W: number;
    H: number;
}) => {
    x: number;
    y: number;
};
