# Bug 修复：快速质控返回 Mock 数据问题

## 📋 问题描述

**症状**：
- 入院记录的批量质控 ✅ 正常工作
- 入院记录的快速质控 ✅ 正常工作
- **病程记录的快速质控 ❌ 返回 Mock 数据，瞬间完成**

**用户报告**：
> "我发现在对病程记录进行质控时，质控过程几乎瞬间就结束了，没有像处理入院记录那样需要等待一段时间。"

## 🔍 根本原因分析

### 问题定位

通过深入代码审查发现，**病程记录快速质控返回 Mock 数据的根本原因有两个**：

#### 原因1：后端依赖注入问题（已修复）

1. **全局 `service` 实例在应用启动时初始化**
   - 位置：`backend/app/main.py` 第 237 行
   - 调用：`await qc_sichuan_router.init_qc_service()`

2. **部分端点直接使用全局 `service`，部分使用依赖注入**
   - ❌ `/test-rule` 端点（第 897 行）：直接使用 `service.get_rule_by_id()`
   - ✅ `/evaluate` 端点（第 141 行）：使用 `qc_service: SichuanQCService = Depends(get_qc_service)`
   - ✅ `/evaluate-fast` 端点（第 103 行）：使用依赖注入

3. **全局实例不会自动重新加载配置**
   - 如果应用启动时数据库配置加载失败，全局实例会回退到 `.env` 配置
   - 即使后续在 LLM 配置页面更新了数据库配置，全局实例也不会自动更新
   - 使用依赖注入的端点每次请求都会检查并初始化，能获取最新配置

#### 原因2：前端未调用真实 API（**真正的问题**）

**关键发现**：`DocumentCategoryView.vue` 中的 `analyzeDocumentQC` 函数（第 772-789 行）**只是显示了模拟进度条，但没有实际调用任何 API**！

```typescript
// 修复前的代码（只显示进度，不调用API）
const analyzeDocumentQC = async (document: DocumentItem) => {
  try {
    currentAnalysisDocument.value = document
    showAnalysisProgress.value = true  // 只显示模拟进度条
    analyzingDocuments.value.add(document.id)
    // ❌ 没有任何 API 调用！
  } catch (error) {
    // ...
  }
}
```

而 `AnalysisProgress.vue` 组件（第 389 行）使用的是 `simulateAnalysis()` 函数，这是一个**纯模拟函数**，不会调用任何真实的 LLM API。

### 为什么入院记录正常，病程记录不正常？

- **入院记录**：使用 `BatchRuleTestV3.vue` 组件，调用 `testQCRule()` 函数（第 746 行），真正调用了 `/api/v1/qc/sichuan/test-rule` API
- **病程记录**：使用 `DocumentCategoryView.vue` 组件，`analyzeDocumentQC()` 函数只显示模拟进度，**从未调用任何 API**

## ✅ 修复方案

### 修复1：后端依赖注入（已完成）

将所有直接使用全局 `service` 的端点改为使用依赖注入，确保每次请求都能获取最新配置。

**修改文件**：`backend/app/routers/qc_sichuan.py`

**修改的端点**：

1. **`/test-rule` 端点**（第 893-910 行）
   ```python
   # 修改前
   @router.post("/test-rule")
   async def test_rule(request: Request, req: TestRuleRequest):
       target_rule = service.get_rule_by_id(req.rule_id)
       engine_result = await service.rule_engine.evaluate(...)
   
   # 修改后
   @router.post("/test-rule")
   async def test_rule(
       request: Request,
       req: TestRuleRequest,
       qc_service: SichuanQCService = Depends(get_qc_service)
   ):
       target_rule = qc_service.get_rule_by_id(req.rule_id)
       engine_result = await qc_service.rule_engine.evaluate(...)
   ```

2. **`/evaluate/batch` 端点**（第 353-365 行）
   ```python
   # 修改前
   @router.post("/evaluate/batch")
   async def evaluate_batch(request: Request, req: SichuanBatchRequest):
       results = await service.evaluate_batch(payloads)
   
   # 修改后
   @router.post("/evaluate/batch")
   async def evaluate_batch(
       request: Request,
       req: SichuanBatchRequest,
       qc_service: SichuanQCService = Depends(get_qc_service)
   ):
       results = await qc_service.evaluate_batch(payloads)
   ```

3. **`/stats` 端点**（第 617-621 行）
   ```python
   # 修改前
   @router.get("/stats")
   async def stats(request: Request):
       st = service.stats()
   
   # 修改后
   @router.get("/stats")
   async def stats(
       request: Request,
       qc_service: SichuanQCService = Depends(get_qc_service)
   ):
       st = qc_service.stats()
   ```

