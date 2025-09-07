# 🔌 API 接口规范文档

**版本**: v2.0.0  
**制定时间**: 2024-12-25  
**适用范围**: 前后端并行开发  
**维护者**: Agent B (后端专家)  

---

## 📋 **接口规范说明**

### 🎯 **设计原则**
- **RESTful 设计**: 遵循 REST API 设计规范
- **统一响应格式**: 所有接口使用统一的响应结构
- **错误处理**: 标准化的错误码和错误信息
- **版本控制**: 支持 API 版本管理
- **安全认证**: 基于 JWT 的认证机制

### 📊 **通用响应格式**
```typescript
interface ApiResponse<T = any> {
  success: boolean
  data?: T
  message?: string
  error?: {
    code: string
    message: string
    details?: any
  }
  meta?: {
    total?: number
    page?: number
    limit?: number
    timestamp: string
  }
}
```

### 🔐 **认证机制**
```typescript
// 请求头
interface AuthHeaders {
  'Authorization': `Bearer ${jwt_token}`
  'Content-Type': 'application/json'
}

// JWT Payload
interface JWTPayload {
  user_id: string
  role: 'admin' | 'doctor' | 'qc_manager' | 'viewer'
  department_id?: string
  exp: number
  iat: number
}
```

---

## 🔐 **认证相关接口**

### **POST /api/auth/login**
用户登录

**请求体**:
```typescript
interface LoginRequest {
  email: string
  password: string
  remember_me?: boolean
}
```

**响应**:
```typescript
interface LoginResponse {
  user: {
    id: string
    email: string
    full_name: string
    role: string
    department_id?: string
    avatar_url?: string
  }
  tokens: {
    access_token: string
    refresh_token: string
    expires_in: number
  }
}
```

### **POST /api/auth/register**
用户注册

**请求体**:
```typescript
interface RegisterRequest {
  email: string
  password: string
  full_name: string
  role: 'doctor' | 'qc_manager' | 'viewer'
  department_id?: string
  phone?: string
}
```

### **POST /api/auth/refresh**
刷新令牌

**请求体**:
```typescript
interface RefreshRequest {
  refresh_token: string
}
```

### **POST /api/auth/logout**
用户登出

**请求体**:
```typescript
interface LogoutRequest {
  refresh_token: string
}
```

### **GET /api/auth/profile**
获取用户资料

**响应**:
```typescript
interface UserProfile {
  id: string
  email: string
  full_name: string
  role: string
  department_id?: string
  department_name?: string
  avatar_url?: string
  phone?: string
  created_at: string
  last_login?: string
}
```

---

## 📄 **医疗记录接口**

### **GET /api/records**
获取医疗记录列表

**查询参数**:
```typescript
interface RecordsQuery {
  page?: number
  limit?: number
  search?: string
  department_id?: string
  doctor_id?: string
  status?: 'draft' | 'completed' | 'reviewed'
  date_from?: string
  date_to?: string
  sort_by?: 'created_at' | 'updated_at' | 'patient_name'
  sort_order?: 'asc' | 'desc'
}
```

**响应**:
```typescript
interface RecordsListResponse {
  records: MedicalRecord[]
  pagination: {
    total: number
    page: number
    limit: number
    pages: number
  }
}

interface MedicalRecord {
  id: string
  record_number: string
  patient_name: string
  patient_id: string
  admission_date: string
  discharge_date?: string
  department_id: string
  department_name: string
  doctor_id: string
  doctor_name: string
  diagnosis_primary: string
  diagnosis_secondary?: string[]
  status: string
  qc_status?: string
  qc_score?: number
  qc_grade?: string
  created_at: string
  updated_at: string
}
```

### **POST /api/records**
创建医疗记录

**请求体**:
```typescript
interface CreateRecordRequest {
  patient_name: string
  patient_id: string
  admission_date: string
  discharge_date?: string
  department_id: string
  diagnosis_primary: string
  diagnosis_secondary?: string[]
  content: string
  attachments?: string[]
}
```

### **GET /api/records/{record_id}**
获取医疗记录详情

**响应**:
```typescript
interface RecordDetail extends MedicalRecord {
  content: string
  attachments: FileAttachment[]
  qc_results?: QCResult[]
  history: RecordHistory[]
}

interface FileAttachment {
  id: string
  filename: string
  file_type: string
  file_size: number
  url: string
  uploaded_at: string
}
```

### **PUT /api/records/{record_id}**
更新医疗记录

### **DELETE /api/records/{record_id}**
删除医疗记录

### **POST /api/records/upload**
上传医疗记录文件

**请求**: `multipart/form-data`
```typescript
interface UploadRequest {
  file: File
  record_id?: string
  metadata?: {
    patient_name?: string
    patient_id?: string
    department_id?: string
  }
}
```

**响应**:
```typescript
interface UploadResponse {
  file_id: string
  filename: string
  file_size: number
  file_type: string
  url: string
  extracted_data?: {
    patient_name?: string
    diagnosis?: string
    content_preview?: string
  }
}
```

---

## 🔍 **质控分析接口**

### **POST /api/qc/analyze**
执行质控分析

**请求体**:
```typescript
interface QCAnalyzeRequest {
  record_id: string
  rules?: string[]  // 指定质控规则，为空则使用所有激活规则
  force_reanalyze?: boolean
}
```

**响应**:
```typescript
interface QCAnalyzeResponse {
  task_id: string
  status: 'queued' | 'processing' | 'completed' | 'failed'
  estimated_time?: number
}
```

### **GET /api/qc/results/{record_id}**
获取质控结果

