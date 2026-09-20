import { createElement } from 'react'
import { act, create, type ReactTestRenderer } from 'react-test-renderer'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { WorkBuddyProbeControl, type WorkBuddyProbeControlProps } from '../src/client/WorkBuddyProbeControl.tsx'
import { en } from '../src/client/locales.ts'

/**
 * Composer-entry tests. The interaction these pin down:
 *
 * - the inline label is a *static* feature name, never a state readout (the
 *   verified levels belong to the model dropdown, not to composer chrome);
 * - a hover/focus tooltip carries the state and the click's purpose;
 * - the confirmation is an in-page bubble, not `window.confirm` — and cancelling
 *   it sends nothing, because probing spends the user's credit.
 */

describe('Composer model probe', () => {
  let view: ReactTestRenderer | undefined
  let provider: string
  let model: string
  let state: ReturnType<WorkBuddyProbeControlProps['directory']['getSnapshot']>
  let statusBody: Record<string, unknown>
  const listeners = new Set<() => void>()
  const request = vi.fn()
  /** Backing map for the stubbed localStorage. */
  let seenStore = new Map<string, string>()
  /** Captured `focus` listeners, so a reconcile can be fired on demand. */
  let focusHandlers: (() => void)[] = []
  const directory = {
    getSnapshot: () => state,
    subscribe: (listener: () => void) => { listeners.add(listener); return () => listeners.delete(listener) },
  } as WorkBuddyProbeControlProps['directory']
  const t: WorkBuddyProbeControlProps['t'] = (key, params = {}) =>
    Object.entries(params).reduce((text, [name, value]) => text.replace(`{${name}}`, String(value)), en[key] as string)

  function select(nextProvider: string, nextModel: string) {
    provider = nextProvider
    model = nextModel
    state = { current: { provider, model }, status: 'ready', groups: [], failures: [], error: null, routable: true }
    listeners.forEach(listener => listener())
  }

  /** The status document, with the probe section's fields overridable. */
  function probeStatus(overrides: Record<string, unknown> = {}): void {
    statusBody = {
      status: 'signed-in',
      probeKey: 'test-key',
      probe: { consent: true, running: false, candidates: ['glm-5.2', 'auto'], results: [], ...overrides },
    }
  }

  /** Display name the stubbed status document would report for a model id. */
  function nameFor(model: string): string {
    return model === 'auto' ? 'Auto' : 'GLM-5.2'
  }

  beforeEach(() => {
    probeStatus()
    select('workbuddy', 'glm-5.2')
    request.mockReset().mockImplementation(async (_url: string, init?: RequestInit) => {
      if (init?.method !== 'POST') return { ok: true, json: async () => statusBody }
      // A successful probe writes a result that the next status read reports,
      // the way the host does. Without that the control would refresh and see
      // the same candidate list, and there would be no outcome to announce.
      const probed = JSON.parse(String(init.body)) as { model: string }
      const probe = statusBody['probe'] as Record<string, unknown>
      const name = nameFor(probed.model)
      probe['candidates'] = (probe['candidates'] as string[]).filter(id => id !== probed.model)
      probe['results'] = [
        { id: probed.model, name, validation: 'non-validating', efforts: [], probedAt: Date.now() },
        ...(probe['results'] as unknown[]),
      ]
      return { ok: true, json: async () => ({ state: 'ok', validation: 'non-validating', efforts: [] }) }
    })
    vi.stubGlobal('fetch', request)
    // Minimal in-memory localStorage: the "already read" marks are persisted
    // there precisely so a reload cannot replay an old detection as news.
    seenStore = new Map()
    focusHandlers = []
    vi.stubGlobal('window', {
      setInterval: () => 1,
      clearInterval: () => {},
      addEventListener: (name: string, handler: () => void) => { if (name === 'focus') focusHandlers.push(handler) },
      removeEventListener: () => {},
      localStorage: {
        getItem: (key: string) => seenStore.get(key) ?? null,
        setItem: (key: string, value: string) => { seenStore.set(key, value) },
        removeItem: (key: string) => { seenStore.delete(key) },
      },
    })
  })
  afterEach(() => {
    act(() => view?.unmount())
    vi.unstubAllGlobals()
    listeners.clear()
  })

  async function mount() {
    await act(async () => { view = create(createElement(WorkBuddyProbeControl, { directory, t })) })
  }

  const posts = () => request.mock.calls.filter(([, init]) => init?.method === 'POST')
  const button = () => view!.root.findAllByType('button')
  const buttonLabels = () => button().map(node => node.children.join(''))
  const tooltips = () => view!.root.findAllByProps({ role: 'tooltip' })

  it('does not read status or show an entry for another provider', async () => {
    select('other', 'glm-5.2')
    await mount()
    expect(view?.toJSON()).toBeNull()
    expect(request).not.toHaveBeenCalled()
  })

  it('hides declared or non-candidate models', async () => {
    select('workbuddy', 'glm-5.3')
    await mount()
    expect(view?.toJSON()).toBeNull()
  })

  it('shows a static feature label that never carries state', async () => {
    await mount()
    expect(JSON.stringify(view!.toJSON())).toContain(en.probeLabel)
    // A detection result must not turn the label into a state readout; the
    // entry stays visible for the detected model, label unchanged.
    probeStatus({
      candidates: [],
      results: [{ id: 'glm-5.2', name: 'GLM-5.2', validation: 'validating', efforts: ['low', 'high'], probedAt: Date.now() }],
    })
    await act(async () => { listeners.forEach(listener => listener()) })
    expect(JSON.stringify(view!.toJSON())).toContain(en.probeLabel)
    expect(JSON.stringify(view!.toJSON())).not.toContain('low / high')
  })

  it('explains the click in a tooltip on hover, not a native title', async () => {
    await mount()
    expect(tooltips()).toHaveLength(0)
    const wrapper = view!.root.findAllByType('span')[0]!
    await act(async () => { wrapper.props.onMouseEnter() })
    expect(tooltips()).toHaveLength(1)
    expect(tooltips()[0]!.children.join('')).toContain('glm-5.2')
    // The tooltip is the accessible description; no `title` attribute is used.
    expect(button()[0]!.props.title).toBeUndefined()
    expect(button()[0]!.props['aria-describedby']).toBeTruthy()
  })

  it('does not announce a result that predates this page', async () => {
    // The note is for "you just ran a detection, here is the outcome". A stored
    // result the user never saw announced here is recorded as read silently, so
    // neither a reload nor a model switch replays it as news.
    probeStatus({
      candidates: [],
      results: [{ id: 'glm-5.2', name: 'GLM-5.2', validation: 'validating', efforts: ['low', 'high'], probedAt: Date.now() }],
    })
    await mount()
    expect(buttonLabels()).not.toContain(en.probeNoteDismiss)
    // The result is still discoverable: the tooltip reports it on hover.
    const wrapper = view!.root.findAllByType('span')[0]!
    await act(async () => { wrapper.props.onMouseEnter() })
    expect(tooltips()).toHaveLength(1)
    expect(tooltips()[0]!.children.join('')).toContain('low / high')
  })

  it('does not re-announce after switching models away and back', async () => {
    probeStatus({
      candidates: ['glm-5.2', 'auto'],
      results: [{ id: 'glm-5.2', name: 'GLM-5.2', validation: 'validating', efforts: ['low'], probedAt: Date.now() }],
    })
    await mount()
    expect(buttonLabels()).not.toContain(en.probeNoteDismiss)
    await act(async () => { select('workbuddy', 'auto') })
    await act(async () => { select('workbuddy', 'glm-5.2') })
    // Switching is not a reason to repeat something already on record.
    expect(buttonLabels()).not.toContain(en.probeNoteDismiss)
  })

  it('opens an in-page confirmation instead of window.confirm', async () => {
    await mount()
    const confirmSpy = vi.fn()
    vi.stubGlobal('confirm', confirmSpy)
    await act(async () => { button()[0]!.props.onClick() })
    expect(confirmSpy).not.toHaveBeenCalled()
    expect(buttonLabels()).toEqual(expect.arrayContaining([en.cancel, en.probeConfirmAction]))
  })

  it('sends nothing when the confirmation is cancelled', async () => {
    await mount()
    await act(async () => { button()[0]!.props.onClick() })
    const cancel = button().find(node => node.children.join('') === en.cancel)!
    await act(async () => { cancel.props.onClick() })
    expect(posts()).toHaveLength(0)
    // The bubble is gone again, leaving only the trigger.
    expect(button()).toHaveLength(1)
  })

  it('confirms the newly selected model and sends only that id, without automatic consent', async () => {
    await mount()
    await act(async () => { select('workbuddy', 'auto') })
    await act(async () => { button()[0]!.props.onClick() })
    const detect = button().find(node => node.children.join('') === en.probeConfirmAction)!
    await act(async () => { detect.props.onClick() })
    expect(posts()).toHaveLength(1)
    expect(JSON.parse(posts()[0]![1].body)).toEqual({ action: 'probe', model: 'auto' })
    expect(posts()[0]![1].headers['X-WorkBuddy-Probe-Key']).toBe('test-key')
  })

  it('blocks double clicks before the request finishes', async () => {
    await mount()
    await act(async () => { button()[0]!.props.onClick() })
    const detect = button().find(node => node.children.join('') === en.probeConfirmAction)!
    await act(async () => { detect.props.onClick(); detect.props.onClick() })
    expect(posts()).toHaveLength(1)
  })

  it('closes the confirmation once the request completes', async () => {
    await mount()
    await act(async () => { button()[0]!.props.onClick() })
    const detect = button().find(node => node.children.join('') === en.probeConfirmAction)!
    await act(async () => { detect.props.onClick() })
    // The confirmation is gone — replaced by the outcome note, which is a
    // different bubble. Only Cancel/Detect disappear.
    expect(buttonLabels()).not.toContain(en.probeConfirmAction)
    expect(buttonLabels()).not.toContain(en.cancel)
  })

  it('announces the outcome of a detection this control started', async () => {
    // The self-initiated path still announces: the user just spent a request
    // and needs to know what came back.
    await mount()
    await act(async () => { button()[0]!.props.onClick() })
    const detect = button().find(node => node.children.join('') === en.probeConfirmAction)!
    await act(async () => { detect.props.onClick() })
    // The POST answer is reported by the note.
    expect(buttonLabels()).toContain(en.probeNoteDismiss)
  })

  it('announces a cached result even if its timestamp predates the click', async () => {
    probeStatus({ candidates: [], results: [{ id: 'glm-5.2', name: 'GLM-5.2',
      validation: 'validating', efforts: ['low', 'high'], probedAt: 1 }] })
    await mount()
    request.mockImplementation(async (_url: string, init?: RequestInit) => ({
      ok: true, json: async () => init?.method === 'POST'
        ? { state: 'ok', validation: 'validating', efforts: ['low', 'high'], requests: 0 }
        : statusBody,
    }))
    await act(async () => { button()[0]!.props.onClick() })
    await act(async () => { button().find(node => node.children.join('') === en.probeConfirmAction)!.props.onClick() })
    expect(buttonLabels()).toContain(en.probeNoteDismiss)
    expect(JSON.stringify(view!.toJSON())).toContain('low / high')
  })

  it('shows completion without waiting for a hung credit/status refresh', async () => {
    await mount()
    request.mockImplementation(async (_url: string, init?: RequestInit) => {
      if (init?.method !== 'POST') return new Promise(() => {})
      return { ok: true, json: async () => ({ state: 'ok', validation: 'validating', efforts: ['high'] }) }
    })
    await act(async () => { button()[0]!.props.onClick() })
    await act(async () => { button().find(node => node.children.join('') === en.probeConfirmAction)!.props.onClick() })
    expect(buttonLabels()).toContain(en.probeNoteDismiss)
    expect(button()[0]!.props['aria-busy']).toBe(false)
  })

  it('keeps a successful result when the following status request fails', async () => {
    await mount()
    request.mockImplementation(async (_url: string, init?: RequestInit) => {
      if (init?.method !== 'POST') throw new Error('credit unavailable')
      return { ok: true, json: async () => ({ state: 'ok', validation: 'validating', efforts: ['high'] }) }
    })
    await act(async () => { button()[0]!.props.onClick() })
    await act(async () => { button().find(node => node.children.join('') === en.probeConfirmAction)!.props.onClick() })
    expect(buttonLabels()).toContain(en.probeNoteDismiss)
    expect(button()[0]!.props['aria-label']).not.toBe(en.probeTooltipRetry)
  })

  it('reports a non-validating outcome instead of verified levels', async () => {
    // The stubbed POST answers `non-validating`.
    await mount()
    await act(async () => { button()[0]!.props.onClick() })
    const detect = button().find(node => node.children.join('') === en.probeConfirmAction)!
    await act(async () => { detect.props.onClick() })
    expect(JSON.stringify(view!.toJSON())).toContain(en.probeNoteNotValidating)
  })

  it('still announces when a poll delivers a result mid-flight', async () => {
    // The 60s reconcile poll can land while the user's own probe is running.
    // That used to consume the "I started this" flag, so the real outcome was
    // filed as read and no note appeared.
    await mount()
    await act(async () => { button()[0]!.props.onClick() })
    const detect = button().find(node => node.children.join('') === en.probeConfirmAction)!

    // A poll lands mid-flight reporting another model's result — the
    // interference that used to consume the "I started this" flag.
    statusBody['probe'] = {
      ...(statusBody['probe'] as Record<string, unknown>),
      results: [{ id: 'auto', name: 'Auto', validation: 'validating', efforts: ['low'], probedAt: Date.now() }],
    }
    await act(async () => { detect.props.onClick() })

    // The user's own detection is still announced.
    expect(buttonLabels()).toContain(en.probeNoteDismiss)
  })

  it('persists the dismissal so it survives a remount', async () => {
    await mount()
    await act(async () => { button()[0]!.props.onClick() })
    const detect = button().find(node => node.children.join('') === en.probeConfirmAction)!
    await act(async () => { detect.props.onClick() })
    const dismiss = button().find(node => node.children.join('') === en.probeNoteDismiss)!
    await act(async () => { dismiss.props.onClick() })
    expect(buttonLabels()).not.toContain(en.probeNoteDismiss)

    // A fresh mount stands in for a reload or restart: the mark is on disk, so
    // the same outcome must not be announced again.
    const probedAt = Date.now()
    probeStatus({
      candidates: [],
      results: [{ id: 'glm-5.2', name: 'GLM-5.2', validation: 'non-validating', efforts: [], probedAt }],
    })
    await mount()
    expect(buttonLabels()).not.toContain(en.probeNoteDismiss)
  })
})
