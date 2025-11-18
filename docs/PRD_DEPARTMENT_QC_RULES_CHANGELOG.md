# 科室级质控规则配置功能 PRD - 变更日志

> **文档版本**: 2.0  
> **更新日期**: 2025-10-12  
> **相关文档**: [PRD 主文档](./PRD_DEPARTMENT_QC_RULES.md)

---

## 📋 版本历史

### Version 2.0 (2025-10-12) - 重大改进版本

根据技术评审意见，对 PRD 进行了全面改进和补强。

---

## 🔄 主要变更

### 1. 数据模型增强 (高优先级)

#### 1.1 新增字段

| 字段 | 类型 | 说明 | 原因 |
|------|------|------|------|
| `override_action` | VARCHAR(20) | 覆盖行为：override / disable | 明确区分"覆盖配置"和"禁用规则" |
| `status` | VARCHAR(20) | 规则状态：draft / published / archived | 支持草稿、审核、发布流程 |
| `version` | VARCHAR(20) | 规则版本号 | 支持规则版本管理 |
| `effective_from` | TIMESTAMPTZ | 生效开始时间 | 支持定时生效 |
| `effective_to` | TIMESTAMPTZ | 生效结束时间 | 支持自动失效 |
| `approved_by` | UUID | 审核人 ID | 记录审核信息 |
| `approved_at` | TIMESTAMPTZ | 审核时间 | 记录审核时间 |

#### 1.2 新增约束和索引

```sql
-- 唯一约束：同科室同规则编号的已发布规则唯一
CREATE UNIQUE INDEX uk_dept_rule_code_published
ON qc_rules(department_id, rule_code)
WHERE scope = 'department' AND status = 'published';

-- 生效期索引
CREATE INDEX idx_qc_rules_effective 
ON qc_rules(effective_from, effective_to);

-- 状态索引
CREATE INDEX idx_qc_rules_status 
ON qc_rules(status);
```

---

### 2. 禁用全局规则的明确建模 (高优先级)

#### 2.1 问题描述

初版 PRD 中提到"科室可选择性禁用某些全局规则"，但未明确如何建模：
- 仅靠 `is_active=false` 会有歧义
- 无法区分"无覆盖"和"明确禁用"

#### 2.2 解决方案

引入 `override_action` 字段：

| 值 | 含义 | 行为 |
|---|------|------|
| `override` | 覆盖配置 | 使用科室规则的配置覆盖全局规则 |
| `disable` | 禁用规则 | 该全局规则对该科室不生效 |

#### 2.3 数据示例

```json
{
  "id": "rule-004",
  "rule_code": "R010",
  "name": "禁用：成人用药剂量检查",
  "scope": "department",
  "department_id": "dept-003",
  "override_action": "disable",
  "is_active": true,
  "status": "published",
  "reason": "儿科使用儿童用药剂量标准，不适用成人标准"
}
```

#### 2.4 匹配逻辑更新

```python
# 处理科室规则
for rule in dept_rules:
    if rule.override_action == 'disable':
        # 禁用规则：标记该 rule_code 不生效
        disabled_rules.add(rule.rule_code)
        if rule.rule_code in rule_map:
            del rule_map[rule.rule_code]
    elif rule.override_action == 'override':
        # 覆盖规则：替换全局规则
        rule_map[rule.rule_code] = rule
```

---

### 3. 规则版本与生效期管理 (中优先级)

#### 3.1 问题描述

实际运营中经常需要：
- 草稿 → 审核 → 发布的流程
- 定时生效/失效
- 版本管理和回滚

#### 3.2 解决方案

**状态流转**:
```
draft (草稿) → published (已发布) → archived (已归档)
```

**生效期控制**:
- `effective_from`: 规则开始生效的时间
- `effective_to`: 规则停止生效的时间
- 为空表示无限制

**审核流程**:
- `approved_by`: 记录审核人
- `approved_at`: 记录审核时间

#### 3.3 匹配逻辑更新

```python
# 仅选取已发布且在生效期内的规则
global_rules = db.query(QCRule).filter(
    QCRule.scope == 'global',
    QCRule.is_active == True,
    QCRule.status == 'published',  # 新增
    or_(
        QCRule.effective_from == None,
        QCRule.effective_from <= now
    ),  # 新增
    or_(
        QCRule.effective_to == None,
        QCRule.effective_to >= now
    )  # 新增
).all()
```

