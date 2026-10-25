// @ts-nocheck
/**
 * 认证和权限管理相关类型定义
 * 病案质控系统 - 用户认证与权限控制
 */

interface BaseAuthUser {
  id: string
  email?: string
}

// 用户角色枚举
export enum UserRole {
  ADMIN = 'admin',
  QC_MANAGER = 'qc_manager',
  QC_STAFF = 'qc_staff',
  DOCTOR = 'doctor',
}

// API保留原角色，并为sync_admin返回运行时继承的管理角色。
export type AuthUserRole = UserRole | 'sync_admin' | 'super_admin' | 'developer'

// 权限操作枚举
export enum PermissionAction {
  CREATE = 'create',
  READ = 'read',
  UPDATE = 'update',
  DELETE = 'delete',
  ANALYZE = 'analyze',
  REVIEW = 'review',
  MANAGE = 'manage',
  EXPORT = 'export',
}

// 资源类型枚举
export enum ResourceType {
  MEDICAL_RECORDS = 'medical_records',
  QC_RESULTS = 'qc_results',
  QC_RULES = 'qc_rules',
  USERS = 'users',
  STATISTICS = 'statistics',
  SETTINGS = 'settings',
}

// 扩展的用户信息接口
export interface User extends BaseAuthUser {
  id: string
  email?: string
  display_name?: string
  department?: string
  hospital_id?: string
  institute_id?: string
  roles?: AuthUserRole[]
  permissions?: Permission[]
  is_active?: boolean
  last_login?: string
  created_at?: string
  updated_at?: string
  is_demo_account?: boolean
}

// 用户角色数据库记录
export interface UserRoleRecord {
  id: string
  user_id: string
  role: UserRole
  hospital_id?: string
  department?: string
  created_at: string
  updated_at?: string
}

// 权限定义
export interface Permission {
  id: string
  resource: ResourceType
  action: PermissionAction
  conditions?: PermissionCondition[]
}

// 权限条件
export interface PermissionCondition {
  field: string
  operator: 'eq' | 'neq' | 'in' | 'nin' | 'gt' | 'gte' | 'lt' | 'lte'
  value: Record<string, unknown>
}

// 权限检查结果
export interface PermissionCheckResult {
  allowed: boolean
  reason?: string
  conditions?: PermissionCondition[]
}

// 角色权限映射
export interface RolePermissions {
  [UserRole.ADMIN]: Permission[]
  [UserRole.QC_MANAGER]: Permission[]
  [UserRole.QC_STAFF]: Permission[]
  [UserRole.DOCTOR]: Permission[]
}

// 登录请求
export interface LoginRequest {
  account: string
  email?: string
  password: string
  role?: string // 改为字符串类型，与后端API保持一致
  remember_me?: boolean
}

// 登录响应
export interface LoginResponse {
  access_token: string
  refresh_token?: string
  token_type?: string
  expires_in?: number
  user: User
}

// 注册请求
export interface RegisterRequest {
  username?: string
  institute_id?: string
  email: string
  password: string
  display_name: string
  department: string
  hospital_id?: string
  role?: UserRole
}

// 注册响应
export interface RegisterResponse {
  success: boolean
  user?: User
  error?: string
}

// 密码重置请求
export interface PasswordResetRequest {
  email: string
}

// 密码更新请求
export interface PasswordUpdateRequest {
  current_password: string
  new_password: string
}

// 用户档案更新请求
export interface ProfileUpdateRequest {
  display_name?: string
  department?: string
  hospital_id?: string
}

// 会话信息
export interface SessionInfo {
  user: User
  token: string
  expires_at: string
  last_activity: string
}

// 多因素认证相关
export interface MFASetupRequest {
  type: 'totp' | 'sms' | 'email'
  phone?: string
}

export interface MFAVerifyRequest {
  code: string
  type: 'totp' | 'sms' | 'email'
}

// 审计日志
export interface AuditLog {
  id: string
  user_id: string
  action: string
  resource_type: ResourceType
  resource_id?: string
  details?: Record<string, unknown>
  ip_address?: string
  user_agent?: string
  created_at: string
}

// 安全策略
export interface SecurityPolicy {
  password_min_length: number
  password_require_uppercase: boolean
  password_require_lowercase: boolean
  password_require_numbers: boolean
  password_require_symbols: boolean
  password_expire_days: number
  max_login_attempts: number
  lockout_duration_minutes: number
  session_timeout_minutes: number
  require_mfa: boolean
  allowed_ip_ranges?: string[]
}

// 用户状态
export enum UserStatus {
  ACTIVE = 'active',
  INACTIVE = 'inactive',
  LOCKED = 'locked',
  SUSPENDED = 'suspended',
}

// 用户管理相关
export interface UserListItem {
  id: string
  email: string
  display_name: string
  department: string
  roles: UserRole[]
  status: UserStatus
  last_login?: string
  created_at: string
}

export interface CreateUserRequest {
  email: string
  password: string
  display_name: string
  department: string
  hospital_id?: string
  roles: UserRole[]
}

export interface UpdateUserRequest {
  display_name?: string
  department?: string
  hospital_id?: string
  roles?: UserRole[]
  status?: UserStatus
}

// 权限检查函数类型
export type PermissionChecker = (
  user: User,
  resource: ResourceType,
  action: PermissionAction,
  context?: Record<string, unknown>,
) => Promise<PermissionCheckResult>

// 认证状态
export interface AuthState {
  user: User | null
  loading: boolean
  initialized: boolean
  sessionExpiry: Date | null
}

// 认证配置
export interface AuthConfig {
  autoRefreshToken: boolean
  persistSession: boolean
  detectSessionInUrl: boolean
  sessionTimeout: number
  refreshThreshold: number
}
