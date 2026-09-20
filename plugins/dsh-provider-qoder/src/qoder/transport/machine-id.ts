import crypto from 'node:crypto'
import { existsSync, mkdirSync, readFileSync, writeFileSync } from 'node:fs'
import { homedir } from 'node:os'
import { dirname, join } from 'node:path'

function defaultMachineIdPaths(): string[] {
  return [
    join(homedir(), '.qoder', '.auth', 'machine_id'),
    join(homedir(), '.dsh', 'qoder', 'machine_id'),
  ]
}

/** Read Qoder's machine id or create the DSH-owned fallback. */
export function getMachineId(paths: readonly string[] = defaultMachineIdPaths()): string {
  for (const path of paths) {
    if (!existsSync(path)) continue
    try {
      const value = readFileSync(path, 'utf8').trim()
      if (value) return value
    } catch {
      // Try the next trusted location.
    }
  }

  const machineId = crypto.randomUUID()
  const savePath = paths.at(-1)
  if (savePath !== undefined) {
    try {
      mkdirSync(dirname(savePath), { recursive: true })
      writeFileSync(savePath, machineId, { encoding: 'utf8', flag: 'wx' })
    } catch {
      // Another process may have won creation; prefer its stable value.
      try {
        const existing = readFileSync(savePath, 'utf8').trim()
        if (existing) return existing
      } catch {
        // An ephemeral id is still sufficient for this process.
      }
    }
  }
  return machineId
}
