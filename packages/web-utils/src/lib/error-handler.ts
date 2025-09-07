export function handleDatabaseError(error: unknown, context?: Record<string, unknown>): void {
  // Lightweight, UI-agnostic error handler for shared utils
  // Apps may wrap this with their own UI notification logic
  console.error("[db]", error, context || {});
}

export function handleNetworkError(error: unknown, context?: Record<string, unknown>): void {
  console.error("[network]", error, context || {});
}

export function handleBusinessError(message: string, extra?: Record<string, unknown>): void {
  console.warn("[biz]", message, extra || {});
}
