# LLM 服务迁移指南

## 背景

为了解决代码重复问题（P0-1），我们创建了统一的 LLM 服务架构。旧的实现包括：
- `llmService.ts` (2239 行)
- `llmServiceNew.ts` (735 行) - 已备份为 `.backup`
- `enhancedLLMService.ts` (377 行) - 已备份为 `.backup`

新的统一实现位于 `llm-unified/` 目录。

## 迁移步骤

### 1. 更新导入语句

**旧代码**:
```typescript
import { llmService } from '@/services/llmServiceNew'
// 或
import { llmService } from '@/services/llmService'
// 或
import { EnhancedLLMService } from '@/services/enhancedLLMService'
```

**新代码**:
```typescript
import { llmService } from '@/services/llm-unified'
```

### 2. API 方法对照

大部分 API 保持不变，但有一些细微差别：

| 旧方法 | 新方法 | 变化 |
|--------|--------|------|
| `llmService.initialize(configName)` | `llmService.loadConfigFromDatabase(configName)` | 方法名更明确 |
| `llmService.parseMedicalText(text, options)` | `llmService.parseMedicalText(text, options)` | 无变化 |
| `llmService.extractMedicalData(text, options)` | `llmService.extractMedicalData(text, options)` | 无变化 |
| `llmService.parseBatchMedicalTexts(texts, options)` | `llmService.parseBatchMedicalTexts(texts, options)` | 无变化 |
| `llmService.getCurrentConfig()` | `llmService.getCurrentConfig()` | 返回类型简化 |
| `llmService.updateConfig(updates)` | `llmService.updateConfig(updates)` | 无变化 |

### 3. 类型导入

**旧代码**:
```typescript
import type { ExtractedMedicalData, DocumentType } from '@/services/llmService'
```

**新代码**:
```typescript
import type { ExtractedMedicalData, DocumentType } from '@/services/llm-unified'
```

### 4. 需要更新的文件列表

根据代码搜索，以下文件引用了旧的 LLM 服务：

#### 前端视图文件
- `src/views/medical-records/SmartImportSimple.vue.ts`
- `src/views/medical-records/SmartImportMedicalRecordNew.vue.ts`
- `src/views/medical-records/LLMParseResultView.vue.ts`
- `src/views/medical-records/SmartImportMedicalRecord.vue.ts`
- `src/views/settings/SettingsView.vue.ts`
- `src/views/test/SimpleLLMTest.vue.ts`

#### 工具文件
- `src/utils/documentTypeUtils.ts`

#### 组件文件
- `src/components/LLMResultModal.vue.ts`

### 5. 迁移示例

#### 示例 1: 基本使用

**旧代码**:
```typescript
const { llmService } = await import('@/services/llmServiceNew')
await llmService.initialize('default')
const result = await llmService.parseMedicalText(text)
```

**新代码**:
```typescript
import { llmService } from '@/services/llm-unified'
await llmService.loadConfigFromDatabase('default')
const result = await llmService.parseMedicalText(text)
```

#### 示例 2: 配置更新

**旧代码**:
```typescript
const { llmService } = await import('@/services/llmServiceNew')
llmService.updateConfig({
  pointerMode: true,
  summaryMaxLength: 1000
})
```

**新代码**:
```typescript
import { llmService } from '@/services/llm-unified'
llmService.updateConfig({
  pointerMode: true,
  summaryMaxLength: 1000
})
```

#### 示例 3: 获取配置

**旧代码**:
```typescript
const config = llmService.getCurrentConfig()
console.log(config.provider.providerName)
```

**新代码**:
```typescript
const config = llmService.getCurrentConfig()
console.log(config?.provider) // 返回 'openai' | 'deepseek' | 'aliyun'
```

## 兼容性说明

### 临时兼容层

为了平滑迁移，我们保留了 `llmServiceNew.ts` 作为兼容层，它会：
1. 重新导出新的 `llmService`
2. 在控制台输出废弃警告
3. 将所有调用转发到新的实现

这意味着现有代码可以继续工作，但会看到废弃警告。

### 移除计划

兼容层将在以下时间点移除：
- **第一阶段** (当前): 创建新实现，保留兼容层
- **第二阶段** (1-2周后): 更新所有引用，移除兼容层
- **第三阶段** (1个月后): 完全移除旧代码

## 测试

迁移后请确保：

1. **功能测试**: 所有 LLM 相关功能正常工作
2. **单元测试**: 运行 `pnpm test llm-unified`
3. **集成测试**: 测试病案导入、质控分析等完整流程

## 回滚方案

如果迁移后出现问题，可以快速回滚：

```bash
# 恢复旧文件
cd apps/medqc-web/src/services
mv llmServiceNew.ts.backup llmServiceNew.ts
mv enhancedLLMService.ts.backup enhancedLLMService.ts

# 删除新目录
rm -rf llm-unified
```

## 获取帮助

如果在迁移过程中遇到问题：
1. 查看 `llm-unified/README.md` 了解详细用法
2. 查看 `llm-unified/__tests__/` 中的测试示例
3. 联系开发团队

## 检查清单

迁移完成后，请确认：

- [ ] 所有导入语句已更新
- [ ] 所有 API 调用已验证
- [ ] 单元测试通过
- [ ] 功能测试通过
- [ ] 没有 TypeScript 编译错误
- [ ] 没有运行时错误
- [ ] 性能没有明显下降

