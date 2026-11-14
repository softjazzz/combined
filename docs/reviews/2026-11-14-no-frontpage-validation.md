# 无首页质控：合同调整与隔离验证

本报告补充 `2026-11-14-pro-a1-a2-a3-validation.md`。原始基线为 `3893a93c3193d6733c02a4425498fbc32ebe736c`；所有变更位于独立分支 `codex/pro-a1-a2-a3-fixes-20261114`。

## 用户确认的合同

所有当前质控默认没有病案首页；首页不能作为质控前提、事实回退或资料不足原因。当前取材使用原始临床文书，真实来源、字段、实施事实、身份、关联、截断和完整性仍须满足原有校验。

`LX0609-08-01-03` 的原合同专门对照首页与出院记录。按用户确认，该项暂为 `not_executed / policy_definition_pending`，等待改为原始临床文书口径，不转为合规或资料不足。没有批量停用其他规则。

## 行为边界

- 当前质控来源与历史可验证来源分开：首页来源从新任务的主动读取、事件触发和回退中移除，旧来源及其查询版本仍由历史合同验证。
- 新取材标识进入材料内容，当前质控装配不要求首页视图；普通病历查看的首页显示能力保留。
- 手术使用实际手术、麻醉及相关原始文书；输血使用实际输注证据。计划、申请、医嘱或缺首页不能充当已实施或未实施证明。
- 新任务的临床时间取登记/原始文书，不借首页补齐；旧任务已冻结时间与材料不改写。
- A1 的独立阳性引用仍须绑定实际证明原行；去掉未消费来源的依赖不等于忽略真实消费来源的错误。

## 验证状态

当前实现及直接受影响的旧首页测试已收口，准备固定提交独立复审。所有命令通过离线 runner 执行，dotenv/网络/非 SQLite 连接受阻，不启动应用生命周期、调度或真实质控。

| 必要范围 | 结果及具体边界 |
| --- | --- |
| 新无首页手术合同、A1独立阳性 | 初始18例通过；后续共享夹具和003分支变化的独立阳性用例已纳入下面四文件复验 |
| 新扩展/输血合同 | `test_extended_no_frontpage_contract.py` 的10条分别定向通过：原行绑定、真实来源错误、typed输血、计划/取消、历史MR事实与篡改拒绝 |
| 基础来源、捕获、历史063、登记/出院时刻、总表 | 38 passed；另有场景冻结/消费者/旧快照边界4 passed |
| 原始术后/输血/有创操作相邻链 | `test_luxian_0609_native_extended_document_execution.py` 13 passed / 426 deselected，保留逐台关联、实际时间缺失、医嘱目录、三日窗口与引文保护 |
| TC02已证缺陷与未知事件并存 | 改为原始输血文书前提后10 passed / 95 deselected；存储边界另见下方6例 |
| 直接受影响的旧手术测试迁移 | 三执行器文件 + 独立阳性文件最终集合309 passed / 1 failed；唯一剩余为非手术目录汇总事实边界，已最小修复 |
| 最后目录边界修复 | 直接 applicability 文件及两个MDT节点10 passed。保留未知分类、不同来源同ID的事实；未重复宣称上行309项在此最后小修后重跑 |

已诊断集合没有剩余失败；上述集合存在重叠，不合计为唯一测试总数，也不代表全仓验收。

整合期间实际发现并修复：070未消费来源使原始引用清空；场景仍通过列表首页时间进入终末；003原始麻醉证据的24小时时窗被误删；明确非手术原行的汇总事实重新触发手术。003成熟缺记录仍走完整性与覆盖闸门，未赋独立阳性豁免；新增截断、不可用、计划未实施、无时区、倒序、多事件、`empty_unconfirmed` 和 `not_captured` 负例。

主要命令（测试均为合成边界）：

```powershell
python -B apps/medqc-web/backend/scripts/run_pr8_offline_tests.py tests/unit/test_no_frontpage_material_contract.py tests/unit/test_automatic_case_material.py::test_main_diagnosis_pending_keeps_saved_positive_conflict_readable tests/unit/test_discharge_horizon_document_fallback.py::test_original_registration_or_document_wins_without_frontpage tests/unit/test_luxian_0609_rule_master.py
python -B apps/medqc-web/backend/scripts/run_pr8_offline_tests.py tests/unit/test_luxian_0609_native_surgery_document_execution.py tests/unit/test_luxian_0609_native_mdt_execution.py tests/unit/test_luxian_0609_native_surgery_gate_execution.py tests/unit/test_surgery_independent_positive_scope.py --tb=short
python -B apps/medqc-web/backend/scripts/run_pr8_offline_tests.py tests/unit/test_luxian_0609_surgery_applicability.py tests/unit/test_luxian_0609_native_mdt_execution.py::test_catalog_operation_never_triggers_level_four_mdt tests/unit/test_luxian_0609_native_mdt_execution.py::test_catalog_exclusion_keeps_unknown_document_fact_and_source_identity --tb=short
```

已补验迁移后的6个 TC02 合成 SQLite 存储节点：`known_nc_unknown` 的新实例读回，以及5个非法计数/状态/类型拒绝节点，**6 passed**。验证命令：

```powershell
python -B apps/medqc-web/backend/scripts/run_pr8_offline_tests.py 'tests/unit/test_luxian_0609_tc02_performed_event_contract.py::test_tc02_synthetic_sqlite_new_instance_preserves_status_scope_and_real_source_refs[known_nc_unknown]' tests/unit/test_luxian_0609_tc02_performed_event_contract.py::test_tc02_store_rejects_reserved_count_status_or_type_before_persisting
```

这6例只验证合成原始文书结论的存储与拒绝合同，不代表PG并发或完整质控验收。固定提交独立复审结论另行记录。

## 保留与限制

不修改已有任务、结果、材料对象或任务索引；没有迁移、数据修复或现场回填脚本。不推送、不合并、不部署。

验证只使用合成数据、离线读取替身、临时材料对象及合成内存 SQLite；未连接真实业务库、CDM、Caché、旧双库，未调用真实模型，未创建质控任务或重跑27份。没有真实PG并发、真实临床数据、浏览器和医学质量验收结论。

新查询投影的原始入院时间列只完成代码及合成序列化检查，未执行真实源SQL。术后正式开始时间估算仍沿用原合同并显式标记；出院经过“专用文书与重大事件”额外语义改造未包含在本轮。A5模型4xx重试仍未处理。
