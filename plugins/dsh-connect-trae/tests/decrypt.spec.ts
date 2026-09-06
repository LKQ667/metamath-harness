import { createCipheriv, createHash, randomBytes } from 'node:crypto'
import { describe, expect, it } from 'vitest'
import { parseTraeAuthValue, parseTraeStorageDocument, TRAE_AUTH_STORAGE_KEY } from '../src/decrypt.ts'

const A = [82,9,106,213,48,54,165,56,191,64,163,158,129,243,215,251,124,227,57,130,155,47,255,135,52,142,67,68,196,222,233,203,84,123,148,50,166,194,35,61,238,76,149,11,66,250,195,78,8,46,161,102,40,217,36,178,118,91,162,73,109,139,209,37]
const B = [31,221,168,51,136,7,199,49,177,18,16,89,39,128,236,95,96,81,127,169,25,181,74,13,45,229,122,159,147,201,156,239,160,224,59,77,174,42,245,176,200,235,187,60,131,83,153,97,23,43,4,126,186,119,214,38,225,105,20,99,85,33,12,125]

function encryptFixture(text: string): string {
  const random = randomBytes(32)
  const salt = Buffer.from(A.map((value, index) => value ^ (B[index] ?? 0)))
  const first = createHash('sha512').update(random).digest()
  const derived = createHash('sha512').update(Buffer.concat([first, salt])).digest()
  const plaintext = Buffer.from(text)
  const payload = Buffer.concat([createHash('sha512').update(plaintext).digest(), plaintext])
  const cipher = createCipheriv('aes-128-cbc', derived.subarray(0, 16), derived.subarray(16, 32))
  return Buffer.concat([Buffer.from([0x74, 0x63, 0x05, 0x10, 0, 0]), random, cipher.update(payload), cipher.final()]).toString('base64')
}

describe('Trae auth decryption', () => {
  it('parses plaintext JSON by content rather than edition', () => {
    expect(parseTraeAuthValue('{"token":"at"}')).toEqual({ token: 'at' })
  })

  it('decrypts a synthetic tc value and verifies its integrity hash', () => {
    const encoded = encryptFixture(JSON.stringify({ token: 'secret', userId: 'u' }))
    expect(parseTraeAuthValue(encoded)).toEqual({ token: 'secret', userId: 'u' })
    const tampered = Buffer.from(encoded, 'base64')
    const index = tampered.length - 20
    tampered[index] = (tampered[index] ?? 0) ^ 1
    expect(() => parseTraeAuthValue(tampered.toString('base64'))).toThrow()
  })

  it('reads the expected storage key and rejects a missing key', () => {
    expect(parseTraeStorageDocument(JSON.stringify({ [TRAE_AUTH_STORAGE_KEY]: '{"token":"at"}' }))).toEqual({ token: 'at' })
    expect(() => parseTraeStorageDocument('{}')).toThrow(/has no/)
  })
})
