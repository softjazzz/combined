const TRACE_HEADER = 'X-Trace-ID'
const REQUEST_HEADER = 'X-Request-ID'
const TRACE_PARENT_HEADER = 'traceparent'
const TRACE_PARENT_VERSION = '00'
const TRACE_PARENT_FLAGS = '01'

type HeaderCarrier = Record<string, unknown> & {
  get?: (name: string) => unknown
  set?: (name: string, value: unknown) => void
}

type ResponseLike = {
  headers?: unknown
  data?: unknown
}

function asNonEmptyString(value: unknown): string | undefined {
  if (typeof value !== 'string') {
    return undefined
  }
  const trimmed = value.trim()
  return trimmed ? trimmed : undefined
}

function randomHex(length: number): string {
  const bytes = Math.ceil(length / 2)
  if (typeof globalThis !== 'undefined' && globalThis.crypto && typeof globalThis.crypto.getRandomValues === 'function') {
    const buf = new Uint8Array(bytes)
    globalThis.crypto.getRandomValues(buf)
    return Array.from(buf, (n) => n.toString(16).padStart(2, '0'))
      .join('')
      .slice(0, length)
  }

  let output = ''
  while (output.length < length) {
    output += Math.floor(Math.random() * 0xffffffff)
      .toString(16)
      .padStart(8, '0')
  }
  return output.slice(0, length)
}

function isValidTraceParent(value: string): boolean {
  return /^[\da-f]{2}-[\da-f]{32}-[\da-f]{16}-[\da-f]{2}$/i.test(value.trim())
}

function readHeader(headers: unknown, name: string): string | undefined {
  if (!headers) {
    return undefined
  }

  const carrier = headers as HeaderCarrier
  if (typeof carrier.get === 'function') {
    const viaGet = asNonEmptyString(carrier.get(name)) || asNonEmptyString(carrier.get(name.toLowerCase()))
    if (viaGet) {
      return viaGet
    }
  }

  if (typeof carrier === 'object') {
    const target = name.toLowerCase()
    for (const [key, value] of Object.entries(carrier)) {
      if (key.toLowerCase() === target) {
        const candidate = asNonEmptyString(value)
        if (candidate) {
          return candidate
        }
      }
    }
  }

  return undefined
}

function writeHeader(headers: HeaderCarrier, name: string, value: string): void {
  if (typeof headers.set === 'function') {
    headers.set(name, value)
    return
  }
  headers[name] = value
}

function readTraceIdFromBody(data: unknown): string | undefined {
  if (!data || typeof data !== 'object') {
    return undefined
  }

  const body = data as Record<string, unknown>
  return (
    asNonEmptyString(body.trace_id) ||
    asNonEmptyString(body.traceId) ||
    asNonEmptyString((body.error as Record<string, unknown> | undefined)?.trace_id) ||
    asNonEmptyString((body.error as Record<string, unknown> | undefined)?.traceId)
  )
}

export function createTraceId(prefix = 'trace'): string {
  const now = Date.now().toString(36)
  const random =
    typeof globalThis !== 'undefined' &&
    globalThis.crypto &&
    typeof globalThis.crypto.randomUUID === 'function'
      ? globalThis.crypto.randomUUID().replace(/-/g, '')
      : Math.random().toString(36).slice(2, 14)

  return `${prefix}_${now}_${random.slice(0, 12)}`
}

export function createTraceParent(): string {
  const traceId = randomHex(32).toLowerCase()
  const spanId = randomHex(16).toLowerCase()
  return `${TRACE_PARENT_VERSION}-${traceId}-${spanId}-${TRACE_PARENT_FLAGS}`
}

export function ensureTraceHeaders(
  headers?: HeaderCarrier,
  traceId?: string,
): { headers: HeaderCarrier; traceId: string; traceparent: string } {
  const merged = (headers || {}) as HeaderCarrier
  const existingTraceId = readHeader(merged, TRACE_HEADER)
  const existingRequestId = readHeader(merged, REQUEST_HEADER)
  const existingTraceParent = readHeader(merged, TRACE_PARENT_HEADER)
  const resolvedTraceId = traceId || existingTraceId || existingRequestId || createTraceId()
  const resolvedTraceParent =
    existingTraceParent && isValidTraceParent(existingTraceParent)
      ? existingTraceParent.toLowerCase()
      : createTraceParent()

  writeHeader(merged, TRACE_HEADER, resolvedTraceId)
  writeHeader(merged, REQUEST_HEADER, resolvedTraceId)
  writeHeader(merged, TRACE_PARENT_HEADER, resolvedTraceParent)

  return {
    headers: merged,
    traceId: resolvedTraceId,
    traceparent: resolvedTraceParent,
  }
}

export function extractTraceIdFromHeaders(headers?: unknown): string | undefined {
  if (!headers) {
    return undefined
  }
  return readHeader(headers, TRACE_HEADER) || readHeader(headers, REQUEST_HEADER)
}

export function extractTraceIdFromResponse(response?: ResponseLike | null): string | undefined {
  if (!response) {
    return undefined
  }

  return (
    readHeader(response.headers, TRACE_HEADER) ||
    readHeader(response.headers, TRACE_HEADER.toLowerCase()) ||
    readTraceIdFromBody(response.data)
  )
}

export function attachTraceIdToError<T extends Record<string, unknown>>(
  error: T,
  explicitTraceId?: string,
): T {
  if (!error || typeof error !== 'object') {
    return error
  }

  const traceId =
    explicitTraceId ||
    extractTraceIdFromResponse((error as { response?: ResponseLike }).response) ||
    undefined

  if (!traceId) {
    return error
  }

  ;(error as T & { traceId?: string }).traceId = traceId
  ;(error as T & { trace_id?: string }).trace_id = traceId
  ;(error as T & { trace?: string }).trace = traceId

  const context = (error as T & { context?: Record<string, unknown> }).context
  if (!context || typeof context !== 'object') {
    ;(error as T & { context: Record<string, unknown> }).context = { trace_id: traceId, trace: traceId }
  } else {
    if (!context.trace_id && !context.traceId) {
      context.trace_id = traceId
    }
    if (!context.trace) {
      context.trace = traceId
    }
  }

  return error
}

export { REQUEST_HEADER, TRACE_HEADER, TRACE_PARENT_HEADER }
