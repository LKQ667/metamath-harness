/**
 * 桌宠配置管理设置页（settings.section 插槽，id: pet-config）
 *
 * - 多开：管理多个桌宠，每个宠物独立 id/name/size/位置（corner + marginX/Y）
 * - 数据流：设置页持有「main 条目宠物列表」→ 保存时全量 PUT /dsh-pet-7340/config
 *   （写用户层 main-config.json = 可编辑层，文件宠物永不回写）
 * - 数据入口：配置由 host readAllConfig 合并为**成品**（GET /dsh-pet-7340/config），
 *   设置页只读 main 条目（可编辑）+ 统计文件宠物条数，不做任何校验
 * - 即时生效：保存/恢复默认后调用 petBridge.sync 通知容器重新渲染，无需刷新页面
 *
 * 样式对齐官方设置页：max-width 720px、全走 --dsw-alias-* 语义 token（主题跟随）。
 */
import { PET_DISPLAYS } from '../shared/config';
import { NOTIFY_ICONS, reloadNotifications, requestNotificationPermission } from './notify';
import type { Corner, Pet, PetDisplay } from '../shared/types';
import type { ChangeEvent, CSSProperties, Dispatch, FunctionComponent, SetStateAction } from 'react';
import type * as ReactNS from 'react';
import type { jsx } from 'react/jsx-runtime';

/** 容器与设置页共享的桥（同一 bundle 单例）：
 * current=最新完整宠物列表（成品拍平，默认空）；sync=容器注册的重渲染回调（未注册时为无操作函数）；
 * template=main 条目的宠物[0]（「添加宠物」用它作为默认配置） */
export const petBridge: {
  current: Pet[];
  sync: (pets: Pet[]) => void;
  template: Pet | undefined;
} = {
  current: [],
  sync: () => {},
  template: undefined,
};

/** 字典命名空间 */
export const NS = 'pet.config';

export const zh = {
  nav: '桌宠配置',
  intro: '管理多个桌宠：每个宠物可独立设置大小与位置（保存后即时生效）。',
  petsLabel: '宠物列表',
  add: '添加宠物',
  importPack: '导入宠物包',
  importPackHint: '选择包含 <名称>-config.json 与 <名称>-animation/*.webm 的完整文件夹。',
  importReading: '正在读取宠物包…',
  importUploading: '正在上传宠物包…',
  importSuccess: '宠物包“{name}”导入成功，正在刷新…',
  importInvalid: '请选择完整宠物包文件夹：根目录一个配置文件，以及同名前缀动画目录中的 WebM。',
  importTooLarge: '宠物包原始文件总大小不得超过 192 MiB。',
  closePet: '关闭宠物',
  showPet: '显示宠物',
  filePetControl: '文件宠物由独立配置维护；可在这里快速关闭或重新显示。',
  remove: '删除',
  confirmRemove: '确定删除宠物「{id}」吗？',
  confirmTitle: '确认操作',
  cancel: '取消',
  atLeastOne: '至少保留一个宠物。',
  emptyPets: '暂无宠物，点击「添加宠物」创建。',
  sizeLabel: '大小（宽度 px）',
  sizeHint: '高度自动 = 宽度 × 9/16。',
  nameLabel: '名字',
  nameHint: '显示名：鼠标悬浮宠物时弹出，也会加进 AI 人设（你的名字是 X）。可重复，留空按宠物 id 处理。',
  balanceEnabled: '余额功能',
  balanceEnabledHint: '启用后该宠物触发余额动画并显示余额气泡。',
  whisperEnabled: '碎碎念',
  whisperEnabledHint: '启用后该宠物按周期用 AI 生成一句话并播碎碎念动画（人设与周期在配置文件顶层）。',
  displayLabel: '显示位置',
  displayHint: 'web=仅浏览器 / desktop=仅桌面 / both=两者都显示 / none=都不显示',
  'display.web': '仅浏览器',
  'display.desktop': '仅桌面',
  'display.both': '两者都显示',
  'display.none': '都不显示',
  cornerLabel: '位置',
  'corner.top-left': '左上角',
  'corner.top-right': '右上角',
  'corner.bottom-left': '左下角',
  'corner.bottom-right': '右下角',
  marginX: '水平偏移',
  marginY: '垂直偏移',
  save: '保存',
  reset: '恢复默认',
  confirmReset: '确定恢复默认吗？将删除整个用户配置（含自定义的动画池与播放权重）。',
  resetHint: '「重置」会删除整个用户配置（含自定义的动画池与播放权重），不只是宠物列表。',
  configMeta: '高级配置（文件）',
  configMetaHint: '用户配置可覆盖宠物列表 / 动画池 / 播放权重，修改后刷新或重启生效；默认配置为完整参考。',
  defaultConfig: '默认配置（只读，完整参考）',
  userConfig: '用户配置（自定义覆盖）',
  animationDir: '动画素材目录（可自定义/扩充动画）',
  saved: '已保存，桌宠即时生效。',
  loadError: '加载配置失败',
  invalid: '请检查输入：大小需为正数，边距可为任意数字。',
  busy: '保存中…',
  extraPetsHint: '另 {n} 只文件宠物由 pet/ 目录定义，并在列表中标记为“文件”；请通过对应配置文件维护。',
  notifyToggle: '系统通知',
  notifyToggleHint: '对话完成 / 生成失败 / 权限申请 / 用户选择，在窗口失焦时弹出系统级通知（桌面右下角）。',
  notifyGetPermission: '获取权限',
  notifyPermissionOk: '已获得通知权限，右下角出现测试通知。',
  notifyDenyUnsupported: '当前环境不支持系统通知（浏览器无 Notification API）。',
  notifyDenyBlocked: '通知权限已被浏览器标记为「阻止」。',
  notifyDenyRejected: '你在权限询问弹窗中选择了「阻止」。',
  notifyDenyError: '申请权限时出错',
  notifyGuide: '引导：点击地址栏左侧 🔒/ⓘ →「网站设置」→「通知」→ 改为「允许」，刷新页面后重试。',
};