---

### 4. 规则变更审计 (高优先级)

#### 4.1 问题描述

缺少规则变更的审计追踪，无法：
- 查看规则的变更历史
- 对比变更前后的差异
- 追溯变更责任人

#### 4.2 解决方案

新增 `qc_rule_change_logs` 表：

```sql
CREATE TABLE qc_rule_change_logs (
    id UUID PRIMARY KEY,
    rule_id UUID NOT NULL,
    department_id UUID,
    action VARCHAR(20),  -- create/update/delete/enable/disable/publish/archive
    old_values JSONB,
    new_values JSONB,
    diff JSONB,
    actor_id UUID NOT NULL,
    actor_name VARCHAR(200),
    actor_role VARCHAR(50),
    reason TEXT,
    ip_address VARCHAR(50),
    user_agent TEXT,
    created_at TIMESTAMPTZ
);
```

#### 4.3 自动记录变更

使用数据库触发器自动记录所有变更：

```sql
CREATE TRIGGER trigger_log_qc_rule_changes
AFTER INSERT OR UPDATE OR DELETE ON qc_rules
FOR EACH ROW EXECUTE FUNCTION log_qc_rule_changes();
```

#### 4.4 UI 功能

- 查看规则的完整变更历史
- 对比变更前后的差异
- 显示变更原因和操作人

---

### 5. 数据库 RPC 函数 (高优先级)

#### 5.1 问题描述

规则匹配逻辑在应用层实现，可能导致：
- 不同客户端实现不一致
- 多次网络往返，性能差
- 逻辑分散，难以维护

#### 5.2 解决方案

在数据库层实现 `get_applicable_qc_rules` RPC 函数：

```sql
CREATE OR REPLACE FUNCTION get_applicable_qc_rules(
    p_department_id UUID,
    p_document_type TEXT DEFAULT NULL,
    p_at TIMESTAMPTZ DEFAULT NOW()
)
RETURNS TABLE (...) AS $$
BEGIN
    -- 统一的规则匹配逻辑
    -- 1. 获取全局规则
    -- 2. 获取科室规则
    -- 3. 处理覆盖和禁用
    -- 4. 按优先级排序
END;
$$ LANGUAGE plpgsql STABLE;
```

#### 5.3 优点

- ✅ 统一规则匹配逻辑
- ✅ 减少网络往返
- ✅ 提升查询性能
- ✅ 易于测试和维护

#### 5.4 应用层调用

```python
# 调用数据库 RPC 函数
result = await supabase.rpc(
    'get_applicable_qc_rules',
    {
        'p_department_id': department_id,
        'p_document_type': document_type,
        'p_at': datetime.now().isoformat()
    }
)
```

---

### 6. 文书类别维度保留 (中优先级)

#### 6.1 问题描述

匹配逻辑主要围绕科室，未充分考虑文书类别维度。

#### 6.2 解决方案

- 保留现有的 `applicable_documents` 字段
- RPC 函数支持按文书类别过滤
- 支持"科室 + 文书类别"的组合匹配

```sql
-- RPC 函数中的文书类别过滤
AND (p_document_type IS NULL OR r.applicable_documents @> ARRAY[p_document_type]::TEXT[])
```

---

### 7. 测试用例补充 (中优先级)

#### 7.1 新增测试场景

**规则匹配逻辑测试**:
- 禁用全局规则
- 覆盖全局规则
- 多层覆盖
- 优先级排序
- 生效期过滤
- 文书类别匹配

**审计日志测试**:
- 创建规则审计
- 更新规则审计
- 删除规则审计
- 启用/禁用审计
- 发布规则审计
- 查看变更历史

**边界条件测试**:
- 禁用不存在的规则
- 生效期冲突
- 草稿规则执行
- 过期规则执行

---

## 📊 影响分析

### 数据库变更

| 变更类型 | 数量 | 影响 |
|---------|------|------|
| 新增字段 | 7 | qc_rules 表 |
| 新增索引 | 3 | 查询性能优化 |
| 新增约束 | 1 | 数据一致性 |
| 新增表 | 1 | qc_rule_change_logs |
| 新增函数 | 2 | RPC + 触发器 |

