import { describe, expect, it } from 'vitest'
import { SlotCore } from '@deepseek-ai/dsh-client-ui-slots'
import { CARD_VARIANTS } from '../src/client/WorkBuddyPluginCard.tsx'

/**
 * The plan's §7 gate: "同一 client bundle 注册两个 settings.plugin.item key…
 * 实施前以最小运行验证两个条目都可见；若插槽不支持，再定位限制，不直接复制
 * 整个插件." — i.e. register two cards from one plugin, and if the slot cannot
 * hold both, find the actual limit rather than duplicating the plugin.
 *
 * `settings.plugin.item` is a keyed slot, so whether two entries coexist is a
 * property of the real slot registry rather than of this plugin's code. These
 * tests drive the actual `SlotCore` to answer it, instead of trusting that the
 * registration shape works.
 *
 * Only the variant ids are needed from the card module (the components
 * themselves cannot render in this Node environment), and the register calls
 * are typed loosely on purpose: the point under test is the registry's
 * behaviour, not the DSH client typings.
 */

/* eslint-disable @typescript-eslint/no-explicit-any */

/** Minimal component stand-in; the registry only stores the reference. */
const Component = (): null => null

const register = (core: SlotCore, options: Record<string, unknown>): unknown =>
  (core.register as any)(options, Component)

/**
 * Declare `settings.plugin.item` the way DSH does: a parent entry contributes a
 * `children` table. `SlotCore` has no standalone declare method — the child
 * spec is owned by the registering entry, which is also why a slot can only be
 * claimed once.
 */
function declarePluginItem(core: SlotCore): void {
  register(core, {
    name: 'root',
    children: {
      'settings.plugin.item': {
        kind: 'keyed',
        keyProps: { workbuddy: {}, 'workbuddy-ai': {} },
      },
    },
  })
}

const entries = (core: SlotCore): any[] => (core.entries as any)('settings.plugin.item')

describe('settings.plugin.item holds both cards', () => {
  it('accepts two registrations with distinct keys from one owner', () => {
    const core = new SlotCore()
    declarePluginItem(core)
    expect(() => {
      for (const [index, variant] of CARD_VARIANTS.entries()) {
        register(core, { name: 'settings.plugin.item', key: variant.id, priority: 30 - index })
      }
    }).not.toThrow()
    // Both entries are live, which is exactly what the two cards need.
    expect(entries(core)).toHaveLength(2)
  })

  it('projects one cell per key, so both cards render', () => {
    const core = new SlotCore()
    declarePluginItem(core)
    for (const [index, variant] of CARD_VARIANTS.entries()) {
      register(core, { name: 'settings.plugin.item', key: variant.id, priority: 30 - index })
    }
    // The projection returns the winning ENTRY per key, so the key is read off
    // `options` — one cell each, which is what the settings page renders.
    const cells = (core.entriesOfSlot as any)('settings.plugin.item') as { options: { key?: string } }[]
    expect(cells).toHaveLength(2)
    expect(cells.map(cell => cell.options.key).sort()).toEqual(['workbuddy', 'workbuddy-ai'])
  })

  it('rejects a duplicate key at the same priority, which is why priorities differ', () => {
    // The registry throws when the SAME key is registered twice at the same
    // priority. Distinct keys would be fine at equal priority, but the plugin
    // still staggers them so the CN card leads in the settings list; this test
    // documents which rule is actually enforced.
    const core = new SlotCore()
    declarePluginItem(core)
    register(core, { name: 'settings.plugin.item', key: 'workbuddy', priority: 30 })
    expect(() => register(core, { name: 'settings.plugin.item', key: 'workbuddy', priority: 30 }))
      .toThrow(/already has an entry for key/)
  })

  it('allows distinct keys at the same priority, so staggering is presentation only', () => {
    const core = new SlotCore()
    declarePluginItem(core)
    // If this ever threw, the two cards would depend on artificial priority
    // differences to coexist — worth knowing explicitly.
    expect(() => {
      register(core, { name: 'settings.plugin.item', key: 'workbuddy', priority: 30 })
      register(core, { name: 'settings.plugin.item', key: 'workbuddy-ai', priority: 30 })
    }).not.toThrow()
    expect(entries(core)).toHaveLength(2)
  })

  it('requires an explicit key, which is why each card passes one', () => {
    const core = new SlotCore()
    declarePluginItem(core)
    // This is the rc.7 breakage the client entry's try/catch exists for.
    expect(() => register(core, { name: 'settings.plugin.item' }))
      .toThrow(/requires options.key/)
  })

  it('rejects registering into an undeclared slot', () => {
    const core = new SlotCore()
    expect(() => register(core, { name: 'settings.plugin.item', key: 'workbuddy' }))
      .toThrow(/not declared/)
  })
})
