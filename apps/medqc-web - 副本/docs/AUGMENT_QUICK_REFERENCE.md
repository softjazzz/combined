# Augment AI 快速参考指南

## 🚀 常用命令速查

### 项目启动
```bash
# 开发环境启动
npm run dev

# 初始化规则系统
npm run setup-rules-system

# 数据库迁移
npm run db:migrate

# 规则数据初始化
npm run init-comprehensive-rules
```

### 代码检查
```bash
# 类型检查
npm run type-check

# 代码格式化
npm run format

# 代码检查
npm run lint
```

## 📁 项目结构速查

```
src/
├── views/rules/           # 规则管理页面
├── services/             # 业务服务层
│   └── rules-service.ts  # 规则服务
├── utils/                # 工具函数
│   └── rules-validator.ts # 规则验证器
├── config/               # 配置文件
│   └── rules-config.ts   # 规则配置
└── types/                # 类型定义
    └── database.ts       # 数据库类型
```

## 🏥 医疗术语对照表

| 英文术语 | 中文术语 | 说明 |
|---------|---------|------|
| admission_diagnosis | 入院诊断 | 患者入院时的初步诊断 |
| discharge_diagnosis | 出院诊断 | 患者出院时的最终诊断 |
| primary_diagnosis | 主要诊断 | 主要疾病诊断 |
| secondary_diagnosis | 次要诊断 | 次要疾病诊断 |
| complication | 并发症 | 疾病过程中出现的并发症 |
| comorbidity | 合并症 | 同时存在的其他疾病 |

## 🔢 规则编码规范

### 分类编码
- **1.x.x**: 完整性规则 (Completeness)
- **2.x.x**: 一致性规则 (Consistency)
- **3.x.x**: 合理性规则 (Rationality)
- **4.x.x**: 及时性规则 (Timeliness)

### 示例编码
```
1.1.1 - 患者基本信息完整性检查
1.2.1 - 入院记录完整性检查
2.1.1 - 诊断一致性检查
3.1.1 - 药物使用合理性检查
4.1.1 - 病程记录及时性检查
```

## 💻 代码模板

### Vue组件模板
```vue
<template>
  <div class="page-container">
    <div class="page-header">
      <h1 class="page-title">页面标题</h1>
      <div class="header-actions">
        <a-button type="primary" @click="handleAction">
          操作按钮
        </a-button>
      </div>
    </div>
    
    <a-card>
      <!-- 页面内容 -->
    </a-card>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { message } from 'ant-design-vue'

// 响应式数据
const loading = ref<boolean>(false)
const dataList = ref<any[]>([])

// 方法定义
const handleAction = async () => {
  try {
    loading.value = true
    // 业务逻辑
    message.success('操作成功')
  } catch (error) {
    console.error('操作失败:', error)
    message.error('操作失败')
  } finally {
    loading.value = false
  }
}

// 生命周期
onMounted(() => {
  // 初始化逻辑
})
</script>

<style scoped>
.page-container {
  @apply p-6;
}
.page-header {
  @apply flex items-center justify-between mb-6;
}
.page-title {
  @apply text-2xl font-bold text-gray-900;
}
</style>
```

### 服务层模板
```typescript
import { supabase } from '@/lib/supabase'
import type { Database } from '@/types/supabase'

type TableRow = Database['public']['Tables']['table_name']['Row']
type TableInsert = Database['public']['Tables']['table_name']['Insert']
type TableUpdate = Database['public']['Tables']['table_name']['Update']

export class ExampleService {
  /**
   * 获取所有记录
   */
  static async getAll(): Promise<TableRow[]> {
    try {
      const { data, error } = await supabase
        .from('table_name')
        .select('*')
        .order('created_at', { ascending: false })
      
      if (error) {
        throw new Error(`获取数据失败: ${error.message}`)
      }
      
      return data || []
    } catch (error) {
      console.error('服务层错误:', error)
      throw error
    }
  }
  
  /**
   * 创建记录
   */
  static async create(data: TableInsert): Promise<TableRow> {
    try {
      const { data: result, error } = await supabase
        .from('table_name')
        .insert([data])
        .select()
        .single()
      
      if (error) {
        throw new Error(`创建失败: ${error.message}`)
      }
      
      return result
    } catch (error) {
      console.error('创建记录失败:', error)
      throw error
    }
  }
}
```

