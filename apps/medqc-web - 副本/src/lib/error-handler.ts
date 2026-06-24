export enum ErrorType {
  NETWORK = 'NETWORK',
  VALIDATION = 'VALIDATION',
  BUSINESS = 'BUSINESS',
  DATABASE = 'DATABASE',
  AUTHENTICATION = 'AUTHENTICATION',
  AUTHORIZATION = 'AUTHORIZATION',
  FILE_UPLOAD = 'FILE_UPLOAD',
  UNKNOWN = 'UNKNOWN',
}

export enum ErrorSeverity {
  LOW = 'low',
  MEDIUM = 'medium',
  HIGH = 'high',
  CRITICAL = 'critical',
}

export interface ErrorContext {
  component?: string
  props?: Record<string, unknown>
  [key: string]: unknown
}

export interface CapturedErrorRecord {
  type: ErrorType
  severity: ErrorSeverity
  message: string
  userMessage: string
  timestamp: string
  url: string
  stack?: string
  context?: ErrorContext
}

export interface ErrorStats {
  totalErrors: number
  errorsByType: Record<string, number>
  errorsBySeverity: Record<string, number>
  recentErrors: CapturedErrorRecord[]
}

function normalizeError(error: unknown): Error {
  if (error instanceof Error) {
    return error
  }
  return new Error(typeof error === 'string' ? error : '未知错误')
}

function inferErrorType(message: string): ErrorType {
  const lower = message.toLowerCase()
  if (lower.includes('network') || lower.includes('fetch') || lower.includes('timeout')) {
    return ErrorType.NETWORK
  }
  if (lower.includes('validation') || lower.includes('invalid') || lower.includes('参数')) {
    return ErrorType.VALIDATION
  }
  if (lower.includes('permission') || lower.includes('forbidden') || lower.includes('权限')) {
    return ErrorType.AUTHORIZATION
  }
  if (lower.includes('auth') || lower.includes('token') || lower.includes('login')) {
    return ErrorType.AUTHENTICATION
  }
  if (lower.includes('database') || lower.includes('sql') || lower.includes('db')) {
    return ErrorType.DATABASE
  }
  if (lower.includes('upload') || lower.includes('file')) {
    return ErrorType.FILE_UPLOAD
  }
  if (lower.includes('business') || lower.includes('业务')) {
    return ErrorType.BUSINESS
  }
  return ErrorType.UNKNOWN
}

function inferSeverity(type: ErrorType): ErrorSeverity {
  if (type === ErrorType.DATABASE || type === ErrorType.NETWORK) {
    return ErrorSeverity.HIGH
  }
  if (type === ErrorType.AUTHENTICATION || type === ErrorType.AUTHORIZATION) {
    return ErrorSeverity.MEDIUM
  }
  if (type === ErrorType.VALIDATION) {
    return ErrorSeverity.LOW
  }
  return ErrorSeverity.MEDIUM
}

function userMessageByType(type: ErrorType): string {
  const map: Record<ErrorType, string> = {
    [ErrorType.NETWORK]: '网络连接异常，请稍后重试。',
    [ErrorType.VALIDATION]: '输入参数不合法，请检查后重试。',
    [ErrorType.BUSINESS]: '业务处理失败，请检查当前操作条件。',
    [ErrorType.DATABASE]: '数据服务暂不可用，请稍后重试。',
    [ErrorType.AUTHENTICATION]: '登录状态失效，请重新登录。',
    [ErrorType.AUTHORIZATION]: '当前账户权限不足，请联系管理员。',
    [ErrorType.FILE_UPLOAD]: '文件处理失败，请检查文件格式后重试。',
    [ErrorType.UNKNOWN]: '系统发生未知错误，请稍后重试。',
  }
  return map[type]
}

class GlobalErrorHandler {
  private readonly maxKeep = 200
  private readonly records: CapturedErrorRecord[] = []

  handleError(error: unknown, context?: ErrorContext): CapturedErrorRecord {
    const normalized = normalizeError(error)
    const type = inferErrorType(normalized.message)
    const severity = inferSeverity(type)

    const record: CapturedErrorRecord = {
      type,
      severity,
      message: normalized.message,
      userMessage: userMessageByType(type),
      timestamp: new Date().toISOString(),
      url: typeof window === 'undefined' ? '' : window.location.href,
      stack: normalized.stack,
      context,
    }

    this.records.unshift(record)
    if (this.records.length > this.maxKeep) {
      this.records.length = this.maxKeep
    }

    return record
  }

  getStats(): ErrorStats {
    const errorsByType: Record<string, number> = {}
    const errorsBySeverity: Record<string, number> = {}

    this.records.forEach((item) => {
      errorsByType[item.type] = (errorsByType[item.type] ?? 0) + 1
      errorsBySeverity[item.severity] = (errorsBySeverity[item.severity] ?? 0) + 1
    })

    return {
      totalErrors: this.records.length,
      errorsByType,
      errorsBySeverity,
      recentErrors: this.records.slice(0, 50),
    }
  }

  clear(): void {
    this.records.length = 0
  }
}

export const globalErrorHandler = new GlobalErrorHandler()
