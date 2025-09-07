# LLM服务重构迁移指南

## 概述

原来的 `llmService.ts` 文件有2000多行代码，现在已经重构为模块化架构，提高了代码的可维护性和可测试性。

## 新的模块结构

```
src/services/
├── types/
│   └── medical.ts              # 医疗相关类型定义
├── llm/
│   ├── documentClassifier.ts   # 文档分类器
│   ├── promptBuilder.ts        # 提示词构建器
│   ├── responseParser.ts       # 响应解析器
│   └── configManager.ts        # 配置管理器
├── llmServiceNew.ts            # 新的主服务文件
└── llmService.ts               # 原始文件（待替换）
```

## 迁移步骤

### 1. 更新导入语句

**旧的导入方式：**
```typescript
import { llmService } from '@/services/llmService'
```

**新的导入方式：**
```typescript
import { llmService } from '@/services/llmServiceNew'
// 或者导入特定的类
import { LLMService, DocumentClassifier } from '@/services/llmServiceNew'
```

### 2. API接口变化

大部分API保持兼容，但有一些改进：

**初始化服务：**
```typescript
// 新增：支持从数据库加载配置
await llmService.initialize('default', userId)
```

**解析医疗文本：**
```typescript
// API保持不变
const result = await llmService.parseMedicalText(text, options)
```

**批量处理：**
```typescript
// 新增：支持真正的批量处理
const results = await llmService.parseBatchMedicalTexts(texts, {
  enableBatchProcessing: true
})
```

### 3. 配置管理改进

**获取配置信息：**
```typescript
// 新增：获取详细的配置摘要
const summary = llmService.getConfigSummary()
console.log(summary)
// {
//   provider: '阿里通义千问',
//   model: 'Qwen2.5-7B-1M',
//   endpoint: 'https://dashscope.aliyuncs.com/api/v1/services/aigc/text-generation/generation',
//   hasApiKey: true,
//   pointerMode: true,
//   summaryMaxLength: 80
// }
```

### 4. 独立使用子模块

现在可以独立使用各个子模块：

**文档分类：**
```typescript
import { DocumentClassifier } from '@/services/llmServiceNew'

// 基于规则的快速分类
const type = DocumentClassifier.classifyByTitle('入院记录', content)

// 获取类型中文名称
const name = DocumentClassifier.getDocumentTypeName(type)
```

**提示词构建：**
```typescript
import { PromptBuilder } from '@/services/llmServiceNew'

// 构建自定义提示词
const prompt = PromptBuilder.buildMedicalParsePrompt(text, {
  extractPatientInfo: true,
  classifyDocuments: true
})
```

**响应解析：**
```typescript
import { ResponseParser } from '@/services/llmServiceNew'

// 解析API响应
const data = ResponseParser.parseMedicalResponse(response)

// 验证结果质量
const validation = ResponseParser.validateResponse(data)
```

## 兼容性说明

### 保持兼容的API
- `parseMedicalText()`
- `updateConfig()`
- `getCurrentConfig()`
- 所有类型定义

### 新增的API
- `initialize()` - 从数据库加载配置
- `parseBatchMedicalTexts()` - 真正的批量处理
- `generateSummary()` - 生成文档摘要
- `classifyDocument()` - 文档分类
- `getConfigSummary()` - 获取配置摘要
- `getStatus()` - 获取服务状态

### 移除的API
- 一些内部使用的私有方法已经移动到对应的子模块中

## 测试建议

1. **单元测试**：现在可以为每个模块编写独立的单元测试
2. **集成测试**：测试主服务的完整流程
3. **性能测试**：验证模块化后的性能表现

## 逐步迁移策略

### 阶段1：并行运行
- 保留原有的 `llmService.ts`
- 在新功能中使用 `llmServiceNew.ts`
- 逐步测试新服务的稳定性

### 阶段2：逐步替换
- 将现有组件逐个切换到新服务
- 重点测试关键功能：
  - 智能病历导入
  - LLM解析结果展示
  - 配置管理

### 阶段3：完全切换
- 将 `llmServiceNew.ts` 重命名为 `llmService.ts`
- 删除旧的服务文件
- 更新所有导入引用

## 回滚计划

如果发现问题，可以快速回滚：

1. 恢复原有的 `llmService.ts` 文件
2. 更新导入语句
3. 重新部署

## 优势总结

### 代码质量
- ✅ 单一职责原则：每个模块负责特定功能
- ✅ 可测试性：可以为每个模块编写独立测试
- ✅ 可维护性：修改某个功能不会影响其他模块
- ✅ 可扩展性：容易添加新的功能模块

### 开发体验
- ✅ 更好的IDE支持和代码提示
- ✅ 更清晰的错误定位
- ✅ 更容易的代码审查
- ✅ 更好的团队协作

### 性能优化
- ✅ 按需加载：只导入需要的模块
- ✅ 更好的缓存策略
- ✅ 减少内存占用

## 注意事项

1. **类型安全**：确保所有类型定义正确导入
2. **错误处理**：新的模块有更完善的错误处理机制
3. **配置管理**：新的配置管理器支持更多功能
4. **向后兼容**：大部分API保持兼容，但建议使用新的API

## 支持

如果在迁移过程中遇到问题，请：
1. 检查控制台错误信息
2. 验证类型定义是否正确
3. 确认配置是否完整
4. 查看各模块的文档注释
