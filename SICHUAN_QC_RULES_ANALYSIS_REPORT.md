# 四川质控引擎 68 条语义质控规则分析报告 🔍

**分析时间**: 2025-10-11  
**分析人**: Augment Agent  
**分析范围**: 数据库结构、代码实现、规则分类

---

## 📊 执行摘要

### 核心发现

1. ✅ **68 条规则已按病历单据类型进行分类**
2. ✅ **数据库支持 `applicable_documents` 字段（通过 `check_logic` JSONB 字段）**
3. ⚠️ **代码实现中规则筛选逻辑存在问题**
4. ❌ **四川质控引擎未真正使用数据库中的规则**

---

## 1. 数据库表结构分析

### 1.1 `qc_rules` 表结构

#### 基础 Schema（`000_init_base_schema.sql`）

```sql
CREATE TABLE IF NOT EXISTS qc_rules (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  name TEXT NOT NULL,
  description TEXT,
  category TEXT NOT NULL,
  prompt_template TEXT NOT NULL,  -- ⭐ 核心字段：Prompt 模板
  is_active BOOLEAN DEFAULT true,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
  updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
```

**问题**: ❌ 缺少 `applicable_documents` 字段

#### 增强 Schema（`002_add_rules_engine_support.sql`）

```sql
CREATE TABLE IF NOT EXISTS qc_rules (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    rule_code VARCHAR(50) UNIQUE NOT NULL,
    name VARCHAR(200) NOT NULL,
    description TEXT,
    category VARCHAR(50) NOT NULL CHECK (category IN ('completeness', 'consistency', 'rationality', 'timeliness', 'similarity', 'compliance')),
    rule_type VARCHAR(20) NOT NULL CHECK (rule_type IN ('objective', 'subjective', 'hybrid')),
    severity VARCHAR(20) NOT NULL CHECK (severity IN ('critical', 'major', 'minor')),
    max_score INTEGER NOT NULL DEFAULT 100,
    weight DECIMAL(3,2) NOT NULL DEFAULT 1.0,
    is_active BOOLEAN NOT NULL DEFAULT true,
    version VARCHAR(10) NOT NULL DEFAULT '1.0',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    created_by UUID REFERENCES auth.users(id)
);
```

**问题**: ❌ 仍然缺少 `applicable_documents` 字段

### 1.2 实际实现方式

根据代码分析（`app/routers/semantic_rules.py`），`applicable_documents` 字段是通过以下方式存储的：

```python
# 从 check_logic JSONB 字段中读取
check_logic = r.get("check_logic") if isinstance(r.get("check_logic"), dict) else {}
docs = (
    (check_logic or {}).get("applicable_documents")
    or r.get("applicable_documents")
    or r.get("document_types")
    or r.get("applicable_record_types")
    or []
)
```

**结论**: ✅ `applicable_documents` 存储在 `check_logic` JSONB 字段中

---

## 2. 68 条规则的分类情况

### 2.1 规则分组（根据文档）

根据 `四川省质控功能实现总结.md`，68 条规则按病历单据类型分为 4 组：

| 病历单据类型 | 规则编码范围 | 规则数量 | 说明 |
|------------|------------|---------|------|
| **病程记录** | SC-001 ~ SC-020 | 20 条 | 检查病程记录的完整性、逻辑性和规范性 |
| **手术记录** | SC-021 ~ SC-035 | 15 条 | 关注手术过程、并发症记录和术后情况 |
| **入院记录** | SC-036 ~ SC-050 | 15 条 | 验证主诉、现病史、体格检查等关键信息 |
| **出院记录** | SC-051 ~ SC-068 | 18 条 | 检查诊断一致性、治疗效果和出院指导 |
| **总计** | SC-001 ~ SC-068 | **68 条** | 覆盖 4 种主要病历单据类型 |

**结论**: ✅ 68 条规则已按病历单据类型进行了明确分类

### 2.2 规则类别（category）

根据数据库约束，规则分为 6 个类别：

