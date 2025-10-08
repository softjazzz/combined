/**
 * 统一错误处理工具
 * 提供友好的错误信息和处理机制
 */

import { message, notification } from 'ant-design-vue'

// 错误类型枚举
export enum ErrorType {
  VALIDATION = 'VALIDATION',
  NETWORK = 'NETWORK',
  DATABASE = 'DATABASE',
  AUTHENTICATION = 'AUTHENTICATION',
  AUTHORIZATION = 'AUTHORIZATION',
  FILE_UPLOAD = 'FILE_UPLOAD',
  BUSINESS = 'BUSINESS',
  UNKNOWN = 'UNKNOWN'
}

// 错误级别枚举
export enum ErrorLevel {
  INFO = 'INFO',
  WARNING = 'WARNING',
  ERROR = 'ERROR',
  CRITICAL = 'CRITICAL'
}

// 应用错误接口
export interface AppError {
  type: ErrorType
  level: ErrorLevel
  code: string
  message: string
  originalError?: Error
  context?: Record<string, unknown>
  timestamp: string
  userMessage: string
  suggestions?: string[]
}

// 错误处理器类
export class ErrorHandler {
  private static instance: ErrorHandler
  private errorQueue: AppError[] = []

  static getInstance(): ErrorHandler {
    if (!ErrorHandler.instance) {
      ErrorHandler.instance = new ErrorHandler()
    }
    return ErrorHandler.instance
  }

  // 创建应用错误
  createError(
    type: ErrorType,
    level: ErrorLevel,
    code: string,
    message: string,
    originalError?: Error,
    context?: Record<string, unknown>
  ): AppError {
    const userMessage = this.generateUserMessage(type, code, message)
    const suggestions = this.generateSuggestions(type, code)

    return {
      type,
      level,
      code,
      message,
      originalError,
      context,
      timestamp: new Date().toISOString(),
      userMessage,
      suggestions
    }
  }

  // 处理错误
  handleError(error: AppError | Error | any): void {
    let appError: AppError

    if (this.isAppError(error)) {
      appError = error
    } else if (error instanceof Error) {
      appError = this.convertToAppError(error)
    } else {
      appError = this.createError(
        ErrorType.UNKNOWN,
        ErrorLevel.ERROR,
        'UNKNOWN_ERROR',
        '未知错误',
        error
      )
    }

    // 记录错误
    this.logError(appError)

    // 显示用户提示
    this.showUserNotification(appError)

    // 添加到错误队列
    this.errorQueue.push(appError)
  }

  // 生成用户友好的错误信息
  private generateUserMessage(type: ErrorType, code: string, message: string): string {
    const userMessages: Record<string, Record<string, string>> = {
      [ErrorType.VALIDATION]: {
        'REQUIRED_FIELD': '请填写必填字段',
        'INVALID_FORMAT': '输入格式不正确',
        'LENGTH_EXCEEDED': '输入内容过长',
        'INVALID_FILE_TYPE': '不支持的文件格式',
        'FILE_SIZE_EXCEEDED': '文件大小超出限制',
        'DEFAULT': '输入信息有误，请检查后重试'
      },
      [ErrorType.NETWORK]: {
        'CONNECTION_FAILED': '网络连接失败，请检查网络设置',
        'TIMEOUT': '请求超时，请稍后重试',
        'SERVER_ERROR': '服务器暂时无法响应，请稍后重试',
        'DEFAULT': '网络请求失败，请检查网络连接'
      },
      [ErrorType.DATABASE]: {
        'CONNECTION_FAILED': '数据库连接失败',
        'QUERY_ERROR': '数据查询失败',
        'DUPLICATE_KEY': '数据已存在，请检查输入信息',
        'FOREIGN_KEY_CONSTRAINT': '数据关联错误，请联系管理员',
        'DEFAULT': '数据操作失败，请稍后重试'
      },
      [ErrorType.AUTHENTICATION]: {
        'INVALID_CREDENTIALS': '用户名或密码错误',
        'TOKEN_EXPIRED': '登录已过期，请重新登录',
        'ACCOUNT_LOCKED': '账户已被锁定，请联系管理员',
        'DEFAULT': '身份验证失败，请重新登录'
      },
      [ErrorType.AUTHORIZATION]: {
        'INSUFFICIENT_PERMISSIONS': '权限不足，无法执行此操作',
        'RESOURCE_FORBIDDEN': '无权访问该资源',
        'DEFAULT': '权限不足，请联系管理员'
      },
      [ErrorType.FILE_UPLOAD]: {
        'UPLOAD_FAILED': '文件上传失败，请重试',
        'INVALID_FILE': '文件格式不正确',
        'FILE_TOO_LARGE': '文件大小超出限制',
        'DEFAULT': '文件处理失败，请检查文件格式和大小'
      },
      [ErrorType.BUSINESS]: {
        'RECORD_NOT_FOUND': '未找到相关记录',
        'OPERATION_NOT_ALLOWED': '当前状态下不允许此操作',
        'DUPLICATE_OPERATION': '请勿重复操作',
        'DEFAULT': '业务处理失败，请稍后重试'
      }
    }

    const typeMessages = userMessages[type]
    if (typeMessages && typeMessages[code]) {
      return typeMessages[code]
    }

    return typeMessages?.DEFAULT || '操作失败，请稍后重试'
  }

