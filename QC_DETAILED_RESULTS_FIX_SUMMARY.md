# 四川质控详细结果修复总结

## 问题描述

质控运行完成后，对于不通过的规则，只显示笼统的描述如"该规则在汇总结果中判定为不合规"，没有提供：
- 具体的失败原因
- 违规证据（病历原文引用）
- 问题定位（在病历的哪个部分）
- 整改建议

## 根本原因

经过诊断，发现问题出在**后端 API 路由层**：

1. **Service 层**（`app/services/sichuan_qc_service.py`）：
   - ✅ 成功调用 LLM API（阿里云通义千问 qwen2.5-14b-instruct）
   - ✅ 获取到 LLM 的完整响应文本
   - ❌ **但没有解析 LLM 返回的 JSON 格式结果**
   - ❌ 只把原始文本存储在 `llm_output` 字段中

2. **API 路由层**（`app/routers/qc_sichuan.py`）：
   - ❌ **完全忽略了 LLM 的详细输出**
   - ❌ **返回硬编码的占位符数据**：
     ```python
     "evaluation_results": [
         {
             "rule_id": "SC-PLACEHOLDER",
             "is_compliant": True,
             "findings": "模型输出摘要",
             "evidence": (result.get("llm_output") or "")[:120],
             "confidence": 0.75,
         }
     ]
     ```

## 修复方案

### 步骤 1: 优化 LLM Prompt 模板

**文件**: `health-qc-monorepo/apps/medqc-web/backend/app/services/sichuan_qc_service.py`

**修改内容**:
- 重写 `_build_prompt()` 方法中的 Prompt 模板（第 232-314 行）
- 明确要求 LLM 返回**严格的 JSON 数组格式**
- 每条规则的评估结果必须包含：
  - `rule_id`: 规则编号
  - `rule_name`: 规则名称
  - `is_compliant`: 是否符合（布尔值）
  - `findings`: 评估发现（详细说明违反了哪个要求）
  - `evidence`: **原文证据**（从病历中直接引用的文本片段）
  - `location`: **问题定位**（指出问题在病历的哪个部分）
  - `suggestion`: **整改建议**（具体的、可操作的改进建议）
  - `confidence`: 评估置信度（0.0-1.0）
- 提供 JSON 输出示例，确保 LLM 理解格式要求
- 强调：对于不通过的规则，必须提供具体的原文证据和问题定位

**关键改进**:
```python
## 输出要求
请对上述病历内容，逐条评估每个质控规则的符合情况。

**重要：你必须返回一个严格的 JSON 数组格式，数组中每个对象代表一条规则的评估结果。**

**JSON 输出示例：**
```json
[
  {
    "rule_id": "SC-001",
    "rule_name": "主诉应简明扼要",
    "is_compliant": false,
    "findings": "主诉过于冗长，包含了详细的病史描述，不符合'简明扼要'的要求",
    "evidence": "患者主诉：'反复胸痛、胸闷3年，加重伴气促1周。患者3年前无明显诱因出现胸痛...'（共120字）",
    "location": "主诉部分",
    "suggestion": "将主诉精简为：'反复胸痛、胸闷3年，加重伴气促1周'，详细病史移至现病史部分",
    "confidence": 0.95
  }
]
```
```

### 步骤 2: 实现 LLM 响应解析函数

**文件**: `health-qc-monorepo/apps/medqc-web/backend/app/services/sichuan_qc_service.py`

**新增方法**:

1. **`_parse_llm_json_response()`**（第 316-385 行）:
   - 提取 JSON 部分（查找 `[` 和 `]` 边界）
   - 使用 `json.loads()` 解析
   - 验证和规范化每条结果的字段
   - 处理解析失败的情况（记录日志，调用降级方案）
   - 返回规范化的评估结果列表

2. **`_create_fallback_results()`**（第 387-410 行）:
   - 当 JSON 解析失败时，创建降级结果
   - 返回一条汇总结果，避免系统崩溃
   - 标记为低置信度，提示需要人工复核

**修改方法**:

3. **`evaluate_document()`**（第 452-485 行）:
   - 调用 LLM 后，添加对返回文本的 JSON 解析
   - 计算实际的合规率和问题数（基于解析结果）
   - 在返回的 `result` 字典中新增 `parsed_evaluation_results` 字段

**关键代码**:
```python
# 新增：解析 LLM 返回的 JSON 格式结果
logger.info(f"开始解析 LLM 响应（长度: {len(text)} 字符）")
parsed_results = self._parse_llm_json_response(text, rules)

# 计算实际的合规率和问题数
total_evaluated = len(parsed_results)
compliant_count = sum(1 for r in parsed_results if r.get('is_compliant', True))
compliance_rate = (compliant_count / total_evaluated * 100.0) if total_evaluated > 0 else 100.0
issues_found = total_evaluated - compliant_count

return {
    # ... 其他字段 ...
    "parsed_evaluation_results": parsed_results,  # 新增：解析后的结构化结果
}
```

### 步骤 3: 修复 API 路由层的数据映射

**文件**: `health-qc-monorepo/apps/medqc-web/backend/app/routers/qc_sichuan.py`

**修改内容**（第 155-219 行）:
- **删除硬编码的占位符数据**
- 从 `result` 中提取 `parsed_evaluation_results`
- 将解析后的逐条规则结果映射到 `evaluation_results` 数组
- 确保每条结果包含完整的字段：`rule_id`, `rule_name`, `is_compliant`, `findings`, `evidence`, `location`, `suggestion`, `confidence`
- 如果解析失败或没有详细结果，提供降级方案

