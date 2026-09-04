/**
 * dsh-client-ui-skins — Host side.
 *
 * Registers the `ui-skins` settings namespace so the browser half can persist
 * the active skin choice through the ordinary settings transport. The actual
 * skins live in the client bundle; this Host file is deliberately thin.
 */
import { settingsNamespace } from "@deepseek-ai/dsh-settings";
import z from "@deepseek-ai/schemastery";

/** Settings namespace owned by the skins plugin. */
export const SKINS_SETTINGS_NAMESPACE = "ui-skins";
/** Field carrying the active skin id ("system" = none). */
export const SKIN_FIELD = "skin";
/** Default: no skin, native appearance. */
export const DEFAULT_SKIN = "system";

/** Durable skins schema; also the wire envelope the browser scope validates against. */
export const SkinsSettingsSchema = z.object({
  [SKIN_FIELD]: z.string().default(DEFAULT_SKIN),
});

/**
 * Register the durable skin section when the optional settings service is
 * composed.
 * @param ctx - Host context.
 */
export function apply(ctx) {
  ctx.inject(["settings"], (settingsCtx) => {
    settingsCtx.settings.register(
      settingsNamespace(SKINS_SETTINGS_NAMESPACE),
      SkinsSettingsSchema,
    );
  });
}
