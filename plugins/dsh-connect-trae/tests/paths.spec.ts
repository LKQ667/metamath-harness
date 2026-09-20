import { describe, expect, it } from 'vitest'
import { join } from 'node:path'
import { traeCliCandidates, traeStorageCandidates } from '../src/paths.ts'

describe('Trae storage paths', () => {
  it('uses the four observed macOS application-support paths', () => {
    // Expected values are built with the same host join() as the implementation,
    // so the assertion stays platform-independent: on a POSIX host it matches the
    // literal mac path structure, on a Windows host it matches the same four
    // directory names and nesting with backslash separators.
    const apps = ['Trae CN', 'Trae', 'TRAE SOLO CN', 'TRAE SOLO']
    const paths = traeStorageCandidates('darwin', '/Users/test', {}).filter(item => item.source === 'desktop').map(item => item.path)
    expect(paths).toEqual(apps.map(app => join('/Users/test', 'Library', 'Application Support', app, 'User', 'globalStorage', 'storage.json')))
  })

  it('uses APPDATA on Windows and XDG_CONFIG_HOME on Linux', () => {
    expect(traeStorageCandidates('win32', 'C:/home', { APPDATA: 'C:/Roaming' })[0]?.path).toContain(join('C:/Roaming', 'Trae CN'))
    expect(traeStorageCandidates('linux', '/home/test', { XDG_CONFIG_HOME: '/cfg' })[0]?.path).toBe(join('/cfg', 'trae-cn', 'User', 'globalStorage', 'storage.json'))
  })

  it('probes the macOS spelling of Linux config directories as well', () => {
    // The real Linux directory name is unverified on a real host, so both the
    // lowercase Electron spelling and the macOS spelling must be probed. Guessing
    // only one of them would either miss real installs or drop existing users.
    const paths = traeStorageCandidates('linux', '/home/test', {}).map(item => item.path)
    expect(paths).toContain(join('/home/test', '.config', 'trae-cn', 'User', 'globalStorage', 'storage.json'))
    expect(paths).toContain(join('/home/test', '.config', 'Trae CN', 'User', 'globalStorage', 'storage.json'))
  })
})

describe('Trae CLI token paths', () => {
  it('finds the CLI dotfile home that carries a bare JWT', () => {
    // Reported in issue #5: a WSL2 user signs in with `traecli`, which writes a
    // bare JWT under the CLI's own dotfile home rather than an Electron
    // globalStorage/storage.json. Without these candidates the plugin reports
    // "not signed in" on every CLI-only machine, including all of WSL2.
    const paths = traeCliCandidates('linux', '/home/u', {}).map(item => item.path)
    expect(paths).toContain(join('/home/u', '.trae-cn', 'trae-jwt-token'))
    expect(paths).toContain(join('/home/u', '.trae', 'trae-jwt-token'))
  })

  it('marks CLI candidates with the cli source so parsing can branch', () => {
    const candidates = traeStorageCandidates('darwin', '/Users/test', {})
    const cli = candidates.filter(item => item.source === 'cli')
    expect(cli.map(item => item.path)).toEqual([
      join('/Users/test', '.trae-cn', 'trae-jwt-token'),
      join('/Users/test', '.trae', 'trae-jwt-token'),
    ])
    expect(cli.every(item => item.edition === 'cn' || item.edition === 'sg')).toBe(true)
  })

  it('includes CLI candidates alongside desktop ones on every platform', () => {
    for (const platform of ['darwin', 'win32', 'linux'] as const) {
      const all = traeStorageCandidates(platform, '/h', {})
      expect(all.some(item => item.source === 'cli')).toBe(true)
      expect(all.some(item => item.source === 'desktop')).toBe(true)
    }
  })
})
