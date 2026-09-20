/** Bounded, redacted diagnostics internal to the Qoder transport. */

export interface QoderLogger {
  debug?(message: string, ...details: unknown[]): void
  warn?(message: string, ...details: unknown[]): void
  error?(message: string, ...details: unknown[]): void
}

const sensitiveKey = /(?:authorization|credential|password|secret|token)/iu
const identifierKey = /^(?:accountId|id|uid|userId)$/iu
const tokenValue = /\b(?:jrt|jt|pt)-[\w.-]+\b/giu
const bearerValue = /Bearer\s+[^\s,;]+/giu
const maxDepth = 4
const maxEntries = 50
const maxStringLength = 500

function maskIdentifier(value: unknown): string {
  const text = String(value)
  return text.length <= 4 ? '[REDACTED]' : `…${text.slice(-4)}`
}

function maskEmail(value: unknown): string {
  const text = String(value)
  const at = text.indexOf('@')
  if (at <= 0) return '[REDACTED]'
  return `${text.slice(0, 1)}***${text.slice(at)}`
}

function redactString(value: string): string {
  const bounded = value.length > maxStringLength ? `${value.slice(0, maxStringLength)}…` : value
  return bounded.replace(tokenValue, '[REDACTED]').replace(bearerValue, 'Bearer [REDACTED]')
}

/** Redact credentials and bound arbitrary provider values before logging them. */
export function redactLogValue(value: unknown, depth = 0): unknown {
  if (typeof value === 'string') return redactString(value)
  if (value === null || typeof value !== 'object') return value
  if (depth >= maxDepth) return '[TRUNCATED]'
  if (value instanceof Error) {
    return {
      name: value.name,
      message: redactString(value.message),
      ...('code' in value ? { code: redactLogValue(value.code, depth + 1) } : {}),
      ...('cause' in value ? { cause: redactLogValue(value.cause, depth + 1) } : {}),
      ...(value instanceof AggregateError ? { errors: redactLogValue(value.errors, depth + 1) } : {}),
    }
  }
  if (Array.isArray(value)) {
    return value.slice(0, maxEntries).map(item => redactLogValue(item, depth + 1))
  }

  return Object.fromEntries(Object.entries(value).slice(0, maxEntries).map(([key, item]) => {
    if (sensitiveKey.test(key)) return [key, '[REDACTED]']
    if (identifierKey.test(key)) return [key, maskIdentifier(item)]
    if (key.toLowerCase() === 'email') return [key, maskEmail(item)]
    return [key, redactLogValue(item, depth + 1)]
  }))
}

/** Parse JSON-shaped diagnostics when possible, then apply the same redaction boundary. */
export function redactLogPayload(text: string): unknown {
  try {
    return redactLogValue(JSON.parse(text))
  } catch {
    return redactLogValue(text)
  }
}

/** Log one successfully parsed non-stream response through the shared redaction policy. */
export function logParsedResponse(
  logger: QoderLogger | undefined,
  operation: string,
  result: unknown,
): void {
  logger?.debug?.('[Qoder Response] Parsed', redactLogValue({ operation, result }))
}