**响应**:
```typescript
interface QCResult {
  id: string
  record_id: string
  overall_score: number
  overall_grade: 'A' | 'B' | 'C' | 'D'
  analysis_date: string
  issues: QCIssue[]
  suggestions: QCSuggestion[]
  rule_results: RuleResult[]
}

interface QCIssue {
  id: string
  rule_id: string
  rule_name: string
  severity: 'critical' | 'major' | 'minor'
  category: string
  description: string
  location?: string
  suggestion?: string
}
```

### **GET /api/qc/tasks/{task_id}**
获取质控任务状态

### **POST /api/qc/batch-analyze**
批量质控分析

**请求体**:
```typescript
interface BatchQCRequest {
  record_ids: string[]
  rules?: string[]
  priority?: 'high' | 'normal' | 'low'
}
```

---

## 🔍 **搜索接口**

### **POST /api/search/semantic**
语义搜索

**请求体**:
```typescript
interface SemanticSearchRequest {
  query: string
  similarity_threshold?: number
  max_results?: number
  content_types?: string[]
  filters?: {
    department_id?: string
    date_range?: {
      start: string
      end: string
    }
  }
}
```

**响应**:
```typescript
interface SearchResult {
  record_id: string
  record_number: string
  patient_name: string
  diagnosis_primary: string
  content_snippet: string
  similarity_score: number
  highlight?: string[]
}
```

### **POST /api/search/similar-cases**
相似病例搜索

**请求体**:
```typescript
interface SimilarCasesRequest {
  record_id: string
  similarity_threshold?: number
  max_results?: number
}
```

### **GET /api/search/suggestions**
搜索建议

**查询参数**:
```typescript
interface SearchSuggestionsQuery {
  q: string  // 查询关键词
  limit?: number
}
```

---

## 📊 **统计分析接口**

### **GET /api/analytics/dashboard**
获取仪表板数据

**查询参数**:
```typescript
interface DashboardQuery {
  date_range?: {
    start: string
    end: string
  }
  department_id?: string
  granularity?: 'day' | 'week' | 'month'
}
```

**响应**:
```typescript
interface DashboardData {
  summary: {
    total_records: number
    completed_records: number
    avg_qc_score: number
    grade_distribution: Record<string, number>
  }
  trends: {
    date: string
    records_count: number
    avg_score: number
  }[]
  department_stats: {
    department_id: string
    department_name: string
    records_count: number
    avg_score: number
    grade_a_rate: number
  }[]
}
```

### **GET /api/analytics/reports**
获取分析报告

### **POST /api/analytics/export**
导出分析数据

---

## 🏥 **基础数据接口**

### **GET /api/departments**
获取科室列表

**响应**:
```typescript
interface Department {
  id: string
  name: string
  code: string
  description?: string
  category: string
  is_active: boolean
}
```

### **GET /api/users**
获取用户列表 (管理员权限)

### **GET /api/qc-rules**
获取质控规则列表

**响应**:
```typescript
interface QCRule {
  id: string
  name: string
  description: string
  category: string
  severity: 'critical' | 'major' | 'minor'
  rule_type: 'completeness' | 'accuracy' | 'timeliness' | 'consistency'
  conditions: any
  is_active: boolean
}
```

---

## 🚨 **错误码规范**

### **HTTP 状态码**
- `200` - 成功
- `201` - 创建成功
- `400` - 请求参数错误
- `401` - 未认证
- `403` - 权限不足
- `404` - 资源不存在
- `409` - 资源冲突
- `422` - 数据验证失败
- `500` - 服务器内部错误

### **业务错误码**
```typescript
enum ErrorCode {
  // 认证相关
  AUTH_INVALID_CREDENTIALS = 'AUTH_001',
  AUTH_TOKEN_EXPIRED = 'AUTH_002',
  AUTH_INSUFFICIENT_PERMISSIONS = 'AUTH_003',
  
  // 记录相关
  RECORD_NOT_FOUND = 'RECORD_001',
  RECORD_INVALID_FORMAT = 'RECORD_002',
  RECORD_UPLOAD_FAILED = 'RECORD_003',
  
  // 质控相关
  QC_ANALYSIS_FAILED = 'QC_001',
  QC_RULE_NOT_FOUND = 'QC_002',
  
  // 搜索相关
  SEARCH_QUERY_INVALID = 'SEARCH_001',
  SEARCH_SERVICE_UNAVAILABLE = 'SEARCH_002'
}
```

---

## 🧪 **接口测试**

### **测试环境**
- **开发环境**: `http://localhost:8001`
- **测试环境**: `https://test-api.medqc.com`
- **生产环境**: `https://api.medqc.com`

### **测试工具**
- **Postman Collection**: `docs/api/MedQC_API.postman_collection.json`
- **OpenAPI Spec**: `docs/api/openapi.yaml`
- **测试脚本**: `tools/testing/api_tests.py`

### **认证测试**
```bash
# 获取测试 token
curl -X POST http://localhost:8001/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "test@example.com", "password": "password123"}'
```

---

## 📝 **更新日志**

### **v2.0.0** (2024-12-25)
- 初始版本发布
- 定义核心 API 接口规范
- 支持并行开发协作

### **更新规则**
1. **接口变更**: 必须通知前端开发者
2. **版本控制**: 重大变更需要版本号升级
3. **向后兼容**: 尽量保持向后兼容性
4. **文档同步**: 接口变更后立即更新文档

---

**维护者**: Agent B (后端专家)  
**审核者**: Agent A (前端专家)  
**最后更新**: 2024-12-25