| 类别 | 英文名 | 说明 | 示例规则 |
|------|--------|------|---------|
| **完整性** | completeness | 检查必填字段是否完整 | 基本信息完整性、诊断信息完整性 |
| **一致性** | consistency | 检查数据逻辑一致性 | 诊断一致性、时间逻辑一致性 |
| **合理性** | rationality | 检查诊疗方案合理性 | 诊断合理性、治疗合理性 |
| **时效性** | timeliness | 检查记录时效性 | 记录时效性、诊疗时效性 |
| **相似性** | similarity | 检查内容相似性 | （暂未使用） |
| **合规性** | compliance | 检查是否符合规范 | 知情同意合规、医疗规范合规 |

**结论**: ✅ 规则按类别进行了分类

### 2.3 规则严重程度（severity）

| 严重程度 | 英文名 | 说明 | 扣分影响 |
|---------|--------|------|---------|
| **严重** | critical | 致命缺陷，直接判为丙级 | 单项否决 |
| **重大** | major | 重要缺陷，扣 11 分 | 显著扣分 |
| **轻微** | minor | 一般缺陷 | 少量扣分 |

**结论**: ✅ 规则按严重程度进行了分级

---

## 3. 代码实现分析

### 3.1 语义规则引擎（`semantic_rules.py`）

#### 规则加载逻辑

```python
# 从 Supabase 加载规则
resp = await _exec(supabase.table("qc_rules").select("*").limit(2000))
rows: List[Dict[str, Any]] = list(resp.data or [])
```

**问题**: ⚠️ 加载所有规则，未按 `document_type` 筛选

#### 规则筛选逻辑

```python
def _refine_docs(docs: list[str], rule_name: str) -> list[str]:
    """对文书类别做校准"""
    name = (rule_name or "").strip()
    base = set(docs)
    
    # 强覆盖：若命中以下关键类目，直接收敛为该类目
    if has(r"手术|术前|术后|术中|麻醉|植入|出入量"):
        return ["手术记录"]
    if has(r"出院|死亡"):
        return ["出院记录"]
    if has(r"检验|检查|影像|CT|MRI|X线|放射|化验|病理"):
        return ["检验检查"]
    if has(r"同意书|知情|告知书"):
        return ["知情同意书"]
    
    # 病程类优先级高于默认"入院记录"
    if has(r"首次病程|病程|查房|诊疗经过|病情"):
        base.discard("入院记录")
        base.add("病程记录")
    
    return list(sorted(base))
```

**问题**: ⚠️ 通过规则名称推断文书类型，而不是使用 `applicable_documents` 字段

**结论**: ⚠️ 规则筛选逻辑依赖名称推断，不够准确

### 3.2 四川质控引擎（`sichuan_qc_service.py`）

#### 单文档评估（`evaluate_document`）

```python
async def evaluate_document(self, document_id: str, content: str, document_type: str = "病程记录") -> Dict[str, Any]:
    prompt = f"进行四川省住院病历质控分析。文书类型: {document_type}\n内容:\n{content[:4000]}"
    result = await self.client.generate(prompt)
    # ...
    return {
        "document_id": document_id,
        "document_type": document_type,
        "llm_output": text,
        # ...
    }
```

**问题**: ❌ **未从数据库加载规则，直接调用 LLM**

#### 多文档评估（`evaluate_multi_document`）

```python
async def evaluate_multi_document(
    self,
    document_id: str,
    document_content: str,
    document_types: Optional[List[str]] = None,
    preclassified_documents: Optional[Dict[str, Any]] = None,
    rules_by_document_type: Optional[Dict[str, List[Dict[str, Any]]]] = None,
) -> Dict[str, Any]:
    # ...
    # Use actual rules if provided, otherwise fallback to default calculation
    if rules_by_document_type:
        total_rules_per_doc = lambda doc_type: len(rules_by_document_type.get(doc_type, []))
    else:
        default_rules_per_doc = max(10, int(68 / n_docs))
        total_rules_per_doc = lambda doc_type: default_rules_per_doc
```

**问题**: ❌ **规则数量是硬编码的 68，未从数据库动态加载**

**关键代码**:
```python
# 硬编码的 68 条规则
default_rules_per_doc = max(10, int(68 / n_docs))
```

**结论**: ❌ **四川质控引擎未真正使用数据库中的规则**

---

## 4. 对比分析

### 4.1 规则定义 vs 代码实现

