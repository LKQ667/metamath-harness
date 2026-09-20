import { createElement } from 'react'
import { act, create, type ReactTestRenderer } from 'react-test-renderer'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { WorkBuddyPluginCard } from '../src/client/WorkBuddyPluginCard.tsx'
import { en } from '../src/client/locales.ts'

/**
 * Card tests. The plugin card had none, which is how a shared `busy` flag ended
 * up driving a per-model button label: pressing one candidate made every button
 * claim it was running. These pin the label to the model actually started.
 */

const t = (key: keyof typeof en, params: Record<string, unknown> = {}): string =>
  Object.entries(params).reduce(
    (text, [name, value]) => text.replace(`{${name}}`, String(value)),
    en[key] as string,
  )

describe('WorkBuddy plugin card', () => {
  let view: ReactTestRenderer | undefined
  let statusBody: Record<string, unknown>
  /** Resolvers for in-flight POSTs, so a run can be held open deliberately. */
  let pendingPosts: (() => void)[] = []
  const request = vi.fn()

  function status(overrides: Record<string, unknown> = {}): void {
    statusBody = {
      status: 'signed-in',
      nickname: '昵称',
      expiresAt: Date.now() + 3_600_000,
      probeKey: 'test-key',
      credits: { total: 100, accounts: [] },
      models: [],
      probe: {
        consent: true,
        running: false,
        candidates: ['hy3', 'glm-5.2', 'minimax-m3'],
        results: [],
        ...overrides,
      },
    }
  }

  beforeEach(() => {
    status()
    pendingPosts = []
    request.mockReset().mockImplementation(async (_url: string, init?: RequestInit) => {
      if (init?.method !== 'POST') return { ok: true, json: async () => statusBody }
      // Hold the POST open until the test releases it, so "in flight" is
      // observable rather than a race against the microtask queue.
      await new Promise<void>(resolve => { pendingPosts.push(resolve) })
      return { ok: true, json: async () => ({ state: 'ok', validation: 'non-validating', efforts: [] }) }
    })
    vi.stubGlobal('fetch', request)
    vi.stubGlobal('window', {
      setInterval: () => 1,
      clearInterval: () => {},
      addEventListener: () => {},
      removeEventListener: () => {},
      localStorage: { getItem: () => null, setItem: () => {}, removeItem: () => {} },
    })
  })

  afterEach(() => {
    act(() => view?.unmount())
    vi.unstubAllGlobals()
  })

  /** Mount the card and expand it so the probe section renders. */
  async function mount(): Promise<void> {
    // The card only reads `t`; the remaining props belong to the slot that
    // mounts it in DSH, so the test supplies the one it uses.
    const props = { t } as unknown as Parameters<typeof WorkBuddyPluginCard>[0]
    await act(async () => { view = create(createElement(WorkBuddyPluginCard, props)) })
    await act(async () => { view!.root.findAllByType('button')[0]!.props.onClick() })
  }

  const buttonLabels = (): string[] => view!.root.findAllByType('button').map(node => node.children.join(''))
  /**
   * Press a button by its label. `nth` disambiguates labels that repeat once
   * every row carries its own button (all idle rows read "Detect").
   */
  const press = async (label: string, nth = 0): Promise<void> => {
    const matches = view!.root.findAllByType('button').filter(entry => entry.children.join('') === label)
    const node = matches[nth]
    if (node === undefined) {
      throw new Error(`no button #${nth} labelled ${label}; have: ${buttonLabels().join(' | ')}`)
    }
    await act(async () => { node.props.onClick() })
  }

  it('labels only the pressed model as running', async () => {
    // Regression: a card-wide `busy` flag drove the label, so starting one
    // detection made all three candidate buttons read "Detecting …".
    await mount()
    await press(en.probeStart, 0)
    await press(en.probeConfirmAction)

    const labels = buttonLabels()
    const running = labels.filter(label => label.startsWith('Detecting'))
    // Exactly one row reports progress, and its label names the model.
    expect(running).toHaveLength(1)
    expect(running[0]).toContain('hy3')
    // The other rows keep their idle label.
    expect(labels.filter(label => label === en.probeStart)).toHaveLength(2)
  })

  it('returns the button to its idle label once the run finishes', async () => {
    await mount()
    await press(en.probeStart, 0)
    await press(en.probeConfirmAction)
    expect(buttonLabels().filter(label => label.startsWith('Detecting'))).toHaveLength(1)

    // Release the held POST; the running label must clear.
    await act(async () => {
      for (const release of pendingPosts.splice(0)) release()
    })
    expect(buttonLabels().filter(label => label.startsWith('Detecting'))).toHaveLength(0)
    expect(buttonLabels().filter(label => label === en.probeStart)).toHaveLength(3)
  })

  it('shows the confirmation inside the row that asked for it', async () => {
    // Rendered after the whole list, the confirmation sat at the bottom of a
    // long candidate list: the question was a screen away from the button.
    status({ candidates: ['hy3', 'glm-5.2', 'minimax-m3'] })
    await mount()

    // Open the confirmation for the FIRST candidate.
    await press(en.probeStart, 0)
    const confirmBody = en.probeConfirmBody.replace('{model}', 'hy3').slice(0, 12)
    expect(JSON.stringify(view!.toJSON())).toContain(confirmBody)

    // It belongs to the first row, i.e. it precedes the later candidates in
    // document order rather than trailing the list.
    const tree = JSON.stringify(view!.toJSON())
    expect(tree.indexOf(confirmBody)).toBeLessThan(tree.indexOf('minimax-m3'))
  })

  it('keeps a detected model in the candidate list, relabelled', async () => {
    // Regression: a detected model used to leave the candidate list, so its
    // button vanished and re-running it meant clearing every other result.
    status({
      candidates: ['hy3', 'glm-5.2'],
      results: [{ id: 'hy3', name: 'Hy3', validation: 'non-validating', efforts: [], probedAt: Date.now() }],
    })
    await mount()
    // Both rows are present. The detected one offers a re-run, the other a
    // first run — and neither row disappeared.
    expect(JSON.stringify(view!.toJSON())).toContain('Hy3')
    expect(JSON.stringify(view!.toJSON())).toContain('glm-5.2')
    expect(buttonLabels()).toContain(en.probeRedetect)
    expect(buttonLabels()).toContain(en.probeStart)
  })

  it('shows the same list before and after a detection', async () => {
    status({ candidates: ['hy3', 'glm-5.2'] })
    await mount()
    expect(buttonLabels().filter(label => label === en.probeStart)).toHaveLength(2)

    // Simulate the host reporting a result for hy3 without removing it from
    // the candidate list, which is how the host now behaves.
    status({
      candidates: ['hy3', 'glm-5.2'],
      results: [{ id: 'hy3', name: 'Hy3', validation: 'non-validating', efforts: [], probedAt: Date.now() }],
    })
    await act(async () => { await press(en.refresh) })
    // Still two rows: one re-run, one first run.
    expect(buttonLabels()).toContain(en.probeRedetect)
    expect(buttonLabels().filter(label => label === en.probeStart)).toHaveLength(1)
  })

  it('distinguishes the saved catalog from a live list and the built-in fallback', async () => {
    const fetchedAt = Date.UTC(2026, 8, 12, 8, 30)
    status()
    statusBody.catalog = { source: 'saved', fetchedAt }
    await mount()
    let rendered = JSON.stringify(view!.toJSON())
    expect(rendered).toContain(en.catalogSaved.split('{time}')[0]!)
    expect(rendered).not.toContain(en.catalogFallback)

    status()
    statusBody.catalog = { source: 'live', fetchedAt }
    await act(async () => { await press(en.refresh) })
    rendered = JSON.stringify(view!.toJSON())
    expect(rendered).toContain(en.catalogLive.split('{time}')[0]!)

    status()
    statusBody.catalog = { source: 'fallback' }
    await act(async () => { await press(en.refresh) })
    expect(JSON.stringify(view!.toJSON())).toContain(en.catalogFallback)
  })

  it('does not leave whitespace after the English no-nickname label', async () => {
    status()
    delete statusBody.nickname
    await mount()
    const rendered = JSON.stringify(view!.toJSON())
    expect(rendered).toContain('Signed in as')
    expect(rendered).not.toContain('Signed in as ')
  })
})
