# LX0609验证数据与规则边界根因修复 Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 修复LX0609 v3验证集的时间污染、客户样本验证任务的逐病例评价终点、会诊阶段耦合及手术规则门控双轨，使37条受控金标准完整通过，并锁定750条结果的跨规则不变量。

**Architecture:** 保持“客户样本验证入口 → 共享批量执行层 → EvidenceSnapshot/MaterialStore → Native规则 → Canonical Envelope”不变。只增加一个小型逐病例评价快照合同，规则引擎继续使用MaterialStore作为唯一资料源；会诊和手术只修现有执行器边界，不增加LLM调用、不建设新证据链、不重写引擎。

**Tech Stack:** FastAPI、SQLAlchemy、PostgreSQL、Python dataclass/Enum、pytest、现有LX0609 Native RuleDecision与Canonical Envelope。

---

## 一、锁定范围与非目标

### 本轮必须完成

1. 冻结37条受控金标准的状态、门控事实、关键时间、必需来源、客户解释和证据要求。
2. 修复v3病例的住院时间轴及017样本文本。
3. 客户样本验证任务保存逐病例评价快照，并纳入幂等身份。
4. 区分“评价终点缺失”“时间冲突”“评价窗口未成熟”。
5. 021/022不再被020/023的执行关联失败污染。
6. 029/030/032共享底层手术事件事实，但严格使用各自正式门控。
7. 37/37通过后，再验证10份病例750条结果的跨规则不变量。

### 明确不做

- 不增加LLM调用。
- 不重写质控引擎。
- 不新增第二套Bundle或Evidence来源。
- 不修改Canonical状态终结架构。
- 不改前端视觉和交互。
- 不清理无关历史命名或巨型文件。
- 不把另外713条无金标准结果宣称为临床正确。

## 二、最终业务合同

### 2.1 逐病例评价快照

每条任务记录保存：

```json
{
  "record_id": "record-001",
  "record_scene": "running|final|unknown",
  "admission_datetime": "2026-06-01 08:00:00",
  "discharge_datetime": "2026-06-10 09:00:00",
  "evaluation_horizon": "2026-06-10",
  "evaluation_basis": "discharge_time|task_frozen_date|none",
  "resolution_status": "resolved|horizon_missing|horizon_conflict|scene_uncertain"
}
```

解析规则：

- `running`：使用任务创建日，`evaluation_basis=task_frozen_date`。
- `final`且当前住院出院时间有效：使用出院时间，`evaluation_basis=discharge_time`。
- `final`但出院时间缺失：不生成评价终点，`resolution_status=horizon_missing`。
- 出院早于入院或事件时间明显超出当前住院窗口：`resolution_status=horizon_conflict`。
- Scene未知：不使用任务当天日期兜底，`resolution_status=scene_uncertain`。
- 完整逐病例快照进入任务幂等哈希。
- 日期精度只能保守证明窗口成熟，禁止把日期静默解释为当天00:00或23:59。

### 2.2 评价原因

| 场景           | Canonical状态 | reason code                  | 客户解释                                   |
| -------------- | ------------- | ---------------------------- | ------------------------------------------ |
| 无评价终点     | data_gap      | authoritative_time_missing   | 缺少评价截止日期或有效出院时间             |
| 时间互相冲突   | data_gap      | authoritative_time_conflict  | 当前住院的入院、出院或事件时间存在冲突     |
| 24小时尚未届满 | data_gap      | evaluation_window_not_mature | 截至评价日期尚未满24小时，本次暂不判定缺陷 |

### 2.3 手术规则门控

统一底层事实字段：

```text
surgery_order_present
surgery_application_present
catalog_qualified_surgery
performed_surgery_present
formal_surgery_record_present
event_within_current_stay
source_complete
time_conflict
```

规则选择器：

- LX0609-029：当前住院存在手术医嘱或受控等价手术申请，检查术前小结。
- LX0609-030：当前住院存在手术医嘱或受控等价手术申请，检查正式手术记录。
- LX0609-032：当前住院存在正式手术记录，检查手术安全核查表。
- `mr_surgery`只作为底层事件和分类辅助，不能替代029/030的手术医嘱，也不能替代032的正式手术记录。
- 无手术医嘱却出现正式手术记录时，029/030不得静默判不适用；返回受控关联冲突，避免隐藏数据矛盾。

---

## Task 1：冻结37条金标准合同

**Files:**

- Modify: `backend/scripts/build_luxian_0609_0426_synthetic_v3.py`
- Modify: `backend/scripts/luxian_0609_v3_controlled_evidence.py`
- Test: `backend/tests/unit/test_luxian_0609_0426_synthetic_v3.py`
- Test: `backend/tests/unit/test_luxian_0609_mainline_synthetic_eval.py`

### Steps