4. **`/rules/{rule_id}/prompt` 端点**（第 960-978 行）
   ```python
   # 修改前
   @router.get("/rules/{rule_id}/prompt")
   async def get_rule_prompt(
       request: Request,
       rule_id: str,
       admin_user: dict = Depends(require_admin)
   ):
       rule = service.get_rule_by_id(rule_id)
   
   # 修改后
   @router.get("/rules/{rule_id}/prompt")
   async def get_rule_prompt(
       request: Request,
       rule_id: str,
       admin_user: dict = Depends(require_admin),
       qc_service: SichuanQCService = Depends(get_qc_service)
   ):
       rule = qc_service.get_rule_by_id(rule_id)
   ```

5. **`/rules/{rule_id}/prompt` PUT 端点**（第 1068-1087 行）
   ```python
   # 修改前
   @router.put("/rules/{rule_id}/prompt")
   async def update_rule_prompt(
       request: Request,
       rule_id: str,
       req: UpdatePromptRequest,
       admin_user: dict = Depends(require_admin)
   ):
       success = service.update_rule_prompt(rule_id, req.custom_prompt)

   # 修改后
   @router.put("/rules/{rule_id}/prompt")
   async def update_rule_prompt(
       request: Request,
       rule_id: str,
       req: UpdatePromptRequest,
       admin_user: dict = Depends(require_admin),
       qc_service: SichuanQCService = Depends(get_qc_service)
   ):
       success = qc_service.update_rule_prompt(rule_id, req.custom_prompt)
   ```

### 修复2：前端真实 API 调用（**关键修复**）

修复 `DocumentCategoryView.vue` 中的 `analyzeDocumentQC` 函数，让它真正调用质控 API 而不是只显示模拟进度。

**修改文件**：`src/components/DocumentCategoryView.vue`

**修改内容**（第 771-852 行）：

```typescript
// 修复前：只显示模拟进度，不调用API
const analyzeDocumentQC = async (document: DocumentItem) => {
  try {
    currentAnalysisDocument.value = document
    showAnalysisProgress.value = true  // ❌ 只显示模拟进度条
    analyzingDocuments.value.add(document.id)
    // ❌ 没有任何 API 调用！
  } catch (error) {
    // ...
  }
}

// 修复后：调用真实的质控 API
const analyzeDocumentQC = async (document: DocumentItem) => {
  try {
    currentAnalysisDocument.value = document
    showAnalysisProgress.value = false  // 不显示模拟进度条
    analyzingDocuments.value.add(document.id)

    message.loading('正在进行质控分析...', 0)

    // ✅ 调用四川质控 API 进行真实的质控分析
    const response = await fetch('/api/v1/qc/sichuan/evaluate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        document_id: document.id,
        document_content: document.content || '',
        document_type: document.type || '病程记录',
        persist: false
      }),
      signal: AbortSignal.timeout(180000) // 3分钟超时
    })

    message.destroy()

    if (!response.ok) {
      const errorText = await response.text()
      throw new Error(`质控评估API调用失败: ${response.status} ${errorText}`)
    }

    const result = await response.json()

    // ✅ 更新文档的质控状态
    const qcScore = result.data?.evaluation_summary?.compliance_rate || 0
    const qcStatus = qcScore >= 90 ? 'passed' : qcScore >= 70 ? 'warning' : 'failed'

    // ✅ 显示真实的分析结果
    message.success(
      `${statusIcon} 质控分析完成！状态: ${statusText}，合规率: ${qcScore.toFixed(1)}%`,
      3
    )
  } catch (error) {
    // ...
  }
}
```

**关键改进**：
1. ✅ 调用真实的 `/api/v1/qc/sichuan/evaluate` API
2. ✅ 传递正确的文档内容和类型
3. ✅ 处理真实的质控结果
4. ✅ 更新文档的质控状态
5. ✅ 显示真实的合规率和质控结果

## 🧪 验证方法

### 1. 运行验证脚本

```bash
cd backend
python3 verify_qc_service_fix.py
```

**预期输出**：
```
======================================================================
🔍 验证四川质控服务初始化
======================================================================

1️⃣ 测试从数据库加载配置...
✅ 数据库配置加载成功:
   - API 端点: https://dashscope.aliyuncs.com/compatible-mode/v1
   - API 密钥: 已配置
   - 模型: qwen2.5-14b-instruct
   - 配置源: database
   - Temperature: 0.1

📊 总结:
   ✅ 数据库配置完整，快速质控应该正常工作
```

