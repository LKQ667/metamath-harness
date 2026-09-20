import type { Animations, Category } from './types';
/** 叶子：可点击的菜单项 */
export interface MenuLeaf {
    label: string;
    /** 播放的动画名（点播动作）；action 优先于 anim */
    anim?: string;
    /** 自定义动作：open-site=打开网站 / show-balance=查看余额；whisper=立即碎碎念一句；
     * chat=打开对话弹窗；home=回到初始位置。手动触发均不受 whisperEnabled 影响（该字段只关自动周期轮询） */
    action?: 'open-site' | 'show-balance' | 'whisper' | 'chat' | 'home';
}
/** 分支：带子菜单的项 */
export interface MenuBranch {
    label: string;
    children: MenuNode[];
}
export type MenuNode = MenuLeaf | MenuBranch;
/**
 * 由合并后的 animations 配置推导菜单树 —— 输出 [{ 动作 → [ 分类 → [ 具体动画 ] ] }]：
 * 一级只有一个「动作」分支；二级 = 分类（待机/转向/拖拽/点击回应/移动 + config 随机动作
 * 分类 + 事件档位）；三级 = 具体动画名。空池/空分类自动省略。
 */
export declare function buildMenuTree(animations: Animations): MenuNode[];
/** 该动画是否属于 noMirror 分类（文字类）：朝右（镜像）时点播前强制朝左，避免文字镜像 */
export declare function isNoMirrorAnimation(categories: Category[], anim: string): boolean;
/** 菜单样式 —— 两端注入同一份（浏览器并入 plugin css；桌面入窗口 head）。
 *  每一级面板是独立的绝对定位盒子（.dsh-pet-menu-column），位置由 JS 内联写入；
 *  面板与面板之间互不嵌套，各自独立滚动。 */
export declare const MENU_CSS: string;
/** mountContextMenu 返回值 */
export interface ContextMenuMount {
    /** 已挂载的根元素（document.body 下） */
    el: HTMLElement;
    /** 关闭并清理（幂等） */
    close: () => void;
}
/**
 * 挂载一个系统风格右键菜单（级联子菜单）到 document.body。
 * 位置为视口坐标（桌面=窗口视口，浏览器=页面视口）——两端一致。
 *
 * 结构：根容器（fixed，零尺寸）下平级挂**每一级独立面板**，绝无嵌套；
 * 面板按触发项屏幕位置贴边定位（右/下边缘自动翻转夹取）。
 * 级联：悬停分支切换/展开子面板；指针整体离开菜单树（root mouseleave）才关闭整棵菜单；
 * 点击项回调后自动关闭、点击菜单外或按 Esc 关闭；超高列表面板内独立滚动。
 */
export declare function mountContextMenu(opts: {
    tree: MenuNode[];
    x: number;
    y: number;
    onAction: (leaf: MenuLeaf) => void;
    /** 菜单被关闭（点项/点外/Esc）后的通知：挂载方据此复位自身状态（如桌面可交互标记） */
    onClose?: () => void;
}): ContextMenuMount;
