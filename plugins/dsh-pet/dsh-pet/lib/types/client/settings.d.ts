import type { Pet } from '../shared/types';
import type { Dispatch, FunctionComponent, SetStateAction } from 'react';
import type * as ReactNS from 'react';
import type { jsx } from 'react/jsx-runtime';
/** 容器与设置页共享的桥（同一 bundle 单例）：
 * current=最新完整宠物列表（成品拍平，默认空）；sync=容器注册的重渲染回调（未注册时为无操作函数）；
 * template=main 条目的宠物[0]（「添加宠物」用它作为默认配置） */
export declare const petBridge: {
    current: Pet[];
    sync: (pets: Pet[]) => void;
    template: Pet | undefined;
};
/** 字典命名空间 */
export declare const NS = "pet.config";
export declare const zh: {
    nav: string;
    intro: string;
    petsLabel: string;
    add: string;
    importPack: string;
    importPackHint: string;
    importReading: string;
    importUploading: string;
    importSuccess: string;
    importInvalid: string;
    importTooLarge: string;
    closePet: string;
    showPet: string;
    filePetControl: string;
    remove: string;
    confirmRemove: string;
    confirmTitle: string;
    cancel: string;
    atLeastOne: string;
    emptyPets: string;
    sizeLabel: string;
    sizeHint: string;
    nameLabel: string;
    nameHint: string;
    balanceEnabled: string;
    balanceEnabledHint: string;
    whisperEnabled: string;
    whisperEnabledHint: string;
    displayLabel: string;
    displayHint: string;
    'display.web': string;
    'display.desktop': string;
    'display.both': string;
    'display.none': string;
    cornerLabel: string;
    'corner.top-left': string;
    'corner.top-right': string;
    'corner.bottom-left': string;
    'corner.bottom-right': string;
    marginX: string;
    marginY: string;
    save: string;
    reset: string;
    confirmReset: string;
    resetHint: string;
    configMeta: string;
    configMetaHint: string;
    defaultConfig: string;
    userConfig: string;
    animationDir: string;
    saved: string;
    loadError: string;
    invalid: string;
    busy: string;
    extraPetsHint: string;
    notifyToggle: string;
    notifyToggleHint: string;
    notifyGetPermission: string;
    notifyPermissionOk: string;
    notifyDenyUnsupported: string;
    notifyDenyBlocked: string;
    notifyDenyRejected: string;
    notifyDenyError: string;
    notifyGuide: string;
};
export declare const en: {
    nav: string;
    intro: string;
    petsLabel: string;
    add: string;
    importPack: string;
    importPackHint: string;
    importReading: string;
    importUploading: string;
    importSuccess: string;
    importInvalid: string;
    importTooLarge: string;
    closePet: string;
    showPet: string;
    filePetControl: string;
    remove: string;
    confirmRemove: string;
    confirmTitle: string;
    cancel: string;
    atLeastOne: string;
    emptyPets: string;
    sizeLabel: string;
    sizeHint: string;
    nameLabel: string;
    nameHint: string;
    balanceEnabled: string;
    balanceEnabledHint: string;
    whisperEnabled: string;
    whisperEnabledHint: string;
    displayLabel: string;
    displayHint: string;
    'display.web': string;
    'display.desktop': string;
    'display.both': string;
    'display.none': string;
    cornerLabel: string;
    'corner.top-left': string;
    'corner.top-right': string;
    'corner.bottom-left': string;
    'corner.bottom-right': string;
    marginX: string;
    marginY: string;
    save: string;
    reset: string;
    confirmReset: string;
    resetHint: string;
    configMeta: string;
    configMetaHint: string;
    defaultConfig: string;
    userConfig: string;
    animationDir: string;
    saved: string;
    loadError: string;
    invalid: string;
    busy: string;
    extraPetsHint: string;
    notifyToggle: string;
    notifyToggleHint: string;
    notifyGetPermission: string;
    notifyPermissionOk: string;
    notifyDenyUnsupported: string;
    notifyDenyBlocked: string;
    notifyDenyRejected: string;
    notifyDenyError: string;
    notifyGuide: string;
};
/**
 * 制造「桌宠配置」设置页组件（工厂函数）。
 *
 * 为什么是工厂而非直接定义组件：client 半侧是 __ModuleLoader__ 单文件形态，
 * react 能力不能顶层 import，只能由 DSH 的 require('react') 在运行时注入，
 * 因此把组件依赖作为参数传入，在工厂内制造出可用的组件后再注册进设置页插槽。
 *
 * @param rt        运行时注入的依赖集合
 * @param rt.h      react/jsx-runtime 的 jsx 函数（即 factory 里的 `h`）——
 *                  用于手写 React 元素，如 `h('button', { onClick, children: '保存' })`
 * @param rt.useState react 的 useState hook——管理页面内可变状态
 *                  （宠物列表 / 选中项 / 忙碌 / 保存消息），值变化时自动重渲染
 * @param rt.t      locale 绑定到本插件的翻译函数（ctx.locale.bind(NS)）——
 *                  取中英文文案，如 `t('nav')` → '桌宠配置' / 'Pet Config'
 * @returns PetConfigSection 组件：即整个「桌宠配置」设置页
 *          （props 仅有 close，由设置页外壳提供，本页当前未使用）
 */
export declare function makePetConfigSection(rt: {
    h: typeof jsx;
    useState: <T>(init: T) => [T, Dispatch<SetStateAction<T>>];
    useEffect: (effect: ReactNS.EffectCallback, deps?: ReactNS.DependencyList) => void;
    t: (key: string) => string;
}): FunctionComponent<{
    close?: () => void;
}>;
