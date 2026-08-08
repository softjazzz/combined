# LX0609 规则详情：以规则总表为唯一客户口径来源

## 目标

让“质控规则管理工作台”的 LX0609 规则详情只展示 `luxian_0609_rule_master_v1.json` 中维护的客户口径与政策摘要，避免继续把执行包装器中的旧描述、触发条件和资料状态当作客户规则说明。

执行规则映射仍保留，但明确降级为“执行映射（实现信息）”。本任务不改变任何质控判定、资料读取、LLM 调用、Canonical、Envelope、API 结果或前端启动质控行为。

## 已确认的问题与根因

当前 `/api/v1/qc/sichuan/rules?rule_set_key=luxian_0609_qc_v1` 直接返回 `load_luxian_0609_rules()` 的执行包装器。该包装器仅用总表校验 75 个规则 ID 是否一致，并不投影总表的政策字段。

`SemanticRuleDetailModal.vue` 因而直接渲染包装器中的以下客户说明字段：

- `customer_text`；
- `trigger_condition`；
- `non_trigger_condition`；
- `dependency_type`、`required_documents_label`；
- `data_status`、`implementation_status`；
- 包装器描述与示例。

这些字段与最新总表会漂移。已可复现的例子包括：

- `LX0609-009`：执行包装器仍是旧的病危查房文案，而总表已纳入“病情变化”的客户确认说明；
- `LX0609-010`：总表明确保留检查前原因，并说明后续的医嘱一致和报告完整目标；
- `LX0609-020/023`：总表已区分“是否记录会诊意见及执行情况”和“只写遵嘱执行但未具体落实”的口径；
- `LX0609-025`：总表已明确省标主项为条码、种类、数量，名称/型号/材质仅为本院扩展；
- `LX0609-066/070`：包装器客户文本存在空值，而总表已有非空政策摘要。

权威来源已经存在：`backend/app/data/luxian_0609_rule_master_v1.json`。它由 `luxian_0609_rule_master.py` 做 schema、顺序、来源枚举和摘要长度校验，故本任务不新建第二份规则说明数据。

## 收敛后的展示合同

对 LX0609 规则详情：

```text
规则编号
总表.source_document：总表.qc_point

客户规则口径
总表.policy_summary

政策依据
总表.policy_sources 的中文标签

执行映射（实现信息，辅助）
primary_execution_rule_id / mapped_rule_ids
```

规则详情不得再把以下执行包装器字段作为客户口径展示：

```text
description
customer_text
trigger_condition
non_trigger_condition
dependency_type
required_documents_label
data_status
implementation_status
positive_example / negative_example
custom_prompt
```

其中执行模板仍可由既有后台/代码入口维护，但不在 LX0609 的客户规则详情中展示，避免把实现文本误读为政策说明。

非 LX0609 的 SC 规则详情保持现状。

政策来源代码只做显示标签转换，不承载规则内容：

| 总表代码                   | 页面标签                                             |
| -------------------------- | ---------------------------------------------------- |
| `sichuan_2026_handbook`    | 四川省病案管理质量控制指标检查要点指导手册（2026版） |
| `sichuan_2023_standard`    | 四川省住院病历评定标准                               |
| `customer_confirmed`       | 客户确认口径                                         |
| `hospital_local_extension` | 本院扩展口径                                         |

未知来源代码显示为“未识别政策来源”，但不以执行包装器文本回退。由于总表加载时已拒绝未知代码，此项仅是前端稳健性保护。

## 最小改动范围

允许修改：

1. `backend/app/services/luxian_0609_rule_catalog.py`
2. `backend/app/routers/qc_sichuan.py`
3. `backend/tests/unit/test_luxian_0609_rule_catalog.py`
4. `src/views/workstation-v4/semantic-rules/types.ts`
5. `src/views/workstation-v4/semantic-rules/service.ts`
6. `src/views/workstation-v4/semantic-rules/components/modals/SemanticRuleDetailModal.vue`
7. `tests/unit/services/semantic-rules-workspace-service.spec.ts`
8. `tests/unit/views/workstation-v4/semantic-rules/SemanticRuleDetailModal.spec.ts`（新增）

禁止修改：

- `luxian_0609_rule_master_v1.json` 的任何业务口径；
- Native 执行器、Source Registry、EvidenceSnapshot、MaterialStore；
- RuleDecision、Reducer、Aggregator、Canonical、Envelope、任务保存或结果 API；
- LLM Prompt、调用次数、Token 预算；
- 规则列表行、启动质控流程、SC 规则详情。

## 实施步骤

### Task 1：后端生成“总表政策详情”投影

文件：

- 修改 `backend/app/services/luxian_0609_rule_catalog.py`
- 修改 `backend/app/routers/qc_sichuan.py`
- 修改 `backend/tests/unit/test_luxian_0609_rule_catalog.py`

先写失败测试，再实现。

1. 在规则目录模块新增一个仅用于详情/列表 API 的纯投影函数，例如 `attach_luxian_0609_customer_policy(rules)`。
2. 函数按 `rule_id` 将当前执行包装器与 `load_luxian_0609_rule_master()` 的同 ID 条目连接，在返回副本上新增唯一嵌套字段：

   ```json
   {
     "customer_policy": {
       "source_document": "…",
       "qc_point": "…",
       "summary": "…",
       "sources": ["customer_confirmed"]
     }
   }
   ```

