# Migration 006 使用指南

## 📚 快速开始

本指南介绍如何在应用代码中使用 Migration 006 添加的 `applicable_documents` 字段和相关功能。

## 🎯 核心功能

### 1. 数据库层面筛选规则

使用新的 `applicable_documents` 字段，可以在数据库层面高效筛选适用于特定文书类型的规则。

### 2. 辅助函数

提供了 `get_applicable_rules()` 函数，简化查询逻辑。

### 3. 统计视图

提供了两个视图用于规则统计和分析。

---

## 💻 代码示例

### Python (Supabase Client)

#### 方式 1: 使用 RPC 调用函数（推荐）

```python
from supabase import create_client, Client

# 初始化 Supabase 客户端
supabase: Client = create_client(supabase_url, supabase_key)

async def get_rules_for_document(document_type: str, is_active: bool = True):
    """
    获取适用于指定文书类型的规则
    
    Args:
        document_type: 文书类型，如 "首次病程记录"
        is_active: 是否只返回激活的规则
    
    Returns:
        规则列表
    """
    response = await supabase.rpc(
        'get_applicable_rules',
        {
            'p_document_type': document_type,
            'p_is_active': is_active
        }
    ).execute()
    
    return response.data

# 使用示例
rules = await get_rules_for_document('首次病程记录', True)
print(f"找到 {len(rules)} 条适用规则")
```

#### 方式 2: 使用 Supabase 查询

```python
async def get_rules_for_document_v2(document_type: str):
    """
    使用 Supabase 查询语法筛选规则
    """
    response = await supabase.table('qc_rules') \
        .select('*') \
        .eq('is_active', True) \
        .or_(
            f'applicable_documents.cs.{{{document_type}}},'
            f'applicable_documents.is.null,'
            f'applicable_documents.eq.{{}}'
        ) \
        .execute()
    
    return response.data
```

#### 方式 3: 原始 SQL 查询

```python
async def get_rules_for_document_v3(document_type: str):
    """
    使用原始 SQL 查询
    """
    query = """
        SELECT *
        FROM qc_rules
        WHERE is_active = true
        AND (
            %s = ANY(applicable_documents)
            OR applicable_documents IS NULL
            OR array_length(applicable_documents, 1) IS NULL
            OR array_length(applicable_documents, 1) = 0
        )
        ORDER BY name
    """
    
    response = await supabase.rpc('exec_sql', {
        'query': query,
        'params': [document_type]
    }).execute()
    
    return response.data
```

### JavaScript/TypeScript

#### 使用 Supabase JS Client

```typescript
import { createClient } from '@supabase/supabase-js'

const supabase = createClient(supabaseUrl, supabaseKey)

// 方式 1: 使用 RPC 函数（推荐）
async function getRulesForDocument(
  documentType: string,
  isActive: boolean = true
) {
  const { data, error } = await supabase.rpc('get_applicable_rules', {
    p_document_type: documentType,
    p_is_active: isActive
  })
  
  if (error) {
    console.error('Error fetching rules:', error)
    return []
  }
  
  return data
}

// 方式 2: 使用查询构建器
async function getRulesForDocumentV2(documentType: string) {
  const { data, error } = await supabase
    .from('qc_rules')
    .select('*')
    .eq('is_active', true)
    .or(
      `applicable_documents.cs.{${documentType}},` +
      `applicable_documents.is.null,` +
      `applicable_documents.eq.{}`
    )
  
  if (error) {
    console.error('Error fetching rules:', error)
    return []
  }
  
  return data
}

// 使用示例
const rules = await getRulesForDocument('首次病程记录', true)
console.log(`找到 ${rules.length} 条适用规则`)
```

---

## 📊 查询统计信息

### 获取规则统计

```typescript
// 获取总体统计
async function getRulesStatistics() {
  const { data, error } = await supabase
    .from('qc_rules_statistics')
    .select('*')
    .single()
  
  if (error) {
    console.error('Error fetching statistics:', error)
    return null
  }
  
  return data
}

// 使用示例
const stats = await getRulesStatistics()
console.log('规则统计:', {
  总规则数: stats.total_rules,
  激活规则: stats.active_rules,
  通用规则: stats.universal_rules,
  特定规则: stats.specific_rules
})
```

### 按文书类型统计