1. 生成固定37条绑定清单，每条包含：`case_index`、`rule_id`、`expected_status`、`expected_reason_code`、`trigger_facts`、`required_sources`、`expected_evidence_roles`。
2. 为017明确样本意图：本轮保留“合规样本”，因此必须重写病程内容；不得降低70%阈值。
3. 写失败测试，要求37条绑定字段完整、规则ID唯一、fixture定位唯一。
4. 运行：

```powershell
python -m pytest backend/tests/unit/test_luxian_0609_0426_synthetic_v3.py backend/tests/unit/test_luxian_0609_mainline_synthetic_eval.py -q
```

5. 最小修改使测试通过。
6. 独立提交：`测试：冻结LX0609 v3三十七条金标准合同`。

**暂停条件：** 任何规则缺少明确门控或期望证据时停止，不进入Task 2。

---

## Task 2：修复v3住院时间轴与017样本

**Files:**

- Modify: `backend/scripts/build_luxian_0609_0426_synthetic_v3.py`
- Modify: `backend/scripts/luxian_0609_v3_controlled_evidence.py`
- Test: `backend/tests/unit/test_luxian_0609_0426_synthetic_v3.py`

### Steps

1. 先写失败测试，锁定38份病例：
   - final病例必须具有当前住院出院时间；
   - 出院时间不得早于入院；
   - 目标事件不得落在入院前或出院/评价终点后；
   - 2025年残留手术不得进入2026年合成住院；
   - 历史史料字段不参与本次住院事件检查。
2. 修复生成器，只清理或重写受控资料行，不修改生产数据库同步逻辑。
3. 重写病例006的4份病程，使症状、检查、治疗调整和疗效判断真正不同。
4. 校验样本池Scene、workspace记录、`inpat_registration`、`discharge_record`和目标事件时间一致。
5. 运行聚焦测试。
6. 独立提交：`修复：统一LX0609 v3住院时间轴`。

**验收：** 38份病例时间完整性检查100%通过，病例006的最高相似度不超过70%。

---

## Task 3：建立客户样本验证逐病例评价快照

**Files:**

- Create: `backend/app/services/luxian_0609/evaluation_horizon.py`
- Modify: `backend/app/routers/qc_sample_pools.py`
- Modify: `backend/app/routers/qc_sichuan.py`（仅共享批量执行worker读取逐病例快照，不改变入口语义）
- Modify: `backend/app/services/luxian_0609/evidence_snapshot_provider.py`
- Test: `backend/tests/unit/test_qc_sample_pools_router.py`
- Test: `backend/tests/unit/test_qc_sichuan_batch_throughput.py`
- Test: `backend/tests/unit/test_luxian_0609_evidence_snapshot_provider.py`

### Steps

1. 为纯函数`resolve_record_evaluation_horizon(...)`写表驱动失败测试，覆盖running、final、缺出院、时间冲突、Scene未知。
2. 实现不可变的小型快照对象；不读取规则结果，不生成Canonical状态。
3. 客户样本验证任务创建时冻结任务日期，并按病例解析快照。
4. 将快照整体加入`execution_scope_hash`，证明病例状态或出院时间变化后不会复用旧任务。
5. worker按`record_id`取对应快照：
   - running且resolved时传冻结日期；
   - final让Evidence Provider使用权威出院时间；
   - missing/conflict/unknown禁止用当天日期回退。
6. Evidence Provider校验出院时间不早于入院；冲突时不生成horizon事实。
7. 运行聚焦测试。
8. 独立提交：`修复：冻结客户样本质控逐病例评价终点`。

**验收：** final缺出院时间不能被当天日期掩盖；running重试使用同一冻结日期；逐病例快照进入幂等身份。

---

## Task 4：拆分评价终点缺失与窗口未成熟

> 详细执行与验收以 `docs/plans/2026-08-04-lx0609-task4-evaluation-window-reasons.md` 为准；该子计划补充锁定了“检查检验投影不得绕过Task 3策略直接使用原始出院时间”的边界合同。

**Files:**

- Modify: `backend/app/services/luxian_0609/native_exam_lab_execution.py`
- Modify: `backend/app/services/luxian_0609/decision_model.py`
- Modify: `backend/app/services/luxian_0609/canonical_result_finalizer.py`
- Test: `backend/tests/unit/test_luxian_0609_native_exam_lab_execution.py`
- Test: `backend/tests/unit/test_luxian_0609_canonical_result_finalizer.py`

### Steps

1. 写三组失败测试：终点缺失、时间冲突、窗口未成熟。
2. 将当前`bool | None`的horizon结果最小替换为受控枚举：`mature/not_mature/missing/conflict`。
3. 分别映射：
   - missing → `authoritative_time_missing`；
   - conflict → `authoritative_time_conflict`；
   - not_mature → `evaluation_window_not_mature`。
4. 在Canonical数据不足解释表增加客户可懂文案。
5. 保持012/015阳性识别、正则和LLM调用不变。
6. 运行聚焦测试并独立提交：`修复：区分评价终点缺失与窗口未成熟`。

