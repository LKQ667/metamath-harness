/**
 * dsh-client-ui-skins — Host side.
 *
 * DSH 0.2.2-rc.5 适配（2026-11-27）：`@deepseek-ai/dsh-settings` 自动从导出
 * Config schema 的 `.volatile()` 字段投影配置表单，不再调用已移除的 `settings.register`。
 * 皮肤实际状态、FX 与内置壁纸仍保留在本地派生 `lib/client.js` 与浏览器 localStorage。
 */
import z from "@deepseek-ai/schemastery";

export const SKINS_SETTINGS_NAMESPACE = "ui-skins";
export const SKIN_FIELD = "skin";
export const DEFAULT_SKIN = "system";

export const Config = z.object({
  [SKIN_FIELD]: z.string().default(DEFAULT_SKIN).volatile(),
});
export const SkinsSettingsSchema = Config;

export function apply() {}