export const en = {
  nav: 'Pet Config',
  intro: 'Manage multiple pets: each pet has its own size and position (applies instantly after saving).',
  petsLabel: 'Pets',
  add: 'Add pet',
  importPack: 'Import pet pack',
  importPackHint: 'Choose a complete folder containing <name>-config.json and <name>-animation/*.webm.',
  importReading: 'Reading pet pack…',
  importUploading: 'Uploading pet pack…',
  importSuccess: 'Imported pet pack "{name}". Refreshing…',
  importInvalid: 'Choose a complete pet pack folder with one root config and a matching WebM animation folder.',
  importTooLarge: 'Raw pet pack files must not exceed 192 MiB in total.',
  closePet: 'Hide pet',
  showPet: 'Show pet',
  filePetControl: 'This file-defined pet is managed by its own config; hide or show it here.',
  remove: 'Remove',
  confirmRemove: 'Delete pet "{id}"?',
  confirmTitle: 'Confirm action',
  cancel: 'Cancel',
  atLeastOne: 'Keep at least one pet.',
  emptyPets: 'No pets yet — click "Add pet" to create one.',
  sizeLabel: 'Size (width px)',
  sizeHint: 'Height is automatic = width × 9/16.',
  nameLabel: 'Name',
  nameHint:
    'Shown on hover and added to AI personas ("your name is X"). Duplicates allowed; empty falls back to the pet id.',
  balanceEnabled: 'Balance',
  balanceEnabledHint: 'When enabled, this pet plays balance animations and shows the balance bubble.',
  whisperEnabled: 'Whisper',
  whisperEnabledHint:
    'When enabled, this pet periodically generates a line via AI and plays the whisper animation (persona & interval live in the top-level config).',
  displayLabel: 'Display',
  displayHint: 'web = browser only / desktop = desktop only / both = both / none = neither',
  'display.web': 'Browser only',
  'display.desktop': 'Desktop only',
  'display.both': 'Both',
  'display.none': 'Neither',
  cornerLabel: 'Position',
  'corner.top-left': 'Top-left',
  'corner.top-right': 'Top-right',
  'corner.bottom-left': 'Bottom-left',
  'corner.bottom-right': 'Bottom-right',
  marginX: 'Horizontal offset',
  marginY: 'Vertical offset',
  save: 'Save',
  reset: 'Reset to default',
  confirmReset: 'Reset to default? This deletes the whole user config (including custom animation pools & weights).',
  resetHint:
    '"Reset" deletes the whole user config (including custom animation pools & weights), not just the pet list.',
  configMeta: 'Advanced (files)',
  configMetaHint:
    'User config may override pets / animation pools / weights — refresh or restart to apply. The default config is the complete reference.',
  defaultConfig: 'Default config (read-only, complete reference)',
  userConfig: 'User config (custom overrides)',
  animationDir: 'Animation assets dir (add/customize animations here)',
  saved: 'Saved — the pets updated instantly.',
  loadError: 'Failed to load config',
  invalid: 'Check your input: size must be positive; margins can be any number.',
  busy: 'Saving…',
  extraPetsHint:
    '{n} file-defined pet(s) from pet/ are marked “file” in this list and remain managed by their config files.',
  notifyToggle: 'System notifications',
  notifyToggleHint:
    'OS-level toasts (bottom-right of the desktop) for conversation completion, failures, permission requests, and questions — only while this window is unfocused.',
  notifyGetPermission: 'Get permission',
  notifyPermissionOk: 'Notification permission granted — a test notification was sent.',
  notifyDenyUnsupported: 'System notifications are not supported in this environment (no Notification API).',
  notifyDenyBlocked: 'Notification permission is blocked by the browser.',
  notifyDenyRejected: 'You chose "Block" in the permission prompt.',
  notifyDenyError: 'Failed to request permission',
  notifyGuide:
    'Guide: click the 🔒/ⓘ icon next to the address bar → Site settings → Notifications → set to "Allow", then refresh and retry.',
};

const MAX_IMPORT_BYTES = 192 * 1024 * 1024;
const PET_CONFIG_RE = /^(.+)-config\.(json|jsonc)$/;

/** 浏览器 File → base64；分块拼接避免对大 Uint8Array 使用超长函数参数。 */
async function fileToBase64(file: File): Promise<string> {
  const bytes = new Uint8Array(await file.arrayBuffer());
  const chunks: string[] = [];
  const chunkSize = 0x8000;
  for (let offset = 0; offset < bytes.length; offset += chunkSize) {
    chunks.push(String.fromCharCode(...bytes.subarray(offset, offset + chunkSize)));
  }
  return btoa(chunks.join(''));
}

