# V3.6 评分标准与计分服务合同（P2-S）

> 日期：2026-09-27。用户已确认：实现评分标准配置，默认不启用。得分由独立的计分服务根据已保存的质控结果计算，不改执行器。院方录入并启用标准之前，得分类指标一律显示“未配置评分标准”，不显示伪造的分数。

## 1. 证据

- LX0609 的 Canonical 结果没有评分。
- `rules_v1.json` 中 49 条规则的 `score_deduction` 全部是 2，不能作为评分标准。
- 旧 `qc_results.overall_score` 来自旧链路，身份未核实。
- 规则目录中没有单否/核心制度字段。

## 2. 存储（迁移 62，`qc`/`public` 双建）

**`qc_scoring_standards`**

| 列 | 约束 |
|---|---|
| `id` | — |
| `name` | VARCHAR(100) |
| `scene` | `running` / `final` / `outpatient` |
| `rule_set_key` | — |
| `status` | `draft` / `active` / `archived` |
| `is_default` | BOOLEAN |
| `base_score` | NUMERIC(6,2) > 0 |
| `grade_bands_json` | `[{name, min_score, max_score}]`，区间左闭右开，最高档右闭；按分数降序排列，连续无空隙、无重叠，覆盖 [0, base_score]；档位个数不固定为三档 |
| `veto_grade` | VARCHAR(50)：命中否决项时强制使用的档位名，必须是 bands 中的一个名称 |
| `version_seq` | CAS |
| `created_by/at`、`updated_by/at`、`activated_by/at` | — |

- 部分唯一索引 `(scene) WHERE status='active' AND is_default`：每个场景最多一个默认标准。
- 唯一约束 `(name, scene)`。

**`qc_scoring_items`**

| 列 | 约束 |
|---|---|
| `id` | — |
| `standard_id` | FK，级联删除 |
| `group_name` | VARCHAR(100)，项目组 |
| `rule_id` | — |
| `deduction` | NUMERIC(6,2) ≥ 0 |
| `is_veto` | BOOLEAN，单项否决 |
| `enabled` | BOOLEAN |

- 唯一约束 `(standard_id, rule_id)`：一条规则在一个标准内只属于一个项目组。

**`qc_scoring_groups`**

| 列 | 约束 |
|---|---|
| `standard_id` | — |
| `group_name` | — |
| `max_deduction` | NUMERIC(6,2)，可空，表示不封顶 |
| `sort_order` | — |

- 唯一约束 `(standard_id, group_name)`。

**修改规则**：只有 `draft` 状态的标准可以编辑。`active` 标准不能改，要修改须复制成新草稿再启用。启用时，同一场景的原默认标准会在同一事务内改为 `archived`（或者只取消其默认标记，由请求参数决定）。

## 3. 计分（只有一个 owner：`scoring_service.score_result(items, standard)`，纯函数）

- **输入**：结果对象的客户可见条目（即 `project_customer_safe_result_item` 的输出）。
- **扣分条件**：只对 `is_confirmed_issue == true` 的条目扣分，也就是执行器判定的确定问题；待核实、未执行、不适用都不扣。
- **计算**：`score = max(0, base_score - Σ组内扣分)`，每组扣分不超过该组 `max_deduction`。
- **定档**：按 bands 确定等级；命中任一 `is_veto` 且 enabled 的条目时，等级强制为 `veto_grade`，并标记 `veto_hit=true`。
- **输出**：`{score, grade, veto_hit, deductions:[{rule_id, group_name, deduction, is_veto}], unscored_rule_ids}`。
  - `unscored_rule_ids` 列出结果中出现、但标准里没有配置的确定问题。这些规则不扣分，但单独列出，不静默忽略。
- **确定性**：同一个结果对象配同一个标准，结果必定相同。
- **按需计算，不落库**：结果对象可能被重写；读取时按当前默认标准实时计算，响应里带上 `standard_id` 和标准的 `updated_at`，标明计分依据。

**读取接口**

- `GET /api/v1/scoring/case?institute_id&patient_id&visit_id&scene=`：按单病历最新 ready 结果和该场景的默认标准计分。
  - 没有默认标准时返回 `{status: "no_standard"}`；
  - 没有 ready 结果时返回 `{status: "no_result"}`。
- 批量函数 `score_cases(results, scene)`：供列表页和报表使用。一次读取标准，纯函数计分。

## 4. 管理接口（admin/qc_manager；读取需要登录）

- 标准的 CRUD、复制、启用、归档；
- 项目组和条目的批量保存（整表提交，按 version_seq 做 CAS）；
- 规则 id 必须属于该场景对应规则集的当前版本全集，否则返回 422；
- bands 校验失败返回 422，并逐条列出问题；
- 数据库故障返回脱敏的 503。

## 5. 展示接入（本批）

- **V5 运行/终末列表**：行上增加得分和等级。取值来自 `score_cases`，与审核状态相同，只对 ready 结果计算。没有默认标准时，这一列整列显示“未配置评分标准”。
- **结果抽屉**：显示得分、等级、否决命中，以及扣分明细（按项目组）。
- **评分标准管理页**：沿用现有的 `qc/scoring-config` 路由，先查它现在接的是什么，再替换为真实实现。
- 统计报表中的平均分、甲级率等得分类指标，放在 P2 报表批次里消费 `score_cases`。
