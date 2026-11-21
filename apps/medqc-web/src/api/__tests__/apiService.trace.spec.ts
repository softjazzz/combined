import { beforeEach, describe, expect, it, vi } from 'vitest'
import { clearAuthTokens, getRefreshToken } from '@/utils/auth-token'

type InterceptorFn = (value: any) => any

const mockMessageError = vi.fn()

vi.mock('ant-design-vue', () => ({
  message: {
    error: mockMessageError,
  },
}))

vi.mock('@/utils/auth-token', () => ({
  getAccessToken: vi.fn(() => null),
  getRefreshToken: vi.fn(() => null),
  setAccessToken: vi.fn(),
  setRefreshToken: vi.fn(),
  clearAuthTokens: vi.fn(),
}))

async function loadApiServiceWithAxiosMock() {
  let requestFulfilled: InterceptorFn | undefined
  let responseRejected: InterceptorFn | undefined
  let responseFulfilled: InterceptorFn | undefined

  const apiClientMock = {
    interceptors: {
      request: {
        use: vi.fn((fulfilled: InterceptorFn) => {
          requestFulfilled = fulfilled
          return 0
        }),
      },
      response: {
        use: vi.fn((_fulfilled: InterceptorFn, rejected: InterceptorFn) => {
          responseFulfilled = _fulfilled
          responseRejected = rejected
          return 0
        }),
      },
    },
    get: vi.fn(),
    post: vi.fn(),
    put: vi.fn(),
    delete: vi.fn(),
  }

  const axiosMock = {
    create: vi.fn(() => apiClientMock),
    post: vi.fn(),
  }

  vi.doMock('axios', () => ({
    default: axiosMock,
  }))

  const { ApiService } = await import('@/services/apiService')

  return {
    requestFulfilled,
    responseRejected,
    responseFulfilled,
    ApiService,
    get: apiClientMock.get,
    post: apiClientMock.post,
  }
}