  // 生成解决建议
  private generateSuggestions(type: ErrorType, code: string): string[] {
    const suggestions: Record<string, Record<string, string[]>> = {
      [ErrorType.VALIDATION]: {
        'REQUIRED_FIELD': ['请填写所有必填字段', '检查表单是否完整'],
        'INVALID_FORMAT': ['请按照正确格式输入', '参考输入示例'],
        'FILE_SIZE_EXCEEDED': ['压缩文件后重试', '选择更小的文件'],
        'DEFAULT': ['检查输入信息', '按照提示修改']
      },
      [ErrorType.NETWORK]: {
        'CONNECTION_FAILED': ['检查网络连接', '稍后重试'],
        'TIMEOUT': ['网络较慢，请稍后重试', '刷新页面重试'],
        'DEFAULT': ['检查网络连接', '刷新页面重试']
      },
      [ErrorType.AUTHENTICATION]: {
        'INVALID_CREDENTIALS': ['检查用户名和密码', '使用忘记密码功能'],
        'TOKEN_EXPIRED': ['重新登录', '刷新页面'],
        'DEFAULT': ['重新登录', '清除浏览器缓存']
      },
      [ErrorType.AUTHORIZATION]: {
        'INSUFFICIENT_PERMISSIONS': ['联系管理员申请权限', '使用有权限的账户'],
        'DEFAULT': ['联系管理员', '检查账户权限']
      }
    }

    const typeSuggestions = suggestions[type]
    if (typeSuggestions && typeSuggestions[code]) {
      return typeSuggestions[code]
    }

    return typeSuggestions?.DEFAULT || ['稍后重试', '联系技术支持']
  }

  // 转换普通错误为应用错误
  private convertToAppError(error: Error): AppError {
    // 根据错误信息判断错误类型
    const message = error.message.toLowerCase()

    if (message.includes('network') || message.includes('fetch')) {
      return this.createError(
        ErrorType.NETWORK,
        ErrorLevel.ERROR,
        'NETWORK_ERROR',
        error.message,
        error
      )
    }

    if (message.includes('unauthorized') || message.includes('authentication')) {
      return this.createError(
        ErrorType.AUTHENTICATION,
        ErrorLevel.ERROR,
        'AUTH_ERROR',
        error.message,
        error
      )
    }

    if (message.includes('permission') || message.includes('forbidden')) {
      return this.createError(
        ErrorType.AUTHORIZATION,
        ErrorLevel.ERROR,
        'PERMISSION_ERROR',
        error.message,
        error
      )
    }

    if (message.includes('validation') || message.includes('invalid')) {
      return this.createError(
        ErrorType.VALIDATION,
        ErrorLevel.WARNING,
        'VALIDATION_ERROR',
        error.message,
        error
      )
    }

    // 默认为未知错误
    return this.createError(
      ErrorType.UNKNOWN,
      ErrorLevel.ERROR,
      'UNKNOWN_ERROR',
      error.message,
      error
    )
  }

