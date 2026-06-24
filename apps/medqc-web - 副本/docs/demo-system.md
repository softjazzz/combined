# LLM质控演示系统说明文档

## 📋 概述

LLM质控演示系统是一个交互式的医疗病历质量控制演示平台，展示了从病历选择到质控分析、结果反馈、申诉管理的完整流程。

**访问路径**：`/demo/llm-qc-new`

---

## 🎯 质控规则来源

### 当前使用规则

演示系统当前使用**四川省质控规则**作为标准规则库。

### 规则特点

| 特性 | 说明 |
|------|------|
| **权威性** | 基于《四川省住院病历质量评定标准（2023年版）》 |
| **完整性** | 包含146条标准化规则 |
| **LLM优化** | 每条规则包含专为大模型设计的 `prompt_template` |
| **分类清晰** | 按复杂度（高/中/低）和缺陷级别（严重/一般/轻微）分类 |
| **文书适配** | 每条规则明确标注适用的文书类型 |

### 规则字段结构

```typescript
{
  rule_id: "SC-001",              // 规则ID
  name: "入院记录完整性",          // 规则名称
  description: "检查入院记录...",  // 规则描述
  category: "基础",                // 规则分类
  complexity: "中复杂度",           // 复杂度（高/中/低）
  defect_level: "一般缺陷",        // 缺陷级别
  applicable_documents: [...],     // 适用文书类型
  prompt_template: "...",          // LLM提示词模板
  requires_rag: false,             // 是否需要RAG
  requires_cot: false,             // 是否需要思维链
  score_deduction: 2,              // 扣分值
  medical_domain: "通用"           // 医疗领域
}
```

---

## 🔄 规则加载流程

### 1. 前端加载规则

```typescript
// stores/qcDemo.ts - loadTestData()
const sichuanRules = await demoDataService.getSichuanQCRules()
availableRules.value = sichuanRules
```

### 2. 数据服务层获取规则

```typescript
// services/demoDataService.ts - getSichuanQCRules()
const response = await fetch('/api/v1/qc/sichuan/rules')
const data = await response.json()
return transformSichuanRules(data.rules)
```

### 3. 字段映射转换

```typescript
transformSichuanRules(rules) {
  return rules.map(rule => ({
    id: rule.rule_id,           // 四川规则ID → 系统ID
    ruleCode: rule.rule_id,     // 保留原始编码
    name: rule.name,
    complexity: rule.complexity,
    defect_level: rule.defect_level,
    applicable_documents: rule.applicable_documents,
    // ... 其他字段映射
  }))
}
```

### 4. 智能规则过滤

根据选中的文书类型自动过滤适用规则：

```typescript
// stores/qcDemo.ts - applicableRules
const filtered = availableRules.filter(rule => {
  const applicableDocs = rule.applicable_documents || []
  return applicableDocs.includes(selectedDocument.type)
})
```

---

## ⚙️ 质控执行流程

### 1. 用户选择病历和文书

**步骤1：测试对象选择**
- 从数据库加载真实病历列表
- 选择病历后自动加载关联文书
- 支持文书预览和筛选

### 2. 用户配置质控规则

**步骤2：规则配置**
- 根据文书类型自动筛选适用规则
- 用户勾选要应用的规则
- 显示规则详情和统计信息

### 3. 执行质控分析

**步骤3：运行与结果**

```typescript
// 调用四川质控引擎
POST /api/qc/sichuan/evaluate
{
  document_id: "uuid",
  document_content: "病历内容...",
  document_type: "首次病程记录",
  rule_ids: ["SC-001", "SC-002", ...],  // 用户选中的规则ID
  persist: false  // 演示模式不持久化
}
```

### 4. 解析质控结果

```typescript
{
  evaluation_summary: {
    total_rules: 146,
    compliant_rules: 130,
    compliance_rate: 89.0,
    overall_grade: "A",
    critical_violations: 2
  },
  evaluation_results: [
    {
      rule_id: "SC-001",
      rule_name: "入院记录完整性",
      is_compliant: true,
      findings: "...",
      evidence: "...",
      confidence: 0.92
    }
  ],
  performance_metrics: {
    processing_time: 3.5,
    token_usage: 1200,
    estimated_cost: 0.0024
  }
}
```

---

## 📂 相关文件