| 维度 | 规则定义（数据库） | 代码实现（四川质控引擎） | 差异 |
|------|------------------|----------------------|------|
| **规则来源** | Supabase `qc_rules` 表 | 硬编码 68 条规则 | ❌ 未使用数据库 |
| **规则分类** | `applicable_documents` 字段 | 硬编码分组（SC-001~SC-020 等） | ❌ 未使用字段 |
| **规则筛选** | 按 `document_type` 筛选 | 平均分配规则数量 | ❌ 未实现筛选 |
| **Prompt 模板** | `prompt_template` 字段 | 硬编码 Prompt | ❌ 未使用模板 |

**结论**: ❌ **存在严重的规则定义与代码实现不一致问题**

### 4.2 语义规则引擎 vs 四川质控引擎

| 维度 | 语义规则引擎 | 四川质控引擎 | 差异 |
|------|------------|------------|------|
| **规则来源** | Supabase `qc_rules` 表 | 硬编码 68 条规则 | ✅ 语义规则引擎使用数据库 |
| **规则筛选** | 按名称推断文书类型 | 平均分配规则数量 | ⚠️ 都不够准确 |
| **Prompt 使用** | 使用 `prompt_template` 字段 | 硬编码 Prompt | ✅ 语义规则引擎使用模板 |
| **LLM 调用** | 占位实现（未真正调用） | 真正调用 LLM API | ✅ 四川质控引擎调用 LLM |

**结论**: ⚠️ **两个引擎各有优缺点，需要整合**

---

## 5. 首次病程记录的特定质控规则

### 5.1 应该有的特定规则

根据医疗规范，首次病程记录应该包含以下质控点：

| 质控点 | 说明 | 严重程度 |
|--------|------|---------|
| **病情分析** | 必须包含病情分析和诊断依据 | critical |
| **鉴别诊断** | 必须包含鉴别诊断 | critical |
| **诊疗计划** | 必须包含详细的诊疗计划 | major |
| **风险评估** | 应包含风险评估（如 GRACE 评分） | major |
| **医嘱规范** | 医嘱格式必须规范 | major |
| **签名完整** | 必须有住院医师和上级医师签名 | major |

### 5.2 实际质控结果

根据之前的质控报告（`FIRST_COURSE_RECORD_QC_REPORT.md`），首次病程记录的质控结果：

- **总规则数**: 68
- **合规规则数**: 57
- **不合规规则数**: 11
- **合规率**: 85.0%
- **严重违规数**: 3

**严重违规项**:
1. ❌ 缺少病情分析和诊断依据
2. ❌ 缺少鉴别诊断
3. ❌ 医嘱格式不规范

**结论**: ✅ **质控结果准确识别了首次病程记录的特定问题**

### 5.3 规则是否按单据类型细分

根据分析，68 条规则的分类方式：

**方式 1**: 按病历单据类型分组（前端实现）
- 病程记录: SC-001 ~ SC-020 (20 条)
- 手术记录: SC-021 ~ SC-035 (15 条)
- 入院记录: SC-036 ~ SC-050 (15 条)
- 出院记录: SC-051 ~ SC-068 (18 条)

**方式 2**: 按质控类别分类（数据库实现）
- completeness（完整性）
- consistency（一致性）
- rationality（合理性）
- timeliness（时效性）
- compliance（合规性）

**结论**: ✅ **规则已按单据类型细分，但实现方式不统一**

---

## 6. 存在的问题

### 6.1 严重问题 ❌

#### 问题 1: 四川质控引擎未使用数据库规则

**现状**:
- 四川质控引擎硬编码了 68 条规则的数量
- 未从数据库加载实际的规则定义
- 未使用 `prompt_template` 字段
- 未使用 `applicable_documents` 字段

**影响**:
- 规则更新需要修改代码
- 无法动态管理规则
- 无法按病历单据类型筛选规则
- 无法使用自定义 Prompt 模板

**证据**:
```python
# sichuan_qc_service.py, line 158
default_rules_per_doc = max(10, int(68 / n_docs))  # 硬编码 68
```

#### 问题 2: 规则筛选逻辑不准确

**现状**:
- 语义规则引擎通过规则名称推断文书类型
- 未使用 `applicable_documents` 字段
- 推断逻辑基于关键词匹配，不够准确