## 🎨 样式规范

### Tailwind CSS 常用类
```css
/* 布局 */
.page-container { @apply p-6; }
.page-header { @apply flex items-center justify-between mb-6; }
.page-title { @apply text-2xl font-bold text-gray-900; }

/* 卡片 */
.stat-card { @apply shadow-sm hover:shadow-md transition-shadow; }
.filter-card { @apply mb-6; }

/* 表格 */
.rule-name .name { @apply font-medium text-gray-900 mb-1; }
.rule-name .description { @apply text-sm text-gray-500 line-clamp-2; }

/* 状态标签颜色 */
.status-active { @apply text-green-600 bg-green-50; }
.status-inactive { @apply text-red-600 bg-red-50; }
.severity-critical { @apply text-red-600 bg-red-50; }
.severity-major { @apply text-orange-600 bg-orange-50; }
.severity-minor { @apply text-blue-600 bg-blue-50; }
```

## 🔍 调试技巧

### 浏览器调试
```javascript
// Vue DevTools 调试
// 在组件中添加调试点
console.log('组件数据:', { loading, rules, formData })

// 网络请求调试
// 在Network面板查看API请求
// 检查请求参数和响应数据

// 数据库查询调试
// 在Supabase控制台查看SQL日志
```

### 常见问题排查
```typescript
// 1. 数据库连接问题
const testConnection = async () => {
  const { data, error } = await supabase.from('qc_rules').select('count').limit(1)
  console.log('连接测试:', { data, error })
}

// 2. 权限问题排查
const checkPermissions = async () => {
  const { data: { user } } = await supabase.auth.getUser()
  console.log('当前用户:', user)
}

// 3. 数据验证问题
const validateData = (data: any) => {
  const validation = RulesValidator.validateRule(data)
  console.log('验证结果:', validation)
}
```

## 📊 性能优化检查点

### 前端性能
- [ ] 组件是否使用了懒加载
- [ ] 列表是否实现了分页
- [ ] 计算属性是否正确使用缓存
- [ ] 是否避免了不必要的重渲染

### 数据库性能
- [ ] 查询是否使用了适当的索引
- [ ] 是否避免了N+1查询问题
- [ ] 批量操作是否使用了批量接口
- [ ] 是否设置了合理的查询限制

## 🛡️ 安全检查点

### 数据安全
- [ ] 敏感数据是否正确处理
- [ ] 用户输入是否经过验证
- [ ] 数据库查询是否使用参数化
- [ ] 权限控制是否正确实现

### 代码安全
- [ ] 是否避免了XSS攻击
- [ ] 是否避免了SQL注入
- [ ] 文件上传是否安全
- [ ] 错误信息是否泄露敏感信息

## 📝 提交信息模板

```bash
# 功能开发
feat(rules): 添加规则批量导入功能

# Bug修复
fix(database): 修复规则权重约束问题

# 文档更新
docs(rules): 更新规则管理使用指南

# 代码重构
refactor(services): 优化规则服务层代码结构

# 性能优化
perf(rules): 优化规则列表查询性能

# 测试相关
test(rules): 添加规则验证器单元测试
```

## 🔗 常用链接

- **项目文档**: `docs/RULES_SYSTEM.md`
- **工作规则**: `docs/AUGMENT_WORK_RULES.md`
- **API文档**: `src/services/rules-service.ts`
- **类型定义**: `src/types/database.ts`
- **配置文件**: `src/config/rules-config.ts`

## 📞 问题解决流程

1. **查看控制台错误** - 检查浏览器控制台和终端输出
2. **检查文档** - 查阅相关文档和代码注释
3. **调试代码** - 使用断点和日志进行调试
4. **查看数据库** - 检查Supabase控制台的数据和日志
5. **参考示例** - 查看项目中的类似实现
6. **测试验证** - 编写测试用例验证修复

---

**版本**: v1.0  
**更新日期**: 2025-07-20  
**适用项目**: 医疗病案质控系统
