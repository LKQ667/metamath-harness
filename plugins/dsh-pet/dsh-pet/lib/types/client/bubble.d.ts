import { type BalanceState } from '../shared/balance';
import type { ReactNode } from 'react';
import type { jsx } from 'react/jsx-runtime';
/**
 * 制造余额气泡（工厂）。
 * 工厂内注入样式一次（与 pet.ts 的 injectCss 同模式）；组件为哑组件，props = { state, on }。
 * 内容来自 src/shared 的 balanceBubbleView（与桌面模式完全一致）。
 */
export declare function makeBalanceBubble(rt: {
    h: typeof jsx;
}): (props: {
    state: BalanceState;
    on: boolean;
}) => ReactNode;
/**
 * 制造碎碎念气泡（工厂）。
 * 与余额气泡共用同一套样式（dsh-pet-bubble）与行渲染（rowsToNodes）；
 * 内容来自 src/shared 的 whisperBubbleView（与桌面模式完全一致）。
 */
export declare function makeWhisperBubble(rt: {
    h: typeof jsx;
}): (props: {
    text: string;
    on: boolean;
}) => ReactNode;
