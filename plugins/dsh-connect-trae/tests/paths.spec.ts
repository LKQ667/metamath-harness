import { describe, expect, it } from 'vitest'
import { join } from 'node:path'
import { traeStorageCandidates } from '../src/paths.ts'

describe('Trae storage paths', () => {
  it('uses the four observed macOS application-support paths', () => {
    // Expected values are built with the same host join() as the implementation,
    // so the assertion stays platform-independent: on a POSIX host it matches the
    // literal mac path structure, on a Windows host it matches the same four
    // directory names and nesting with backslash separators.
    const apps = ['Trae CN', 'Trae', 'TRAE SOLO CN', 'TRAE SOLO']
    const paths = traeStorageCandidates('darwin', '/Users/test', {}).map(item => item.path)
    expect(paths).toEqual(apps.map(app => join('/Users/test', 'Library', 'Application Support', app, 'User', 'globalStorage', 'storage.json')))
  })

  it('uses APPDATA on Windows and XDG_CONFIG_HOME on Linux', () => {
    expect(traeStorageCandidates('win32', 'C:/home', { APPDATA: 'C:/Roaming' })[0]?.path).toContain(join('C:/Roaming', 'Trae CN'))
    expect(traeStorageCandidates('linux', '/home/test', { XDG_CONFIG_HOME: '/cfg' })[0]?.path).toBe(join('/cfg', 'Trae CN', 'User', 'globalStorage', 'storage.json'))
  })
})
