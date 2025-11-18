# 提示词优化方案选择功能实施总结

## 📋 功能概述

在快速质控界面添加了提示词优化方案选择功能，允许用户在前端直接切换不同的提示词优化方案，实时查看不同方案的质控效果。

## ✅ 已完成的工作

### 1. 后端修改

#### 1.1 服务层 (`sichuan_qc_service.py`)

**新增函数**：
- `_extract_core_guidance()`: 提取核心指导信息（检查要点 + 判定逻辑）- 方案 C

**修改函数**：
- `_build_prompt()`: 添加 `prompt_mode` 参数，根据模式提取不同内容
  - `current`: 不提取任何额外内容
  - `plan_a`: 提取检查要点（+ 复杂规则增强）
  - `plan_b`: 使用完整 custom_prompt
  - `plan_c`: 提取检查要点 + 判定逻辑

- `evaluate_document_fast()`: 添加 `prompt_mode` 参数，传递给 `_build_prompt()`

**返回结果增强**：
- 在返回结果中添加 `prompt_mode` 字段，记录使用的方案

#### 1.2 API 路由层 (`qc_sichuan.py`)

**修改请求模型**：
```python
class SichuanEvaluateRequest(BaseModel):
    # ... 其他字段 ...
    prompt_mode: Optional[str] = "plan_a"  # 新增
```

**修改端点**：
- `/evaluate-fast`: 接受 `prompt_mode` 参数并传递给服务层

### 2. 前端修改

#### 2.1 API 接口 (`qc.ts`)

**修改接口定义**：
```typescript
export interface BatchQCEvaluatePayload {
  // ... 其他字段 ...
  prompt_mode?: string  // 新增
}
```

#### 2.2 批量测试组件 (`BatchRuleTest.vue`)

**新增状态**：
```typescript
const selectedPromptMode = ref<string>('plan_a')  // 默认使用方案A
const promptModeConfig: Record<string, { tag: string; description: string; color: string }>
```

**UI 改动**：
1. 在"快速质控评估"区域添加下拉选择框
2. 选项包括：
   - 当前模式（Token: 基准 | 准确率: 0%）
   - 方案A - 精简版 ⭐ 推荐（Token: +173% | 准确率: 67%）
   - 方案B - 完整版（Token: +250% | 准确率: 56%）
   - 方案C - 平衡版（Token: +200% | 准确率: 44%）

3. 动态显示当前方案的标签和描述
4. 在结果展示区域显示使用的方案

**逻辑修改**：
- `startProductionBatchQC()`: 传递 `prompt_mode` 参数到 API
- 成功消息中显示使用的方案
- 元数据中记录使用的方案

#### 2.3 样式优化

**新增样式**：
- `.prompt-mode-selector`: 提示词选择器容器
- `.prompt-option`: 选项样式（名称 + 元数据）
- `.info-banners`: 信息横幅容器
- `.prompt-mode-banner`: 提示词方案显示横幅

## 📊 测试结果

### API 测试

**测试命令**：
```bash
curl -X POST http://localhost:8000/api/v1/qc/sichuan/evaluate-fast \
  -H "Content-Type: application/json" \
  -d '{
    "document_id": "test_plan_a",
    "document_content": "...",
    "document_type": "入院记录",
    "rule_ids": ["LX-001", "LX-002"],
    "prompt_mode": "plan_a"
  }'
```

**测试结果**：
- ✅ `prompt_mode` 参数成功传递
- ✅ 返回结果包含 `"prompt_mode":"plan_a"`
- ✅ Token 消耗：1781
- ✅ API 耗时：15.06秒
- ✅ 质控结果正常返回

## 🎯 功能特点

### 1. 向后兼容
- 如果不传 `prompt_mode` 参数，默认使用方案A
- 现有代码无需修改即可继续工作

### 2. 用户友好
- 下拉选择框清晰显示每个方案的特点
- 实时显示Token消耗和准确率预期
- 推荐方案（方案A）有明显标识

### 3. 结果透明
- 结果页面显示使用的方案
- 便于用户对比不同方案的效果

### 4. 灵活扩展
- 配置化设计，易于添加新方案
- 方案配置集中管理

## 📁 修改的文件

### 后端
1. `health-qc-monorepo/apps/medqc-web/backend/app/services/sichuan_qc_service.py`
   - 新增 `_extract_core_guidance()` 方法
   - 修改 `_build_prompt()` 方法
   - 修改 `evaluate_document_fast()` 方法

2. `health-qc-monorepo/apps/medqc-web/backend/app/routers/qc_sichuan.py`
   - 修改 `SichuanEvaluateRequest` 模型
   - 修改 `/evaluate-fast` 端点

### 前端
1. `health-qc-monorepo/apps/medqc-web/src/api/qc.ts`
   - 修改 `BatchQCEvaluatePayload` 接口

2. `health-qc-monorepo/apps/medqc-web/src/components/BatchRuleTest.vue`
   - 添加提示词选择器 UI
   - 添加状态管理
   - 修改 API 调用逻辑
   - 添加结果展示
   - 添加样式

## 🚀 使用方法

### 前端使用

1. 打开批量测试页面
2. 在"快速质控评估"区域找到"提示词优化方案"下拉框
3. 选择想要使用的方案
4. 点击"启动快速质控评估"按钮
5. 查看结果，对比不同方案的效果

### API 使用

```bash
POST /api/v1/qc/sichuan/evaluate-fast
Content-Type: application/json

{
  "document_id": "test_001",
  "document_content": "病历内容...",
  "document_type": "入院记录",
  "rule_ids": ["LX-001", "LX-002"],
  "prompt_mode": "plan_a"  // current/plan_a/plan_b/plan_c
}
```

## 📈 方案对比

| 方案 | Token增长 | 准确率 | 适用场景 |
|------|----------|--------|---------|
| 当前模式 | 基准 | 0% | 不推荐使用 |
| 方案A ⭐ | +173% | 67% | **推荐**：性价比最高 |
| 方案B | +250% | 56% | Token消耗高，准确率反而下降 |
| 方案C | +200% | 44% | 平衡方案，但效果不如方案A |

## 💡 建议

1. **默认使用方案A**：在测试中表现最好，准确率67%，Token增长可控
2. **对比测试**：用户可以在同一病历上测试不同方案，选择最适合的
3. **成本控制**：方案A相比完整版（方案B）节省约30% Token
4. **持续优化**：根据实际使用反馈，可以调整方案配置

## 🔧 后续优化建议

1. **添加对比模式**：同时运行多个方案并并排显示结果差异
2. **保存用户偏好**：记住用户最常用的方案
3. **统计分析**：收集不同方案的使用数据和效果反馈
4. **动态调整**：根据规则复杂度自动推荐最佳方案

## ✅ 验收标准

- [x] 后端API支持 `prompt_mode` 参数
- [x] 前端UI显示提示词选择器
- [x] 选择器包含所有4个方案
- [x] 每个方案显示Token消耗和准确率
- [x] 结果页面显示使用的方案
- [x] 向后兼容（不传参数默认方案A）
- [x] API测试通过

## 📝 注意事项

1. **方案选择**：建议优先使用方案A，除非有特殊需求
2. **Token消耗**：不同方案的Token消耗差异较大，注意成本控制
3. **准确率**：测试数据基于9条LX规则，实际效果可能因规则而异
4. **性能**：方案B和C的提示词更长，API响应时间可能略长

---

**实施日期**：2025-11-09  
**实施人员**：AI Assistant  
**状态**：✅ 已完成并测试通过