  // 显示用户通知
  private showUserNotification(error: AppError): void {
    const { level, userMessage, suggestions } = error

    switch (level) {
      case ErrorLevel.INFO:
        message.info(userMessage)
        break
      case ErrorLevel.WARNING:
        message.warning(userMessage)
        break
      case ErrorLevel.ERROR:
        if (suggestions && suggestions.length > 0) {
          notification.error({
            message: '操作失败',
            description: userMessage,
            duration: 6,
            style: { marginTop: '24px' }
          })
        } else {
          message.error(userMessage)
        }
        break
      case ErrorLevel.CRITICAL:
        notification.error({
          message: '严重错误',
          description: userMessage,
          duration: 0, // 不自动关闭
          style: { marginTop: '24px' }
        })
        break
    }
  }

  // 记录错误日志
  private logError(error: AppError): void {
    const logData = {
      timestamp: error.timestamp,
      type: error.type,
      level: error.level,
      code: error.code,
      message: error.message,
      context: error.context,
      stack: error.originalError?.stack
    }

    // 开发环境输出到控制台
    if (process.env.NODE_ENV === 'development') {
      console.group(`🚨 ${error.level} - ${error.type}`)
      console.error('错误信息:', error.message)
      console.error('用户信息:', error.userMessage)
      console.error('原始错误:', error.originalError)
      console.error('上下文:', error.context)
      console.groupEnd()
    }

    // 生产环境发送到日志服务
    if (process.env.NODE_ENV === 'production') {
      // TODO: 集成日志服务（如 Sentry, LogRocket 等）
      this.sendToLogService(logData)
    }
  }

  // 发送到日志服务
  private sendToLogService(logData: unknown): void {
    // TODO: 实现日志服务集成
    console.log('发送错误日志:', logData)
  }

  // 检查是否为应用错误
  private isAppError(error: unknown): error is AppError {
    return error && typeof error === 'object' && 'type' in error && 'level' in error
  }

  // 获取错误历史
  getErrorHistory(): AppError[] {
    return [...this.errorQueue]
  }

  // 清空错误历史
  clearErrorHistory(): void {
    this.errorQueue = []
  }
}

// 便捷的错误处理函数
export const errorHandler = ErrorHandler.getInstance()

// 特定类型的错误处理函数
export const handleValidationError = (message: string, context?: Record<string, unknown>) => {
  const error = errorHandler.createError(
    ErrorType.VALIDATION,
    ErrorLevel.WARNING,
    'VALIDATION_ERROR',
    message,
    undefined,
    context
  )
  errorHandler.handleError(error)
}

export const handleNetworkError = (error: Error, context?: Record<string, unknown>) => {
  const appError = errorHandler.createError(
    ErrorType.NETWORK,
    ErrorLevel.ERROR,
    'NETWORK_ERROR',
    error.message,
    error,
    context
  )
  errorHandler.handleError(appError)
}

export const handleDatabaseError = (error: Error, context?: Record<string, unknown>) => {
  const appError = errorHandler.createError(
    ErrorType.DATABASE,
    ErrorLevel.ERROR,
    'DATABASE_ERROR',
    error.message,
    error,
    context
  )
  errorHandler.handleError(appError)
}

export const handleAuthError = (message: string, context?: Record<string, unknown>) => {
  const error = errorHandler.createError(
    ErrorType.AUTHENTICATION,
    ErrorLevel.ERROR,
    'AUTH_ERROR',
    message,
    undefined,
    context
  )
  errorHandler.handleError(error)
}

export const handleBusinessError = (message: string, context?: Record<string, unknown>) => {
  const error = errorHandler.createError(
    ErrorType.BUSINESS,
    ErrorLevel.ERROR,
    'BUSINESS_ERROR',
    message,
    undefined,
    context
  )
  errorHandler.handleError(error)
}

// 导出默认错误处理器
export default errorHandler 