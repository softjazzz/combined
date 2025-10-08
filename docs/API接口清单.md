# 病案质控系统 API 接口清单

**文档版本**: v2.0  
**创建日期**: 2025-10-08  
**基础URL**: `http://localhost:8001`

---

## 📋 目录

- [1. 系统管理](#1-系统管理)
- [2. 认证授权](#2-认证授权)
- [3. 病案管理](#3-病案管理)
- [4. 文档管理](#4-文档管理)
- [5. 质控分析](#5-质控分析)
- [6. 规则管理](#6-规则管理)
- [7. LLM配置](#7-llm配置)
- [8. 报告生成](#8-报告生成)
- [9. 工具接口](#9-工具接口)

---

## 1. 系统管理

### 1.1 健康检查

**路由文件**: `app/routers/system.py`

| 方法 | 路径 | 说明 | 状态 |
|------|------|------|------|
| GET | `/api/health` | 系统健康检查 | ✅ |
| GET | `/api/metrics` | 系统运行指标 | ✅ |

**示例**:
```bash
# 健康检查
curl http://localhost:8001/api/health

# 系统指标
curl http://localhost:8001/api/metrics
```

---

## 2. 认证授权

### 2.1 用户认证

**路由文件**: `app/routers/auth.py`

| 方法 | 路径 | 说明 | 状态 |
|------|------|------|------|
| POST | `/api/auth/register` | 用户注册 | ✅ |
| POST | `/api/auth/login` | 用户登录 | ✅ |
| POST | `/api/auth/refresh` | 刷新Token | ✅ |
| GET | `/api/auth/me` | 获取当前用户信息 | ✅ |
| POST | `/api/auth/logout` | 用户登出 | ✅ |

**示例**:
```bash
# 用户登录
curl -X POST http://localhost:8001/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "email": "user@example.com",
    "password": "password123"
  }'

# 获取当前用户
curl http://localhost:8001/api/auth/me \
  -H "Authorization: Bearer {access_token}"
```

---

## 3. 病案管理

### 3.1 病案CRUD

**路由文件**: `app/routers/records.py`

| 方法 | 路径 | 说明 | 状态 |
|------|------|------|------|
| POST | `/api/records` | 创建病案 | ✅ |
| GET | `/api/records` | 获取病案列表 | ✅ |
| GET | `/api/records/{record_id}` | 获取病案详情 | ✅ |
| PUT | `/api/records/{record_id}` | 更新病案 | ✅ |
| DELETE | `/api/records/{record_id}` | 删除病案 | ✅ |
| GET | `/api/records/{record_id}/documents` | 获取病案文档列表 | ✅ |

**查询参数**:
- `page`: 页码（默认1）
- `page_size`: 每页数量（默认20）
- `department`: 科室筛选
- `qc_status`: 质控状态（pending/processing/completed/failed）
- `search`: 搜索关键词

**示例**:
```bash
# 创建病案
curl -X POST http://localhost:8001/api/records \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer {token}" \
  -d '{
    "record_number": "2025001",
    "record_name": "张三住院病历",
    "patient_info": {
      "name": "张三",
      "gender": "男",
      "age": 45
    },
    "department": "心内科",
    "primary_diagnosis": "冠心病"
  }'

# 获取病案列表
curl "http://localhost:8001/api/records?page=1&page_size=20&department=心内科"

# 获取病案文档
curl http://localhost:8001/api/records/{record_id}/documents
```

### 3.2 病案导入

**路由文件**: `app/routers/ingest.py`

| 方法 | 路径 | 说明 | 状态 |
|------|------|------|------|
| POST | `/api/medical-records` | 保存LLM解析结果 | ✅ |

---

## 4. 文档管理

### 4.1 文档操作

**路由文件**: `app/routers/medical_documents.py`

| 方法 | 路径 | 说明 | 状态 |
|------|------|------|------|
| GET | `/api/medical-documents/document-types` | 获取文档类型列表 | ✅ |
| POST | `/api/medical-documents` | 创建文档 | ✅ |
| GET | `/api/medical-documents/{document_id}` | 获取文档详情 | ✅ |
| PUT | `/api/medical-documents/{document_id}` | 更新文档 | ✅ |
| DELETE | `/api/medical-documents/{document_id}` | 删除文档 | ✅ |

**示例**:
```bash
# 获取文档类型
curl http://localhost:8001/api/medical-documents/document-types

# 创建文档
curl -X POST http://localhost:8001/api/medical-documents \
  -H "Content-Type: application/json" \
  -d '{
    "medical_record_id": "record-uuid",
    "title": "入院记录",
    "content": "患者因...",
    "document_type": "入院记录",
    "category_code": "admission"
  }'
```

### 4.2 文档分类

**路由文件**: `app/routers/classification.py`

| 方法 | 路径 | 说明 | 状态 |
|------|------|------|------|
| POST | `/api/classification/classify` | 文档分类 | ✅ |
| POST | `/api/classification/batch-classify` | 批量文档分类 | ✅ |

---

## 5. 质控分析

### 5.1 四川省质控

**路由文件**: `app/routers/qc_sichuan.py`

| 方法 | 路径 | 说明 | 状态 |
|------|------|------|------|
| POST | `/api/qc/sichuan/evaluate` | 单文档质控分析 | ✅ |
| POST | `/api/qc/sichuan/batch-evaluate` | 批量质控分析 | ✅ |
| GET | `/api/qc/sichuan/rules` | 获取四川省质控规则 | ✅ |
| GET | `/api/qc/sichuan/stats` | 获取质控统计 | ✅ |

**请求参数**:
```json
{
  "document_id": "doc-uuid",
  "document_content": "病程记录内容...",
  "document_type": "病程记录",
  "patient_info": {
    "name": "张三",
    "age": 45,
    "gender": "男"
  },
  "persist": true,
  "model": "gpt-4o-mini",
  "provider": "openai"
}
```

**响应格式**:
```json
{
  "success": true,
  "data": {
    "document_id": "doc-uuid",
    "total_rules": 20,
    "compliant_rules": 17,
    "compliance_rate": 85.0,
    "overall_grade": "乙级",
    "evaluation_results": [
      {
        "rule_id": "SC-001",
        "rule_name": "病程记录书写规范",
        "is_compliant": false,
        "findings": "记录时间不准确",
        "suggestions": "请核对记录时间",
        "score_deduction": 2
      }
    ],
    "processing_time": 2.5,
    "token_usage": 1500
  }
}
```

**示例**:
```bash
# 单文档质控
curl -X POST http://localhost:8001/api/qc/sichuan/evaluate \
  -H "Content-Type: application/json" \
  -d '{
    "document_id": "doc-uuid",
    "document_content": "病程记录：患者今日...",
    "document_type": "病程记录",
    "persist": true
  }'

# 获取质控规则（按文档类型分组）
curl "http://localhost:8001/api/qc/sichuan/rules?grouped=true"

# 批量质控
curl -X POST http://localhost:8001/api/qc/sichuan/batch-evaluate \
  -H "Content-Type: application/json" \
  -d '{
    "documents": [
      {
        "document_id": "doc1",
        "document_content": "...",
        "document_type": "病程记录"
      },
      {
        "document_id": "doc2",
        "document_content": "...",
        "document_type": "手术记录"
      }
    ]
  }'
```

### 5.2 通用质控

**路由文件**: `app/routers/qc.py`

| 方法 | 路径 | 说明 | 状态 |
|------|------|------|------|
| GET | `/api/qc/rules` | 获取质控规则列表 | ✅ |
| POST | `/api/qc/rules` | 创建质控规则 | ✅ |
| PUT | `/api/qc/rules/{rule_id}` | 更新质控规则 | ✅ |
| DELETE | `/api/qc/rules/{rule_id}` | 删除质控规则 | ✅ |
| GET | `/api/qc/rules/document-categories/config` | 获取文书类别配置 | ✅ |

---

## 6. 规则管理

### 6.1 语义规则

**路由文件**: `app/routers/semantic_rules.py`

| 方法 | 路径 | 说明 | 状态 |
|------|------|------|------|
| GET | `/api/semantic-rules` | 获取语义规则列表 | ✅ |
| POST | `/api/semantic-rules` | 创建语义规则 | ✅ |
| GET | `/api/semantic-rules/{rule_id}` | 获取规则详情 | ✅ |
| PUT | `/api/semantic-rules/{rule_id}` | 更新语义规则 | ✅ |
| DELETE | `/api/semantic-rules/{rule_id}` | 删除语义规则 | ✅ |

**查询参数**:
- `q`: 搜索关键词
- `category`: 规则分类
- `defect_level`: 缺陷级别
- `is_enabled`: 启用状态
- `page`: 页码
- `page_size`: 每页数量
- `sort_by`: 排序字段
- `sort_order`: 排序方向（asc/desc）

**示例**:
```bash
# 获取语义规则列表
curl "http://localhost:8001/api/semantic-rules?page=1&page_size=50&category=病程记录&is_enabled=true"

# 创建语义规则
curl -X POST http://localhost:8001/api/semantic-rules \
  -H "Content-Type: application/json" \
  -d '{
    "rule_name": "逻辑一致性检查",
    "description": "检查病历记录的逻辑一致性",
    "category": "病程记录",
    "defect_level": "一般缺陷",
    "deduction_score": 2,
    "system_role": "你是一位专业的医疗质控专家",
    "task_description": "检查病历记录的逻辑一致性"
  }'
```

### 6.2 质控LLM配置

**路由文件**: `app/routers/qc_llm_configs.py`

| 方法 | 路径 | 说明 | 状态 |
|------|------|------|------|
| GET | `/api/qc-llm-configs` | 获取质控LLM配置列表 | ✅ |
| POST | `/api/qc-llm-configs` | 创建质控LLM配置 | ✅ |
| PUT | `/api/qc-llm-configs/{config_id}` | 更新配置 | ✅ |
| DELETE | `/api/qc-llm-configs/{config_id}` | 删除配置 | ✅ |

---

## 7. LLM配置

### 7.1 LLM信息

**路由文件**: `app/routers/llm_info.py`

| 方法 | 路径 | 说明 | 状态 |
|------|------|------|------|
| GET | `/api/llm/providers` | 获取LLM提供商列表 | ✅ |
| GET | `/api/llm/models` | 获取LLM模型列表 | ✅ |

**示例**:
```bash
# 获取提供商列表
curl http://localhost:8001/api/llm/providers

# 获取模型列表
curl "http://localhost:8001/api/llm/models?provider_id=openai"
```

### 7.2 用户LLM配置

**路由文件**: `app/routers/llm_configs.py`

| 方法 | 路径 | 说明 | 状态 |
|------|------|------|------|
| GET | `/api/llm-configs/configs` | 获取用户LLM配置 | ✅ |
| POST | `/api/llm-configs/configs` | 创建LLM配置 | ✅ |
| PUT | `/api/llm-configs/configs/{config_id}` | 更新配置 | ✅ |
| DELETE | `/api/llm-configs/configs/{config_id}` | 删除配置 | ✅ |

---

## 8. 报告生成

### 8.1 质控报告

**路由文件**: `app/routers/reports.py`

| 方法 | 路径 | 说明 | 状态 |
|------|------|------|------|
| POST | `/api/reports/qc/generate` | 生成质控报告 | ✅ |
| GET | `/api/reports/qc/summary` | 获取质控概览 | ✅ |

**示例**:
```bash
# 生成质控报告
curl -X POST http://localhost:8001/api/reports/qc/generate \
  -H "Content-Type: application/json" \
  -d '{
    "record_ids": ["uuid1", "uuid2"],
    "report_type": "summary",
    "format": "pdf"
  }'

# 获取质控概览
curl http://localhost:8001/api/reports/qc/summary
```

---

## 9. 工具接口

### 9.1 工具服务

**路由文件**: `app/routers/tools.py`

| 方法 | 路径 | 说明 | 状态 |
|------|------|------|------|
| POST | `/api/tools/extract-text` | 文本提取 | ✅ |
| POST | `/api/tools/ocr` | OCR识别 | ✅ |

### 9.2 调试接口

**路由文件**: `app/routers/debug.py`

| 方法 | 路径 | 说明 | 状态 |
|------|------|------|------|
| GET | `/api/debug/pdf-env` | PDF环境检查 | ✅ |

---

## 附录

### A. 通用响应格式

**成功响应**:
```json
{
  "success": true,
  "data": {...},
  "message": "操作成功"
}
```

**错误响应**:
```json
{
  "success": false,
  "error": {
    "code": "ERROR_CODE",
    "message": "错误描述",
    "details": [...]
  }
}
```

**分页响应**:
```json
{
  "success": true,
  "data": [...],
  "pagination": {
    "page": 1,
    "page_size": 20,
    "total": 100,
    "total_pages": 5
  }
}
```

### B. 认证方式

所有需要认证的接口都使用 JWT Bearer Token:

```bash
Authorization: Bearer {access_token}
```

### C. 错误码

| 错误码 | 说明 |
|--------|------|
| 400 | 请求参数错误 |
| 401 | 未认证 |
| 403 | 权限不足 |
| 404 | 资源不存在 |
| 500 | 服务器内部错误 |

### D. 完整路由列表

**已注册的路由模块**（按注册顺序）:

1. `system` - 系统管理
2. `proxy` - 代理服务
3. `auth` - 认证授权
4. `records` - 病案管理
5. `qc` - 通用质控
6. `qc_sichuan` - 四川省质控
7. `tools` - 工具服务
8. `ingest` - 数据导入
9. `medical_documents` - 文档管理
10. `debug` - 调试接口
11. `llm_info` - LLM信息
12. `qc_llm_configs` - 质控LLM配置
13. `semantic_rules` - 语义规则
14. `tasks` - 任务管理
15. `classification` - 文档分类
16. `llm_configs` - 用户LLM配置
17. `medical_records_alias` - 病案别名（兼容）
18. `reports` - 报告生成

---

**文档维护**: 本文档基于实际代码生成，随系统迭代持续更新  
**最后更新**: 2025-10-08  
**API文档**: http://localhost:8001/docs (Swagger UI)

