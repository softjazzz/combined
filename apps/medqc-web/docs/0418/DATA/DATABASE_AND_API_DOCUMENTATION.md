# 医疗质控系统 - 数据库表结构与 API 接口文档

## 📋 目录

- [数据库表结构](#数据库表结构)
- [API 接口文档](#api-接口文档)
- [使用示例](#使用示例)
- [错误处理](#错误处理)

---

## 🗄️ 数据库表结构

### 1. medical_records 表 - 医疗记录主表

**表名**: `medical_records`  
**描述**: 存储医疗记录的核心信息

| 字段名                | 数据类型    | 是否必填 | 默认值            | 描述                              |
| --------------------- | ----------- | -------- | ----------------- | --------------------------------- |
| `id`                  | uuid        | 是       | gen_random_uuid() | 主键，自动生成                    |
| `record_number`       | varchar     | 是       | -                 | 病历编号，唯一标识                |
| `patient_name`        | varchar     | 是       | -                 | 患者姓名                          |
| `patient_id`          | varchar     | 否       | null              | 患者身份证号/病历号               |
| `patient_age`         | integer     | 否       | null              | 患者年龄                          |
| `patient_gender`      | varchar     | 否       | null              | 患者性别                          |
| `department_id`       | uuid        | 是       | -                 | 科室ID，外键关联 departments 表   |
| `doctor_id`           | uuid        | 否       | null              | 医生ID，外键关联 user_profiles 表 |
| `admission_date`      | date        | 否       | null              | 入院日期                          |
| `discharge_date`      | date        | 否       | null              | 出院日期                          |
| `record_type`         | varchar     | 是       | 'inpatient'       | 记录类型：inpatient/outpatient    |
| `diagnosis_primary`   | text        | 否       | null              | 主要诊断                          |
| `diagnosis_secondary` | array       | 否       | null              | 次要诊断列表                      |
| `content`             | text        | 是       | -                 | 病历内容                          |
| `content_sections`    | jsonb       | 否       | {}                | 结构化内容分段                    |
| `file_attachments`    | jsonb       | 否       | []                | 附件文件信息                      |
| `total_pages`         | integer     | 否       | 1                 | 总页数                            |
| `word_count`          | integer     | 否       | 0                 | 字数统计                          |
| `status`              | varchar     | 否       | 'pending'         | 状态：pending/completed/failed    |
| `qc_score`            | numeric     | 否       | null              | 质控评分                          |
| `qc_grade`            | varchar     | 否       | null              | 质控等级                          |
| `priority_level`      | integer     | 否       | 1                 | 优先级：1-5                       |
| `tags`                | array       | 否       | null              | 标签列表                          |
| `metadata`            | jsonb       | 否       | {}                | 元数据信息                        |
| `created_by`          | uuid        | 是       | -                 | 创建者ID                          |
| `created_at`          | timestamptz | 否       | now()             | 创建时间                          |
| `updated_at`          | timestamptz | 否       | now()             | 更新时间                          |

### 2. departments 表 - 科室信息表

**表名**: `departments`  
**描述**: 存储医院科室信息

| 字段名          | 数据类型    | 是否必填 | 默认值            | 描述           |
| --------------- | ----------- | -------- | ----------------- | -------------- |
| `id`            | uuid        | 是       | gen_random_uuid() | 主键           |
| `name`          | varchar     | 是       | -                 | 科室名称       |
| `code`          | varchar     | 是       | -                 | 科室代码，唯一 |
| `description`   | text        | 否       | null              | 科室描述       |
| `category`      | varchar     | 是       | 'clinical'        | 科室类别       |
| `parent_id`     | uuid        | 否       | null              | 上级科室ID     |
| `director_id`   | uuid        | 否       | null              | 科室主任ID     |
| `contact_phone` | varchar     | 否       | null              | 联系电话       |
| `location`      | varchar     | 否       | null              | 科室位置       |
| `is_active`     | boolean     | 否       | true              | 是否启用       |
| `sort_order`    | integer     | 否       | 0                 | 排序序号       |
| `created_at`    | timestamptz | 否       | now()             | 创建时间       |
| `updated_at`    | timestamptz | 否       | now()             | 更新时间       |

### 3. user_profiles 表 - 用户信息表

**表名**: `user_profiles`  
**描述**: 存储用户个人信息和权限

| 字段名           | 数据类型    | 是否必填 | 默认值            | 描述           |
| ---------------- | ----------- | -------- | ----------------- | -------------- |
| `id`             | uuid        | 是       | gen_random_uuid() | 主键           |
| `user_id`        | uuid        | 否       | null              | 关联认证用户ID |
| `username`       | varchar     | 是       | -                 | 用户名，唯一   |
| `full_name`      | varchar     | 是       | -                 | 真实姓名       |
| `email`          | varchar     | 是       | -                 | 邮箱地址       |
| `phone`          | varchar     | 否       | null              | 手机号码       |
| `avatar_url`     | text        | 否       | null              | 头像URL        |
| `department_id`  | uuid        | 否       | null              | 所属科室ID     |
| `role_type`      | varchar     | 是       | 'doctor'          | 角色类型       |
| `job_title`      | varchar     | 否       | null              | 职务           |
| `license_number` | varchar     | 否       | null              | 执业证号       |
| `is_active`      | boolean     | 否       | true              | 是否启用       |
| `last_login_at`  | timestamptz | 否       | null              | 最后登录时间   |
| `created_at`     | timestamptz | 否       | now()             | 创建时间       |
| `updated_at`     | timestamptz | 否       | now()             | 更新时间       |
| `password_hash`  | text        | 否       | null              | 密码哈希       |
| `role`           | varchar     | 否       | null              | 角色权限       |

### 4. qc_results 表 - 质控结果表

**表名**: `qc_results`  
**描述**: 存储质控分析结果

| 字段名              | 数据类型    | 描述           |
| ------------------- | ----------- | -------------- |
| `id`                | uuid        | 主键           |
| `medical_record_id` | uuid        | 关联医疗记录ID |
| `rule_id`           | uuid        | 质控规则ID     |
| `score`             | numeric     | 质控得分       |
| `grade`             | varchar     | 质控等级       |
| `issues`            | jsonb       | 发现的问题列表 |
| `suggestions`       | jsonb       | 改进建议       |
| `created_at`        | timestamptz | 创建时间       |

### 5. qc_rules 表 - 质控规则表

**表名**: `qc_rules`  
**描述**: 存储质控规则配置

| 字段名        | 数据类型    | 描述     |
| ------------- | ----------- | -------- |
| `id`          | uuid        | 主键     |
| `name`        | varchar     | 规则名称 |
| `description` | text        | 规则描述 |
| `rule_config` | jsonb       | 规则配置 |
| `is_active`   | boolean     | 是否启用 |
| `created_at`  | timestamptz | 创建时间 |

---

## 🔌 API 接口文档

### 基础信息

**服务地址**: `http://localhost:8002`  
**API 版本**: v2.0.0  
**内容类型**: `application/json`

### 1. 系统接口

#### 1.1 健康检查

```http
GET /api/v1/health
```

**响应示例**:

```json
{
  "status": "healthy",
  "service": "medical_qc_api_supabase",
  "version": "2.0.0",
  "timestamp": "2025-08-29T14:38:09.589Z",
  "supabase_status": "connected",
  "message": "医疗质控系统API运行正常"
}
```

#### 1.2 根路径信息

```http
GET /
```

### 2. 文件解析接口

#### 2.1 解析医疗文件

```http
POST /api/parse-medical-file-public
Content-Type: multipart/form-data
```

**请求参数**:

- `file`: 文件对象 (PDF/TXT/DOC/DOCX)
- `options`: JSON字符串，解析选项 (可选)

**响应示例**:

```json
{
  "success": true,
  "data": {
    "content": "解析出的文本内容",
    "method": "PyMuPDF (fitz) - 高性能PDF文本提取",
    "pages": 5,
    "medical_info": {
      "patient_age": 45,
      "patient_gender": "男",
      "diagnosis": ["头痛"]
    },
    "file_info": {
      "filename": "test.pdf",
      "size": 1024,
      "type": "application/pdf"
    }
  },
  "tokensUsed": 0
}
```

### 3. 医疗记录接口

#### 3.1 智能导入医疗记录

```http
POST /api/smart-import
Content-Type: application/json
```

**请求体**:

```json
{
  "patient_name": "患者姓名",
  "content": "病历内容",
  "file_info": {
    "filename": "test.pdf",
    "size": 1024,
    "type": "application/pdf"
  },
  "parse_result": {
    "method": "PDF解析",
    "medical_info": {
      "patient_age": 45,
      "patient_gender": "男",
      "diagnosis": ["头痛"]
    }
  }
}
```

**响应示例**:

```json
{
  "id": "0537e405-6567-45d3-a9de-993ca1ab8e80",
  "record_number": "SMART_20250829_143808",
  "patient_name": "测试患者",
  "patient_age": 45,
  "patient_gender": "男",
  "department_id": "11111111-1111-1111-1111-111111111111",
  "diagnosis_primary": "头痛",
  "content": "病历内容...",
  "status": "pending",
  "tags": ["智能导入"],
  "created_at": "2025-08-29T14:38:09.589Z"
}
```

#### 3.2 创建医疗记录（完整版）

```http
POST /api/medical-records
Content-Type: application/json
```

**请求体**:

```json
{
  "record_number": "MR20250829001",
  "patient_name": "张三",
  "patient_id": "110101199001011234",
  "patient_age": 35,
  "patient_gender": "男",
  "department_id": "11111111-1111-1111-1111-111111111111",
  "doctor_id": "22222222-2222-2222-2222-222222222222",
  "record_type": "inpatient",
  "diagnosis_primary": "高血压",
  "diagnosis_secondary": ["糖尿病", "冠心病"],
  "content": "详细病历内容...",
  "priority_level": 2,
  "tags": ["急诊", "重点关注"],
  "metadata": {
    "import_method": "manual",
    "source": "HIS系统"
  },
  "created_by": "22222222-2222-2222-2222-222222222222"
}
```

#### 3.3 获取医疗记录列表

```http
GET /api/medical-records?page=1&page_size=10&status=pending&department_id=xxx
```

**查询参数**:

- `page`: 页码 (默认: 1)
- `page_size`: 每页数量 (默认: 10)
- `status`: 状态筛选 (可选)
- `department_id`: 科室筛选 (可选)

**响应示例**:

```json
{
  "data": [
    {
      "id": "0537e405-6567-45d3-a9de-993ca1ab8e80",
      "record_number": "SMART_20250829_143808",
      "patient_name": "测试患者",
      "status": "pending",
      "created_at": "2025-08-29T14:38:09.589Z"
    }
  ],
  "page": 1,
  "page_size": 10,
  "total": 1
}
```

#### 3.4 获取单个医疗记录

```http
GET /api/medical-records/{record_id}
```

### 4. 调试接口

#### 4.1 创建测试数据

```http
POST /api/debug/create-test-data
```

**响应示例**:

```json
{
  "message": "测试数据创建完成",
  "results": [
    {
      "type": "department",
      "status": "created",
      "data": [{ "id": "11111111-1111-1111-1111-111111111111" }]
    },
    {
      "type": "user",
      "status": "created",
      "data": [{ "id": "22222222-2222-2222-2222-222222222222" }]
    }
  ]
}
```

#### 4.2 调试表信息

```http
GET /api/debug/tables
```

---

## 📝 使用示例

### 完整的智能导入流程

```javascript
// 1. 解析文件
const formData = new FormData()
formData.append('file', fileObject)
formData.append('options', '{}')

const parseResponse = await fetch('http://localhost:8002/api/parse-medical-file-public', {
  method: 'POST',
  body: formData,
})

const parseResult = await parseResponse.json()

// 2. 智能导入到数据库
const importResponse = await fetch('http://localhost:8002/api/smart-import', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
  },
  body: JSON.stringify({
    patient_name: '患者姓名',
    content: parseResult.data.content,
    file_info: parseResult.data.file_info,
    parse_result: parseResult.data,
  }),
})

const medicalRecord = await importResponse.json()
console.log('创建的医疗记录:', medicalRecord)

// 3. 查询记录列表
const listResponse = await fetch('http://localhost:8002/api/medical-records?page=1&page_size=10')
const recordList = await listResponse.json()
```

### 前端 Vue 组件集成示例

```vue
<script setup lang="ts">
import { ref } from 'vue'

const isUploading = ref(false)
const uploadResult = ref(null)

const handleFileUpload = async (file: File) => {
  isUploading.value = true

  try {
    // 1. 解析文件
    const formData = new FormData()
    formData.append('file', file)

    const parseResponse = await fetch('http://localhost:8002/api/parse-medical-file-public', {
      method: 'POST',
      body: formData,
    })

    const parseResult = await parseResponse.json()

    if (!parseResult.success) {
      throw new Error(parseResult.error)
    }

    // 2. 智能导入
    const importResponse = await fetch('http://localhost:8002/api/smart-import', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        patient_name: '从解析结果中提取或用户输入',
        content: parseResult.data.content,
        file_info: parseResult.data.file_info,
        parse_result: parseResult.data,
      }),
    })

    uploadResult.value = await importResponse.json()
  } catch (error) {
    console.error('上传失败:', error)
  } finally {
    isUploading.value = false
  }
}
</script>
```

---

## ⚠️ 错误处理

### 常见错误码

| HTTP状态码 | 错误类型              | 描述           |
| ---------- | --------------------- | -------------- |
| 400        | Bad Request           | 请求参数错误   |
| 404        | Not Found             | 资源不存在     |
| 422        | Unprocessable Entity  | 数据验证失败   |
| 500        | Internal Server Error | 服务器内部错误 |

### 错误响应格式

```json
{
  "detail": "错误描述信息"
}
```

### 数据库约束错误

- **外键约束**: 确保 `department_id` 和 `created_by` 引用存在的记录
- **唯一约束**: `record_number` 必须唯一
- **非空约束**: 必填字段不能为空

---

## 🔧 配置信息

### 环境变量

```env
# Supabase 配置
VITE_SUPABASE_URL=https://dgsdkdbjpucyawnyfbdu.supabase.co
VITE_SUPABASE_ANON_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...

# DeepSeek API 配置
VITE_DEEPSEEK_API_KEY=sk-xxx
VITE_DEEPSEEK_API_URL=https://api.deepseek.com
```

### 测试数据

**测试部门ID**: `11111111-1111-1111-1111-111111111111`
**测试用户ID**: `22222222-2222-2222-2222-222222222222`

---

## 📚 相关文档

- [Supabase 官方文档](https://supabase.com/docs)
- [FastAPI 官方文档](https://fastapi.tiangolo.com/)
- [Vue 3 官方文档](https://vuejs.org/)

---

**文档版本**: v1.0
**最后更新**: 2025-08-29
**维护者**: 医疗质控系统开发团队

```

```
