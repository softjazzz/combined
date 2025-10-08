/**
 * 统一 API 响应类型定义
 * 
 * 这些类型定义与后端的统一响应格式保持一致
 */

// ============================================================================
// 基础响应类型
// ============================================================================

/**
 * 统一成功响应格式
 */
export interface ApiSuccessResponse<T = unknown> {
  success: true;
  data: T;
  message?: string;
  trace_id?: string;
}

/**
 * 统一错误响应格式
 */
export interface ApiErrorResponse {
  success: false;
  error: string;
  code?: string;
  trace_id?: string;
  details?: Array<{
    loc: string[];
    msg: string;
    type: string;
  }>;
}

/**
 * 统一响应类型（成功或失败）
 */
export type ApiResponse<T = unknown> = ApiSuccessResponse<T> | ApiErrorResponse;

/**
 * 分页数据结构
 */
export interface PaginatedData<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

/**
 * 分页响应类型
 */
export type PaginatedResponse<T> = ApiSuccessResponse<PaginatedData<T>>;

// ============================================================================
// 类型守卫函数
// ============================================================================

/**
 * 检查响应是否为成功响应
 */
export function isSuccessResponse<T>(
  response: ApiResponse<T>
): response is ApiSuccessResponse<T> {
  return response.success === true;
}

/**
 * 检查响应是否为错误响应
 */
export function isErrorResponse(
  response: ApiResponse
): response is ApiErrorResponse {
  return response.success === false;
}

// ============================================================================
// 业务数据类型
// ============================================================================

/**
 * 病案记录
 */
export interface MedicalRecord {
  id: string;
  patient_name: string;
  patient_id: string;
  admission_date: string;
  discharge_date?: string;
  department?: string;
  diagnosis?: string;
  created_at: string;
  updated_at: string;
}

/**
 * 医疗文档
 */
export interface MedicalDocument {
  id: string;
  record_id: string;
  document_type: string;
  document_category?: string;
  content: string;
  created_at: string;
  updated_at: string;
}

/**
 * 质控规则
 */
export interface QCRule {
  rule_id: string;
  rule_name: string;
  rule_description?: string;
  rule_category?: string;
  defect_level?: string;
  is_enabled: boolean;
  created_at: string;
  updated_at: string;
}

/**
 * 质控结果
 */
export interface QCResult {
  id: string;
  record_id: string;
  rule_id: string;
  status: 'pass' | 'fail' | 'warning';
  message?: string;
  details?: Record<string, unknown>;
  created_at: string;
}

/**
 * LLM 配置
 */
export interface LLMConfig {
  id: string;
  provider: string;
  model: string;
  api_key?: string;
  base_url?: string;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

/**
 * LLM 提供商信息
 */
export interface LLMProvider {
  id: string;
  name: string;
  display_name: string;
  description?: string;
  is_active: boolean;
}

/**
 * LLM 模型信息
 */
export interface LLMModel {
  id: string;
  provider_id: string;
  model_name: string;
  display_name: string;
  description?: string;
  is_active: boolean;
}

/**
 * 用户信息
 */
export interface User {
  id: string;
  email: string;
  username?: string;
  role?: string;
  created_at: string;
  updated_at: string;
}

/**
 * 登录响应
 */
export interface LoginResponse {
  access_token: string;
  token_type: string;
  user: User;
}

/**
 * 系统健康状态
 */
export interface HealthStatus {
  status: 'healthy' | 'unhealthy';
  version?: string;
  timestamp: string;
  services?: Record<string, {
    status: 'up' | 'down';
    message?: string;
  }>;
}

/**
 * 系统指标
 */
export interface SystemMetrics {
  cpu_usage?: number;
  memory_usage?: number;
  disk_usage?: number;
  uptime?: number;
  timestamp: string;
}

// ============================================================================
// 请求参数类型
// ============================================================================

/**
 * 分页查询参数
 */
export interface PaginationParams {
  page?: number;
  page_size?: number;
  sort_by?: string;
  sort_order?: 'asc' | 'desc';
}

/**
 * 质控分析请求
 */
export interface QCAnalysisRequest {
  record_id: string;
  rule_ids?: string[];
  options?: Record<string, unknown>;
}

/**
 * 批量质控分析请求
 */
export interface BatchQCAnalysisRequest {
  record_ids: string[];
  rule_ids?: string[];
  options?: Record<string, unknown>;
}

/**
 * 创建文档请求
 */
export interface CreateDocumentRequest {
  record_id: string;
  document_type: string;
  document_category?: string;
  content: string;
}

/**
 * 更新文档请求
 */
export interface UpdateDocumentRequest {
  document_type?: string;
  document_category?: string;
  content?: string;
}

/**
 * 登录请求
 */
export interface LoginRequest {
  email: string;
  password: string;
}

/**
 * 注册请求
 */
export interface RegisterRequest {
  email: string;
  password: string;
  username?: string;
}

// ============================================================================
// 辅助类型
// ============================================================================

/**
 * 文档类型
 */
export type DocumentType = 
  | '入院记录'
  | '首次病程记录'
  | '病程记录'
  | '查房记录'
  | '手术记录'
  | '术前小结'
  | '术前讨论'
  | '检验检查'
  | '其他';

/**
 * 缺陷等级
 */
export type DefectLevel = 'A' | 'B' | 'C' | 'D';

/**
 * 质控状态
 */
export type QCStatus = 'pending' | 'in_progress' | 'completed' | 'failed';

/**
 * 排序顺序
 */
export type SortOrder = 'asc' | 'desc';