**影响**:
- 规则可能被错误分类
- 无法准确筛选适用规则
- 依赖规则命名规范

**证据**:
```python
# semantic_rules.py, line 92-99
if has(r"手术|术前|术后|术中|麻醉|植入|出入量"):
    return ["手术记录"]
# 基于名称推断，而不是使用 applicable_documents 字段
```

#### 问题 3: 数据库 Schema 不完整

**现状**:
- `qc_rules` 表缺少 `applicable_documents` 字段
- `applicable_documents` 存储在 `check_logic` JSONB 字段中
- 字段名称不统一（`applicable_documents` vs `document_types` vs `applicable_record_types`）

**影响**:
- 查询不方便
- 索引效率低
- 字段语义不清晰

### 6.2 中等问题 ⚠️

#### 问题 4: 规则执行端点未实现

**现状**:
- 语义规则引擎的执行端点是占位实现
- 未真正调用 LLM API
- 未使用 `prompt_template` 字段

**影响**:
- 无法通过语义规则引擎执行质控
- 只能使用四川质控引擎

**证据**:
```python
# semantic_rules.py, line 600+
# 执行端点是占位实现
```

#### 问题 5: 两个引擎功能重复

**现状**:
- 语义规则引擎和四川质控引擎功能重复
- 两个引擎实现方式不同
- 无法统一管理

**影响**:
- 代码维护成本高
- 功能不一致
- 用户困惑

---

## 7. 改进建议

### 7.1 立即改进（必须）

#### 建议 1: 统一规则引擎实现

**目标**: 将四川质控引擎改为使用数据库中的规则

**实现步骤**:
1. 修改 `sichuan_qc_service.py`，从数据库加载规则
2. 使用 `applicable_documents` 字段筛选规则
3. 使用 `prompt_template` 字段构建 Prompt
4. 移除硬编码的 68 条规则数量

**代码示例**:
```python
async def evaluate_document(self, document_id: str, content: str, document_type: str = "病程记录") -> Dict[str, Any]:
    # 1. 从数据库加载规则
    supabase = get_supabase()
    resp = await supabase.table("qc_rules").select("*").eq("is_active", True).execute()
    all_rules = resp.data or []
    
    # 2. 筛选适用规则
    applicable_rules = []
    for rule in all_rules:
        check_logic = rule.get("check_logic", {})
        applicable_docs = check_logic.get("applicable_documents", [])
        if document_type in applicable_docs or not applicable_docs:
            applicable_rules.append(rule)
    
    # 3. 构建 Prompt
    rules_text = "\n".join([
        f"{i+1}. {rule['name']}: {rule.get('description', '')}"
        for i, rule in enumerate(applicable_rules)
    ])
    
    prompt = f"""进行四川省住院病历质控分析。
文书类型: {document_type}
适用规则数: {len(applicable_rules)}

规则清单:
{rules_text}

病历内容:
{content[:4000]}

请按照上述规则进行质控分析。
"""
    
    # 4. 调用 LLM
    result = await self.client.generate(prompt)
    
    # 5. 返回结果
    return {
        "document_id": document_id,
        "document_type": document_type,
        "total_rules": len(applicable_rules),
        "applicable_rules": [r["rule_code"] for r in applicable_rules],
        "llm_output": result.get("choices", [{}])[0].get("message", {}).get("content", ""),
        # ...
    }
```

#### 建议 2: 完善数据库 Schema

**目标**: 添加 `applicable_documents` 字段到 `qc_rules` 表

**实现步骤**:
1. 创建数据库迁移脚本
2. 添加 `applicable_documents` 字段（TEXT[] 类型）
3. 从 `check_logic` JSONB 字段迁移数据
4. 创建索引优化查询

**SQL 示例**:
```sql
-- 添加字段
ALTER TABLE qc_rules 
ADD COLUMN IF NOT EXISTS applicable_documents TEXT[];

-- 迁移数据
UPDATE qc_rules 
SET applicable_documents = ARRAY(
    SELECT jsonb_array_elements_text(check_logic->'applicable_documents')
)
WHERE check_logic ? 'applicable_documents';

-- 创建索引
CREATE INDEX IF NOT EXISTS idx_qc_rules_applicable_documents 
ON qc_rules USING GIN (applicable_documents);
```