### API 变更

| 变更类型 | 数量 | 说明 |
|---------|------|------|
| 新增字段 | 7 | 请求/响应体 |
| 新增接口 | 2 | 发布规则、查看变更历史 |
| 修改接口 | 4 | 创建/更新规则增加新字段 |

### 前端变更

| 变更类型 | 数量 | 说明 |
|---------|------|------|
| 新增表单字段 | 7 | 规则编辑表单 |
| 新增状态标签 | 3 | draft/published/archived |
| 新增功能 | 2 | 发布规则、查看变更历史 |

---

## 🚀 迁移计划

### Phase 1: 数据库迁移 (1 天)

```sql
-- 1. 备份现有数据
CREATE TABLE qc_rules_backup AS SELECT * FROM qc_rules;

-- 2. 添加新字段
ALTER TABLE qc_rules ADD COLUMN override_action VARCHAR(20) DEFAULT 'override';
ALTER TABLE qc_rules ADD COLUMN status VARCHAR(20) DEFAULT 'published';
-- ... 其他字段

-- 3. 更新现有数据
UPDATE qc_rules SET status = 'published' WHERE is_active = true;
UPDATE qc_rules SET status = 'archived' WHERE is_active = false;

-- 4. 创建新表
CREATE TABLE qc_rule_change_logs (...);

-- 5. 创建 RPC 函数
CREATE OR REPLACE FUNCTION get_applicable_qc_rules(...);

-- 6. 创建触发器
CREATE TRIGGER trigger_log_qc_rule_changes ...;

-- 7. 验证迁移
SELECT * FROM qc_rules WHERE status IS NULL;  -- 应该为空
```

### Phase 2: 后端代码更新 (2 天)

- 更新 ORM 模型（新增字段）
- 更新 API 接口（支持新字段）
- 实现 RPC 函数调用
- 更新规则匹配逻辑
- 编写单元测试

### Phase 3: 前端代码更新 (2 天)

- 更新规则编辑表单
- 添加状态标签和筛选
- 实现发布规则功能
- 实现变更历史查看
- 更新 UI 测试

### Phase 4: 集成测试 (1 天)

- 端到端测试
- 性能测试
- 审计日志测试
- Bug 修复

---

## ✅ 验收标准

### 功能验收

- [ ] 可以创建"禁用全局规则"的科室规则
- [ ] 可以创建草稿规则并发布
- [ ] 可以设置规则的生效期
- [ ] 规则匹配时正确处理禁用、覆盖、生效期
- [ ] 所有规则变更都有审计日志
- [ ] 可以查看规则的变更历史

### 性能验收

- [ ] 规则列表加载 < 500ms
- [ ] 规则匹配（RPC 函数）< 100ms
- [ ] 质控执行（50 条规则）< 5s

### 数据验收

- [ ] 现有规则数据迁移成功
- [ ] 无数据丢失
- [ ] 约束和索引正确创建

---

## 🔍 风险与缓解

| 风险 | 影响 | 概率 | 缓解措施 |
|------|------|------|---------|
| 数据迁移失败 | 高 | 低 | 充分测试、备份数据、准备回滚脚本 |
| RPC 函数性能问题 | 中 | 中 | 添加索引、优化查询、性能测试 |
| 审计日志写入失败 | 中 | 低 | 触发器异常处理、监控告警 |
| 前端兼容性问题 | 低 | 低 | 渐进式升级、向后兼容 |

---

## 📚 相关文档

- [PRD 主文档 v2.0](./PRD_DEPARTMENT_QC_RULES.md)
- [PRD 设计总结](./PRD_DEPARTMENT_QC_RULES_SUMMARY.md)
- [数据库迁移脚本](../infra/supabase/medqc/migrations/009_department_qc_rules.sql)（待创建）

---

## 🎯 下一步行动

1. **评审变更** - 与产品、技术团队评审变更内容
2. **编写迁移脚本** - 创建数据库迁移脚本
3. **更新 API 文档** - 更新 OpenAPI 规范
4. **开发实施** - 按阶段推进开发
5. **测试验证** - 执行完整的测试计划

---

**文档版本**: 2.0  
**最后更新**: 2025-10-12  
**维护者**: Product Team  
**审核者**: Tech Lead

