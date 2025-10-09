# 代码注释规范指南

**文档版本**: v1.0
**创建日期**: 2025-10-09
**适用范围**: Health-QC-Monorepo 项目

---

## 📋 概述

本文档定义了项目的代码注释规范，旨在提高代码可读性和可维护性。

## 🎯 注释原则

### 1. 注释的目的

- ✅ **解释为什么**（Why），而不是什么（What）
- ✅ **说明复杂逻辑**的设计思路
- ✅ **警告潜在问题**和注意事项
- ✅ **提供使用示例**
- ❌ 不要注释显而易见的代码

### 2. 好注释 vs 坏注释

**❌ 坏注释**:
```python
# 设置 x 为 5
x = 5

# 循环遍历列表
for item in items:
    process(item)
```

**✅ 好注释**:
```python
# 设置默认超时为 5 秒，防止长时间阻塞
timeout = 5

# 批量处理用户上传的文件
# 注意：大文件可能导致内存占用过高，需要监控
for item in items:
    process(item)
```

---

## 📝 Python 注释规范

### 1. 模块级注释

每个 `.py` 文件开头应有模块说明：

```python
"""
质控服务模块

该模块提供病历质控的核心功能，包括：
- 质控规则评估
- 缺陷检测
- 评分计算
- 改进建议生成

主要类:
    QCService: 质控服务主类
    QCEngine: 质控引擎

使用示例:
    >>> service = QCService()
    >>> result = await service.evaluate(payload)
"""
```

### 2. 类注释（Docstring）

使用 Google 风格的 docstring：

```python
class QCService:
    """
    质控服务类

    负责执行病历质控评估，包括规则匹配、语义分析和评分计算。

    Attributes:
        engine_type (str): 质控引擎类型
        config (Dict): 配置信息

    Example:
        >>> service = QCService(engine_type="demo")
        >>> result = await service.evaluate(payload)
        >>> print(result["overall_score"])
        85
    """
    pass
```

### 3. 函数注释（Docstring）

```python
def normalize_rule(raw: Dict[str, Any]) -> Dict[str, Any]:
    """
    归一化质控规则数据

    将来自不同来源的规则数据统一为标准格式，确保所有必需字段都有默认值。

    Args:
        raw (Dict[str, Any]): 原始规则数据，可能包含不同的字段名

    Returns:
        Dict[str, Any]: 标准化后的规则数据，包含以下字段：
            - id: 规则唯一标识
            - name: 规则名称
            - severity: 严重程度
            - weight: 权重

    Raises:
        ValueError: 当 raw 为空或无效时

    Example:
        >>> raw = {"ruleCode": "R001", "ruleName": "入院记录"}
        >>> normalized = normalize_rule(raw)
        >>> print(normalized["id"])
        'R001'

    Note:
        如果原始数据缺少字段，会使用默认值填充
    """
    pass
```

### 4. 行内注释

```python
# 计算加权评分
# 公式：总分 = Σ(规则得分 × 权重) / 总权重
overall_score = sum(r.score * r.weight for r in results) / total_weight

# 使用缓存减少数据库查询
# TODO: 考虑使用 Redis 替代内存缓存
if cache_key in cache:
    return cache[cache_key]

# FIXME: 这里的逻辑有问题，当 rules 为空时会报错
# 临时方案：使用默认规则
if not rules:
    rules = get_default_rules()

# HACK: Supabase 的分页 API 有 bug，这里手动处理
# 相关 Issue: https://github.com/supabase/supabase/issues/12345
results = manually_paginate(data, page, page_size)
```

### 5. 复杂算法注释

```python
def calculate_similarity(text1: str, text2: str) -> float:
    """
    计算两个文本的相似度

    使用 TF-IDF + 余弦相似度算法：
    1. 对文本进行分词和去停用词
    2. 计算 TF-IDF 向量
    3. 计算余弦相似度

    时间复杂度: O(n*m)，其中 n 和 m 是两个文本的词数
    空间复杂度: O(n+m)

    Args:
        text1: 第一个文本
        text2: 第二个文本

    Returns:
        float: 相似度分数，范围 [0, 1]
    """
    # Step 1: 分词
    # 使用 jieba 分词库，考虑了医疗专业词汇
    tokens1 = jieba.cut(text1)
    tokens2 = jieba.cut(text2)

    # Step 2: 去停用词
    # 停用词列表来源：医疗领域专用停用词表
    stop_words = load_medical_stop_words()
    filtered1 = [t for t in tokens1 if t not in stop_words]
    filtered2 = [t for t in tokens2 if t not in stop_words]

    # Step 3: 计算 TF-IDF
    # 使用 sklearn 的 TfidfVectorizer
    vectorizer = TfidfVectorizer()
    tfidf_matrix = vectorizer.fit_transform([filtered1, filtered2])

    # Step 4: 计算余弦相似度
    # 公式：cos(θ) = A·B / (||A|| * ||B||)
    similarity = cosine_similarity(tfidf_matrix[0], tfidf_matrix[1])

    return float(similarity)
```

---

## 🔤 TypeScript/JavaScript 注释规范

### 1. 文件头注释

```typescript
/**
 * 质控服务模块
 *
 * 提供与后端质控 API 交互的功能
 *
 * @module services/qcService
 * @author MedQC Team
 */
```

### 2. 接口注释

```typescript
/**
 * 质控结果接口
 *
 * @interface QCResult
 * @property {string} id - 结果ID
 * @property {number} score - 评分（0-100）
 * @property {QCIssue[]} issues - 缺陷列表
 */
interface QCResult {
  id: string
  score: number
  issues: QCIssue[]
}
```

