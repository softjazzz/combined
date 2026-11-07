import { beforeEach, describe, expect, it } from 'vitest'
import type { InternalAxiosRequestConfig } from 'axios'
import { apiClient } from '@/services/apiService'
import { http } from '@/utils/http'

describe.each([
  { name: 'ApiService', client: apiClient },
  { name: 'http', client: http },
])('$name业务元数据请求路由', ({ client }) => {
  beforeEach(() => {
    localStorage.clear()
    window.history.replaceState({}, '', '/workstation-v5/rules?tab=semantic')
  })

  it.each([
    ['rule-sets', 'get', undefined],
    ['batch-jobs', 'get', undefined],
    ['rule-sets', 'post', 'independent_cdm'],
    ['batch-jobs', 'post', 'independent_cdm'],
  ])('%s %s保留认证且仅GET不附加临床来源', async (collection, method, expected) => {
    const sent: InternalAxiosRequestConfig[] = []
    await client.request({
      url: `/api/v1/qc/sichuan/workspace/${collection}?page=1`,
      method,
      headers: { Authorization: 'Bearer synthetic-metadata-test' },
      adapter: async (config) => {
        sent.push(config)
        return { config, status: 200, statusText: 'OK', headers: {}, data: { success: true, data: {} } }
      },
    })
    expect(sent).toHaveLength(1)
    expect(sent[0].headers.get('X-Clinical-Source')).toBe(expected)
    expect(sent[0].headers.get('Authorization')).toBe('Bearer synthetic-metadata-test')
  })
})
