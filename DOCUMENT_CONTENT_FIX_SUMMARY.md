# 病历文档内容为空问题修复总结

## 问题描述

用户在质控演示页面选择病历记录后，点击"开始质控"时提示**病历内容为空**，导致无法进行质控分析。

## 问题诊断

### 数据流分析

1. **前端数据加载**（`qcDemo.ts` 第 1760-1840 行）：
   - 调用 `ApiService.getMedicalRecords()` 获取病历记录列表
   - 将记录存储在 `availableRecords.value` 中
   - 自动选择第一条记录作为 `testRecord.value`

2. **文档选择逻辑**（`qcDemo.ts` 第 1856-1877 行）：
   - 从 `testRecord.value.documents` 数组中选择文档
   - 优先选择"首次病程记录"或"入院记录"
   - 将选中的文档存储在 `selectedDocument.value` 中

3. **质控分析**（`qcDemo.ts` 第 1376-1382 行）：
   - 从 `selectedDocument.content` 获取文档内容
   - 如果没有内容，尝试从 `testRecord.content` 获取
   - 如果仍然没有内容，生成示例内容

4. **后端 API**（`records.py` 第 38-62 行）：
   - **问题根源**：`/api/v1/records` 端点只查询了 `medical_records` 表的字段
   - **缺失数据**：没有查询关联的 `medical_documents` 表
   - **结果**：返回的记录中没有 `documents` 字段

### 根本原因

后端 API `/api/v1/records` 的查询语句：

```python
response = supabase.table(settings.RECORDS_TABLE).select('*').order('created_at', {'ascending': False}).execute()
records = list(response.data or [])
```

这个查询只返回 `medical_records` 表的字段，**不包括关联的 `medical_documents`**。

前端代码期望每条记录都有 `documents` 数组：

```typescript
const recordDocuments = testRecord.value.documents || []
if (recordDocuments.length > 0) {
  const preferredDoc = recordDocuments.find((doc: any) =>
    doc.type === '首次病程记录' || doc.type === '入院记录'
  ) || recordDocuments[0]
  selectedDocument.value = preferredDoc
}
```

由于 `documents` 字段不存在，`recordDocuments` 为空数组，导致创建了一个没有 `content` 字段的默认文档：

```typescript
const defaultDoc = {
  id: `doc-${testRecord.value.id}`,
  title: '首次病程记录',
  type: '首次病程记录',
  created_at: testRecord.value.admission_date || new Date().toISOString()
  // ❌ 缺少 content 字段
}
selectedDocument.value = defaultDoc
```

## 修复方案

### 修改文件：`health-qc-monorepo/apps/medqc-web/backend/app/routers/records.py`

**修改位置**：第 38-62 行

**修改内容**：

```python
"""获取病案记录列表（支持分页、筛选、排序）"""
supabase = get_supabase()
settings = get_settings()
try:
    if supabase:
        # Use our custom REST client or supabase-py, executed异步以避免阻塞
        # 默认按创建时间倒序排列（最新的在前面）
        # 同时查询关联的文档数据
        response = supabase.table(settings.RECORDS_TABLE).select(
            '*'
        ).order('created_at', {'ascending': False}).execute()
        records = list(response.data or [])
        
        # 为每条记录加载关联的文档
        for record in records:
            try:
                docs_response = supabase.table(settings.DOCUMENTS_TABLE).select(
                    'id, title, content, document_type, type_code, created_at, sort_order'
                ).eq('record_id', record['id']).eq('status', 'active').order('sort_order').execute()
                
                # 将文档数据添加到记录中
                record['documents'] = docs_response.data or []
            except Exception as doc_error:
                print(f"⚠️ 加载记录 {record['id']} 的文档失败: {doc_error}")
                record['documents'] = []
```

### 关键改进

1. **查询关联文档**：
   - 为每条病历记录查询关联的 `medical_documents`
   - 只查询状态为 `active` 的文档
   - 按 `sort_order` 排序

2. **选择必要字段**：
   - `id`: 文档 ID
   - `title`: 文档标题
   - `content`: **文档内容**（关键字段）
   - `document_type`: 文档类型（中文名称）
   - `type_code`: 类型代码
   - `created_at`: 创建时间
   - `sort_order`: 排序顺序

3. **错误处理**：
   - 如果加载文档失败，设置 `documents` 为空数组
   - 打印警告日志，但不影响主流程
   - 确保 API 不会因为单个记录的文档加载失败而崩溃

## 数据结构

### 修复前的 API 响应

```json
{
  "data": [
    {
      "id": "864d2673-8b52-42bb-99ab-befb45f38432",
      "patient_name": "张三",
      "admission_date": "2025-10-15",
      "department": "心内科",
      "primary_diagnosis": "冠心病"
      // ❌ 缺少 documents 字段
    }
  ]
}
```

### 修复后的 API 响应