### 3. 函数注释

```typescript
/**
 * 执行质控评估
 *
 * @async
 * @function evaluateRecord
 * @param {string} recordId - 病历ID
 * @param {string[]} ruleIds - 质控规则ID列表
 * @returns {Promise<QCResult>} 质控结果
 * @throws {Error} 当病历不存在时抛出异常
 *
 * @example
 * const result = await evaluateRecord('record-123', ['rule-1', 'rule-2'])
 * console.log(result.score) // 85
 */
async function evaluateRecord(
  recordId: string,
  ruleIds: string[]
): Promise<QCResult> {
  // 实现...
}
```

### 4. Vue 组件注释

```vue
<script setup lang="ts">
/**
 * 质控结果展示组件
 *
 * 功能:
 * - 显示质控评分和等级
 * - 展示缺陷列表
 * - 提供改进建议
 *
 * Props:
 * @prop {QCResult} result - 质控结果数据
 * @prop {boolean} [loading=false] - 加载状态
 *
 * Emits:
 * @emits {QCIssue} issue-click - 点击缺陷项时触发
 *
 * @example
 * <QCResultView
 *   :result="qcResult"
 *   :loading="isLoading"
 *   @issue-click="handleIssueClick"
 * />
 */

// Props 定义
const props = defineProps<{
  result: QCResult
  loading?: boolean
}>()

// Emits 定义
const emit = defineEmits<{
  (e: 'issue-click', issue: QCIssue): void
}>()
</script>
```

---

## 🏷️ 特殊标记

### 1. 标记类型

| 标记 | 含义 | 使用场景 |
|------|------|---------|
| `TODO` | 待办事项 | 需要将来实现的功能 |
| `FIXME` | 需要修复 | 已知的 bug 或问题 |
| `HACK` | 临时方案 | 不优雅但可用的解决方案 |
| `NOTE` | 重要说明 | 需要特别注意的地方 |
| `OPTIMIZE` | 需要优化 | 性能可以改进的地方 |
| `DEPRECATED` | 已废弃 | 不建议使用的代码 |

### 2. 使用示例

```python
# TODO: 添加缓存机制提高性能
# 预计工时: 4h
# 负责人: @zhangsan
# Issue: #123
def get_qc_rules():
    pass

# FIXME: 这里会导致内存泄漏
# 原因: 没有正确关闭数据库连接
# Issue: #456
def query_database():
    conn = get_connection()
    # 查询操作...
    # 缺少 conn.close()

# HACK: Supabase SDK 的 bug 导致无法使用 IN 查询
# 临时方案: 循环查询
# 相关 Issue: supabase/supabase#789
for rule_id in rule_ids:
    result = supabase.table("rules").select("*").eq("id", rule_id).execute()

# NOTE: 此函数必须在主线程中调用
# 原因: 使用了非线程安全的全局变量
def process_in_main_thread():
    pass

# OPTIMIZE: 这里的循环可以用向量化操作替代
# 预期性能提升: 10x
for i in range(len(array)):
    result[i] = array[i] * 2

# DEPRECATED: 使用 new_function() 替代
# 移除时间: v2.0.0
def old_function():
    warnings.warn("old_function is deprecated, use new_function instead")
    pass
```

---

## 📊 注释覆盖率目标

### 1. 目标

| 代码类型 | 注释覆盖率目标 | 当前 | 状态 |
|---------|--------------|------|------|
| 模块文件 | 100% | ~40% | ⚠️ |
| 公开类 | 100% | ~39% | ⚠️ |
| 公开函数 | 80% | ~27% | ❌ |
| 复杂函数 | 100% | ~20% | ❌ |

### 2. 检查方式

```bash
# Python 代码注释分析
python scripts/analyze_code_comments.py

# TypeScript 代码注释分析（需要 typedoc）
npx typedoc --options typedoc.json
```

---

## 🛠️ 工具和插件

### 1. VSCode 插件

- **Python Docstring Generator**: 自动生成 docstring
- **Better Comments**: 高亮 TODO、FIXME 等标记
- **Document This**: TypeScript 注释生成

### 2. Pre-commit Hook

```bash
# .git/hooks/pre-commit
# 检查注释覆盖率
python scripts/analyze_code_comments.py --fail-under 60
```

---

## ✅ 检查清单

### 代码提交前

- [ ] 所有公开类都有 docstring
- [ ] 所有公开函数都有 docstring
- [ ] 复杂逻辑有详细注释
- [ ] 所有 TODO 都有 Issue 链接
- [ ] 所有 FIXME 都有说明原因
- [ ] 所有 HACK 都有替代方案说明
- [ ] 注释中没有敏感信息（密钥、密码等）

### 代码审查时

- [ ] 注释是否准确描述了代码行为
- [ ] 注释是否解释了"为什么"而不仅是"是什么"
- [ ] 复杂算法是否有时间/空间复杂度说明
- [ ] 是否有使用示例
- [ ] 是否有异常情况说明

---

## 📚 参考资料

- [PEP 257 - Docstring Conventions](https://www.python.org/dev/peps/pep-0257/)
- [Google Python Style Guide](https://google.github.io/styleguide/pyguide.html)
- [JSDoc Reference](https://jsdoc.app/)
- [TypeScript TSDoc](https://tsdoc.org/)

---

## 🔄 更新日志

| 日期 | 版本 | 变更内容 |
|------|------|---------|
| 2025-10-09 | v1.0 | 初始版本，定义基础规范 |

---

**文档维护**: P2-1 代码注释完善任务
**创建日期**: 2025-10-09
**最后更新**: 2025-10-09
