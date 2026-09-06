import { mkdtemp, mkdir, rm, writeFile } from 'node:fs/promises'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { afterEach, describe, expect, it } from 'vitest'
import { identityHeaders, pickTraeStorageIdentity, readTraeIdentity } from '../src/identity.ts'

const cleanup: string[] = []
afterEach(async () => { await Promise.all(cleanup.splice(0).map(path => rm(path, { recursive: true, force: true }))) })

describe('Trae persisted identity', () => {
  it('reads Trae-owned machine and telemetry IDs without random generation', async () => {
    const root = await mkdtemp(join(tmpdir(), 'trae-id-')); cleanup.push(root)
    const storage = join(root, 'User', 'globalStorage', 'storage.json')
    await mkdir(join(root, 'User', 'globalStorage'), { recursive: true })
    await writeFile(join(root, 'machineid'), 'machine-stable')
    await writeFile(storage, JSON.stringify({ 'telemetry.devDeviceId': 'device-stable', 'telemetry.machineId': 'telemetry-machine', 'iCubeAuthInfo://icube-dc:221464824136636': 'encrypted', iCubeLastVersion: '2.3.1' }))
    const first = await readTraeIdentity({ edition: 'cn', path: storage }, { platform: 'darwin', home: root, env: {} })
    const second = await readTraeIdentity({ edition: 'cn', path: storage }, { platform: 'darwin', home: root, env: {} })
    expect(first).toEqual(second)
    expect(first).toMatchObject({ machineId: 'telemetry-machine', deviceId: '221464824136636', buildVersion: '2.3.1', platform: 'darwin' })
    // darwin install: no win32/windows-specific device type.
    expect(identityHeaders(first)['x-device-type']).toBe('mac')
  })

  it('falls back to root machineid and derives a deterministic device id only when telemetry IDs are absent', async () => {
    const root = await mkdtemp(join(tmpdir(), 'trae-id-')); cleanup.push(root)
    const storage = join(root, 'User', 'globalStorage', 'storage.json')
    await mkdir(join(root, 'User', 'globalStorage'), { recursive: true })
    await writeFile(join(root, 'machineid'), 'machine-stable')
    await writeFile(storage, '{}')
    const value = await readTraeIdentity({ edition: 'cn', path: storage }, { platform: 'darwin', home: root, env: {} })
    expect(value.deviceId).toMatch(/^[a-f0-9]{32}$/)
  })

  it('reads appVersion from the Windows install product.json', async () => {
    const root = await mkdtemp(join(tmpdir(), 'trae-win-')); cleanup.push(root)
    const storage = join(root, 'User', 'globalStorage', 'storage.json')
    await mkdir(join(root, 'User', 'globalStorage'), { recursive: true })
    await writeFile(storage, JSON.stringify({ 'telemetry.devDeviceId': 'device-stable', 'telemetry.machineId': 'telemetry-machine' }))
    const productDir = join(root, 'local', 'Programs', 'TRAE SOLO CN', 'resources', 'app')
    await mkdir(productDir, { recursive: true })
    await writeFile(join(productDir, 'product.json'), JSON.stringify({ appVersion: '0.1.56', version: '1.107.1', buildId: '1207052290818' }))
    const value = await readTraeIdentity({ edition: 'solo', path: storage }, { platform: 'win32', home: root, env: { LOCALAPPDATA: join(root, 'local') } })
    expect(value.appVersion).toBe('0.1.56')
    expect(value.platform).toBe('win32')
    expect(identityHeaders(value)['x-device-type']).toBe('windows')
    expect(value.osVersion).toMatch(/^Windows /)
  })

  it('falls back to <home>\\AppData\\Local when LOCALAPPDATA is missing', async () => {
    const root = await mkdtemp(join(tmpdir(), 'trae-win-')); cleanup.push(root)
    const storage = join(root, 'User', 'globalStorage', 'storage.json')
    await mkdir(join(root, 'User', 'globalStorage'), { recursive: true })
    await writeFile(storage, JSON.stringify({ 'telemetry.devDeviceId': 'device-stable', 'telemetry.machineId': 'telemetry-machine' }))
    const productDir = join(root, 'AppData', 'Local', 'Programs', 'TRAE SOLO CN', 'resources', 'app')
    await mkdir(productDir, { recursive: true })
    await writeFile(join(productDir, 'product.json'), JSON.stringify({ appVersion: '0.1.57' }))
    const value = await readTraeIdentity({ edition: 'solo', path: storage }, { platform: 'win32', home: root, env: {} })
    expect(value.appVersion).toBe('0.1.57')
    expect(value.platform).toBe('win32')
  })

  it('does not read product.json on linux and leaves appVersion undefined', async () => {
    const root = await mkdtemp(join(tmpdir(), 'trae-linux-')); cleanup.push(root)
    const storage = join(root, 'User', 'globalStorage', 'storage.json')
    await mkdir(join(root, 'User', 'globalStorage'), { recursive: true })
    await writeFile(storage, JSON.stringify({ 'telemetry.devDeviceId': 'device-stable', 'telemetry.machineId': 'telemetry-machine' }))
    const value = await readTraeIdentity({ edition: 'cn', path: storage }, { platform: 'linux', home: root, env: {} })
    expect(value.appVersion).toBeUndefined()
    expect(value.platform).toBe('linux')
  })

  it('skips product.json for sg and solo-sg editions on win32', async () => {
    const root = await mkdtemp(join(tmpdir(), 'trae-sg-')); cleanup.push(root)
    const storage = join(root, 'User', 'globalStorage', 'storage.json')
    await mkdir(join(root, 'User', 'globalStorage'), { recursive: true })
    await writeFile(storage, JSON.stringify({ 'telemetry.devDeviceId': 'device-stable', 'telemetry.machineId': 'telemetry-machine' }))
    const productDir = join(root, 'local', 'Programs', 'Trae', 'resources', 'app')
    await mkdir(productDir, { recursive: true })
    await writeFile(join(productDir, 'product.json'), JSON.stringify({ appVersion: '9.9.9' }))
    for (const edition of ['sg', 'solo-sg'] as const) {
      const value = await readTraeIdentity({ edition, path: storage }, { platform: 'win32', home: root, env: { LOCALAPPDATA: join(root, 'local') } })
      expect(value.appVersion).toBeUndefined()
      expect(value.platform).toBe('win32')
    }
  })

  it('picks the first present candidate, skipping missing editions (Windows SOLO-only machine)', async () => {
    const root = await mkdtemp(join(tmpdir(), 'trae-pick-')); cleanup.push(root)
    // The cn install is absent on this machine; only the SOLO storage exists.
    const cnStorage = join(root, 'Trae CN', 'User', 'globalStorage', 'storage.json')
    const soloStorage = join(root, 'TRAE SOLO CN', 'User', 'globalStorage', 'storage.json')
    await mkdir(join(root, 'TRAE SOLO CN', 'User', 'globalStorage'), { recursive: true })
    await writeFile(soloStorage, JSON.stringify({ 'telemetry.devDeviceId': 'device-stable', 'telemetry.machineId': 'telemetry-machine' }))
    const value = await pickTraeStorageIdentity(
      [
        { edition: 'cn', path: cnStorage },
        { edition: 'solo', path: soloStorage },
      ],
      { platform: 'win32', home: root, env: {} },
    )
    expect(value.edition).toBe('solo')
    expect(value.machineId).toBe('telemetry-machine')
    expect(value.platform).toBe('win32')
  })

  it('throws a friendly error when every candidate storage is missing', async () => {
    const root = await mkdtemp(join(tmpdir(), 'trae-pick-')); cleanup.push(root)
    const cnStorage = join(root, 'Trae CN', 'User', 'globalStorage', 'storage.json')
    const soloStorage = join(root, 'TRAE SOLO CN', 'User', 'globalStorage', 'storage.json')
    await expect(pickTraeStorageIdentity(
      [
        { edition: 'cn', path: cnStorage },
        { edition: 'solo', path: soloStorage },
      ],
      { platform: 'win32', home: root, env: {} },
    )).rejects.toThrow(/Trae storage was not found/)
  })
})
