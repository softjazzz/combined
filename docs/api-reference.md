# API 接口文档

> 面向前端与集成方，描述认证与规则管理相关 REST API。示例基于当前前端实现（ApiService 与规则列表页）。

## 目录
- 认证
  - 登录 /api/auth/login
  - 刷新 /api/auth/refresh
  - 当前用户 /api/auth/me
  - 登出 /api/auth/logout
- 规则管理
  - 列表查询（分页/筛选/搜索） /api/rules
  - 获取单条 /api/rules/{id}
  - 新增 /api/rules
  - 更新 /api/rules/{id}
  - 删除 /api/rules/{id}
- 参数说明
  - 分页参数
  - 筛选/搜索参数
- 通用响应结构
- 错误码

## 认证

### 登录
- POST /api/auth/login
- Request
```json
{"email":"admin@yibao.com","password":"admin123"}
```
- Response
```json
{"access_token":"<jwt>","refresh_token":"<jwt>"}
```

### 刷新 Token
- POST /api/auth/refresh
- Request
```json
{"refresh_token":"<jwt>"}
```
- Response
```json
{"access_token":"<jwt>","refresh_token":"<jwt>"}
```

### 当前用户
- GET /api/auth/me
- Headers: Authorization: Bearer <access_token>
- Response
```json
{"id":"u_1","email":"admin@yibao.com","display_name":"管理员"}
```

### 登出
- POST /api/auth/logout
- Headers: Authorization: Bearer <access_token>
- Response: 204 或 {"success": true}

> 前端已实现：请求拦截器自动注入 Authorization，响应拦截器在 401 时尝试 refresh；失败则清 token 并重定向到登录。

## 规则管理

### 列表查询（分页/筛选/搜索）
- GET /api/rules
- Query Params（根据前端当前实现）：
  - page: number（默认 1）
  - page_size: number（默认 15，可选 10/15/20/30/50/100）
  - search: string（名称/编码/描述模糊）
  - enabled: boolean（true/false）
  - severity: string（info/warn/block）
  - rule_type: string（参考规则类型映射）
- Response
```json
{
  "data": [
    {"id":1,"code":"DRUG_INSURANCE_TYPE_001","name":"疤痕止痒软化膏 - 保险类型限制","rule_type":"drug_insurance_type","severity":"warn","enabled":true,"version":1,"category_id":"batch_3","updated_at":"2025-09-08T10:00:00Z","description":"..."}
  ],
  "total": 1173
}
```

### 获取单条
- GET /api/rules/{id}
- Response: 同上 data 中单条结构

### 新增
- POST /api/rules
- Body（关键字段）
```json
{
  "code":"DRUG_INSURANCE_TYPE_002",
  "name":"XXX - 保险类型限制",
  "rule_type":"drug_insurance_type",
  "severity":"warn",
  "enabled":true,
  "version":1,
  "category_id":"batch_3",
  "metadata":{},
  "description":"..."
}
```
- Response: 新建后的完整对象或 {"id": new_id}

### 更新
- PUT /api/rules/{id}
- Body: 同新增（部分字段可选）
- Response: 更新后的完整对象或 {"success": true}

### 删除
- DELETE /api/rules/{id}
- Response: {"success": true} | 204

## 参数说明

### 分页参数
- page: 页码，从 1 开始
- page_size: 每页条数，支持 10/15/20/30/50/100
- 返回体包含 total，用于前端显示 “第 X-Y 条，共 N 条规则”

### 筛选/搜索参数
- search: 对 name/code/description 模糊匹配
- enabled: true/false（启用状态）
- severity: info|warn|block
- rule_type: 见下方映射
  - drug_gender（性别限制）
  - drug_age（年龄限制）
  - drug_children_only（儿童专用）
  - drug_children_limit（儿童限制）
  - drug_payment_course（支付疗程限制）
  - drug_insurance_type（保险类型限制）
  - drug_diagnosis（诊断限制）
  - drug_dosage_form（剂型限制）
  - drug_route（给药途径）
  - drug_indication（适应症限制）

## 通用响应结构（示例）
```json
{"success": true, "data": {...}, "message": "ok"}
```
或直接返回业务数据：
```json
{"data": [...], "total": 1173}
```

## 错误码
- 400 Bad Request：参数错误
- 401 Unauthorized：未认证或 token 过期（前端将尝试 refresh，失败后跳转登录）
- 403 Forbidden：无权限访问（前端提示“没有权限访问该资源”）
- 404 Not Found：资源不存在
- 5xx Server Error：服务端异常

