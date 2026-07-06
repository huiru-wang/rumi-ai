const TECHNICAL_ERROR_PATTERNS = [
  /Failed to fetch/i,
  /Failed to fetch file/i,
  /Download failed/i,
  /HTTP\s*\d{3}/i,
  /\b[45]\d{2}\b/,
  /Unexpected token/i,
  /JSON/i,
  /NetworkError/i,
  /Load failed/i,
];

export function toUserFacingErrorMessage(error: unknown, fallback: string): string {
  const message = error instanceof Error ? error.message : error ? String(error) : "";
  const trimmed = message.trim();
  if (!trimmed) return fallback;
  if (TECHNICAL_ERROR_PATTERNS.some((pattern) => pattern.test(trimmed))) {
    return fallback;
  }
  return trimmed;
}
