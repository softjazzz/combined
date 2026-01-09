/**
 * 科室级质控规则 API 服务
 * 
 * 提供科室规则的 CRUD 操作、发布、变更历史查询等功能
 */

import axios, { AxiosInstance } from 'axios'
import { message } from 'ant-design-vue'

// ============================================================================
// 类型定义
// ============================================================================

export enum RuleScope {
  GLOBAL = 'global',
  DEPARTMENT = 'department'
}

export enum RuleStatus {
  DRAFT = 'draft',
  PUBLISHED = 'published',
  ARCHIVED = 'archived'
}

export enum OverrideAction {
  OVERRIDE = 'override',
  DISABLE = 'disable'
}

export interface DepartmentRule {
  id: string
  rule_code: string
  name: string
  description?: string
  category: string
  severity: string
  scope: RuleScope
  department_id?: string
  parent_rule_id?: string
  override_action: OverrideAction
  override_config?: Record<string, any>
  priority: number
  status: RuleStatus
  version?: string
  effective_from?: string
  effective_to?: string
  approved_by?: string
  approved_at?: string
  check_logic?: Record<string, any>
  scoring_config?: Record<string, any>
  applicable_documents?: string[]
  is_active: boolean
  created_at: string
  updated_at: string
}

export interface DepartmentRuleCreate {
  department_id: string
  base_rule_id?: string
  rule_code: string
  name: string
  description?: string
  category: string
  severity: string
  override_action?: OverrideAction
  override_config?: Record<string, any>
  priority?: number
  status?: RuleStatus
  effective_from?: string
  effective_to?: string
  check_logic?: Record<string, any>
  scoring_config?: Record<string, any>
  applicable_documents?: string[]
}

export interface DepartmentRuleUpdate {
  name?: string
  description?: string
  severity?: string
  override_action?: OverrideAction
  override_config?: Record<string, any>
  priority?: number
  effective_from?: string
  effective_to?: string
  check_logic?: Record<string, any>
  scoring_config?: Record<string, any>
  applicable_documents?: string[]
  is_active?: boolean
}

export interface DepartmentRulePublish {
  approved_by: string
  reason?: string
}

export interface RuleChangeLog {
  id: string
  rule_id: string
  department_id?: string
  action: string
  old_values?: Record<string, any>
  new_values?: Record<string, any>
  diff?: Record<string, any>
  actor_id: string
  actor_name?: string
  actor_role?: string
  reason?: string
  ip_address?: string
  user_agent?: string
  created_at: string
}

export interface ApplicableRulesQuery {
  department_id: string
  document_type?: string
  at?: string
}

export interface ApiResponse<T = any> {
  success: boolean
  data?: T
  message?: string
  trace_id?: string
  error?: string
}

export interface PaginatedResponse<T = any> {
  success: boolean
  data: {
    items: T[]
    total: number
    page: number
    page_size: number
  }
  message?: string
  trace_id?: string
}

// ============================================================================
// API 服务类
// ============================================================================

export class DepartmentQCRulesService {
  private static instance: DepartmentQCRulesService
  private apiClient: AxiosInstance

  private constructor() {
    // 使用与主应用相同的 API 配置
    const baseURL = import.meta.env.DEV
      ? '' // 开发环境使用代理
      : (import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000')

    this.apiClient = axios.create({
      baseURL,
      timeout: 15000,
      headers: {
        'Content-Type': 'application/json',
      },
    })

    // 请求拦截器：添加认证 token
    this.apiClient.interceptors.request.use(
      (config) => {
        const token = localStorage.getItem('medqc_access_token')
        if (token) {
          config.headers.Authorization = `Bearer ${token}`
        }
        return config
      },
      (error) => Promise.reject(error)
    )

    // 响应拦截器：统一错误处理
    this.apiClient.interceptors.response.use(
      (response) => response,
      (error) => {
        if (error.response) {
          const { status, data } = error.response
          if (status === 401) {
            message.error('未授权，请重新登录')
            // 可以触发登出逻辑
          } else if (status === 403) {
            message.error('权限不足')
          } else if (status === 404) {
            message.error(data?.error || '资源不存在')
          } else if (status >= 500) {
            message.error('服务器错误，请稍后重试')
          } else {
            message.error(data?.error || '请求失败')
          }
        } else if (error.request) {
          message.error('网络错误，请检查网络连接')
        } else {
          message.error('请求配置错误')
        }
        return Promise.reject(error)
      }
    )
  }

  static getInstance(): DepartmentQCRulesService {
    if (!DepartmentQCRulesService.instance) {
      DepartmentQCRulesService.instance = new DepartmentQCRulesService()
    }
    return DepartmentQCRulesService.instance
  }

  // ============================================================================
  // API 方法
  // ============================================================================

  /**
   * 创建科室规则
   */
  async createDepartmentRule(data: DepartmentRuleCreate): Promise<DepartmentRule> {
    const response = await this.apiClient.post<ApiResponse<DepartmentRule>>(
      '/api/v1/qc/rules/department',
      data
    )
    return response.data.data!
  }

  /**
   * 更新科室规则
   */
  async updateDepartmentRule(id: string, data: DepartmentRuleUpdate): Promise<DepartmentRule> {
    const response = await this.apiClient.put<ApiResponse<DepartmentRule>>(
      `/api/v1/qc/rules/department/${id}`,
      data
    )
    return response.data.data!
  }

  /**
   * 删除科室规则
   */
  async deleteDepartmentRule(id: string): Promise<void> {
    await this.apiClient.delete(`/api/v1/qc/rules/department/${id}`)
  }

  /**
   * 发布规则
   */
  async publishDepartmentRule(id: string, data: DepartmentRulePublish): Promise<DepartmentRule> {
    const response = await this.apiClient.patch<ApiResponse<DepartmentRule>>(
      `/api/v1/qc/rules/department/${id}/publish`,
      data
    )
    return response.data.data!
  }

  /**
   * 查看变更历史
   */
  async getRuleChangeHistory(
    id: string,
    page: number = 1,
    limit: number = 20
  ): Promise<{ items: RuleChangeLog[]; total: number }> {
    const response = await this.apiClient.get<PaginatedResponse<RuleChangeLog>>(
      `/api/v1/qc/rules/department/${id}/history`,
      { params: { page, limit } }
    )
    return response.data.data
  }

  /**
   * 获取适用规则
   */
  async getApplicableRules(query: ApplicableRulesQuery): Promise<DepartmentRule[]> {
    const response = await this.apiClient.get<ApiResponse<{ rules: DepartmentRule[] }>>(
      '/api/v1/qc/rules/department/applicable',
      { params: query }
    )
    return response.data.data?.rules || []
  }

  /**
   * 获取科室规则列表
   */
  async listDepartmentRules(params: {
    department_id?: string
    status_filter?: string
    override_action?: string
    keyword?: string
    page?: number
    limit?: number
  }): Promise<{ items: DepartmentRule[]; total: number }> {
    const response = await this.apiClient.get<PaginatedResponse<DepartmentRule>>(
      '/api/v1/qc/rules/department',
      { params }
    )
    return response.data.data
  }

  /**
   * 获取单个科室规则
   */
  async getDepartmentRule(id: string): Promise<DepartmentRule> {
    const response = await this.apiClient.get<ApiResponse<DepartmentRule>>(
      `/api/v1/qc/rules/department/${id}`
    )
    return response.data.data!
  }
}

// 导出单例实例
export const departmentQCRulesService = DepartmentQCRulesService.getInstance()