```typescript
// 获取按文书类型的规则分布
async function getRulesByDocumentType() {
  const { data, error } = await supabase
    .from('qc_rules_by_document_type')
    .select('*')
    .order('rule_count', { ascending: false })
  
  if (error) {
    console.error('Error fetching document type stats:', error)
    return []
  }
  
  return data
}

// 使用示例
const docTypeStats = await getRulesByDocumentType()
docTypeStats.forEach(stat => {
  console.log(`${stat.document_type}: ${stat.rule_count} 条规则`)
})
```

---

## 🔧 常见使用场景

### 场景 1: 病历质控分析

```python
async def analyze_medical_record(record_id: str, document_type: str):
    """
    分析病历记录
    """
    # 1. 获取适用的规则
    rules = await get_rules_for_document(document_type, is_active=True)
    
    # 2. 获取病历内容
    record = await supabase.table('medical_records') \
        .select('*') \
        .eq('id', record_id) \
        .single() \
        .execute()
    
    # 3. 应用规则进行质控
    results = []
    for rule in rules:
        result = await apply_rule(record.data, rule)
        results.append(result)
    
    return results
```

### 场景 2: 规则管理界面

```typescript
// 获取所有文书类型及其规则数量
async function getDocumentTypesWithRuleCounts() {
  const { data, error } = await supabase
    .from('qc_rules_by_document_type')
    .select('document_type, rule_count, active_rule_count')
    .order('rule_count', { ascending: false })
  
  return data || []
}

// 在 Vue 组件中使用
const documentTypes = ref([])

onMounted(async () => {
  documentTypes.value = await getDocumentTypesWithRuleCounts()
})
```

### 场景 3: 批量质控

```python
async def batch_qc_analysis(record_ids: list[str]):
    """
    批量质控分析
    """
    results = {}
    
    for record_id in record_ids:
        # 获取病历
        record = await get_medical_record(record_id)
        document_type = record.get('document_type', '通用')
        
        # 获取适用规则（使用缓存）
        rules = await get_rules_for_document(document_type)
        
        # 执行质控
        results[record_id] = await analyze_with_rules(record, rules)
    
    return results
```

---

## ⚡ 性能优化建议

### 1. 使用缓存

```python
from functools import lru_cache
from datetime import datetime, timedelta

# 缓存规则查询结果（5分钟）
_rules_cache = {}
_cache_timeout = timedelta(minutes=5)

async def get_rules_for_document_cached(document_type: str):
    cache_key = f"rules_{document_type}"
    
    # 检查缓存
    if cache_key in _rules_cache:
        cached_data, cached_time = _rules_cache[cache_key]
        if datetime.now() - cached_time < _cache_timeout:
            return cached_data
    
    # 查询数据库
    rules = await get_rules_for_document(document_type)
    
    # 更新缓存
    _rules_cache[cache_key] = (rules, datetime.now())
    
    return rules
```

### 2. 批量查询

```python
async def get_rules_for_multiple_documents(document_types: list[str]):
    """
    一次性获取多种文书类型的规则
    """
    # 使用 IN 查询
    response = await supabase.table('qc_rules') \
        .select('*') \
        .eq('is_active', True) \
        .or_(
            f'applicable_documents.ov.{{{",".join(document_types)}}},'
            f'applicable_documents.is.null'
        ) \
        .execute()
    
    return response.data
```

---

## 🐛 故障排查

### 问题 1: 查询返回空结果

**可能原因**:
- 文书类型名称不匹配
- 所有规则都被禁用
- `applicable_documents` 字段为空

**解决方法**:
```sql
-- 检查规则的 applicable_documents 字段
SELECT name, applicable_documents, is_active
FROM qc_rules
LIMIT 10;

-- 检查是否有通用规则
SELECT COUNT(*) 
FROM qc_rules 
WHERE applicable_documents IS NULL 
   OR array_length(applicable_documents, 1) = 0;
```

### 问题 2: 性能较慢

**解决方法**:
```sql
-- 检查索引是否存在
SELECT indexname, indexdef
FROM pg_indexes
WHERE tablename = 'qc_rules';

-- 如果索引不存在，重新创建
CREATE INDEX IF NOT EXISTS idx_qc_rules_applicable_documents 
ON qc_rules USING GIN (applicable_documents);
```

---

## 📚 相关资源

- [PostgreSQL 数组操作文档](https://www.postgresql.org/docs/current/functions-array.html)
- [Supabase JavaScript Client 文档](https://supabase.com/docs/reference/javascript/introduction)
- [Supabase Python Client 文档](https://supabase.com/docs/reference/python/introduction)

---

**最后更新**: 2025-10-11  
**版本**: 1.0

