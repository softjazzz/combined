# 环境配置指南

## 🔧 环境变量配置

### **问题解决**

在开发过程中遇到了 `process is not defined` 错误，这是因为在浏览器环境中使用了Node.js的`process.env`。

**错误信息：**
```
ReferenceError: process is not defined
    LLMService llmService.ts:116
```

**解决方案：**
1. 在Vite项目中应该使用 `import.meta.env` 而不是 `process.env`
2. 或者使用默认配置避免环境变量依赖

### **当前配置**

```typescript
// LLMService 构造函数
constructor(config: {
  apiEndpoint?: string
  apiKey?: string
  model?: string
} = {}) {
  // 使用默认配置，避免环境变量问题
  this.apiEndpoint = config.apiEndpoint || 'http://localhost:8000'
  this.apiKey = config.apiKey || ''
  this.model = config.model || 'medical-llm-v1'
}
```

## 📋 环境变量列表

### **Supabase配置**
```env
# Supabase数据库连接
VITE_SUPABASE_URL=https://your-project.supabase.co
VITE_SUPABASE_ANON_KEY=your-anon-key
```

### **LLM服务配置**
```env
# LLM API配置
VITE_LLM_API_ENDPOINT=http://localhost:8000
VITE_LLM_API_KEY=your-llm-api-key
VITE_LLM_MODEL=medical-llm-v1
```

### **安全配置**
```env
# 数据加密
VITE_ENCRYPTION_KEY=your-encryption-key-32-chars-long
VITE_MAX_FILE_SIZE=10485760
```

### **应用配置**
```env
# 应用信息
VITE_APP_TITLE=医疗质控系统
VITE_APP_VERSION=1.0.0
VITE_APP_ENV=development
```

## 🚀 部署配置

### **开发环境**
```bash
# 复制环境变量模板
cp .env.example .env.local

# 编辑配置
nano .env.local
```

### **生产环境**
```bash
# 生产环境变量
VITE_SUPABASE_URL=https://prod-project.supabase.co
VITE_SUPABASE_ANON_KEY=prod-anon-key
VITE_LLM_API_ENDPOINT=https://api.your-domain.com
VITE_APP_ENV=production
```

### **测试环境**
```bash
# 测试环境变量
VITE_SUPABASE_URL=https://test-project.supabase.co
VITE_SUPABASE_ANON_KEY=test-anon-key
VITE_LLM_API_ENDPOINT=https://test-api.your-domain.com
VITE_APP_ENV=testing
```

## 🔒 安全注意事项

### **敏感信息保护**
1. **不要提交敏感信息**到版本控制
2. **使用.env.local**存储本地配置
3. **生产环境**使用环境变量注入

### **API密钥管理**
```typescript
// 安全的API密钥使用
const apiKey = import.meta.env.VITE_LLM_API_KEY
if (!apiKey && import.meta.env.PROD) {
  throw new Error('LLM API密钥未配置')
}
```

## 🛠️ 配置验证

### **环境检查函数**
```typescript
export function validateEnvironment() {
  const requiredVars = [
    'VITE_SUPABASE_URL',
    'VITE_SUPABASE_ANON_KEY'
  ]
  
  const missing = requiredVars.filter(
    varName => !import.meta.env[varName]
  )
  
  if (missing.length > 0) {
    console.warn('缺少环境变量:', missing)
  }
  
  return missing.length === 0
}
```

### **配置状态显示**
```typescript
// 在开发环境显示配置状态
if (import.meta.env.DEV) {
  console.log('环境配置:', {
    supabaseUrl: import.meta.env.VITE_SUPABASE_URL,
    llmEndpoint: import.meta.env.VITE_LLM_API_ENDPOINT,
    appEnv: import.meta.env.VITE_APP_ENV
  })
}
```

## 📝 配置文件模板