---

## Task 5：隔离会诊文书判断与执行关联

**Files:**

- Modify: `backend/app/services/luxian_0609/native_consultation_episode_execution.py`
- Test: `backend/tests/unit/test_luxian_0609_native_consultation_episode_execution.py`

### Steps

1. 写失败测试：同时选择020～023、缺评价终点、申请和意见为明确空泛文本。
2. 断言：021/022仍判不合规，020/023为数据不足。
3. 将021/022第一阶段文书内容判断放在020/023评价窗口短路之前。
4. 第二阶段失败只写入020/023，不得覆盖已完成的021/022状态。
5. 不修改Prompt、不增加调用次数；确定性模式命中时维持0次额外LLM。
6. 运行聚焦测试并独立提交：`修复：隔离会诊内容判断与执行关联`。

---

## Task 6：统一手术事件事实并恢复正式规则门控

**Files:**

- Modify: `backend/app/services/luxian_0609/surgery_applicability.py`
- Modify: `backend/app/services/luxian_0609/planner.py`
- Modify: `backend/app/services/luxian_0609/deterministic_gate.py`
- Modify: `backend/app/services/luxian_0609/runtime_shadow_input_provider.py`
- Modify: `backend/app/services/luxian_0609/native_surgery_document_execution.py`
- Modify: `backend/app/services/luxian_0609/native_execution.py`
- Test: `backend/tests/unit/test_luxian_0609_native_surgery_document_execution.py`
- Test: `backend/tests/unit/test_luxian_0609_native_execution.py`
- Test: `backend/tests/unit/test_luxian_0609_surgery_text_fact_contract.py`

### Steps

1. 写失败测试矩阵：
   - 有手术医嘱、无术前小结 → 029不合规；
   - 有手术医嘱、无手术记录 → 030不合规；
   - 有正式手术记录、无核查表 → 032不合规；
   - 只有`mr_surgery`、无手术医嘱 → 不得触发029/030；
   - 只有手术医嘱、无正式手术记录 → 不得触发032；
   - 正式记录存在但手术医嘱缺失 → 029/030受控关联冲突；
   - 事件在当前住院窗口外 → 不得作为本次手术触发。
2. 在现有`surgery_applicability.py`中扩展底层事件事实，不另建手术规则框架。
3. 029/030选择`order/application`门控；032选择`formal_surgery_record`门控。
4. 移除“已实施手术可替代029/030手术医嘱”的现有Planner替代策略。
5. 保留032对正式手术记录的独立门控，不让首页操作清单或医嘱触发。
6. 运行手术族聚焦测试。
7. 独立提交：`修复：统一手术事件事实与规则门控`。

---

## Task 7：受控验收与暂停

**Files:**

- Use: `scripts/qc/run_luxian_0609_mainline_synthetic_eval.py`
- Use: `backend/scripts/build_luxian_0609_0426_synthetic_v3.py`
- Test: 上述所有聚焦测试文件
- Report: `docs/acceptance/2026-08-04-lx0609-v3-contract-recheck.md`

### Steps

1. 组合回归：只运行本计划涉及的后端测试，不在每个小补丁后运行全量检查。
2. 通过客户样本验证真实任务入口重跑v3，不只调用执行器单测。
3. 首先核验37条金标准，每条同时检查：
   - status；
   - reason code；
   - 门控事实；
   - 客户解释；
   - 可定位证据。
4. 37/37未通过时停止，不进入750条审查。
5. 37/37通过后，抽查同一10份病例共750条，锁定跨规则不变量：
   - 0 technical_error；
   - 0 not_executed；
   - 029/030/032门控事实不矛盾；
   - 021/022不受020/023影响；
   - 数据不足原因与真实缺口一致；
   - final/running评价终点与Scene一致。
6. 明确标注另外713条没有临床金标准，只能证明合同与不变量，不宣称逐条正确。
7. 输出报告并暂停，未经再次确认不启动会诊事件级LLM试点或其他技术债治理。

## 三、最终验收门槛

| 项目                          |  门槛 |
| ----------------------------- | ----: |
| 37条金标准状态                | 37/37 |
| 37条reason code               | 37/37 |
| 37条规则专属门控事实          | 37/37 |
| 37条客户解释                  | 37/37 |
| 应有证据的规则可定位          |  100% |
| 技术异常                      |     0 |
| 未执行                        |     0 |
| 新增LLM调用                   |     0 |
| final缺出院时间被当天日期兜底 |     0 |
| 跨住院时间污染事件            |     0 |

## 四、执行纪律

- 每个Task先写失败测试，再做最小实现，再运行聚焦测试。
- 每个Task形成独立绿色提交，可以单独回滚。
- Task 6完成后再做一次组合回归；不反复运行完整类型/编码检查。
- 发现需要新增第二证据链、重写执行器或扩大到其他规则族时立即停止并汇报。
- 所有生产文件保持UTF-8无BOM、LF。
