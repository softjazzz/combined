# 基础时限规则族真正收口验收

## 范围与根因

本闭环只处理 `LX0609-001/002/004/005/006` 的执行器、Decision Binding、公共文书证据投影与结果聚合边界。

此前结果聚合器直接调用基础时限族的展示事实校验、客户证据生成及来源过滤；005 的旧客户证据投影还把实际选中的 `daily_course_record` 硬编码为 `senior_course_record`。004 的多次抢救记录和“有有效抢救医嘱但无记录”路径也没有把每个实际材料行绑定到 `fact_refs`。

## 本次收口

- 执行器在选择点绑定 001/002/005/006 的目标文书行；004 绑定全部实际检查的抢救记录行，或绑定有效抢救医嘱行。
- 执行器仅输出客户安全事实；内部文书 ID、抢救事件行 ID 与医嘱 ID 不再进入 `customer_display_facts`，只保留于已验证的行级 `fact_refs`。
- Finalizer 暴露通用执行器事实接收入口：基础时限族的受控事实合同仍由既有投影器校验，含内部 ID 的事实 fail closed。Finalizer 原有状态补全语义未修改。
- Aggregator 只调用该通用入口及公共 `project_selected_document_evidence()`，不再导入或调用 `basic_timeliness_customer_projection` 的专属接口。
- 公共投影通过 source registry 将内部受控 dotted source key 规范为已注册客户文书类型；`inpat_nondrug_order.rescue_order` 因而投影为 `inpat_nondrug_order`。未知、非法或没有客户文书前缀的来源保持 fail closed。
- Canonical 写入和客户投影复用 Finalizer 的同一校验入口；被拒绝的内部 ID 事实直接触发合同错误，不存在“清洗后放行”的旧链兼容回退。

## 冻结行为

- 五条规则的 status、reason_code、findings、Canonical `customer_display_facts`、Prompt 与 LLM 调用／Token 合同未改。确定性冻结路径仍为零模型调用、零 Token。
- 004 多事件证据的完整坐标集合（`source_type`、`source_document_id`、`field_path`、`record_time`）无丢失、无重复；有效抢救医嘱仍定位到 `inpat_nondrug_order`。
- 004 多事件证据按执行器 `fact_refs` 顺序稳定交付；两次执行顺序一致，前端定位、业务判定及每个坐标字段不变。
- 选中文书无法唯一定位、跨快照、材料篡改或 Binding 失败时仍映射为 `technical_error` / `snapshot_mismatch`，不会输出“已确认”的客户事实。

## TDD 与验证

红测先后证明：004 执行器泄露内部 ID 且未绑定逐行引用；缺少 Finalizer 通用接收入口；公共来源不能将救援医嘱键规范为客户文书类型。实现后运行：

```text
pytest -q tests/unit/test_luxian_0609_basic_timeliness_architecture_freeze.py \
  tests/unit/test_luxian_0609_basic_timeliness_evidence_freeze.py \
  tests/unit/test_luxian_0609_selected_document_evidence.py \
  tests/unit/test_luxian_0609_selected_document_binding_failure.py \
  tests/unit/test_luxian_0609_decision_binding.py
```

最终影响范围命令共收集 535 项，结果：`535 passed`，15 条既有环境 warning；结果投影服务 `34 passed`；显式开启 `LUXIAN_0609_UNIFIED_ENGINE_ENABLED=true` 的主链测试 `test_basic_timeliness_typed_decisions_share_snapshot_and_skip_legacy_results` 通过，确认基础时限 typed decisions 共用同一快照且跳过旧结果。全部 `test_luxian_0609_*.py` 收集 4256 项，排除固定点已存在且与本闭环无关的 5 个基线节点后，结果为 `4251 passed`、0 failed（49.31 秒）。这 5 个节点分别属于旧 digest 断言（3 个参数）、过期 source registry v23 断言和 070 既有证据预期，本闭环未顺带修改。`py_compile`、Ruff 与 `git diff --check` 通过。未调用真实模型、未写数据库、未修改 Prompt、Renderer、API、数据库或前端。

原来依赖 `customer_display_facts.source_document_id` 或聚合器按规则号过滤来源的测试，已迁移为直接核验 `RuleDecision.fact_refs` 与公共投影坐标；没有为兼容旧断言恢复聚合器专属路径。

## 巨型文件门禁与代码变化

`native_basic_timeliness.py` 在固定点为 1968 行，本次为 2034 行，净增 66 行。新增内容只有该执行器已有职责的一部分：在形成具体规则结论的选择点，将同一批已检查材料绑定为 `fact_refs`，并通过既有规则族安全事实合同输出客户 facts。若拆成独立模块，仍需把规则分支的局部选择状态和材料行传出后再回写 decision，只会形成转发壳或第二个选择所有者，因此本闭环不做机械拆分。

其余生产文件行数（固定点 → 当前）：

- `luxian_0609_result_aggregator.py`：6163 → 6167（+4）；基础时限族专属导入、事实校验和证据来源过滤已归零，保留的是通用接收调用。
- `basic_timeliness_customer_projection.py`：362 → 310（-52）；删除旧证据生成和专属来源推断，仅保留客户安全事实合同。
- `canonical_result_finalizer.py`：264 → 300（+36）；增加执行器 facts 的统一安全接收边界，不改变业务状态。
- `customer_evidence_enrichment.py`：202 → 216（+14）；公共投影实现稳定顺序与 all-or-empty。
- `source_registry.py`：657 → 679（+22）；只允许完整注册键或唯一已注册别名映射，未知 dotted source fail closed。
- `canonical_result_store.py`：867 → 875（+8）；Canonical 写入和客户投影复用 Finalizer 统一事实校验，非法基础时限内部 ID 一律 fail closed。

生产代码合计净增 98 行；没有公开 API、数据库、前端或 Canonical DTO 变化。

## 剩余风险

本闭环只做行为等价结构收口，验证了合成冻结病例、535 项影响范围回归和 4251 项 LX0609 全域非基线回归；未运行真实模型十次性能协议，也未宣称三个真实页面入口已经完成业务验收。公共 evidence projector 影响所有已使用 document refs 的规则，后续变更应保留其“全部引用均可唯一定位才交付”的 all-or-empty 合同。