function importRelativePath(file: File): string {
  return file.webkitRelativePath || file.name;
}

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
export function makePetConfigSection(rt: {
  h: typeof jsx;
  useState: <T>(init: T) => [T, Dispatch<SetStateAction<T>>];
  // 用 React 命名空间类型而非 typeof：type-only import 的 hook 无法进入声明导出（TS4078）
  useEffect: (effect: ReactNS.EffectCallback, deps?: ReactNS.DependencyList) => void;
  t: (key: string) => string;
}): FunctionComponent<{ close?: () => void }> {
  const { h, useState, useEffect, t } = rt;

  const CORNERS: Corner[] = ['top-left', 'top-right', 'bottom-left', 'bottom-right'];
  const cornerLabel = (c: Corner): string => t('corner.' + c);

  const inputStyle = {
    boxSizing: 'border-box',
    border: '1px solid var(--dsw-alias-border-l2)',
    borderRadius: '8px',
    background: 'var(--dsw-alias-bg-layer-1)',
    color: 'var(--dsw-alias-label-primary)',
    padding: '5px 10px',
    fontSize: '13px',
    minHeight: '28px',
    outline: 'none',
  } as CSSProperties;

  /** 生成一个未占用的宠物 id（pet-2、pet-3…） */
  const nextId = (list: Pet[]): string => {
    let n = 2;
    for (; ; n++) {
      const id = 'pet-' + n;
      if (!list.some((p) => p.id === id)) return id;
    }
  };

  return function PetConfigSection() {
    const initPets = petBridge.current.filter((p) => !p.extra);
    // 文件定义宠物（pet/ 目录）：显示在列表中供识别，但仍由各自配置文件维护。
    const extraPets = petBridge.current.filter((p) => p.extra);
    const extraCount = extraPets.length;
    const [pets, setPets] = useState<Pet[]>(initPets.map((p) => ({ ...p, position: { ...p.position } })));
    const [selId, setSelId] = useState<string>(initPets[0]?.id ?? '');
    const [busy, setBusy] = useState(false);
    const [msg, setMsg] = useState<{ kind: 'ok' | 'err' | ''; text: string }>({ kind: '', text: '' });
    const [importMsg, setImportMsg] = useState<{ kind: 'ok' | 'err' | ''; text: string }>({
      kind: '',
      text: '',
    });
    // 确认弹窗（仿官方弹窗：遮罩 + 居中卡片 + 双按钮）
    const [confirm, setConfirm] = useState<null | 'remove' | 'reset'>(null);
    // 配置文件地址（「高级配置」区块；读取失败仅缺省不显示，不影响表单）
    const [paths, setPaths] = useState<null | { user: string; default: string; animations: string }>(null);
    useEffect(() => {
      fetch('/dsh-pet-7340/config/meta')
        .then((r) => (r.ok ? r.json() : null))
        .then((p) => setPaths(p))
        .catch(() => console.warn('[dsh-pet] 读取配置文件路径失败'));
    }, []);

    const importPack = async (event: ChangeEvent<HTMLInputElement>) => {
      const input = event.target;
      const selected = Array.from(input.files ?? []);
      if (selected.length === 0) return;
      setBusy(true);
      setImportMsg({ kind: '', text: t('importReading') });
      try {
        const paths = selected.map(importRelativePath);
        const split = paths.map((path) => path.split('/'));
        const pickerRoot = split[0]?.[0];
        const relative = split.map((parts) =>
          pickerRoot && parts.length >= 2 && split.every((candidate) => candidate[0] === pickerRoot)
            ? parts.slice(1)
            : parts,
        );
        const configs = relative.filter((parts) => parts.length === 1 && PET_CONFIG_RE.test(parts[0]));
        if (configs.length !== 1) throw new Error(t('importInvalid'));
        const match = PET_CONFIG_RE.exec(configs[0][0]);
        const prefix = match?.[1] ?? '';
        const animationDir = prefix + '-animation';
        const validShape = relative.every(
          (parts) =>
            (parts.length === 1 && parts[0] === configs[0][0]) ||
            (parts.length === 2 && parts[0] === animationDir && parts[1].toLowerCase().endsWith('.webm')),
        );
        const animationCount = relative.filter(
          (parts) => parts.length === 2 && parts[0] === animationDir && parts[1].toLowerCase().endsWith('.webm'),
        ).length;
        if (!validShape || animationCount === 0) throw new Error(t('importInvalid'));
        const totalBytes = selected.reduce((sum, file) => sum + file.size, 0);
        if (totalBytes > MAX_IMPORT_BYTES) throw new Error(t('importTooLarge'));

        setImportMsg({ kind: '', text: t('importUploading') });
        const files = await Promise.all(
          selected.map(async (file) => ({ path: importRelativePath(file), data: await fileToBase64(file) })),
        );
        const response = await fetch('/dsh-pet-7340/pet-pack/import', {
          method: 'POST',
          headers: { 'content-type': 'application/json' },
          body: JSON.stringify({ files }),
        });
        const result = (await response.json().catch(() => null)) as { error?: string; prefix?: string } | null;
        if (!response.ok) throw new Error(result?.error || 'HTTP ' + response.status);
        setImportMsg({ kind: 'ok', text: t('importSuccess').replace('{name}', result?.prefix || prefix) });
        window.setTimeout(() => window.location.reload(), 800);
      } catch (error) {
        setImportMsg({ kind: 'err', text: error instanceof Error ? error.message : t('importInvalid') });
      } finally {
        input.value = '';
        setBusy(false);
      }
    };

    // 系统通知总开关（全局：读写用户级配置 main-config.json 的 notificationsEnabled；即时生效）
    const [notifyEnabled, setNotifyEnabled] = useState(true);
    // 权限申请按钮的反馈（就地显示在按钮旁，与全局保存反馈分离）
    const [permMsg, setPermMsg] = useState<{ kind: 'ok' | 'err' | ''; text: string }>({ kind: '', text: '' });
    useEffect(() => {
      let alive = true;
      // 成品聚合的 main 条目已带合并后的 notificationsEnabled（用户手写值优先）
      fetch('/dsh-pet-7340/config')
        .then((r) => (r.ok ? r.json() : null))
        .then((d) => {
          const v =
            d && d.main && typeof d.main.notificationsEnabled === 'boolean' ? d.main.notificationsEnabled : null;
          if (alive && v !== null) setNotifyEnabled(v);
        })
        .catch(() => {
          /* 成品拉取失败时保持默认（true） */
        });
      return () => {
        alive = false;
      };
    }, []);

    const toggleNotify = async (v: boolean) => {
      setBusy(true);
      setMsg({ kind: '', text: '' });
      try {
        // 开启时先借用户手势申请系统通知权限（无手势的自动申请可能被浏览器静默压制）
        if (v) await requestNotificationPermission();
        // 与保存同构：整包写用户级配置（pets + 开关），避免开关写入被 sanitize 拒绝
        const res = await fetch('/dsh-pet-7340/config', {
          method: 'PUT',
          headers: { 'content-type': 'application/json' },
          body: JSON.stringify({ pets: pets, notificationsEnabled: v }),
        });
        if (!res.ok) throw new Error('HTTP ' + res.status);
        setNotifyEnabled(v);
        petBridge.current = pets;
        petBridge.sync(pets);
        void reloadNotifications(); // 引擎重读开关：即时生效，无需刷新页面
        setMsg({ kind: 'ok', text: t('saved') });
      } catch {
        setMsg({ kind: 'err', text: t('loadError') });
      } finally {
        setBusy(false);
      }
    };

    const grantNotifyPermission = async () => {
      setPermMsg({ kind: '', text: '' });
      const r = await requestNotificationPermission();
      if (!r.ok) {
        // 红字：失败理由 + 引导（unsupported 无引导，改环境才有意义）
        const reason =
          r.reason === 'unsupported'
            ? t('notifyDenyUnsupported')
            : r.reason === 'denied'
              ? t('notifyDenyBlocked')
              : r.reason === 'rejected'
                ? t('notifyDenyRejected')
                : t('notifyDenyError') + (r.message ? '：' + r.message : '');
        setPermMsg({ kind: 'err', text: reason + (r.reason === 'unsupported' ? '' : ' ' + t('notifyGuide')) });
        return;
      }
      try {
        // 成功即发一条测试通知验证链路（绕过聚焦门，直接确认）
        new Notification('测试通知', { body: '【dsh-pet】系统通知已就绪。', icon: NOTIFY_ICONS.test });
      } catch {
        /* 个别环境构造失败：仍按已授权提示 */
      }
      setPermMsg({ kind: 'ok', text: t('notifyPermissionOk') });
    };

    // 当前选中的宠物对象（表单数据源）；selId 由 add/remove/reset 同步维护，列表非空时恒有效
    const cur = pets.find((p) => p.id === selId) ?? null;
    const selectedExtra = extraPets.find((p) => p.id === selId) ?? null;

    const togglePetVisibility = async (pet: Pet, visible: boolean) => {
      setBusy(true);
      setMsg({ kind: '', text: '' });
      try {
        if (pet.extra) {
          const response = await fetch('/dsh-pet-7340/pet/visibility', {
            method: 'POST',
            headers: { 'content-type': 'application/json' },
            body: JSON.stringify({ petId: pet.id, visible }),
          });
          if (!response.ok) throw new Error('HTTP ' + response.status);
          window.location.reload();
          return;
        }
        const next: Pet[] = pets.map((candidate) =>
          candidate.id === pet.id ? { ...candidate, display: visible ? 'web' : 'none' } : candidate,
        );
        const response = await fetch('/dsh-pet-7340/config', {
          method: 'PUT',
          headers: { 'content-type': 'application/json' },
          body: JSON.stringify({ pets: next, notificationsEnabled: notifyEnabled }),
        });
        if (!response.ok) throw new Error('HTTP ' + response.status);
        setPets(next);
        petBridge.current = next;
        petBridge.sync(next);
        setMsg({ kind: 'ok', text: t('saved') });
      } catch {
        setMsg({ kind: 'err', text: t('loadError') });
      } finally {
        setBusy(false);
      }
    };

    // 更新选中的宠物：size 走顶层；position 子字段整体替换
    const updateSel = (patch: Partial<Omit<Pet, 'position'>> & { position?: Partial<Pet['position']> }) =>
      setPets((list) =>
        list.map((p) => {
          if (p.id !== selId) return p;
          const { position: posPatch, ...rest } = patch;
          return { ...p, ...rest, position: posPatch ? { ...p.position, ...posPatch } : p.position };
        }),
      );

    const validated = (): boolean => {
      for (const p of pets) {
        if (
          !Number.isFinite(p.size) ||
          p.size <= 0 ||
          !Number.isFinite(p.position.marginX) ||
          !Number.isFinite(p.position.marginY)
        ) {
          setMsg({ kind: 'err', text: t('invalid') });
          return false;
        }
      }
      return true;
    };

    const save = async () => {
      const isOk = validated();
      if (!isOk) return;
      setBusy(true);
      setMsg({ kind: '', text: '' });
      try {
        // 通知总开关随保存一起写：UI 状态初始来自成品 main 条目（即保留用户手写值，不会静默覆盖）
        const body: Record<string, unknown> = { pets: pets, notificationsEnabled: notifyEnabled };
        const res = await fetch('/dsh-pet-7340/config', {
          method: 'PUT',
          headers: { 'content-type': 'application/json' },
          body: JSON.stringify(body),
        });
        if (!res.ok) throw new Error('HTTP ' + res.status);
        petBridge.current = pets;
        petBridge.sync(pets);
        setMsg({ kind: 'ok', text: t('saved') });
      } catch {
        setMsg({ kind: 'err', text: t('loadError') });
      } finally {
        setBusy(false);
      }
    };

    const reset = () => setConfirm('reset');

    const doReset = async () => {
      setBusy(true);
      setMsg({ kind: '', text: '' });
      try {
        // 删除用户层 → 重新拉成品（此时 main 条目 = 内置默认宠物列表）
        await fetch('/dsh-pet-7340/config', { method: 'DELETE' });
        const merged = (await (await fetch('/dsh-pet-7340/config')).json()) as { main?: { pets?: Pet[] } } | null;
        const defs = (merged?.main?.pets ?? []) as Pet[];
        setPets(defs.map((p) => ({ ...p, position: { ...p.position } })));
        setSelId(defs[0]?.id ?? '');
        petBridge.current = defs;
        petBridge.sync(defs);
        setMsg({ kind: 'ok', text: t('saved') });
      } catch {
        setMsg({ kind: 'err', text: t('loadError') });
      } finally {
        setBusy(false);
      }
    };

    const addPet = () => {
      const tpl = petBridge.template;
      if (!tpl) return;
      const id = nextId(pets);
      setPets((list) => [
        ...list,
        {
          id,
          // 新宠物默认名字 = 自己的新 id（与「缺失 name 按 id 处理」同一语义，避免继承模板名字造成同名）
          name: id,
          size: tpl.size,
          balanceEnabled: tpl.balanceEnabled,
          whisperEnabled: tpl.whisperEnabled,
          display: tpl.display,
          position: { ...tpl.position },
        },
      ]);
      setSelId(id);
    };

    const removeSel = () => {
      if (pets.length <= 1) {
        setMsg({ kind: 'err', text: t('atLeastOne') });
        return;
      }
      setConfirm('remove');
    };

    const doRemove = () => {
      const list = pets.filter((p) => p.id !== selId);
      setPets(list);
      setSelId(list[0].id);
    };

    const field = (key: 'size' | 'marginX' | 'marginY', value: number, setter: (v: number) => void, width: string) =>
      h('input', {
        type: 'number',
        step: key === 'size' ? '10' : '1',
        min: key === 'size' ? '120' : '',
        value: String(value),
        disabled: busy,
        onChange: (e: ChangeEvent<HTMLInputElement>) => setter(Number(e.target.value)),
        style: { width, ...inputStyle },
      });

    return h('section', {
      style: {
        maxWidth: '720px',
        color: 'var(--dsw-alias-label-primary)',
        display: 'flex',
        flexDirection: 'column',
        gap: '6px',
      },
      children: [
        h('h2', {
          style: { margin: 0, fontSize: '16px', fontWeight: 500, lineHeight: '24px' },
          children: t('nav'),
        }),
        h('p', {
          style: {
            margin: 0,
            fontSize: '14px',
            color: 'var(--dsw-alias-label-tertiary)',
            lineHeight: '22px',
          },
          children: t('intro'),
        }),
        // 额外宠物提示（文件定义，不在此编辑列表）
        extraCount > 0
          ? h('p', {
              style: {
                margin: 0,
                fontSize: '12px',
                color: 'var(--dsw-alias-label-tertiary)',
                lineHeight: '18px',
              },
              children: t('extraPetsHint').replace('{n}', String(extraCount)),
            })
          : null,

        // 宠物列表 + 添加
        h('div', {
          style: { display: 'flex', gap: '8px', flexWrap: 'wrap', alignItems: 'center', marginTop: '4px' },
          children: [
            h('span', {
              style: { fontSize: '12px', color: 'var(--dsw-alias-label-secondary)' },
              children: t('petsLabel'),
            }),
            ...pets.map((p) =>
              h('button', {
                key: p.id,
                type: 'button',
                onClick: () => setSelId(p.id),
                style: {
                  border:
                    '1px solid ' +
                    (p.id === selId ? 'var(--dsw-alias-state-business-primary)' : 'var(--dsw-alias-border-l2)'),
                  background: p.id === selId ? 'var(--dsw-alias-interactive-bg-active)' : 'transparent',
                  color: 'var(--dsw-alias-label-primary)',
                  borderRadius: '8px',
                  padding: '4px 12px',
                  fontSize: '13px',
                  cursor: 'pointer',
                },
                children: (p.name || p.id) + ' (' + p.size + 'px)',
              }),
            ),
            ...extraPets.map((p) =>
              h('button', {
                key: 'extra-' + p.id,
                type: 'button',
                onClick: () => setSelId(p.id),
                title: t('extraPetsHint').replace('{n}', String(extraCount)),
                style: {
                  border:
                    '1px solid ' +
                    (p.id === selId ? 'var(--dsw-alias-state-business-primary)' : 'var(--dsw-alias-border-l2)'),
                  background: p.id === selId ? 'var(--dsw-alias-interactive-bg-active)' : 'var(--dsw-alias-bg-layer-1)',
                  color: 'var(--dsw-alias-label-primary)',
                  borderRadius: '8px',
                  padding: '4px 12px',
                  fontSize: '13px',
                  cursor: 'pointer',
                },
                children: (p.name || p.id) + ' (' + p.size + 'px · 文件)',
              }),
            ),
            h('button', {
              type: 'button',
              onClick: addPet,
              disabled: busy,
              style: {
                border: '1px dashed var(--dsw-alias-border-l2)',
                background: 'transparent',
                color: 'var(--dsw-alias-label-secondary)',
                borderRadius: '8px',
                padding: '4px 12px',
                fontSize: '13px',
                cursor: 'pointer',
              },
              children: '+ ' + t('add'),
            }),
            h('label', {
              title: t('importPackHint'),
              style: {
                border: '1px dashed var(--dsw-alias-border-l2)',
                background: 'transparent',
                color: 'var(--dsw-alias-label-secondary)',
                borderRadius: '8px',
                padding: '4px 12px',
                fontSize: '13px',
                cursor: busy ? 'not-allowed' : 'pointer',
                opacity: busy ? 0.5 : 1,
              },
              children: [
                '↑ ' + t('importPack'),
                h('input', {
                  type: 'file',
                  multiple: true,
                  // Chromium/Electron 目录选择；保留 multiple 供宿主将目录内文件一次性交给页面。
                  webkitdirectory: '',
                  directory: '',
                  disabled: busy,
                  onChange: (event: ChangeEvent<HTMLInputElement>) => void importPack(event),
                  style: { display: 'none' },
                }),
              ],
            }),
          ],
        }),

        h('div', {
          style: {
            minHeight: '18px',
            fontSize: '11px',
            lineHeight: '18px',
            color:
              importMsg.kind === 'err'
                ? 'var(--dsw-alias-state-error-primary)'
                : importMsg.kind === 'ok'
                  ? 'var(--dsw-alias-state-ok-primary)'
                  : 'var(--dsw-alias-label-tertiary)',
          },
          children: importMsg.text || t('importPackHint'),
        }),

        selectedExtra
          ? h('div', {
              style: {
                display: 'flex',
                gap: '12px',
                alignItems: 'center',
                marginTop: '8px',
                padding: '12px 14px',
                border: '1px solid var(--dsw-alias-border-l2)',
                borderRadius: '12px',
              },
              children: [
                h('span', {
                  style: { flex: 1, fontSize: '12px', color: 'var(--dsw-alias-label-secondary)' },
                  children: t('filePetControl'),
                }),
                h('button', {
                  type: 'button',
                  disabled: busy,
                  onClick: () => void togglePetVisibility(selectedExtra, selectedExtra.display === 'none'),
                  style: {
                    border: '1px solid var(--dsw-alias-border-l2)',
                    background: 'transparent',
                    color: 'var(--dsw-alias-label-primary)',
                    borderRadius: '8px',
                    padding: '5px 12px',
                    cursor: busy ? 'not-allowed' : 'pointer',
                  },
                  children: t(selectedExtra.display === 'none' ? 'showPet' : 'closePet'),
                }),
              ],
            })
          : null,

        // 选中宠物表单
        cur
          ? h('div', {
              style: {
                display: 'flex',
                gap: '16px',
                flexWrap: 'wrap',
                marginTop: '8px',
                padding: '12px 14px',
                border: '1px solid var(--dsw-alias-border-l2)',
                borderRadius: '12px',
              },
              children: [
                h('label', {
                  style: {
                    display: 'flex',
                    flexDirection: 'column',
                    gap: '4px',
                    fontSize: '12px',
                    color: 'var(--dsw-alias-label-secondary)',
                  },
                  children: [
                    t('nameLabel'),
                    h('input', {
                      type: 'text',
                      value: String(cur.name ?? ''),
                      disabled: busy,
                      maxLength: 50,
                      onChange: (e: ChangeEvent<HTMLInputElement>) => updateSel({ name: e.target.value }),
                      style: { width: '200px', ...inputStyle },
                    }),
                    h('span', {
                      style: { fontSize: '11px', color: 'var(--dsw-alias-label-tertiary)' },
                      children: t('nameHint'),
                    }),
                  ],
                }),
                h('label', {
                  style: {
                    display: 'flex',
                    flexDirection: 'column',
                    gap: '4px',
                    fontSize: '12px',
                    color: 'var(--dsw-alias-label-secondary)',
                  },
                  children: [
                    t('sizeLabel'),
                    field('size', cur.size, (v) => updateSel({ size: v }), '150px'),
                    h('span', {
                      style: { fontSize: '11px', color: 'var(--dsw-alias-label-tertiary)' },
                      children: t('sizeHint'),
                    }),
                  ],
                }),
                h('label', {
                  style: {
                    display: 'flex',
                    flexDirection: 'column',
                    gap: '4px',
                    fontSize: '12px',
                    color: 'var(--dsw-alias-label-secondary)',
                  },
                  children: [
                    t('cornerLabel'),
                    h('select', {
                      value: cur.position.corner,
                      disabled: busy,
                      onChange: (e: ChangeEvent<HTMLSelectElement>) =>
                        updateSel({ position: { corner: e.target.value as Corner } }),
                      style: { width: '160px', ...inputStyle },
                      children: CORNERS.map((c) =>
                        h('option', {
                          key: c,
                          value: c,
                          children: cornerLabel(c),
                        }),
                      ),
                    }),
                  ],
                }),
                h('label', {
                  style: {
                    display: 'flex',
                    flexDirection: 'column',
                    gap: '4px',
                    fontSize: '12px',
                    color: 'var(--dsw-alias-label-secondary)',
                  },
                  children: [
                    t('marginX'),
                    field('marginX', cur.position.marginX, (v) => updateSel({ position: { marginX: v } }), '120px'),
                  ],
                }),
                h('label', {
                  style: {
                    display: 'flex',
                    flexDirection: 'column',
                    gap: '4px',
                    fontSize: '12px',
                    color: 'var(--dsw-alias-label-secondary)',
                  },
                  children: [
                    t('marginY'),
                    field('marginY', cur.position.marginY, (v) => updateSel({ position: { marginY: v } }), '120px'),
                  ],
                }),
                h('label', {
                  style: {
                    display: 'flex',
                    flexDirection: 'column',
                    gap: '4px',
                    fontSize: '12px',
                    color: 'var(--dsw-alias-label-secondary)',
                  },
                  children: [
                    t('balanceEnabled'),
                    h('input', {
                      type: 'checkbox',
                      checked: !!cur.balanceEnabled,
                      disabled: busy,
                      onChange: (e: ChangeEvent<HTMLInputElement>) => updateSel({ balanceEnabled: e.target.checked }),
                      style: { width: '16px', height: '16px', accentColor: 'var(--dsw-alias-state-business-primary)' },
                    }),
                    h('span', {
                      style: { fontSize: '11px', color: 'var(--dsw-alias-label-tertiary)' },
                      children: t('balanceEnabledHint'),
                    }),
                  ],
                }),
                h('label', {
                  style: {
                    display: 'flex',
                    flexDirection: 'column',
                    gap: '4px',
                    fontSize: '12px',
                    color: 'var(--dsw-alias-label-secondary)',
                  },
                  children: [
                    t('whisperEnabled'),
                    h('input', {
                      type: 'checkbox',
                      checked: !!cur.whisperEnabled,
                      disabled: busy,
                      onChange: (e: ChangeEvent<HTMLInputElement>) => updateSel({ whisperEnabled: e.target.checked }),
                      style: { width: '16px', height: '16px', accentColor: 'var(--dsw-alias-state-business-primary)' },
                    }),
                    h('span', {
                      style: { fontSize: '11px', color: 'var(--dsw-alias-label-tertiary)' },
                      children: t('whisperEnabledHint'),
                    }),
                  ],
                }),
                h('label', {
                  style: {
                    display: 'flex',
                    flexDirection: 'column',
                    gap: '4px',
                    fontSize: '12px',
                    color: 'var(--dsw-alias-label-secondary)',
                  },
                  children: [
                    t('displayLabel'),
                    h('select', {
                      value: cur.display,
                      disabled: busy,
                      onChange: (e: ChangeEvent<HTMLSelectElement>) =>
                        updateSel({ display: e.target.value as PetDisplay }),
                      style: { width: '160px', ...inputStyle },
                      children: PET_DISPLAYS.map((d) =>
                        h('option', {
                          key: d,
                          value: d,
                          children: t('display.' + d),
                        }),
                      ),
                    }),
                    h('span', {
                      style: { fontSize: '11px', color: 'var(--dsw-alias-label-tertiary)' },
                      children: t('displayHint'),
                    }),
                  ],
                }),
                h('button', {
                  type: 'button',
                  onClick: () => void togglePetVisibility(cur, cur.display === 'none'),
                  disabled: busy,
                  style: {
                    alignSelf: 'flex-end',
                    border: '1px solid var(--dsw-alias-border-l2)',
                    background: 'transparent',
                    color: 'var(--dsw-alias-label-primary)',
                    borderRadius: '8px',
                    padding: '4px 12px',
                    fontSize: '12px',
                    cursor: busy ? 'not-allowed' : 'pointer',
                  },
                  children: t(cur.display === 'none' ? 'showPet' : 'closePet'),
                }),
                h('button', {
                  type: 'button',
                  onClick: removeSel,
                  disabled: busy,
                  title: t('remove'),
                  style: {
                    alignSelf: 'flex-end',
                    border: '1px solid var(--dsw-alias-state-error-secondary)',
                    background: 'transparent',
                    color: 'var(--dsw-alias-state-error-primary)',
                    borderRadius: '8px',
                    padding: '4px 12px',
                    fontSize: '12px',
                    cursor: 'pointer',
                  },
                  children: t('remove'),
                }),
              ],
            })
          : selectedExtra
            ? null
            : h('p', {
                style: { margin: 0, fontSize: '13px', color: 'var(--dsw-alias-label-tertiary)' },
                children: t('emptyPets'),
              }),

        // 系统通知总开关（全局，写入用户级配置；即时生效，不归属单个宠物）
        h('label', {
          style: {
            display: 'flex',
            gap: '8px',
            alignItems: 'center',
            marginTop: '8px',
            fontSize: '13px',
            color: 'var(--dsw-alias-label-primary)',
          },
          children: [
            h('input', {
              type: 'checkbox',
              checked: notifyEnabled,
              disabled: busy,
              onChange: (e: ChangeEvent<HTMLInputElement>) => void toggleNotify(e.target.checked),
              style: { width: '16px', height: '16px', accentColor: 'var(--dsw-alias-state-business-primary)' },
            }),
            h('span', { children: t('notifyToggle') }),
            h('span', {
              style: { fontSize: '11px', color: 'var(--dsw-alias-label-tertiary)' },
              children: t('notifyToggleHint'),
            }),
          ],
        }),

        // 权限获取按钮 + 反馈（独立一行，样式对齐设置页现有按钮）
        h('div', {
          style: { display: 'flex', gap: '8px', alignItems: 'center', marginTop: '4px' },
          children: [
            h('button', {
              type: 'button',
              onClick: () => void grantNotifyPermission(),
              style: {
                border: '1px solid var(--dsw-alias-border-l2)',
                background: 'transparent',
                color: 'var(--dsw-alias-label-primary)',
                borderRadius: '8px',
                padding: '4px 14px',
                fontSize: '12px',
                cursor: 'pointer',
              },
              children: t('notifyGetPermission'),
            }),
            permMsg.text
              ? h('span', {
                  style: {
                    fontSize: '12px',
                    color:
                      permMsg.kind === 'err'
                        ? 'var(--dsw-alias-state-error-primary)'
                        : 'var(--dsw-alias-state-ok-primary)',
                    lineHeight: '18px',
                  },
                  children: permMsg.text,
                })
              : null,
          ],
        }),

        // 操作区
        h('div', {
          style: { display: 'flex', gap: '8px', alignItems: 'center', marginTop: '4px' },
          children: [
            h('button', {
              type: 'button',
              disabled: busy,
              onClick: save,
              style: {
                border: '1px solid var(--dsw-alias-button-info-fill)',
                background: 'var(--dsw-alias-button-info-fill)',
                color: '#fff',
                borderRadius: '8px',
                padding: '4px 14px',
                fontSize: '12px',
                cursor: 'pointer',
                opacity: busy ? 0.5 : 1,
              },
              children: t('save'),
            }),
            h('button', {
              type: 'button',
              disabled: busy,
              onClick: reset,
              style: {
                border: '1px solid var(--dsw-alias-border-l2)',
                background: 'transparent',
                color: 'var(--dsw-alias-label-primary)',
                borderRadius: '8px',
                padding: '4px 14px',
                fontSize: '12px',
                cursor: 'pointer',
                opacity: busy ? 0.5 : 1,
              },
              children: t('reset'),
            }),
            msg.text
              ? h('span', {
                  style: {
                    fontSize: '12px',
                    color:
                      msg.kind === 'err' ? 'var(--dsw-alias-state-error-primary)' : 'var(--dsw-alias-state-ok-primary)',
                    marginLeft: '4px',
                  },
                  children: msg.text,
                })
              : null,
          ],
        }),

        // 重置的副作用提示（DELETE 会清掉整个用户配置，含高级自定义）
        h('p', {
          style: { margin: 0, fontSize: '11px', color: 'var(--dsw-alias-label-tertiary)', lineHeight: '16px' },
          children: t('resetHint'),
        }),

        // 高级配置（文件地址）：供高级用户直接编辑配置文件自定义
        paths
          ? h('div', {
              style: {
                marginTop: '12px',
                padding: '10px 14px',
                border: '1px solid var(--dsw-alias-border-l2)',
                borderRadius: '12px',
                display: 'flex',
                flexDirection: 'column',
                gap: '6px',
                fontSize: '12px',
                color: 'var(--dsw-alias-label-secondary)',
              },
              children: [
                h('div', {
                  style: { fontSize: '12px', color: 'var(--dsw-alias-label-primary)', fontWeight: 500 },
                  children: t('configMeta'),
                }),
                h('div', { style: { fontSize: '12px', lineHeight: '20px' }, children: t('configMetaHint') }),
                h('div', {
                  style: { fontSize: '12px', lineHeight: '18px', wordBreak: 'break-all' },
                  children: t('defaultConfig') + '：' + paths.default,
                }),
                h('div', {
                  style: { fontSize: '12px', lineHeight: '18px', wordBreak: 'break-all' },
                  children: t('userConfig') + '：' + paths.user,
                }),
                h('div', {
                  style: { fontSize: '12px', lineHeight: '18px', wordBreak: 'break-all' },
                  children: t('animationDir') + '：' + paths.animations,
                }),
              ],
            })
          : null,

        // 确认弹窗（仿官方弹窗视觉：遮罩 + 居中卡片 + 双按钮）
        confirm
          ? h('div', {
              style: {
                position: 'fixed',
                inset: 0,
                zIndex: 2147483647,
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                background: 'rgba(0, 0, 0, 0.45)',
              },
              onClick: () => setConfirm(null),
              children: h('div', {
                style: {
                  width: '340px',
                  maxWidth: 'calc(100vw - 40px)',
                  background: 'var(--dsw-alias-bg-layer-1)',
                  border: '1px solid var(--dsw-alias-border-l2)',
                  borderRadius: '12px',
                  padding: '16px 18px',
                  boxShadow: '0 8px 30px rgba(0, 0, 0, 0.35)',
                  display: 'flex',
                  flexDirection: 'column',
                  gap: '12px',
                },
                onClick: (e: ReactNS.MouseEvent<HTMLDivElement>) => e.stopPropagation(),
                children: [
                  h('div', {
                    style: { fontSize: '14px', fontWeight: 500, color: 'var(--dsw-alias-label-primary)' },
                    children: t('confirmTitle'),
                  }),
                  h('div', {
                    style: { fontSize: '13px', lineHeight: '20px', color: 'var(--dsw-alias-label-secondary)' },
                    children: confirm === 'remove' ? t('confirmRemove').replace('{id}', selId) : t('confirmReset'),
                  }),
                  h('div', {
                    style: { display: 'flex', gap: '8px', justifyContent: 'flex-end' },
                    children: [
                      h('button', {
                        type: 'button',
                        onClick: () => setConfirm(null),
                        style: {
                          border: '1px solid var(--dsw-alias-border-l2)',
                          background: 'transparent',
                          color: 'var(--dsw-alias-label-primary)',
                          borderRadius: '8px',
                          padding: '4px 14px',
                          fontSize: '12px',
                          cursor: 'pointer',
                        },
                        children: t('cancel'),
                      }),
                      h('button', {
                        type: 'button',
                        onClick: () => {
                          const k = confirm;
                          setConfirm(null);
                          if (k === 'remove') doRemove();
                          else void doReset();
                        },
                        style:
                          confirm === 'remove'
                            ? {
                                border: '1px solid var(--dsw-alias-state-error-secondary)',
                                background: 'transparent',
                                color: 'var(--dsw-alias-state-error-primary)',
                                borderRadius: '8px',
                                padding: '4px 14px',
                                fontSize: '12px',
                                cursor: 'pointer',
                              }
                            : {
                                border: '1px solid var(--dsw-alias-button-info-fill)',
                                background: 'var(--dsw-alias-button-info-fill)',
                                color: '#fff',
                                borderRadius: '8px',
                                padding: '4px 14px',
                                fontSize: '12px',
                                cursor: 'pointer',
                              },
                        children: confirm === 'remove' ? t('remove') : t('reset'),
                      }),
                    ],
                  }),
                ],
              }),
            })
          : null,
      ],
    });
  };
}
