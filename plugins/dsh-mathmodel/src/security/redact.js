const TOKEN_PATTERNS = [
  /\bsk-[A-Za-z0-9_-]{12,}\b/g,
  /\bAIza[A-Za-z0-9_-]{20,}\b/g,
  /\bBearer\s+[A-Za-z0-9._~+\/-]+=*/gi,
  /([?&](?:api_?key|key|token)=)[^&#\s]+/gi,
];

export function redactText(value, knownSecrets = []) {
  let text = String(value ?? '');
  for (const secret of knownSecrets) {
    if (typeof secret === 'string' && secret.length >= 4) text = text.split(secret).join('[REDACTED]');
  }
  for (const pattern of TOKEN_PATTERNS) {
    text = text.replace(pattern, (match, prefix) => prefix ? `${prefix}[REDACTED]` : '[REDACTED]');
  }
  return text;
}

export function safeError(error, knownSecrets = []) {
  const message = error instanceof Error ? error.message : String(error);
  return new Error(redactText(message, knownSecrets));
}
