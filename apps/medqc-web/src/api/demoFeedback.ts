import { getAccessToken } from '@/utils/auth-token'

/** Feedback contains clinical text: never log request bodies or error responses. */
export async function feedbackRequest(url: string, init: RequestInit = {}): Promise<Response> {
  if (!/^\/api\/v1\/demo\/feedbacks(?:[/?]|$)/.test(url)) {
    throw new Error('无效的反馈接口')
  }
  const token = getAccessToken()
  if (!token) throw new Error('请先登录管理员账号')
  const headers = new Headers(init.headers)
  headers.set('Authorization', `Bearer ${token}`)
  const response = await fetch(url, { ...init, headers })
  if (!response.ok) {
    throw new Error(response.status === 401 ? '登录已失效，请重新登录' :
      response.status === 403 ? '此操作需要系统管理员权限' : '反馈请求失败，请稍后重试')
  }
  return response
}