### 2. 测试快速质控

1. **重启后端服务**（确保加载最新代码）
2. **测试病程记录快速质控**
3. **观察是否有等待时间**（真实 LLM 调用需要 2-5 秒）
4. **检查返回结果**（不应包含 `[MOCK RESULT]` 标记）

## 📊 影响范围

### 修复的端点

| 端点 | 方法 | 用途 | 修复前 | 修复后 |
|------|------|------|--------|--------|
| `/test-rule` | POST | 快速质控（单规则测试） | ❌ 使用全局实例 | ✅ 依赖注入 |
| `/evaluate/batch` | POST | 批量文档质控 | ❌ 使用全局实例 | ✅ 依赖注入 |
| `/stats` | GET | 获取质控统计 | ❌ 使用全局实例 | ✅ 依赖注入 |
| `/rules/{rule_id}/prompt` | GET | 获取规则提示词 | ❌ 使用全局实例 | ✅ 依赖注入 |
| `/rules/{rule_id}/prompt` | PUT | 更新规则提示词 | ❌ 使用全局实例 | ✅ 依赖注入 |

### 已经正确使用依赖注入的端点

| 端点 | 方法 | 用途 |
|------|------|------|
| `/evaluate` | POST | 单文档质控（多规则） |
| `/evaluate-fast` | POST | 快速质控（一次调用） |
| `/reload-config` | POST | 重新加载配置 |
| `/current-config` | GET | 获取当前配置 |

## 🎯 最佳实践

### 依赖注入的优势

1. **配置实时更新**：每次请求都能获取最新配置
2. **测试友好**：可以轻松 mock 依赖
3. **解耦合**：端点不依赖全局状态
4. **一致性**：所有端点使用相同的初始化逻辑

### 推荐模式

```python
# ✅ 推荐：使用依赖注入
@router.post("/some-endpoint")
async def some_endpoint(
    request: Request,
    qc_service: SichuanQCService = Depends(get_qc_service)
):
    result = await qc_service.some_method()
    return result

# ❌ 不推荐：直接使用全局实例
@router.post("/some-endpoint")
async def some_endpoint(request: Request):
    result = await service.some_method()  # 可能使用过期配置
    return result
```

## 📝 相关文档

- [FastAPI 依赖注入文档](https://fastapi.tiangolo.com/tutorial/dependencies/)
- [四川质控数据库配置实现](./SICHUAN_QC_DB_CONFIG_IMPLEMENTATION.md)
- [LLM 配置加载器](./backend/app/services/llm_config_loader.py)

## ✅ 验证清单

### 后端修复
- [x] 修改 `/test-rule` 端点使用依赖注入
- [x] 修改 `/evaluate/batch` 端点使用依赖注入
- [x] 修改 `/stats` 端点使用依赖注入
- [x] 修改 `/rules/{rule_id}/prompt` GET 端点使用依赖注入
- [x] 修改 `/rules/{rule_id}/prompt` PUT 端点使用依赖注入
- [x] 创建验证脚本
- [x] 运行验证脚本确认配置正确
- [x] 重启后端服务

### 前端修复
- [x] 修复 `DocumentCategoryView.vue` 中的 `analyzeDocumentQC` 函数
- [x] 将模拟进度改为真实 API 调用
- [x] 调用 `/api/v1/qc/sichuan/evaluate` 端点
- [x] 正确处理质控结果并更新文档状态

### 测试
- [ ] 测试病程记录快速质控
- [ ] 确认不再返回 Mock 数据
- [ ] 确认有明显的等待时间（2-5秒）
- [ ] 确认返回真实的质控结果

## 🚀 部署步骤

1. **提交代码更改**
   ```bash
   git add backend/app/routers/qc_sichuan.py
   git commit -m "fix: 修复快速质控依赖注入问题，确保使用最新配置"
   ```

2. **重启后端服务**
   ```bash
   # 如果使用 systemd
   sudo systemctl restart medqc-backend
   
   # 或者如果使用 PM2
   pm2 restart medqc-backend
   
   # 或者手动重启
   pkill -f "uvicorn.*main:app"
   cd backend && uvicorn app.main:app --host 0.0.0.0 --port 8001
   ```

3. **验证修复**
   - 访问前端页面
   - 测试病程记录快速质控
   - 确认有等待时间且返回真实结果

---

**修复日期**：2025-11-11  
**修复人员**：Augment Agent  
**问题报告人**：用户

