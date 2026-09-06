/**
 * Browser half: Trae usage summary inside Plugin configuration.
 * Mirrors the `dsh-workbuddy-connect` browser-plugin entry so the external
 * presentation stays consistent across the plugin family.
 */

// DSH 0.1.2 deleted `@deepseek-ai/dsh-client-runtime` (its services moved to
// focused packages), so `ClientContext` is now cordis' own `Context` plus the
// service augmentations below: `slots` comes from `dsh-client-ui-renderer`,
// `settingsScope` from `dsh-client-ui-settings`, `locale` from
// `dsh-client-locale`. All type-only; the bundle requires none of them.
import type { Context as ClientContext } from '@deepseek-ai/cordis'
import type {} from '@deepseek-ai/dsh-client-ui-settings-plugins/client'
import type {} from '@deepseek-ai/dsh-client-locale/client'
import type {} from '@deepseek-ai/dsh-client-ui-slots'
import type {} from '@deepseek-ai/dsh-client-ui-renderer/client'
import type {} from '@deepseek-ai/dsh-client-ui-settings/client'
import { TraeUsageCard } from './TraeUsageCard.tsx'
import type { TraeUsageCardInjected } from './TraeUsageCard.tsx'
import { en, zh } from './locales.ts'
import type { TraeSettingsKey } from './locales.ts'

declare module '@deepseek-ai/dsh-client-ui-slots' {
  interface LocaleNamespaceMap {
    /** Trae plugin card copy. */
    'settings.trae': TraeSettingsKey
  }
}

/** Stable browser-plugin name. */
export const name = 'dsh-connect-trae-client'
/** Client services required by the Plugin configuration contribution. */
export const inject = ['slots', 'locale', 'settingsScope']

/**
 * Register card copy and the Trae card under Plugin configuration.
 *
 * The entire body is wrapped so that a DSH slot-API breaking change (for
 * example the rc.6→rc.7 `id`→`key` / `order`→`priority` rename) degrades
 * to a `console.error` instead of throwing into the DSH loader and raising
 * the red "Failed to load plugins" banner. The host provider keeps working:
 * the `trae` model channel is unaffected.
 *
 * NOTE: the try/catch boundary of this function is mirrored (duplicated) in
 * `tests/client-fallback.spec.ts`, because the real client entry imports
 * browser-only DSH packages that cannot load in the Node test environment.
 */
export function apply(ctx: ClientContext): void {
  try {
    const namespace = 'settings.trae'
    ctx.effect(() => ctx.locale.register(namespace, { zh, en }), 'dsh-connect-trae: settings copy')
    const t = ctx.locale.bind(namespace) as TraeUsageCardInjected['t']
    const settingsScope = ctx.settingsScope.bind({ namespace: 'trae' }) as NonNullable<TraeUsageCardInjected['settingsScope']>
    ctx.slots.inject('settings.plugin.item', () => ctx.slots.register({
      name: 'settings.plugin.item',
      key: 'trae',
      priority: 30,
      inject: (): TraeUsageCardInjected => ({ t, settingsScope }),
    }, TraeUsageCard))
  } catch (error: unknown) {
    // Degrade silently on the page: the host provider still serves models.
    console.error('[dsh-connect-trae] client card failed to load (host provider unaffected):', error)
  }
}
