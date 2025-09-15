# 质控规则设计文档

> 描述规则数据模型、类型与映射、严重级别、生命周期与版本管理。

## 目录
- 数据模型与字段
- 规则类型与中文映射
- 严重级别定义
- 生命周期与版本管理
- 示例

## 数据模型与字段
核心表：`yibao_rules`
- id: bigint 主键
- code: varchar 唯一规则编码（如 `DRUG_INSURANCE_TYPE_001`）
- name: varchar 规则名称（如 `疤痕止痒软化膏 - 保险类型限制`）
- rule_type: varchar 规则类型（如 `drug_insurance_type`）
- severity: varchar 严重级别（`info|warn|block`）
- enabled: bool 是否启用
- version: int 版本号
- category_id: varchar 规则分类（如 `batch_1` ... `batch_5`）
- metadata: jsonb 扩展信息（可存放维护人、来源、标签等）
- description: text 规则描述（前端展示用）
- created_at / updated_at: timestamptz

子表：
- `yibao_rule_triggers`：事件触发
  - rule_id, event_type, priority
- `yibao_rule_conditions`：条件配置
  - rule_id, priority, expression_json（JSON 表达式）
- `yibao_rule_actions`：动作配置
  - rule_id, action_type（`intercept|warn|notify`）, message_template

## 规则类型与中文映射
前端已实现的映射（保持与现网一致）：
- drug_gender → 性别限制  （粉色）
- drug_age → 年龄限制  （橙色）
- drug_children_only → 儿童专用  （绿色）
- drug_children_limit → 儿童限制  （绿色）
- drug_payment_course → 支付疗程限制  （紫色）
- drug_insurance_type → 保险类型限制  （蓝色）
- drug_diagnosis → 诊断限制  （红色）
- drug_dosage_form → 剂型限制  （青色）
- drug_route → 给药途径  （极客蓝）
- drug_indication → 适应症限制  （洋红）
- visit_type → 就诊方式限制
- hospital_level → 机构级别限制
- duration → 疗程限制
- surgery_pricing → 手术折价

> 若后端新增类型，请在前端 `getRuleTypeLabel / getRuleTypeColor` 中同步维护映射。

### 缩略编号（历史需求，当前显示为完整原始编码）：
- DRUG_AGE_007 → 年龄-007
- DRUG_INSURANCE_TYPE_006 → 保险-006
> 现网按需显示：规则编号列仅展示完整原始编码；规则信息列仅展示纯名称（去掉类型尾注）。

## 严重级别定义
- info（信息）：提示类信息，不影响流程。
- warn（警告）：非阻断告警，建议遵守。
- block（阻断/拦截）：违反即阻断，需调整后继续。

前端配色与图标：
- info → 蓝色，Info 图标
- warn → 橙色，Warning 图标
- block → 红色，Exclamation 图标

## 生命周期与版本管理
- 创建：录入 `code/name/rule_type/severity/enabled/version/metadata...`
- 发布/启停：通过启用开关（`enabled`）控制上线状态。
- 变更：更新条件（conditions）与动作（actions），提升 `version`。
- 追溯：在“版本历史”中显示版本时间线与描述，支持对比/回滚（前端已预留入口）。
- 作废：设置 `enabled=false`，并在 metadata/描述中标注作废原因。

### 分类（Category）
- batch_1：第一批（年龄性别）
- batch_2：第二批（手术折价）
- batch_3：第三批（保险类型）
- batch_4：第四批（就诊方式）
- batch_5：第五批（机构级别）

## 示例
规则主表记录（JSON 示例）：
```json
{
  "id": 123,
  "code": "DRUG_INSURANCE_TYPE_001",
  "name": "疤痕止痒软化膏 - 保险类型限制",
  "rule_type": "drug_insurance_type",
  "severity": "warn",
  "enabled": true,
  "version": 2,
  "category_id": "batch_3",
  "description": "对某药品按保险类型进行限制",
  "metadata": {"owner": "admin", "tags": ["药品", "医保"]},
  "updated_at": "2025-09-08T10:00:00Z"
}
```

条件表达式示例：
```json
{
  "op": "AND",
  "conditions": [
    {"field": "patient.insurance_type", "op": "IN", "value": ["城镇职工", "城乡居民"]},
    {"field": "drug.code", "op": "EQ", "value": "H12345"}
  ]
}
```

动作示例：
```json
{
  "action_type": "intercept",
  "message_template": "当前患者保险类型不允许开立该药品"
}
```

