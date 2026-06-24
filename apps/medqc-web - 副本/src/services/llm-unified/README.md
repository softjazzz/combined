# LLM 统一服务

## 概述

这是新的统一 LLM 服务实现，旨在替代旧的 `llmService.ts`、`llmServiceNew.ts` 和 `enhancedLLMService.ts`。

## 架构设计

```
llm-unified/
├── types.ts                    # 统一类型定义
├── BaseLLMClient.ts           # 抽象基类
├── OpenAIClient.ts            # OpenAI 客户端
├── DeepSeekClient.ts          # DeepSeek 客户端
├── AliyunClient.ts            # 阿里云客户端
├── LLMServiceFacade.ts        # 服务门面（统一接口）
├── index.ts                   # 统一导出
└── __tests__/                 # 单元测试
    └── LLMServiceFacade.spec.ts
```

## 使用方式

### 基本使用

```typescript
import { llmService } from '@/services/llm-unified'

// 1. 从数据库加载配置并初始化
await llmService.loadConfigFromDatabase('default')

// 2. 提取医疗数据
const result = await llmService.extractMedicalData(medicalText, {
  extractPatientInfo: true,
  extractDiagnosis: true,
  classifyDocuments: true
})

// 3. 批量处理
const batchResult = await llmService.parseBatchMedicalTexts(texts)
```

### 手动初始化

```typescript
import { llmService } from '@/services/llm-unified'

// 使用 OpenAI
await llmService.initialize('openai', {
  provider: 'openai',
  apiKey: 'sk-...',
  baseURL: 'https://api.openai.com/v1',
  model: 'gpt-4',
  temperature: 0.7
})

// 使用 DeepSeek
await llmService.initialize('deepseek', {
  provider: 'deepseek',
  apiKey: 'sk-...',
  baseURL: 'https://api.deepseek.com/v1',
  model: 'deepseek-chat'
})

// 使用阿里云通义千问
await llmService.initialize('aliyun', {
  provider: 'aliyun',
  apiKey: 'sk-...',
  baseURL: 'https://dashscope.aliyuncs.com/compatible-mode/v1',
  model: 'qwen-turbo'
})
```

### 直接调用 LLM API

```typescript
const response = await llmService.callAPI('你好，请介绍一下自己', {
  temperature: 0.7,
  maxTokens: 1000
})

console.log(response.content)
console.log(response.usage)
```

## 主要特性

### 1. 统一接口

所有 LLM 提供商使用相同的接口，方便切换和测试。

### 2. 类型安全

完整的 TypeScript 类型定义，编译时类型检查。

### 3. 错误处理

统一的错误处理机制，包括：
- `LLMConfigError` - 配置错误
- `LLMAPIError` - API 调用错误
- `LLMParseError` - 响应解析错误

### 4. 可扩展

通过继承 `BaseLLMClient` 可以轻松添加新的 LLM 提供商。

## 迁移指南

### 从旧的 llmService 迁移

**旧代码**:
```typescript
import { llmService } from '@/services/llmService'

await llmService.initialize('default')
const result = await llmService.parseMedicalText(text)
```

**新代码**:
```typescript
import { llmService } from '@/services/llm-unified'

await llmService.loadConfigFromDatabase('default')
const result = await llmService.parseMedicalText(text)
```

### API 对照表

| 旧 API | 新 API | 说明 |
|--------|--------|------|
| `llmService.initialize(configName)` | `llmService.loadConfigFromDatabase(configName)` | 从数据库加载配置 |
| `llmService.parseMedicalText(text)` | `llmService.parseMedicalText(text)` | 解析医疗文本 |
| `llmService.extractMedicalData(text)` | `llmService.extractMedicalData(text)` | 提取医疗数据 |
| `llmService.parseBatchMedicalTexts(texts)` | `llmService.parseBatchMedicalTexts(texts)` | 批量处理 |
| `llmService.getCurrentConfig()` | `llmService.getCurrentConfig()` | 获取当前配置 |
| `llmService.updateConfig(updates)` | `llmService.updateConfig(updates)` | 更新配置 |

## 测试

```bash
# 运行单元测试
pnpm test llm-unified

# 运行测试并查看覆盖率
pnpm test:coverage llm-unified
```

## 性能优化

1. **连接复用**: 客户端实例会被复用，避免重复初始化
2. **超时控制**: 默认 60 秒超时，可配置
3. **错误重试**: 可以在上层实现重试逻辑

## 最佳实践

1. **使用单例**: 使用导出的 `llmService` 实例，而不是创建新实例
2. **错误处理**: 始终使用 try-catch 处理可能的错误
3. **配置管理**: 优先使用数据库配置，便于动态切换
4. **类型定义**: 充分利用 TypeScript 类型系统

## 示例

完整示例请参考：
- `__tests__/LLMServiceFacade.spec.ts` - 单元测试示例
- `../../views/medical-records/SmartImportMedicalRecordNew.vue.ts` - 实际使用示例

## 贡献

如需添加新的 LLM 提供商：

1. 创建新的客户端类，继承 `BaseLLMClient`
2. 实现必需的抽象方法
3. 在 `LLMServiceFacade.ts` 中注册新提供商
4. 添加单元测试
5. 更新文档

## 许可证

MIT