| 文件路径 | 功能说明 |
|---------|---------|
| `src/views/demo/LLMQCDemoEnhancedNew.vue` | 主入口页面 |
| `src/stores/qcDemo.ts` | 状态管理 |
| `src/services/demoDataService.ts` | 规则加载服务 |
| `src/components/demo/QCRulesDemoPanel.vue` | 规则展示组件 |
| `src/components/demo/TargetSelectionStep.vue` | 病历选择组件 |
| `src/components/demo/QCAnalysisDemoPanel.vue` | 结果展示组件 |
| `src/types/quality-control.ts` | 类型定义 |
| `src/config/ruleSourceConfig.ts` | 规则来源配置 |
| `backend/app/routers/qc_sichuan.py` | 四川质控后端API |

---

## 🚀 使用流程

### 完整演示流程

1. **访问演示系统**
   ```
   http://localhost:3000/demo/llm-qc-new
   ```

2. **选择测试对象**（步骤1）
   - 从列表选择病历
   - 查看病历详情
   - 选择要分析的文书

3. **配置质控规则**（步骤2）
   - 查看适用规则列表（根据文书类型自动筛选）
   - 勾选要应用的规则
   - 查看规则详情和统计

4. **开始质控分析**（步骤3）
   - 点击"开始分析"按钮
   - 实时查看分析进度
   - 等待质控完成

5. **查看质控结果**
   - 查看综合评分和等级
   - 查看违规项详细列表
   - 查看性能指标统计

6. **后续操作**（可选）
   - 对不合理的质控结果提出申诉
   - 导出演示状态
   - 查看通知和日志

---

## 🔧 技术架构

### 前端技术栈

- **框架**：Vue 3 + TypeScript
- **状态管理**：Pinia
- **UI组件**：Ant Design Vue
- **构建工具**：Vite

### 后端技术栈

- **框架**：FastAPI + Python
- **数据库**：PostgreSQL (Supabase)
- **LLM集成**：OpenAI/Claude API

### 数据流

```
用户操作
  ↓
前端组件 (Vue 3)
  ↓
状态管理 (Pinia Store)
  ↓
数据服务 (DemoDataService)
  ↓
后端API (/api/qc/sichuan/evaluate)
  ↓
LLM引擎 (GPT-4/Claude)
  ↓
结果返回并展示
```

---

## 📊 扩展性设计

### 支持多规则来源

系统设计支持切换不同的规则来源（已预留配置）：

```typescript
// src/config/ruleSourceConfig.ts
export const RULE_SOURCE_CONFIG = {
  sichuan: {
    label: '四川省标准',
    apiEndpoint: '/api/v1/qc/sichuan/rules',
    ruleCount: 146
  },
  platform: {
    label: '平台语义规则',
    apiEndpoint: '/api/semantic-rules'
  },
  traditional: {
    label: '传统质控规则',
    apiEndpoint: '/api/qc-rules'
  }
}
```

### 切换规则来源（未来功能）

如需切换规则来源，只需修改 `demoDataService` 中的加载方法：

```typescript
// 当前：使用四川规则
const rules = await demoDataService.getSichuanQCRules()

// 切换为平台规则
const rules = await demoDataService.getPlatformSemanticRules()

// 切换为传统规则
const rules = await demoDataService.getQCRules()
```

---

## 🐛 故障排查

### 常见问题

**Q1: 规则列表为空？**
- 检查后端服务是否启动
- 检查 `/api/qc/sichuan/rules` 接口是否可访问
- 查看浏览器控制台是否有错误

**Q2: 质控分析失败？**
- 检查是否选择了病历和文书
- 检查是否勾选了规则
- 查看控制台日志中的错误信息
- 检查后端LLM服务配置

**Q3: 规则ID不匹配？**
- 四川规则ID格式为 `SC-001` 等
- 检查规则映射逻辑是否正确
- 验证 `transformSichuanRules` 方法

---

## 📝 更新日志

### v2.0.0 (2025-01-XX)
- ✅ 切换规则来源为四川省标准
- ✅ 新增四川规则加载服务
- ✅ 优化规则展示界面
- ✅ 扩展类型定义支持四川规则字段
- ✅ 添加规则来源配置文件

### v1.0.0 (2024-XX-XX)
- 初始版本，使用通用规则库

---

## 📚 参考资料

- 《四川省住院病历质量评定标准（2023年版）》
- FastAPI文档：https://fastapi.tiangolo.com/
- Vue 3文档：https://vuejs.org/
- Ant Design Vue文档：https://antdv.com/

---

**文档更新日期**：2025-01-XX
**维护者**：开发团队
