# 增强LLM配置使用指南

本指南介绍如何使用新的增强LLM配置系统，支持多厂商、多模型的灵活配置。

## 🚀 **立即开始 - 在Supabase中执行数据库脚本**

### **第一步：访问Supabase SQL Editor**
1. 登录您的Supabase项目：`https://app.supabase.com/project/[your-project-id]/sql`
2. 点击 "SQL Editor"

### **第二步：执行数据库脚本**
1. 复制 `supabase/setup-database.sql` 文件的完整内容
2. 粘贴到SQL Editor中
3. 点击 "Run" 按钮执行

### **第三步：验证执行结果**
执行成功后，您应该看到类似这样的输出：
```
Enhanced database setup completed successfully!
providers_configured: 7

Total models configured:
models_count: 20

Test table created successfully!
sample_records_inserted: 2
```

### **第四步：开始使用**
1. 访问智能导入页面：`http://localhost:3000/dashboard/medical-records/smart-import`
2. 点击右上角的"API配置"按钮
3. 选择厂商和模型，输入API密钥
4. 测试连接并保存配置
5. 开始使用真实的大模型API进行病历解析！

## 🎯 **主要改进**

### **1. 统一端点配置**
- ✅ **阿里通义千问端点修正**：从旧版API端点修正为官方推荐的兼容模式端点
- ✅ **统一格式**：所有主流厂商都使用兼容OpenAI的格式，简化集成

### **2. 多模型支持**
- ✅ **每个厂商支持多个模型**：用户可以根据需求选择最适合的模型
- ✅ **模型特性标签**：包含定价层级、上下文长度、特殊能力等信息
- ✅ **智能推荐**：为每个厂商设置推荐的默认模型

### **3. 数据库持久化**
- ✅ **配置存储**：用户配置持久化存储在数据库中
- ✅ **使用统计**：详细记录API使用情况和性能数据
- ✅ **历史追踪**：完整的解析历史和模型使用记录

## 🚀 **快速开始**

### **步骤1: 应用数据库更改**

在Supabase SQL Editor中执行更新后的数据库脚本：

```sql
-- 执行完整的 setup-database.sql 脚本
-- 或者运行迁移脚本
```

### **步骤2: 配置API**

1. **访问智能导入页面**
2. **点击"API配置"按钮**
3. **选择您要使用的厂商**
4. **选择具体的模型**
5. **输入API密钥**
6. **测试连接**
7. **保存配置**

### **步骤3: 开始使用**

配置完成后，智能病历导入将使用您选择的真实API进行解析。

## 📊 **支持的厂商和模型**

### **🔥 阿里通义千问 (推荐)**
**端点**: `https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions`

| 模型 | 描述 | 上下文长度 | 定价 | 特点 |
|------|------|------------|------|------|
| qwen-turbo | 快速响应版本 | 8K | 低 | 快速响应、成本低 |
| **qwen-plus** | 平衡版本(推荐) | 32K | 中 | 平衡性能、中等成本 |
| qwen-max | 最强性能版本 | 32K | 高 | 最强性能、复杂推理 |
| qwen3-235b | 超大参数模型 | 32K | 很高 | 超大参数、顶级性能 |
| qwen-doc-turbo | 文档理解专用 | 32K | 中 | 文档理解、结构化提取 |

### **🤖 OpenAI GPT**
**端点**: `https://api.openai.com/v1/chat/completions`

| 模型 | 描述 | 上下文长度 | 定价 | 特点 |
|------|------|------------|------|------|
| **gpt-4** | 最强模型(推荐) | 8K | 高 | 复杂推理、高准确率 |
| gpt-4-turbo | 快速版本 | 128K | 中 | 快速响应、长文本 |
| gpt-3.5-turbo | 经济版本 | 16K | 低 | 性价比高、快速响应 |

### **🐻 百度文心一言**
**端点**: `https://aip.baidubce.com/rpc/2.0/ai_custom/v1/wenxinworkshop/chat/completions`

| 模型 | 描述 | 上下文长度 | 定价 | 特点 |
|------|------|------------|------|------|
| **ERNIE-4.0-8K** | 标准版(推荐) | 8K | 中 | 中文优化、企业级 |
| ERNIE-4.0-Turbo-8K | 加速版 | 8K | 低 | 快速响应、成本低 |
| ERNIE-3.5-8K | 经济版 | 8K | 很低 | 经济实惠、基础功能 |

### **🐧 腾讯混元**
**端点**: `https://hunyuan.tencentcloudapi.com/v1/chat/completions`

