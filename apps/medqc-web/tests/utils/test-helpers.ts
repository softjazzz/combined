/**
 * 测试辅助工具函数
 */

import { mount, VueWrapper } from '@vue/test-utils'
import { createPinia } from 'pinia'
import type { ComponentPublicInstance } from 'vue'

/**
 * 创建测试用的 Pinia 实例
 */
export function createTestPinia() {
  return createPinia()
}

/**
 * 挂载组件的辅助函数
 */
export function mountWithPinia(component: any, options: any = {}) {
  return mount(component, {
    global: {
      plugins: [createTestPinia()],
      ...options.global
    },
    ...options
  })
}

/**
 * 等待异步操作完成
 */
export async function flushPromises() {
  return new Promise((resolve) => setTimeout(resolve, 0))
}

/**
 * 模拟延迟
 */
export function delay(ms: number) {
  return new Promise((resolve) => setTimeout(resolve, ms))
}

/**
 * 创建 Mock 用户
 */
export function createMockUser(overrides: any = {}) {
  return {
    id: 'user-001',
    email: 'test@example.com',
    display_name: '测试用户',
    roles: ['doctor'],
    department: '心内科',
    is_active: true,
    ...overrides
  }
}

/**
 * 创建 Mock 病历记录
 */
export function createMockRecord(overrides: any = {}) {
  return {
    id: 'record-001',
    patient_name: '张三',
    patient_age: 45,
    patient_gender: 'M',
    department: '心内科',
    admission_date: '2024-01-01',
    record_type: 'inpatient',
    content: '患者主诉胸痛...',
    status: 'pending',
    created_at: '2024-01-01T10:00:00Z',
    updated_at: '2024-01-01T10:00:00Z',
    qc_score: 85,
    ...overrides
  }
}

/**
 * 创建 Mock 质控结果
 */
export function createMockQCResult(overrides: any = {}) {
  return {
    id: 'qc-001',
    recordId: 'record-001',
    overallScore: 82,
    overallGrade: 'B',
    analysisDate: '2024-01-01T10:00:00Z',
    issues: [],
    suggestions: [],
    ruleResults: [],
    ...overrides
  }
}

/**
 * 创建 Mock 质控问题
 */
export function createMockIssue(overrides: any = {}) {
  return {
    id: 'issue-001',
    ruleName: '主诉完整性检查',
    ruleId: 'rule-001',
    description: '主诉描述不完整',
    severity: 'major',
    category: '内容完整性',
    location: '主诉',
    suggestion: '请补充完整的主诉信息',
    canAppeal: true,
    ...overrides
  }
}

/**
 * 模拟 localStorage
 */
export function mockLocalStorage() {
  const store: Record<string, string> = {}

  return {
    getItem: (key: string) => store[key] || null,
    setItem: (key: string, value: string) => {
      store[key] = value
    },
    removeItem: (key: string) => {
      delete store[key]
    },
    clear: () => {
      Object.keys(store).forEach((key) => delete store[key])
    }
  }
}

/**
 * 模拟 API 响应
 */
export function createMockApiResponse<T>(data: T, success = true) {
  return {
    success,
    data,
    message: success ? '操作成功' : '操作失败',
    error: success ? undefined : '错误信息'
  }
}

/**
 * 模拟分页响应
 */
export function createMockPaginatedResponse<T>(data: T[], page = 1, pageSize = 20) {
  return {
    data,
    pagination: {
      page,
      pageSize,
      total: data.length,
      totalPages: Math.ceil(data.length / pageSize)
    }
  }
}

/**
 * 触发组件事件
 */
export async function triggerEvent(
  wrapper: VueWrapper<ComponentPublicInstance>,
  selector: string,
  event: string
) {
  const element = wrapper.find(selector)
  if (element.exists()) {
    await element.trigger(event)
  }
}

/**
 * 设置输入框值
 */
export async function setInputValue(
  wrapper: VueWrapper<ComponentPublicInstance>,
  selector: string,
  value: string
) {
  const input = wrapper.find(selector)
  if (input.exists()) {
    await input.setValue(value)
  }
}

/**
 * 等待条件满足
 */
export async function waitFor(
  condition: () => boolean,
  timeout = 1000,
  interval = 50
): Promise<void> {
  const startTime = Date.now()

  while (!condition()) {
    if (Date.now() - startTime > timeout) {
      throw new Error('Timeout waiting for condition')
    }
    await delay(interval)
  }
}

/**
 * 模拟网络请求延迟
 */
export function mockNetworkDelay(ms = 100) {
  return new Promise((resolve) => setTimeout(resolve, ms))
}

/**
 * 创建 Mock 文件
 */
export function createMockFile(
  name = 'test.pdf',
  size = 1024,
  type = 'application/pdf'
): File {
  const blob = new Blob(['test content'], { type })
  return new File([blob], name, { type })
}

/**
 * 断言元素可见
 */
export function assertVisible(wrapper: VueWrapper<ComponentPublicInstance>, selector: string) {
  const element = wrapper.find(selector)
  expect(element.exists()).toBe(true)
  expect(element.isVisible()).toBe(true)
}

/**
 * 断言元素不可见
 */
export function assertHidden(wrapper: VueWrapper<ComponentPublicInstance>, selector: string) {
  const element = wrapper.find(selector)
  if (element.exists()) {
    expect(element.isVisible()).toBe(false)
  }
}

/**
 * 断言文本内容
 */
export function assertText(
  wrapper: VueWrapper<ComponentPublicInstance>,
  selector: string,
  text: string
) {
  const element = wrapper.find(selector)
  expect(element.exists()).toBe(true)
  expect(element.text()).toContain(text)
}

/**
 * 模拟成功的 API 调用
 */
export function mockSuccessfulApiCall<T>(data: T) {
  return vi.fn().mockResolvedValue({
    success: true,
    data,
    message: '操作成功'
  })
}

/**
 * 模拟失败的 API 调用
 */
export function mockFailedApiCall(error = '操作失败') {
  return vi.fn().mockResolvedValue({
    success: false,
    error,
    data: null
  })
}

/**
 * 模拟网络错误
 */
export function mockNetworkError() {
  return vi.fn().mockRejectedValue(new Error('Network Error'))
}

