import { beforeEach, describe, expect, it, vi } from 'vitest'

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

  await import('@/services/apiService')

  return {
    requestFulfilled,
    responseRejected,
  }
}

describe('apiService trace propagation', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.resetModules()
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