### **.env.example**
```env
# Supabase配置
VITE_SUPABASE_URL=https://your-project.supabase.co
VITE_SUPABASE_ANON_KEY=your-anon-key

# LLM服务配置
VITE_LLM_API_ENDPOINT=http://localhost:8000
VITE_LLM_API_KEY=your-llm-api-key
VITE_LLM_MODEL=medical-llm-v1

# 安全配置
VITE_ENCRYPTION_KEY=your-encryption-key-32-chars-long
VITE_MAX_FILE_SIZE=10485760

# 应用配置
VITE_APP_TITLE=医疗质控系统
VITE_APP_VERSION=1.0.0
VITE_APP_ENV=development
```

### **.env.local** (本地开发)
```env
# 本地开发配置
VITE_SUPABASE_URL=https://dgsdkdbjpucyawnyfbdu.supabase.co
VITE_SUPABASE_ANON_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
VITE_LLM_API_ENDPOINT=http://localhost:8000
VITE_APP_ENV=development
```

## 🔄 动态配置

### **运行时配置**
```typescript
// 支持运行时配置更新
export class ConfigManager {
  private config: Record<string, string> = {}
  
  constructor() {
    this.loadFromEnv()
  }
  
  private loadFromEnv() {
    this.config = {
      supabaseUrl: import.meta.env.VITE_SUPABASE_URL || '',
      supabaseKey: import.meta.env.VITE_SUPABASE_ANON_KEY || '',
      llmEndpoint: import.meta.env.VITE_LLM_API_ENDPOINT || 'http://localhost:8000'
    }
  }
  
  get(key: string): string {
    return this.config[key] || ''
  }
  
  set(key: string, value: string) {
    this.config[key] = value
  }
}
```

### **配置热更新**
```typescript
// 开发环境支持配置热更新
if (import.meta.env.DEV) {
  if (import.meta.hot) {
    import.meta.hot.accept('./config', (newConfig) => {
      console.log('配置已更新:', newConfig)
      // 重新初始化服务
    })
  }
}
```

## 📊 配置监控

### **配置使用统计**
```typescript
export function trackConfigUsage() {
  const usage = {
    supabaseConnections: 0,
    llmApiCalls: 0,
    configErrors: 0
  }
  
  // 统计配置使用情况
  return usage
}
```

### **错误报告**
```typescript
export function reportConfigError(error: Error, context: string) {
  if (import.meta.env.PROD) {
    // 生产环境发送错误报告
    console.error(`配置错误 [${context}]:`, error)
  } else {
    // 开发环境详细日志
    console.warn(`配置警告 [${context}]:`, error)
  }
}
```

## 🧪 测试配置

### **配置测试**
```typescript
describe('环境配置', () => {
  test('应该加载必需的环境变量', () => {
    expect(import.meta.env.VITE_SUPABASE_URL).toBeDefined()
    expect(import.meta.env.VITE_SUPABASE_ANON_KEY).toBeDefined()
  })
  
  test('应该有有效的API端点', () => {
    const endpoint = import.meta.env.VITE_LLM_API_ENDPOINT
    expect(endpoint).toMatch(/^https?:\/\//)
  })
})
```

### **集成测试**
```typescript
test('应该能够连接到Supabase', async () => {
  const { supabase } = await import('@/lib/supabase')
  const { data, error } = await supabase.from('medical_records').select('count')
  expect(error).toBeNull()
})
```

## 📚 最佳实践

### **配置管理原则**
1. **分层配置**：默认值 < 环境变量 < 运行时配置
2. **类型安全**：使用TypeScript定义配置接口
3. **验证机制**：启动时验证必需配置
4. **错误处理**：优雅处理配置缺失

### **开发建议**
1. **本地开发**：使用.env.local文件
2. **团队协作**：维护.env.example模板
3. **部署自动化**：使用CI/CD注入环境变量
4. **监控告警**：配置错误及时通知

这个配置指南解决了环境变量使用问题，并提供了完整的配置管理方案。