#### 建议 3: 实现语义规则引擎执行端点

**目标**: 实现真正的规则执行逻辑

**实现步骤**:
1. 实现 `/api/v1/semantic-rules/{rule_id}/execute` 端点
2. 从数据库加载规则
3. 使用 `prompt_template` 字段构建 Prompt
4. 调用 LLM API
5. 解析结果并返回

### 7.2 建议改进（推荐）

#### 建议 4: 统一两个引擎

**目标**: 将语义规则引擎和四川质控引擎合并为一个统一的引擎

**实现步骤**:
1. 保留语义规则引擎的 CRUD 功能
2. 将四川质控引擎的执行逻辑迁移到语义规则引擎
3. 统一 API 端点
4. 移除重复代码

#### 建议 5: 优化规则筛选逻辑

**目标**: 使用 `applicable_documents` 字段进行准确筛选

**实现步骤**:
1. 移除基于名称的推断逻辑
2. 使用 `applicable_documents` 字段筛选
3. 支持多文书类型匹配
4. 添加规则优先级

#### 建议 6: 添加规则版本管理

**目标**: 支持规则的版本控制和 A/B 测试

**实现步骤**:
1. 添加 `rule_version` 表
2. 支持规则的多版本共存
3. 支持规则的激活/停用
4. 支持规则的 A/B 测试

---

## 8. 总结

### 8.1 回答用户问题

#### 问题 1: 68 条规则是否按病历单据类型进行了区分？

**答案**: ✅ **是的，已经区分**

- 病程记录: SC-001 ~ SC-020 (20 条)
- 手术记录: SC-021 ~ SC-035 (15 条)
- 入院记录: SC-036 ~ SC-050 (15 条)
- 出院记录: SC-051 ~ SC-068 (18 条)

#### 问题 2: 数据库是否有字段用于区分不同的病历单据类型？

**答案**: ✅ **有，但实现方式不理想**

- `applicable_documents` 字段存储在 `check_logic` JSONB 字段中
- 建议添加独立的 `applicable_documents TEXT[]` 字段

#### 问题 3: 代码实现中是否根据 `document_type` 参数筛选适用的规则？

**答案**: ❌ **没有，存在严重问题**

- 四川质控引擎硬编码了 68 条规则，未从数据库加载
- 语义规则引擎通过名称推断文书类型，不够准确
- 两个引擎都未正确使用 `applicable_documents` 字段

#### 问题 4: 是否存在规则定义了但未在代码中使用的情况？

**答案**: ✅ **是的，存在**

- 数据库中定义了 68 条规则
- 四川质控引擎未使用数据库中的规则定义
- 语义规则引擎的执行端点是占位实现

#### 问题 5: 是否存在代码硬编码了规则而未使用数据库中的规则定义的情况？

**答案**: ✅ **是的，存在**

- 四川质控引擎硬编码了 68 条规则的数量
- 未使用 `prompt_template` 字段
- 未使用 `applicable_documents` 字段

### 8.2 核心结论

1. ✅ **68 条规则已按病历单据类型进行了分类**
2. ✅ **数据库支持规则分类（通过 `check_logic` JSONB 字段）**
3. ❌ **四川质控引擎未真正使用数据库中的规则**
4. ⚠️ **规则筛选逻辑不准确，需要改进**
5. ⚠️ **两个引擎功能重复，需要统一**

### 8.3 优先级建议

| 优先级 | 建议 | 预计工作量 | 影响 |
|--------|------|-----------|------|
| **P0** | 统一规则引擎实现 | 2-3 天 | 高 |
| **P0** | 完善数据库 Schema | 1 天 | 高 |
| **P1** | 实现语义规则引擎执行端点 | 2 天 | 中 |
| **P2** | 统一两个引擎 | 3-5 天 | 中 |
| **P2** | 优化规则筛选逻辑 | 1-2 天 | 中 |
| **P3** | 添加规则版本管理 | 3-5 天 | 低 |

---

**报告完成时间**: 2025-10-11  
**报告状态**: ✅ 完成  
**下一步**: 实施改进建议

