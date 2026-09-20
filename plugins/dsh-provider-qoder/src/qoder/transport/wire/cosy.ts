/**
 * COSY authentication headers and signature algorithm for Qoder services.
 *
 * Implements RSA + AES + MD5 signature generation required by the upstream
 * Qoder gateway.
 *
 * @module dsh-provider-qoder/qoder/transport/wire/cosy
 */

import crypto from 'node:crypto'
import { getMachineId } from '../machine-id.ts'

const qoderRSAPublicKey = `-----BEGIN PUBLIC KEY-----
MIGfMA0GCSqGSIb3DQEBAQUAA4GNADCBiQKBgQDA8iMH5c02LilrsERw9t6Pv5Nc
4k6Pz1EaDicBMpdpxKduSZu5OANqUq8er4GM95omAGIOPOh+Nx0spthYA2BqGz+l
6HRkPJ7S236FZz73In/KVuLnwI8JJ2CbuJap8kvheCCZpmAWpb/cPx/3Vr/J6I17
XcW+ML9FoCI6AOvOzwIDAQAB
-----END PUBLIC KEY-----`

export const qoderIdeVersion = '1.1.47'
export const qoderClientType = '5'
export const defaultUserAgent = `qoder/${qoderIdeVersion}`
const qoderDataPolicy = 'disagree'
const qoderLoginVersion = 'v2'
const qoderMachineOs = process.platform === 'win32'
  ? process.arch === 'arm64'
    ? 'aarch64_windows'
    : 'x86_64_windows'
  : process.arch === 'arm64'
    ? 'aarch64_linux'
    : 'x86_64_linux'
const qoderMachineTypeMagic = '5'

export interface CosyCredentials {
  userID: string
  authToken: string
  name: string
  email: string
  machineID?: string
}

interface UserInfo {
  uid: string
  security_oauth_token: string
  name: string
  aid: string
  email: string
}

interface CosyPayload {
  version: string
  requestId: string
  info: string
  cosyVersion: string
  ideVersion: string
}

export function computeSigPath(urlStr: string): string {
  const parsed = new URL(urlStr)
  let sigPath = parsed.pathname
  if (sigPath.startsWith('/algo')) {
    sigPath = sigPath.substring('/algo'.length)
  }
  return sigPath
}

function rsaEncryptBase64(data: Buffer | string): string {
  const key = {
    key: qoderRSAPublicKey,
    padding: crypto.constants.RSA_PKCS1_PADDING,
  }
  const encrypted = crypto.publicEncrypt(key, typeof data === 'string' ? Buffer.from(data) : data)
  return encrypted.toString('base64')
}

function aesEncryptCBCBase64(plaintext: string, keyStr: string): string {
  const cipher = crypto.createCipheriv('aes-128-cbc', Buffer.from(keyStr), Buffer.from(keyStr))
  let encrypted = cipher.update(plaintext, 'utf8', 'base64')
  encrypted += cipher.final('base64')
  return encrypted
}

export function buildAuthHeaders(
  body: Buffer | string | null,
  requestURL: string,
  creds: CosyCredentials,
): Record<string, string> {
  if (!creds.userID) {
    throw new Error('cosy: user id is empty')
  }
  if (!creds.authToken) {
    throw new Error('cosy: auth token is empty')
  }

  const aesKey = crypto.randomUUID().replace(/-/g, '').slice(0, 16)
  const userInfo: UserInfo = {
    uid: creds.userID,
    security_oauth_token: creds.authToken,
    name: creds.name || '',
    aid: '',
    email: creds.email || '',
  }

  const infoB64 = aesEncryptCBCBase64(JSON.stringify(userInfo), aesKey)
  const cosyKey = rsaEncryptBase64(aesKey)

  const timestamp = Math.floor(Date.now() / 1000).toString()
  const requestId = crypto.randomUUID()

  const cosyPayload: CosyPayload = {
    version: 'v1',
    requestId,
    info: infoB64,
    cosyVersion: qoderIdeVersion,
    ideVersion: '',
  }

  const payloadB64 = Buffer.from(JSON.stringify(cosyPayload)).toString('base64')
  const sigPath = computeSigPath(requestURL)

  const bodyStr = body ? (Buffer.isBuffer(body) ? body.toString('utf8') : body) : ''
  const sigInput = `${payloadB64}\n${cosyKey}\n${timestamp}\n${bodyStr}\n${sigPath}`
  const sig = crypto.createHash('md5').update(sigInput).digest('hex')

  const bodyHash = crypto
    .createHash('md5')
    .update(body || '')
    .digest('hex')
  const bodyLen = body ? (Buffer.isBuffer(body) ? body.length : Buffer.from(body).length).toString() : '0'

  const machineID = creds.machineID || getMachineId()

  return {
    Authorization: `Bearer COSY.${payloadB64}.${sig}`,
    'Cosy-Key': cosyKey,
    'Cosy-User': creds.userID,
    'Cosy-Date': timestamp,
    'Cosy-Version': qoderIdeVersion,
    'Cosy-Machineid': machineID,
    'Cosy-Machinetoken': machineID,
    'Cosy-Machinetype': qoderMachineTypeMagic,
    'Cosy-Machineos': qoderMachineOs,
    'Cosy-Clienttype': qoderClientType,
    'Cosy-Clientip': '127.0.0.1',
    'Cosy-Bodyhash': bodyHash,
    'Cosy-Bodylength': bodyLen,
    'Cosy-Sigpath': sigPath,
    'Cosy-Data-Policy': qoderDataPolicy,
    'Cosy-Organization-Id': '',
    'Cosy-Organization-Tags': '',
    'Login-Version': qoderLoginVersion,
    'X-Request-Id': crypto.randomUUID(),
  }
}