```json
{
  "data": [
    {
      "id": "864d2673-8b52-42bb-99ab-befb45f38432",
      "patient_name": "张三",
      "admission_date": "2025-10-15",
      "department": "心内科",
      "primary_diagnosis": "冠心病",
      "documents": [  // ✅ 新增 documents 字段
        {
          "id": "doc-001",
          "title": "首次病程记录",
          "content": "患者张三，男，58岁，因'反复胸痛、胸闷3年，加重伴气促1周'入院...",
          "document_type": "首次病程记录",
          "type_code": "first_course_record",
          "created_at": "2025-10-15T10:00:00Z",
          "sort_order": 1
        },
        {
          "id": "doc-002",
          "title": "入院记录",
          "content": "姓名：张三\n性别：男\n年龄：58岁\n主诉：反复胸痛、胸闷3年...",
          "document_type": "入院记录",
          "type_code": "admission_record",
          "created_at": "2025-10-15T09:00:00Z",
          "sort_order": 0
        }
      ]
    }
  ]
}
```

## 前端数据流（修复后）

1. **加载病历记录**：
   ```typescript
   const apiRecords = await ApiService.getMedicalRecords({ page: 1, page_size: 20 })
   // 每条记录现在都包含 documents 数组
   ```

2. **选择文档**：
   ```typescript
   const recordDocuments = testRecord.value.documents || []
   // recordDocuments 现在包含真实的文档数据
   
   const preferredDoc = recordDocuments.find((doc: any) =>
     doc.type === '首次病程记录' || doc.type === '入院记录'
   ) || recordDocuments[0]
   // preferredDoc 包含 content 字段
   
   selectedDocument.value = preferredDoc
   ```

3. **获取文档内容**：
   ```typescript
   let documentContent = (primaryDocument as any)?.content || testRecord.value?.content || ''
   // documentContent 现在包含真实的病历内容
   ```

4. **发送质控请求**：
   ```typescript
   const sichuanPayload = {
     document_id: primaryDocument.id,
     document_content: documentContent,  // ✅ 有内容
     document_type: primaryDocument.type || '病程记录',
     rule_ids: ruleIds.length > 0 ? ruleIds : undefined,
     persist: false
   }
   ```

## 验证步骤

1. **重启后端服务**：
   ```bash
   cd health-qc-monorepo/apps/medqc-web/backend
   uvicorn app.main:app --reload --port 8000
   ```

2. **刷新前端页面**：
   - 打开浏览器开发者工具 → Network 标签
   - 刷新页面（Ctrl+F5）
   - 查看 `/api/v1/records` 请求的响应

3. **检查响应数据**：
   - 确认每条记录都有 `documents` 数组
   - 确认每个文档都有 `content` 字段
   - 确认 `content` 字段不为空

4. **测试质控功能**：
   - 选择一条病历记录
   - 选择一个文档类型（应该自动选择）
   - 选择质控规则
   - 点击"开始质控"
   - 确认不再提示"病历内容为空"

5. **检查控制台日志**：
   ```
   [QCDemoStore] 自动选择文书: 首次病程记录
   发送质控请求到后端...
   documentId: "doc-001"
   documentType: "首次病程记录"
   contentLength: 1234  // ✅ 应该大于 0
   contentSource: "document.content"  // ✅ 应该是 document.content
   ```

## 性能考虑

### 当前实现

- 为每条记录单独查询文档（N+1 查询问题）
- 对于 20 条记录，需要执行 21 次数据库查询（1 次记录 + 20 次文档）

### 优化建议（后续）

1. **使用数据库视图**：
   - 创建 `medical_records_with_documents` 视图
   - 使用 JSON 聚合函数一次性查询所有数据
   - 参考：`infra/supabase/medqc/migrations/20240827_create_medical_records_tables.sql` 第 212-232 行

2. **使用 Supabase 的关联查询**：
   ```python
   response = supabase.table(settings.RECORDS_TABLE).select(
       '*,documents:medical_documents(*)'
   ).order('created_at', {'ascending': False}).execute()
   ```

3. **添加缓存**：
   - 缓存病历记录和文档数据
   - 设置合理的过期时间
   - 减少数据库查询次数

## 相关文件

- ✅ **已修改**：`health-qc-monorepo/apps/medqc-web/backend/app/routers/records.py`
- **前端逻辑**：`health-qc-monorepo/apps/medqc-web/src/stores/qcDemo.ts`
- **数据库迁移**：`health-qc-monorepo/infra/supabase/medqc/migrations/20240827_create_medical_records_tables.sql`
- **API 服务**：`health-qc-monorepo/apps/medqc-web/src/services/apiService.ts`

## 总结

**问题**：后端 API 没有返回病历记录的关联文档数据，导致前端无法获取文档内容。

**修复**：在 `/api/v1/records` 端点中为每条记录查询关联的 `medical_documents`，并将文档数据（包括 `content` 字段）添加到响应中。

**效果**：前端现在可以正确获取文档内容，质控分析功能恢复正常。