describe('apiService trace propagation', () => {
  it.each(['/api/v1/auth/register', '/api/v1/auth/registration-status'])('%s的401不清理现有会话或自动重放', async (url) => {
    const { responseRejected } = await loadApiServiceWithAxiosMock()
    const error = { config: { method: 'post', url }, response: { status: 401, data: { detail: '账号或口令不正确' } } }
    await expect(responseRejected!(error)).rejects.toBe(error)
    expect(getRefreshToken).not.toHaveBeenCalled()
    expect(clearAuthTokens).not.toHaveBeenCalled()
    expect(error.config).not.toHaveProperty('_retry')
  })
  it('账号创建口令和登录令牌不进入调试日志，原请求响应不变', async () => {
    vi.stubEnv('VITE_API_DEBUG', 'true')
    const log = vi.spyOn(console, 'log').mockImplementation(() => undefined)
    try {
      const { requestFulfilled, responseFulfilled } = await loadApiServiceWithAxiosMock()
      const password = 'synthetic-initial-password-never-log'
      const accessToken = 'synthetic-access-token-never-log'
      const request = {
        method: 'post',
        url: '/api/v1/account-management',
        headers: {},
        data: { password },
      }
      const response = {
        config: { method: 'post', url: '/api/v1/auth/login' },
        status: 200,
        data: { access_token: accessToken, nested: { password_hash: password } },
      }
      requestFulfilled!(request)
      responseFulfilled!(response)
      const output = JSON.stringify(log.mock.calls)
      expect(output).not.toContain(password)
      expect(output).not.toContain(accessToken)
      expect(request.data.password).toBe(password)
      expect(response.data.access_token).toBe(accessToken)
    } finally {
      log.mockRestore()
    }
  })
  beforeEach(() => {
    vi.clearAllMocks()
    vi.resetModules()
    vi.unstubAllEnvs()
  })

  it('只给病历池列表请求留出更长的等待时间，保留调用者的超时覆盖', async () => {
    const { ApiService, get } = await loadApiServiceWithAxiosMock()
    await ApiService.getRaw('/api/medical-records/workstation', { page: 1 })
    await ApiService.getRaw('/api/v1/notifications')
    await ApiService.getRaw('/api/medical-records/workstation', {}, { timeout: 2000 })
    expect(get).toHaveBeenNthCalledWith(1, '/api/medical-records/workstation', {
      timeout: 30000, params: { page: 1 },
    })
    expect(get).toHaveBeenNthCalledWith(2, '/api/v1/notifications', { params: undefined })
    expect(get).toHaveBeenNthCalledWith(3, '/api/medical-records/workstation', { timeout: 2000, params: {} })
  })

  it.each(['ECONNABORTED', 'ERR_CANCELED'])('后台摘要读取 %s 由页面处理，不弹列表错误', async (code) => {
    const { responseRejected } = await loadApiServiceWithAxiosMock()
    const error = {
      code,
      config: { method: 'get', url: '/api/medical-records/workstation', params: { qc_summary_mode: 'only' } },
      message: '合成请求终止',
    }
    await expect(responseRejected!(error)).rejects.toBe(error)
    expect(mockMessageError).not.toHaveBeenCalled()
  })

  it.each([
    { code: 'ERR_CANCELED', response: undefined },
    { code: 'ECONNABORTED', response: undefined },
    { code: 'ERR_NETWORK', response: undefined },
    { code: undefined, response: { status: 503, headers: { 'x-trace-id': 'summary-trace' } } },
  ])('新 POST 后台摘要失败由页面处理，保留错误原值 $code', async ({ code, response }) => {
    const { responseRejected } = await loadApiServiceWithAxiosMock()
    const errorLog = vi.spyOn(console, 'error').mockImplementation(() => undefined)
    try {
      const error = {
        code,
        response,
        config: { method: 'post', url: '/api/medical-records/workstation/qc-summary' },
        message: '合成后台摘要异常',
      }
      await expect(responseRejected!(error)).rejects.toBe(error)
      expect(mockMessageError).not.toHaveBeenCalled()
      if (code === 'ERR_CANCELED') expect(errorLog).not.toHaveBeenCalled()
      if (response) expect(error).toHaveProperty('traceId', 'summary-trace')
    } finally {
      errorLog.mockRestore()
    }
  })

  it('后台摘要 POST 使用 30 秒超时并在调试日志中隐去三键', async () => {
    vi.stubEnv('VITE_API_DEBUG', 'true')
    const log = vi.spyOn(console, 'log').mockImplementation(() => undefined)
    try {
      const { ApiService, post, requestFulfilled } = await loadApiServiceWithAxiosMock()
      const url = '/api/medical-records/workstation/qc-summary'
      const recordKey = '["SYNTHETIC-INSTITUTE","SYNTHETIC-PATIENT","SYNTHETIC-VISIT"]'
      const body = { record_keys: [recordKey] }
      await ApiService.postRaw(url, body)
      await ApiService.postRaw(url, body, { timeout: 2000 })
      await ApiService.postRaw('/api/v1/notifications', {})
      expect(post).toHaveBeenNthCalledWith(1, url, body, { timeout: 30000 })
      expect(post).toHaveBeenNthCalledWith(2, url, body, { timeout: 2000 })
      expect(post).toHaveBeenNthCalledWith(3, '/api/v1/notifications', {}, {})
      requestFulfilled!({ method: 'post', url, headers: {}, data: body })
      const output = JSON.stringify(log.mock.calls)
      expect(output).toContain('[REDACTED]')
      expect(output).not.toMatch(/SYNTHETIC-(INSTITUTE|PATIENT|VISIT)/)
      expect(body.record_keys).toEqual([recordKey])
    } finally {
      log.mockRestore()
    }
  })

  it('request interceptor injects X-Trace-ID and X-Request-ID with same value', async () => {
    const { requestFulfilled } = await loadApiServiceWithAxiosMock()
    expect(requestFulfilled).toBeTypeOf('function')

    const config: Record<string, any> = {
      method: 'post',
      url: '/api/v1/sync/trigger',
      headers: {},
      data: { source: 'pg', tier: 'tier1' },
    }

    const nextConfig = requestFulfilled!(config)
    expect(nextConfig.headers['X-Trace-ID']).toBeTruthy()
    expect(nextConfig.headers['X-Request-ID']).toBe(nextConfig.headers['X-Trace-ID'])
    expect(nextConfig.headers.traceparent).toMatch(
      /^[\da-f]{2}-[\da-f]{32}-[\da-f]{16}-[\da-f]{2}$/i,
    )
  })

  it('redacts activation_code from debug logs without mutating the request body', async () => {
    vi.stubEnv('VITE_API_DEBUG', 'true')
    const consoleSpy = vi.spyOn(console, 'log').mockImplementation(() => undefined)
    const { requestFulfilled } = await loadApiServiceWithAxiosMock()
    const activationCode = 'MQ1.private-payload.private-signature'
    const config: Record<string, any> = {
      method: 'post',
      url: '/api/v1/product-activation/activate',
      headers: {},
      data: {
        activation_code: activationCode,
        nested: [{ activation_code: activationCode }],
      },
    }

    const nextConfig = requestFulfilled!(config)
    const debugOutput = JSON.stringify(consoleSpy.mock.calls)

    expect(debugOutput).not.toContain(activationCode)
    expect(debugOutput).toContain('[REDACTED]')
    expect(nextConfig.data.activation_code).toBe(activationCode)
    expect(nextConfig.data.nested[0].activation_code).toBe(activationCode)
  })

  it('response error attaches server trace id to error object', async () => {
    const { responseRejected } = await loadApiServiceWithAxiosMock()
    expect(responseRejected).toBeTypeOf('function')

    const error: Record<string, any> = {
      config: {
        method: 'get',
        url: '/api/v1/sync/status',
      },
      response: {
        status: 500,
        headers: {
          'x-trace-id': 'trace-header-500',
        },
        data: {
          error: 'internal error',
          trace_id: 'trace-body-ignored',
        },
      },
      message: 'Request failed with status code 500',
    }

    await expect(responseRejected!(error)).rejects.toBe(error)
    expect(error.traceId).toBe('trace-header-500')
    expect(error.trace_id).toBe('trace-header-500')
    expect(error.trace).toBe('trace-header-500')
    expect(error.context?.trace_id).toBe('trace-header-500')
  })

  it('response error falls back to response body trace_id when header is absent', async () => {
    const { responseRejected } = await loadApiServiceWithAxiosMock()
    expect(responseRejected).toBeTypeOf('function')

    const error: Record<string, any> = {
      config: {
        method: 'get',
        url: '/api/v1/sync/runs',
      },
      response: {
        status: 500,
        headers: {},
        data: {
          error: 'internal error',
          trace_id: 'trace-body-500',
        },
      },
      message: 'Request failed with status code 500',
    }

    await expect(responseRejected!(error)).rejects.toBe(error)
    expect(error.traceId).toBe('trace-body-500')
    expect(error.trace_id).toBe('trace-body-500')
    expect(error.trace).toBe('trace-body-500')
  })

  it('response error uses header trace over body trace when both exist', async () => {
    const { responseRejected } = await loadApiServiceWithAxiosMock()
    expect(responseRejected).toBeTypeOf('function')

    const error: Record<string, any> = {
      config: {
        method: 'get',
        url: '/api/v1/records',
      },
      response: {
        status: 500,
        headers: {
          'x-trace-id': 'trace-header-priority',
        },
        data: {
          trace_id: 'trace-body-lower-priority',
          traceId: 'trace-body-camel-priority',
        },
      },
      message: 'Request failed with status code 500',
    }

    await expect(responseRejected!(error)).rejects.toBe(error)
    expect(error.traceId).toBe('trace-header-priority')
    expect(error.trace).toBe('trace-header-priority')
  })
})
