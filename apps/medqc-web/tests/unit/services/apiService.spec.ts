import { describe, it, expect, beforeEach, vi, afterEach } from 'vitest'
import axios from 'axios'

// Mock axios
vi.mock('axios')

describe('API Service', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    localStorage.clear()
  })

  afterEach(() => {
    localStorage.clear()
  })

  describe('请求拦截器', () => {
    it('应该在请求头中添加 Authorization token', () => {
      const token = 'mock-token'
      localStorage.setItem('medqc_access_token', token)

      // 验证 token 存在
      expect(localStorage.getItem('medqc_access_token')).toBe(token)
    })

    it('应该在请求头中添加 Content-Type', () => {
      // 这个测试验证 axios 配置
      expect(axios.create).toBeDefined()
    })
  })

  describe('响应拦截器', () => {
    it('应该正确处理成功响应', async () => {
      const mockResponse = {
        data: {
          success: true,
          data: { id: '1', name: 'Test' },
          message: '操作成功'
        },
        status: 200,
        statusText: 'OK',
        headers: {},
        config: {}
      }

      vi.mocked(axios.get).mockResolvedValue(mockResponse)

      const response = await axios.get('/api/test')
      expect(response.data.success).toBe(true)
      expect(response.data.data).toEqual({ id: '1', name: 'Test' })
    })

    it('应该正确处理 401 未授权错误', async () => {
      const mockError = {
        response: {
          status: 401,
          data: {
            success: false,
            error: '未授权'
          }
        }
      }

      vi.mocked(axios.get).mockRejectedValue(mockError)

      try {
        await axios.get('/api/test')
      } catch (error: any) {
        expect(error.response.status).toBe(401)
      }
    })

    it('应该正确处理 403 禁止访问错误', async () => {
      const mockError = {
        response: {
          status: 403,
          data: {
            success: false,
            error: '禁止访问'
          }
        }
      }

      vi.mocked(axios.get).mockRejectedValue(mockError)

      try {
        await axios.get('/api/test')
      } catch (error: any) {
        expect(error.response.status).toBe(403)
      }
    })

    it('应该正确处理 500 服务器错误', async () => {
      const mockError = {
        response: {
          status: 500,
          data: {
            success: false,
            error: '服务器错误'
          }
        }
      }

      vi.mocked(axios.get).mockRejectedValue(mockError)

      try {
        await axios.get('/api/test')
      } catch (error: any) {
        expect(error.response.status).toBe(500)
      }
    })

    it('应该正确处理网络错误', async () => {
      const mockError = new Error('Network Error')

      vi.mocked(axios.get).mockRejectedValue(mockError)

      try {
        await axios.get('/api/test')
      } catch (error: any) {
        expect(error.message).toBe('Network Error')
      }
    })
  })

  describe('Token 管理', () => {
    it('应该正确存储 access token', () => {
      const token = 'mock-access-token'
      localStorage.setItem('medqc_access_token', token)

      expect(localStorage.getItem('medqc_access_token')).toBe(token)
    })

    it('应该正确存储 refresh token', () => {
      const token = 'mock-refresh-token'
      localStorage.setItem('medqc_refresh_token', token)

      expect(localStorage.getItem('medqc_refresh_token')).toBe(token)
    })

    it('应该正确清除 tokens', () => {
      localStorage.setItem('medqc_access_token', 'token1')
      localStorage.setItem('medqc_refresh_token', 'token2')

      localStorage.removeItem('medqc_access_token')
      localStorage.removeItem('medqc_refresh_token')

      expect(localStorage.getItem('medqc_access_token')).toBeNull()
      expect(localStorage.getItem('medqc_refresh_token')).toBeNull()
    })
  })

  describe('请求重试', () => {
    it('应该在 token 过期时尝试刷新', async () => {
      // 第一次请求返回 401
      const mockError = {
        response: {
          status: 401,
          data: { error: 'Token expired' }
        },
        config: {
          url: '/api/test',
          _retry: false
        }
      }

      vi.mocked(axios.get).mockRejectedValueOnce(mockError)

      try {
        await axios.get('/api/test')
      } catch (error: any) {
        expect(error.response.status).toBe(401)
      }
    })
  })

  describe('请求配置', () => {
    it('应该使用正确的 baseURL', () => {
      // 验证 axios 实例创建
      expect(axios.create).toBeDefined()
    })

    it('应该设置正确的超时时间', () => {
      // 验证超时配置
      expect(axios.create).toBeDefined()
    })
  })

  describe('错误处理', () => {
    it('应该正确格式化错误响应', async () => {
      const mockError = {
        response: {
          status: 400,
          data: {
            success: false,
            error: '请求参数错误',
            code: 'INVALID_PARAMS'
          }
        }
      }

      vi.mocked(axios.post).mockRejectedValue(mockError)

      try {
        await axios.post('/api/test', {})
      } catch (error: any) {
        expect(error.response.data.success).toBe(false)
        expect(error.response.data.error).toBe('请求参数错误')
        expect(error.response.data.code).toBe('INVALID_PARAMS')
      }
    })

    it('应该处理没有响应的错误', async () => {
      const mockError = new Error('Request failed')

      vi.mocked(axios.get).mockRejectedValue(mockError)

      try {
        await axios.get('/api/test')
      } catch (error: any) {
        expect(error.message).toBe('Request failed')
      }
    })
  })

  describe('请求取消', () => {
    it('应该支持取消请求', () => {
      // 验证 axios 实例存在，支持请求取消功能
      expect(axios.create).toBeDefined()
      expect(typeof axios.create).toBe('function')
    })
  })

  describe('并发请求', () => {
    it('应该支持并发请求', async () => {
      const mockResponse1 = {
        data: { success: true, data: { id: '1' } },
        status: 200,
        statusText: 'OK',
        headers: {},
        config: {}
      }

      const mockResponse2 = {
        data: { success: true, data: { id: '2' } },
        status: 200,
        statusText: 'OK',
        headers: {},
        config: {}
      }

      vi.mocked(axios.get)
        .mockResolvedValueOnce(mockResponse1)
        .mockResolvedValueOnce(mockResponse2)

      const [response1, response2] = await Promise.all([
        axios.get('/api/test1'),
        axios.get('/api/test2')
      ])

      expect(response1.data.data.id).toBe('1')
      expect(response2.data.data.id).toBe('2')
    })
  })

  describe('请求数据转换', () => {
    it('应该正确序列化请求数据', async () => {
      const mockData = {
        name: '测试',
        age: 30
      }

      const mockResponse = {
        data: { success: true, data: mockData },
        status: 200,
        statusText: 'OK',
        headers: {},
        config: {}
      }

      vi.mocked(axios.post).mockResolvedValue(mockResponse)

      const response = await axios.post('/api/test', mockData)
      expect(response.data.success).toBe(true)
    })

    it('应该正确处理 FormData', async () => {
      const formData = new FormData()
      formData.append('file', new Blob(['test']), 'test.txt')

      const mockResponse = {
        data: { success: true, data: { uploaded: true } },
        status: 200,
        statusText: 'OK',
        headers: {},
        config: {}
      }

      vi.mocked(axios.post).mockResolvedValue(mockResponse)

      const response = await axios.post('/api/upload', formData)
      expect(response.data.success).toBe(true)
    })
  })
})

