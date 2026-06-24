# 修复质控演示功能中的文书类别与质控点关联错误

## 🐛 问题描述

在质控演示页面中，当用户在第一步选择"入院记录"文书类别后，第二步显示的质控点列表中出现了不相关的"病理"类质控点，这与预期的入院记录相关质控点不符。

### 问题现象
- 用户选择"入院记录"文书类别
- 第二步显示所有质控点，包括病理、病程记录等不相关的质控点
- 没有根据文书类别进行有效筛选

## 🔍 问题根因分析

### 1. 架构分析
质控演示页面有两个不同的组件处理规则选择：

1. **RecordDocumentPicker** - 三步式选择器（病历 → 文书 → 规则）
   - ✅ 已实现正确的文书类别筛选逻辑
   - 使用 `rulesWithApplicability` 计算属性进行筛选

2. **QCRulesDemoPanel** - 主演示页面的规则配置面板
   - ❌ 缺少文书类别筛选逻辑
   - 只基于 `category`、`severity`、`status` 筛选

### 2. 数据流分析
```
LLMQCDemoEnhanced (主页面)
├── 第一步：RecordDocumentPicker (选择病历+文书)
├── 第二步：QCRulesDemoPanel (选择规则) ← 问题所在
└── 第三步：运行分析
```

主演示页面的第二步使用 `QCRulesDemoPanel`，但该组件没有接收和使用文书类别信息。

## ✅ 解决方案

### 1. 修改 QCRulesDemoPanel 组件

#### 1.1 添加文书类别筛选逻辑
```typescript
// 新增 Props
selectedDocuments?: Array<{ id: string; title?: string; type?: string; created_at?: string }>

// 新增计算属性：获取选中文书的标准类别代码
const selectedDocTypeCodes = computed<string[]>(() => {
  const docs = props.selectedDocuments || []
  const set = new Set<string>()
  docs.forEach(d => {
    const typeCode = d.type || ''
    const cat = (DOCUMENT_TYPE_TO_CATEGORY as any)[typeCode]
    let mapped = cat as string | undefined
    // 映射逻辑...
    if (mapped) set.add(mapped)
  })
  return Array.from(set)
})

// 新增计算属性：规则适用性分析
const rulesWithApplicability = computed<any[]>(() => {
  const codes = new Set(selectedDocTypeCodes.value)
  const all = availableRules
  
  const arr = all.map((r: any) => {
    const mapped = lookupRuleCategories(r)
    const raw: string[] = mapped.length > 0 ? mapped : (r.applicable_documents || [])
    const norm = raw.map(normalize).filter((x): x is string => !!x)
    
    let applicable = false
    if (codes.size === 1) {
      const [only] = Array.from(codes)
      applicable = norm.length > 0 && norm.some(d => codes.has(d))
      
      // 特殊保护：入院记录不显示手术相关规则
      if (only === 'admission_record') {
        const text = `${r.name || ''} ${r.description || ''}`
        if (/手术|术前|术后|术中|麻醉|植入|出入量|出院|死亡/.test(text)) {
          applicable = false
        }
      }
    } else {
      applicable = norm.some(d => codes.has(d))
    }
    
    return { ...r, _applicable: applicable, _disabled: !applicable }
  })
  
  return arr.sort((a: any, b: any) => Number(b._applicable) - Number(a._applicable))
})
```

#### 1.2 修改筛选逻辑
```typescript
// 修改 filteredRules 使用 rulesWithApplicability
const filteredRules = computed(() => {
  let rules = rulesWithApplicability.value  // 使用带适用性的规则列表
  
  // 其他筛选条件保持不变
  if (categoryFilter.value) {
    rules = rules.filter(rule => rule.category === categoryFilter.value)
  }
  // ...
  
  return rules
})
```

#### 1.3 添加可视化提示
```vue
<!-- 文书类别筛选提示 -->
<div v-if="selectedDocuments && selectedDocuments.length > 0" class="document-filter-info">
  <a-alert
    type="info"
    show-icon
    :message="`已根据选中的文书类别自动筛选适用规则`"
    :description="`当前文书类别：${selectedDocTypeNames.join('、')} | 显示 ${filteredRules.length} 条适用规则`"
    banner
  />
</div>
```

### 2. 修改父组件传参

#### 2.1 LLMQCDemoEnhanced.vue
```vue
<!-- 传递选中的文书信息 -->
<QCRulesDemoPanel
  :selected-rules="demoStore.selectedRules"
  :available-rules="demoStore.availableRules"
  :test-record="demoStore.testRecord"
  :selected-documents="demoStore.selectedDocumentList"  <!-- 新增 -->
  @rules-updated="handleRulesUpdated"
/>
```

## 🧪 测试验证

### 测试用例
创建了 `test-document-category-filtering.ts` 测试脚本，验证以下场景：

1. **选择入院记录文书**
   - ✅ SC-004（入院诊断）应该显示
   - ❌ PATHOLOGY-001（病理结果）应该被筛选掉
   - ❌ SC-015（医嘱变化）应该被筛选掉

### 测试结果
```
📊 筛选统计:
   适用规则: 1 条
   不适用规则: 3 条

🎯 预期验证:
✅ SC-004 正确显示为适用（入院诊断相关）
✅ PATHOLOGY-001 正确被筛选掉（病理检查不适用于入院记录）
✅ SC-015 正确被筛选掉（医嘱变化主要适用于病程记录）
```

## 📋 修改文件清单

1. **apps/medqc-web/src/components/demo/QCRulesDemoPanel.vue**
   - 添加文书类别筛选逻辑
   - 新增 `selectedDocuments` prop
   - 新增 `rulesWithApplicability` 计算属性
   - 添加可视化筛选提示

2. **apps/medqc-web/src/views/demo/LLMQCDemoEnhanced.vue**
   - 传递 `selectedDocumentList` 给 `QCRulesDemoPanel`

3. **apps/medqc-web/scripts/test-document-category-filtering.ts**
   - 新增测试脚本验证筛选逻辑

## 🎯 预期效果

修复后，当用户在质控演示页面：

1. **第一步**：选择"入院记录"文书类别
2. **第二步**：只显示与入院记录相关的质控点
   - 显示：SC-004（入院诊断相关）
   - 隐藏：病理、病程记录等不相关质控点
3. **用户体验**：看到明确的筛选提示，了解当前显示的规则数量和类别

## 🔄 兼容性说明

- ✅ 向后兼容：未选择文书时显示所有规则
- ✅ 渐进增强：有文书选择时自动筛选
- ✅ 保持原有筛选功能：类别、严重程度、状态筛选仍然有效
- ✅ 复用现有逻辑：使用与 `RecordDocumentPicker` 相同的筛选算法

## 🚀 部署建议

1. 重启前后端服务
2. 清除浏览器缓存
3. 测试完整的演示流程：选择病历 → 选择文书 → 验证规则筛选 → 运行分析