3. 不覆盖包装器原字段；执行计划、筛选、映射、批量质控继续使用原包装器。`customer_policy` 是接口展示投影，不是新的业务存储。
4. 在 `/rules` 的 LX0609 分支中，对过滤后的 `data` 应用该投影；普通和 `grouped=true` 响应都必须得到相同的 `customer_policy`。
5. 如果包装器 ID 无对应总表条目，抛出 `ValueError` 并拒绝返回，不得用旧文本、空摘要或猜测内容回退。现有 75 条 ID 集合校验仍保留。

验收测试：

- 75 条 LX0609 返回项均有非空 `customer_policy.source_document`、`qc_point`、`summary` 和非空来源数组；
- 009、020、023、025、066、070 各抽一条，断言字段逐字来自总表；
- 025 的详情摘要明确保留“条码、种类、数量”和“本院扩展”边界，而不从包装器读取旧必填字段；
- 066、070 即使包装器客户文本为空，`customer_policy.summary` 仍非空；
- `primary_execution_rule_id` 与 `mapped_rule_ids` 原样保留，证明执行映射未被重写；
- 当前 `/rules` API 测试经真实路由断言该嵌套对象存在；不启动任何质控执行器。

### Task 2：前端只消费总表政策对象

文件：

- 修改 `src/views/workstation-v4/semantic-rules/types.ts`
- 修改 `src/views/workstation-v4/semantic-rules/service.ts`
- 修改 `src/views/workstation-v4/semantic-rules/components/modals/SemanticRuleDetailModal.vue`
- 修改 `tests/unit/services/semantic-rules-workspace-service.spec.ts`
- 新增 `tests/unit/views/workstation-v4/semantic-rules/SemanticRuleDetailModal.spec.ts`

先写失败测试，再实现。

1. 在 `SemanticRuleItem` 增加严格的可选 `customer_policy` 类型；包含 `source_document`、`qc_point`、`summary`、`sources`，不把政策字段平铺为另一组易混淆的旧字段。
2. 在 `normalizeSemanticRule()` 仅在 JSON 结构完整时保留 `customer_policy`；非法条目视为缺失，不从 `customer_text` 或 `description` 生成伪政策摘要。
3. 对 LX0609 规则，详情头部使用 `customer_policy.source_document + '：' + customer_policy.qc_point`；客户口径区域只渲染 `customer_policy.summary`。
4. 紧随摘要渲染“政策依据”标签，使用固定的四个来源代码到中文标签的纯显示映射。该映射不包含任何规则正文，不成为第二个规则总表。
5. 将 `primary_execution_rule_id` 与 `mapped_rule_ids` 放入折叠密度低的“执行映射（实现信息）”辅助区；保留主执行标识。
6. 对 LX0609 隐藏旧的客户文本、触发/不触发条件、执行依赖、资料状态、正反例和只读执行模板；SC 规则原有详情和模板编辑行为不变。
7. 若接口暂未返回 `customer_policy`，页面只显示“规则口径暂未同步”，不显示旧包装器文本；这使接口漏投影可见且不会对客户展示过期口径。

验收测试：

- 以故意冲突的 fixture（`customer_text` 为旧文案、`customer_policy.summary` 为新文案）挂载 Modal，断言只显示总表标题、摘要及依据；旧文案、触发条件、资料状态、示例和模板均不出现；
- 断言映射规则仍出现且标注为“执行映射（实现信息）”，但不混入客户口径；
- 断言缺少 `customer_policy` 时只显示“规则口径暂未同步”，不回退 `customer_text` 或 `description`；
- 断言 SC fixture 仍显示其既有详情，不受 LX 条件分支影响；
- service 单测覆盖有效/无效 `customer_policy` 的结构化归一化。

### Task 3：最小回归与人工验收

只运行与本闭环直接相关的检查：

```powershell
python -m pytest backend/tests/unit/test_luxian_0609_rule_catalog.py -q
corepack pnpm exec vitest run tests/unit/services/semantic-rules-workspace-service.spec.ts tests/unit/views/workstation-v4/semantic-rules/SemanticRuleDetailModal.spec.ts
corepack pnpm exec eslint src/views/workstation-v4/semantic-rules/types.ts src/views/workstation-v4/semantic-rules/service.ts src/views/workstation-v4/semantic-rules/components/modals/SemanticRuleDetailModal.vue tests/unit/services/semantic-rules-workspace-service.spec.ts tests/unit/views/workstation-v4/semantic-rules/SemanticRuleDetailModal.spec.ts
corepack pnpm exec vue-tsc --noEmit
git diff --check
```

人工验收仅查看规则工作台的 LX0609 详情：

1. 打开 009，确认页面显示总表中的“病情变化”摘要，而不是旧包装器查房文字。
2. 打开 020/023，确认两条会诊口径区分清楚，且不显示旧触发/不触发条件。
3. 打开 025，确认“条码、种类、数量”与本院扩展边界准确。
4. 打开 066 或 070，确认不再出现空白客户说明。
5. 打开一条 SC 规则，确认其页面无变化。

不需要创建任务、重跑病例或调用 LLM；本任务的成功标准是详情说明与总表一致，而不是质控结果数量变化。

## 完成标准与剩余风险

完成后，客户在 LX0609 详情页看到的规则标题、口径摘要和政策依据都只来自规则总表；执行映射是明确标注的辅助实现信息；执行包装器的旧解释不再有客户展示入口。

剩余风险：总表自身未来仍可能需要业务更新，但更新只需改总表并经过其既有校验和单规则验收；详情页不会再维护第二套可漂移的客户文案。此闭环完成后暂停，不顺带修改 75 条规则的执行语义或规则主表内容。