| 模型 | 描述 | 上下文长度 | 定价 | 特点 |
|------|------|------------|------|------|
| hunyuan-lite | 轻量版本 | 4K | 低 | 轻量级、快速响应 |
| **hunyuan-standard** | 标准版(推荐) | 8K | 中 | 平衡性能、标准功能 |
| hunyuan-pro | 专业版本 | 32K | 高 | 医疗专业、长文本 |

### **🧠 智谱ChatGLM**
**端点**: `https://open.bigmodel.cn/api/paas/v4/chat/completions`

| 模型 | 描述 | 上下文长度 | 定价 | 特点 |
|------|------|------------|------|------|
| **glm-4** | 最新版本(推荐) | 128K | 中 | 长文本、多模态 |
| glm-4-air | 轻量版本 | 128K | 低 | 轻量级、高效率 |
| glm-4-flash | 极速版本 | 128K | 很低 | 极速响应、超低成本 |

## 💡 **使用建议**

### **开发环境**
```typescript
// 使用模拟模式，无需API密钥
const configManager = new EnhancedLLMApiConfigManager('mock')
```

### **生产环境 - 国内推荐**
```typescript
// 阿里通义千问 - 稳定可靠，中文优秀
const configManager = new EnhancedLLMApiConfigManager('alibaba', 'qwen-plus')
configManager.setApiKey('your-api-key')
```

### **医疗场景 - 专业推荐**
```typescript
// 腾讯混元专业版 - 医疗垂直优化
const configManager = new EnhancedLLMApiConfigManager('tencent', 'hunyuan-pro')
configManager.setApiKey('your-api-key')
```

### **成本敏感 - 经济推荐**
```typescript
// 智谱GLM-4-Flash - 超低成本
const configManager = new EnhancedLLMApiConfigManager('zhipu', 'glm-4-flash')
configManager.setApiKey('your-api-key')
```

## 🔧 **高级配置**

### **动态模型切换**
```typescript
const configManager = new EnhancedLLMApiConfigManager('alibaba')

// 简单任务使用快速模型
configManager.switchModel('qwen-turbo')

// 复杂任务切换到强力模型
configManager.switchModel('qwen-max')

// 文档解析使用专用模型
configManager.switchModel('qwen-doc-turbo')
```

### **批量处理优化**
```typescript
// 根据任务复杂度选择模型
function selectOptimalModel(textLength: number, complexity: 'simple' | 'complex') {
  if (complexity === 'simple' && textLength < 1000) {
    return 'qwen-turbo'  // 快速处理简单任务
  } else if (textLength > 10000) {
    return 'qwen-max'    // 长文本使用强力模型
  } else {
    return 'qwen-plus'   // 默认平衡选择
  }
}
```

### **成本控制**
```typescript
// 设置成本控制策略
const costControlConfig = {
  maxTokensPerDay: 100000,
  preferredPricingTier: 'medium',
  fallbackModel: 'qwen-turbo'
}
```

## 📈 **监控和统计**

### **查看使用统计**
```sql
-- 查看本月LLM使用情况
SELECT * FROM llm_usage_stats;

-- 查看特定提供商的模型使用情况
SELECT * FROM get_provider_models('alibaba');
```

### **性能分析**
```sql
-- 分析不同模型的性能表现
SELECT 
    provider_name,
    model_name,
    AVG(processing_time_ms) as avg_time,
    AVG(confidence_scores->>'overall') as avg_confidence
FROM ai_parsing_history aph
JOIN llm_api_providers p ON aph.provider_id = p.id
JOIN llm_models m ON aph.model_id = m.id
GROUP BY provider_name, model_name
ORDER BY avg_confidence DESC;
```

## 🚨 **注意事项**

### **数据安全**
- 医疗数据属于敏感信息，选择API时需考虑数据安全
- 推荐使用国内服务商或本地部署
- API密钥加密存储，定期更换

### **成本控制**
- 大模型API按Token计费，注意控制成本
- 可设置每日调用限额
- 监控API使用情况，及时调整策略

### **性能优化**
- 根据任务复杂度选择合适的模型
- 合理设置并发数量
- 使用缓存减少重复调用

## 🔍 **故障排除**

### **常见问题**

1. **端点连接失败**
   - 检查网络连接
   - 确认端点地址正确
   - 验证API密钥有效性

2. **模型不支持**
   - 确认选择的模型在当前厂商下可用
   - 检查模型代码拼写
   - 查看厂商最新模型列表

3. **解析质量不佳**
   - 尝试切换到更强的模型
   - 优化输入文本格式
   - 调整提示词参数

## 📞 **技术支持**

如果遇到问题，请：
1. 查看控制台错误日志
2. 检查数据库配置状态
3. 参考厂商官方文档
4. 联系技术支持团队

---

**现在您可以享受强大而灵活的多模型LLM配置系统！** 🎉