**关键代码**:
```python
# 新增：提取解析后的逐条规则评估结果
parsed_results = result.get("parsed_evaluation_results", [])

# 将解析后的结果映射到 API 响应格式
evaluation_results = []
if parsed_results and len(parsed_results) > 0:
    # 使用解析后的真实数据
    for item in parsed_results:
        evaluation_results.append({
            "rule_id": item.get("rule_id", "UNKNOWN"),
            "rule_name": item.get("rule_name", "未命名规则"),
            "is_compliant": item.get("is_compliant", True),
            "findings": item.get("findings", ""),
            "evidence": item.get("evidence", ""),
            "location": item.get("location", ""),
            "suggestion": item.get("suggestion", ""),
            "confidence": item.get("confidence", 0.75),
        })
    print(f"✅ 返回 {len(evaluation_results)} 条真实的规则评估结果")
else:
    # 降级方案：使用汇总结果
    print(f"⚠️ 未找到解析后的结果，使用降级方案")
    evaluation_results = [{ /* 降级数据 */ }]

response = {
    # ... 其他字段 ...
    "evaluation_results": evaluation_results,  # 使用真实的解析结果
}
```

### 步骤 4: 前端适配验证

**文件**: `health-qc-monorepo/apps/medqc-web/src/stores/qcDemo.ts`

**验证结果**: ✅ 前端适配逻辑已经正确处理了新增字段

`adaptSichuanQCResult()` 函数（第 1058-1070 行）已经包含了对 `evidence`, `location`, `suggestion` 字段的提取和映射：

```typescript
let ruleResults: QCRuleResult[] = evaluationResults.map((result: any) => ({
  ruleId: result.rule_id || '',
  ruleName: result.rule_name || '质控规则',
  passed: result.is_compliant || false,
  score: result.is_compliant ? 100 : 0,
  maxScore: 100,
  details: result.findings || result.description || '',
  executionTime: performanceMetrics.processing_time || 0,
  confidence: result.confidence || 0.85,
  evidence: result.evidence || '',      // ✅ 已支持
  location: result.location || '',      // ✅ 已支持
  suggestion: result.suggestion || ''   // ✅ 已支持
}))
```

## 测试验证

### 运行测试脚本

```bash
cd health-qc-monorepo
python test_qc_detailed_results.py
```

### 预期结果

测试脚本会：
1. 调用四川质控 API 评估一份首次病程记录
2. 检查返回的 `evaluation_results` 数组
3. 验证每条不通过规则是否包含：
   - ✅ 具体失败原因 (`findings`)
   - ✅ 原文证据 (`evidence`)
   - ✅ 问题定位 (`location`)
   - ✅ 整改建议 (`suggestion`)
4. 计算详细信息完整率

### 前端验证步骤

1. 启动后端服务：
   ```bash
   cd health-qc-monorepo/apps/medqc-web/backend
   uvicorn app.main:app --reload --port 8000
   ```

2. 启动前端服务：
   ```bash
   cd health-qc-monorepo/apps/medqc-web
   npm run dev
   ```

3. 在浏览器中：
   - 打开质控演示页面
   - 选择一份病历和文档类型
   - 点击"开始质控"
   - 等待分析完成
   - 点击"查看完整质控报告"按钮

4. 在弹窗中验证：
   - **发现的问题**部分：每条问题应显示原文证据、定位、建议
   - **规则明细**部分：不通过的规则应显示详细的失败信息

5. 检查浏览器开发者工具：
   - Network 标签 → 找到 `/api/qc/sichuan/evaluate` 请求
   - 查看 Response → `evaluation_results` 数组
   - 确认每条记录都包含 `findings`, `evidence`, `location`, `suggestion` 字段

## 技术亮点

1. **健壮的 JSON 解析**：
   - 容错处理：LLM 可能在 JSON 前后添加说明文字
   - 字段验证：确保每个字段都是正确的类型
   - 降级方案：解析失败时不会导致系统崩溃

2. **详细的日志记录**：
   - 记录解析过程的每个步骤
   - 便于调试 LLM 响应格式问题
   - 区分成功、警告、错误三种级别

3. **向后兼容**：
   - 保留了降级方案
   - 即使 LLM 返回格式不符合预期，系统仍能正常运行
   - 前端已有的兜底逻辑继续生效

4. **优化的 Prompt 工程**：
   - 提供清晰的 JSON 输出示例
   - 强调关键字段的重要性
   - 要求 LLM 直接引用病历原文作为证据

## 预期效果

修复后，质控结果弹窗中每条不通过的规则将显示：

```
❌ 不通过  主诉应简明扼要  得分: 60/100  置信度: 95%

详细说明：
主诉过于冗长，包含了详细的病史描述，不符合'简明扼要'的要求

原文证据：
┌─────────────────────────────────────────────────┐
│ 患者主诉：'反复胸痛、胸闷3年，加重伴气促1周。  │
│ 患者3年前无明显诱因出现胸痛...'（共120字）      │
└─────────────────────────────────────────────────┘

问题定位：主诉部分

整改建议：将主诉精简为：'反复胸痛、胸闷3年，加重伴气促1周'，
详细病史移至现病史部分
```

## 后续优化建议

1. **LLM 响应质量监控**：
   - 记录 JSON 解析成功率
   - 统计字段完整性
   - 定期优化 Prompt 模板

2. **缓存机制**：
   - 对相同病历内容的质控结果进行缓存
   - 减少 LLM API 调用次数和成本

3. **人工复核流程**：
   - 对低置信度的评估结果标记
   - 提供人工复核和修正接口

4. **多模型对比**：
   - 支持切换不同的 LLM 模型
   - 对比不同模型的质控结果质量

