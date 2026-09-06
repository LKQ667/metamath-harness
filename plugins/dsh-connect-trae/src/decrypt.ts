import { createDecipheriv, createHash } from 'node:crypto'

export const TRAE_AUTH_STORAGE_KEY = 'iCubeAuthInfo://icube.cloudide'

type EncryptionType = 'aes' | 'aes-private'

const SALT_A = Uint8Array.from([82,9,106,213,48,54,165,56,191,64,163,158,129,243,215,251,124,227,57,130,155,47,255,135,52,142,67,68,196,222,233,203,84,123,148,50,166,194,35,61,238,76,149,11,66,250,195,78,8,46,161,102,40,217,36,178,118,91,162,73,109,139,209,37])
const SALT_B = Uint8Array.from([31,221,168,51,136,7,199,49,177,18,16,89,39,128,236,95,96,81,127,169,25,181,74,13,45,229,122,159,147,201,156,239,160,224,59,77,174,42,245,176,200,235,187,60,131,83,153,97,23,43,4,126,186,119,214,38,225,105,20,99,85,33,12,125])
const SALT_C = Uint8Array.from([191,192,216,250,122,246,220,97,31,254,98,27,8,72,71,176,135,99,96,18,127,101,203,104,211,102,191,125,37,72,150,156,51,229,121,35,17,153,141,177,110,131,150,128,172,255,254,6,18,140,55,62,236,249,135,64,135,12,117,4,89,149,168,209])
const SALT_D = Uint8Array.from([246,204,26,232,232,70,129,109,223,146,169,242,23,241,105,145,50,196,165,42,254,120,3,54,244,207,209,85,53,6,138,106,175,148,31,204,186,186,165,182,87,142,49,10,39,110,26,154,86,56,173,125,18,64,198,225,99,99,83,82,191,134,76,170])

function xor(a: Uint8Array, b: Uint8Array): Buffer {
  return Buffer.from(a.map((value, index) => value ^ (b[index] ?? 0)))
}

function encryptionType(header: Buffer): EncryptionType {
  if (header.equals(Buffer.from([0x74, 0x63, 0x05, 0x10, 0x00, 0x00]))) return 'aes'
  if (header.equals(Buffer.from([18, 57, 32, 32, 2, 3]))) return 'aes-private'
  throw new Error('unsupported Trae auth encryption header')
}

export function decryptTraeStorageValue(encoded: string): string {
  const buffer = Buffer.from(encoded, 'base64')
  if (buffer.length <= 102) throw new Error('Trae auth ciphertext is too short')
  const type = encryptionType(buffer.subarray(0, 6))
  const random = buffer.subarray(6, 38)
  const encrypted = buffer.subarray(38)
  const salt = type === 'aes-private' ? xor(SALT_C, SALT_D) : xor(SALT_A, SALT_B)
  const first = createHash('sha512').update(random).digest()
  const derived = createHash('sha512').update(Buffer.concat([first, salt])).digest()
  const decipher = createDecipheriv('aes-128-cbc', derived.subarray(0, 16), derived.subarray(16, 32))
  const decrypted = Buffer.concat([decipher.update(encrypted), decipher.final()])
  if (decrypted.length < 64) throw new Error('Trae auth plaintext is too short')
  const expected = decrypted.subarray(0, 64)
  const plaintext = decrypted.subarray(64)
  const actual = createHash('sha512').update(plaintext).digest()
  if (!expected.equals(actual)) throw new Error('Trae auth integrity check failed')
  return plaintext.toString('utf8')
}

export function parseTraeAuthValue(value: string): unknown {
  const trimmed = value.trim()
  if (trimmed === '') throw new Error('Trae auth value is empty')
  const plaintext = trimmed.startsWith('{') ? trimmed : decryptTraeStorageValue(trimmed)
  return JSON.parse(plaintext) as unknown
}

export function parseTraeStorageDocument(text: string): unknown {
  const parsed = JSON.parse(text) as unknown
  if (typeof parsed !== 'object' || parsed === null || Array.isArray(parsed)) throw new Error('Trae storage document must be an object')
  const value = (parsed as Record<string, unknown>)[TRAE_AUTH_STORAGE_KEY]
  if (typeof value !== 'string') throw new Error(`Trae storage document has no ${TRAE_AUTH_STORAGE_KEY}`)
  return parseTraeAuthValue(value)
}
