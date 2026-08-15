# LX0609 质控引擎准商用修复实施计划

> **执行要求：** 按本计划逐个闭环实施；每个 Task 达到验收标准后独立提交并暂停审核。

**Goal:** 消除独立审核发现的规则口径漂移、059实现偏差、历史Canonical状态冲突、033及完整回归失败和客户结果不可定位问题，并用真实病例完成准商用验收。

**Architecture:** 规则总表负责客户口径，`phase_scope`负责发布阶段，规则合同负责执行资料和算法边界；三者必须引用同一版本化业务基线。执行器继续作为唯一判定所有者，Renderer只组织客户文案，Aggregator只投影事实和证据，Finalizer只校验与补缺，Canonical读取与写入共用同一状态一致性验证器。

**Tech Stack:** Python 3.10、FastAPI、SQLAlchemy、PostgreSQL、Pytest、Vue 3、TypeScript、Vitest。

---

## 一、执行原则与停止条件

1. 不新增规则，不重写整套引擎，不新增第二套规则配置或结果表。
2. 后续用户明确确认的业务决策优先于旧版 `phase_scope` 和旧业务基线，但必须回写为带版本和生效日期的权威合同。
3. 每次只处理一个规则或一个低耦合规则族；达到验收标准后提交并进入独立审核，不把下一项混入同一提交。
4. `LX0609-012` 不回退算法；`LX0609-017` 不因旧 phase 状态而关闭；`LX0609-049` 当前不参与正式结论。
5. 任何状态不一致、Envelope损坏、业务定义未确认或证据无法授权关联的情况都失败关闭，不回退旧 `items_json`、Bundle或其他结果表。
6. 自动化测试通过不等于业务准确率通过。最后必须用20–30份脱敏授权真实病例完成人工金标和性能验收。

## 二、总体任务顺序

| 顺序 | 闭环                     | 主要结果                                | 上线阻断     |
| ---: | ------------------------ | --------------------------------------- | ------------ |
|    0 | 权威口径版本化           | 统一规则总表、phase、政策摘要和执行合同 | 是           |
|    1 | Canonical历史结果校验    | 状态冲突Envelope不再返回ready           | 是           |
|    2 | LX0609-059重做           | 诊疗事件—医嘱—病程逐事件一致性          | 是           |
|    3 | LX0609-025合同冻结与实现 | 植入物必查字段和客户文案一致            | 是           |
|    4 | 033与17项失败回归        | 完整3049项规则测试全绿                  | 是           |
|    5 | 证据与整改建议           | 关注结果明确、可定位、可处理            | 是           |
|    6 | 真实病例金标与性能验收   | 给出准确率、Token、耗时和准商用结论     | 是           |
|    7 | Aggregator历史重判清理   | 删除第二判定所有者风险                  | 否，最后处理 |

---

### Task 0：建立最新权威规则基线并校正发布阶段

**目标：** 先解决“谁是最终口径所有者”，再让执行端读取正确的 phase，避免旧JSON覆盖后续明确业务决策。

**Files:**

- Modify: `docs/0602/泸县0609质控点-业务标准基线-v1.md`
- Modify: `backend/app/data/luxian_0609_phase_scope_v1.json`
- Modify: `backend/app/data/luxian_0609_rule_master_v1.json`
- Modify: `backend/app/data/luxian_0609_rule_contracts_v1.json`
- Modify: `backend/app/services/luxian_0609/phase_scope.py`
- Modify: `backend/app/services/luxian_0609/rule_contracts.py`
- Modify: `backend/app/services/luxian_0609/rule_decision_settings.py`
- Modify: `backend/app/services/luxian_0609/native_package.py`
- Modify: `backend/app/services/luxian_0609/execution.py`
- Test: `backend/tests/unit/test_luxian_0609_phase_scope.py`
- Test: `backend/tests/unit/test_luxian_0609_rule_master.py`
- Test: `backend/tests/unit/test_luxian_0609_rule_contracts.py`
- Test: `backend/tests/unit/test_luxian_0609_native_package.py`
- Test: `backend/tests/unit/test_luxian_0609_execution_routing.py`
- Test: `backend/tests/unit/test_luxian_0609_mainline_services.py`（仅更新阶段门禁直接影响的旧执行期望）

**冻结决策：**

- `LX0609-012`：按“影像报告检出异常病灶或异常征象即为阳性”更新权威文档和验收样本，不改回旧算法。
- `LX0609-017`：保留已批准的两级筛选、Top候选和必要时单次LLM；发布状态不得再写成“算法尚未确认”。
- `LX0609-049`：当前无收费数据，明确为不参与正式执行，不输出合规或确定问题。
- `LX0609-009、020、023`：逐条写入已确认的事件、时间、LLM边界和失败语义，不沿用旧 phase 的批量关闭结论。
- `LX0609-059`：在Task 2完成前保持不执行正式结论。
- `LX0609-025`：在Task 3冻结字段前不得根据旧文档擅自删除或新增必查项。
- `LX0609-024、028、056、075`：逐条核对是否已有后续明确确认；没有证据的保持定义待确认。

**TDD步骤：**

1. 新增失败测试：权威基线、规则总表、phase和执行合同必须具有相同 `definition_version` 和75条有序规则身份。
2. 新增失败测试：012、017、049及009/020/023必须符合上述冻结决策。
3. 新增失败测试：真正 `pending_definition` 的规则经公开执行计划不得进入可产生 `compliant/non_compliant` 的执行器集合。
4. 新增失败测试：当前执行边界尚无子条件级投影时，`phase_1_partial` 必须整条失败关闭为 `not_executed`，不得把待确认子条件一起执行。
5. 最小修改四份权威资料和唯一phase加载边界；公开执行入口为待确认规则生成受控 `not_executed` 结果，不在Renderer或Aggregator重复判断phase。
6. 运行：

   ```powershell
   python -m pytest backend/tests/unit/test_luxian_0609_phase_scope.py backend/tests/unit/test_luxian_0609_rule_master.py backend/tests/unit/test_luxian_0609_rule_contracts.py backend/tests/unit/test_luxian_0609_native_package.py backend/tests/unit/test_luxian_0609_execution_routing.py -q
   ```

7. 预期：全部通过；公开计划中pending规则的可执行数为0，049不输出正式结论，012/017仍按最新确认合同存在。
8. 提交：`修复泸县0609权威规则口径与发布阶段`

**停止条件：** 如果同一规则在用户后续确认、规则总表和客户政策之间仍无法确定唯一口径，只记录冲突并保持不执行，不让实现Agent猜测。

---

### Task 1：Canonical历史Envelope状态一致性失败关闭

**目标：** 让latest单病历、批量摘要、首页、HTML和Excel读取同一个严格Canonical校验器；历史状态冲突不得返回ready。

**Files:**

- Modify: `backend/app/services/custom_qc_workspace_service.py`
- Test: `backend/tests/unit/test_luxian_0609_canonical_result_delivery.py`
- Test: `backend/tests/unit/test_luxian_0609_record_result_read_model.py`
- Test: `backend/tests/unit/test_workstation_query_service.py`

**TDD步骤：**

1. 抽取现有写入端的Canonical item状态一致性校验为同文件私有函数，不创建新服务层。
2. 先补公开读取入口失败测试，覆盖：
   - `compliant + is_compliant=false`
   - `non_compliant + is_compliant=true`
   - `data_gap/uncertain/not_applicable/technical_error/not_executed + is_compliant` 非空
   - `status/result_status/display_status` 不一致
   - 非法状态、空rule_id、重复rule_id
3. 运行红测，证明当前latest仍返回ready。
4. 单病历latest、批量summary/include_items、exact batch导出统一调用同一校验器。
5. 不一致时统一返回 `technical_error/canonical_result_envelope_invalid`；不得回退旧结果。
6. 一致的历史Envelope保持原样，不重写数据库。
7. 运行：

   ```powershell
   python -m pytest backend/tests/unit/test_luxian_0609_canonical_result_delivery.py backend/tests/unit/test_luxian_0609_record_result_read_model.py backend/tests/unit/test_workstation_query_service.py -q
   ```

8. 对本地45份最新Envelope只读复核：原25条冲突记录对应的病历不再投影为ready。
9. 提交：`修复Canonical历史结果一致性校验`

**验收：** 新写入与旧读取只有一个状态验证所有者；页面、首页和导出不会对冲突Envelope作二次解释。

---

### Task 2：重做LX0609-059诊疗行为一致性

**目标：** 移除“抗菌药名称出现在病程即合规”的错误实现，改成逐个诊疗事件核对医嘱与病程。

**Files:**

- Modify: `backend/app/services/luxian_0609/native_extended_document_execution.py`
- Modify only if evidence contract requires: `backend/app/services/luxian_0609/luxian_0609_result_aggregator.py`
- Modify only for customer wording: `backend/app/services/luxian_0609/customer_renderer.py`
- Test: `backend/tests/unit/test_luxian_0609_native_extended_document_execution.py`
- Test: `backend/tests/unit/test_luxian_0609_result_aggregator.py`
- Test: `backend/tests/unit/test_luxian_0609_customer_renderer.py`

**执行合同：**

- 一个诊疗事件必须有受控事件身份、时间、对应医嘱引用和病程引用。
- 事件范围先限定结构化可识别的检查、操作、治疗和医嘱变更；不做无限泛化文本扫描。
- Python负责身份、时间和集合一致性；只有“病程是否表达该事件/变更原因”缺少可靠结构化字段时，才向一次受控LLM提供最小事件窗口。
- LLM只输出受控事实枚举和引用，不直接输出规则状态。
- 缺医嘱或医嘱变更无病程说明可判确定问题；事件关联不唯一、资料截断或权威时间缺失为data_gap；模型失败为technical_error。

**TDD步骤：**

1. 红测：病程仅出现抗菌药名称不得判合规。
2. 红测：明确操作无对应医嘱，逐事件输出non_compliant并包含事件时间和可定位来源。
3. 红测：医嘱变更存在但病程未说明，输出具体缺陷。
4. 红测：医嘱、执行事件和病程完整关联时合规。
5. 红测：同visit多个事件不能互相借用证据。
6. 红测：关联冲突/时间缺失失败关闭，不能猜测。
7. 将059移出054–058抗菌药共用分支，建立059专属小函数；不新增通用平台。
8. 运行目标文件及公开聚合/Renderer测试。
9. 用至少3份授权病例或冻结脱敏事件重放，记录状态、原因、证据、LLM次数、Token和耗时差异。
10. 提交：`修复059诊疗行为一致性判定`

**验收：** 药名命中不能单独产生C；每个确定问题能回答“哪项诊疗事件、哪条医嘱、哪份病程、什么时间、缺了什么”。

---

### Task 3：冻结并修复LX0609-025植入物字段合同

**目标：** 让规则标题、客户政策、LLM事实白名单、Python裁决和客户卡片使用同一字段清单。

**Files:**

- Modify: `backend/app/data/luxian_0609_rule_master_v1.json`
- Modify: `backend/app/services/luxian_0609/surgery_text_fact_contract.py`
- Modify: `backend/app/services/luxian_0609/native_surgery_gate_execution.py`
- Modify: `backend/app/services/luxian_0609/customer_renderer.py`
- Test: `backend/tests/unit/test_luxian_0609_surgery_text_fact_contract.py`
- Test: `backend/tests/unit/test_luxian_0609_native_surgery_gate_execution.py`
- Test: `backend/tests/unit/test_luxian_0609_customer_renderer.py`

**先冻结的业务表：**

| 字段      | 是否影响025状态              | 缺失时客户文案              | 依据版本     |
| --------- | ---------------------------- | --------------------------- | ------------ |
| 名称      | 待冻结                       | 明确列出具体缺项            | 最新客户政策 |
| 种类      | 待冻结                       | 明确列出具体缺项            | 最新客户政策 |
| 规格/型号 | 待冻结                       | 明确列出具体缺项            | 最新客户政策 |
| 材质      | 待冻结                       | 明确列出具体缺项            | 最新客户政策 |
| 数量      | 待冻结                       | 明确列出具体缺项            | 最新客户政策 |
| 条码      | 待冻结，不能由旧代码自动决定 | 若为扩展项则不得改变025状态 | 最新客户政策 |

**TDD步骤：**

1. 先只提交合同文档和参数化测试，确认最终必查字段后才改生产裁决。
2. 参数化红测覆盖每个必查字段单独缺失、多个缺失、仅缺扩展字段、未使用永久植入物、植入物身份不确定。
3. LLM输出只允许受控字段名、植入物名称和文书引用；拒绝任意文本字段和值泄漏。
4. Python根据冻结字段清单映射状态；Renderer显示“发现的植入物名称 + 具体缺项”。
5. 真实客户示例至少复核一条“自粘性人工硬脑膜”病例，确认不能凭展示文案反推未读取的原始字段。
6. 提交：`统一025植入物字段判定合同`

**验收：** 客户看到的规则标题、结论、判定事实、证据和建议完全一致；条码是否必填有明确政策版本，不再由Prompt自行决定。

---

### Task 4：修复033并清零完整75规则测试失败

**目标：** 不通过修改断言掩盖行为变化；按公开入口逐组修复17项失败，最终3049项全绿。

**子任务顺序：**

#### Task 4A：LX0609-033手术知情同意

- Files: `native_surgery_gate_execution.py`、`surgery_text_fact_contract.py`、`evidence_snapshot_provider.py`及033对应测试。
- 冻结四种来源状态：完整实质文书、完整空结果、非精确候选、来源查询异常。
- 明确 `data_gap/non_compliant/compliant/technical_error` 唯一映射。
- 公开执行入口验证状态、reason、证据、LLM次数和Token。
- Commit: `修复033手术同意结果合同`

#### Task 4B：规则总表、runtime manifest与预生产范围

- Files: `luxian_0609_rule_master_v1.json`、runtime manifest构建文件、`preproduction_runner.py`及对应测试。
- 不改规则算法，只修规则身份、顺序、执行数和非法范围失败语义。
- Commit: `修复泸县0609运行清单与预生产范围`

#### Task 4C：手术时间与资料Snapshot剩余失败

- Files仅限失败测试实际触达的手术执行器/Snapshot provider。
- 分别冻结：带时区时间、完整空来源、非精确候选、多个手术事件。
- Commit: `修复手术资料快照边界`

**完整门禁：**

```powershell
$tests = Get-ChildItem backend/tests/unit -Filter 'test_luxian_0609*.py'
python -m pytest $tests.FullName -q
```

预期：`3049 passed`或因新增回归而数量增加，但必须`0 failed`。不得只运行窄聚焦集后宣称完成。

---

### Task 5：客户结果证据与整改建议逐规则族闭环

**目标：** 每条关注结果都明确、清晰、可定位、可处理；不再显示内部枚举或通用建议。

**分组顺序：**

1. `005/006`：首次查房文书、记录时间、医生级别证据。
2. `020/023`：会诊episode、意见时间、执行病程或执行事件证据。
3. `051/060/061/067/068/071`：死亡、出院、转科和交接事件证据。
4. `041/044/075`：输血和有创操作事件证据。
5. `018`：内部英文枚举全部映射为客户可读事实。

**Files（每个子任务只选实际规则涉及者）：**

- Rule executor: `backend/app/services/luxian_0609/native_*_execution.py`
- Evidence projection: `backend/app/services/luxian_0609/luxian_0609_result_aggregator.py`
- Customer wording: `backend/app/services/luxian_0609/customer_renderer.py`
- Frontend fallback removal: `src/views/workstation-v4/customer-sample-validation/SingleRecordQcResultPanel.vue`
- Corresponding focused backend and frontend tests.

**每个规则族TDD：**

1. 从最新Canonical统计中冻结一条“关注结果无source_ref”的脱敏反例。
2. 在执行器事实中交付文书ID/事件ID、文书名称和记录时间；不得由Renderer猜引用。
3. Aggregator只白名单投影已经授权的引用。
4. Renderer生成针对缺陷的处理建议，禁止“请按质控要求核对并完善相关记录”。
5. 前端仅在后端确实声明需人工核对时显示准确原因，不再填“本次质控采用的关键判定信息”。
6. 运行该规则公开入口、Canonical、HTML/Excel和组件测试。
7. 一个规则族一个中文提交并独立审核。

**量化验收：**

- 最新关注结果无有效 `source_ref`：从130降至0；确实无法定位时必须有具体、真实的人工核对原因。
- 通用建议：从51降至0。
- 内部英文枚举：从2降至0。
- 不输出正文、Prompt、模型原始响应、SQL、三坐标或内部异常原文。

---

### Task 6：真实病例金标、模型调用和性能验收

**目标：** 用真实业务结果决定准商用，而不是用Mock数量代替准确率。

**Files:**

- Create: `docs/audits/2026-08-xx-lx0609-real-case-gold-acceptance.md`
- Modify only if required by proven defects: corresponding single-rule executor/tests.

**样本要求：**

- 20–30份脱敏授权真实病例。
- 覆盖在院、正常出院、转院、死亡、手术、输血、会诊、CT/MRI、检验培养和资料不足。
- 每个正式启用规则至少有可追溯正例、负例或边界例；无法覆盖的规则明确标记未验收。

**验收记录：**

1. 质控员盲标：适用性、状态、原因、关键事实、证据位置和整改建议。
2. 对比引擎结果，统计每条规则和总体的误报、漏报、无法判断和资料不足归因。
3. 记录每病历逻辑LLM调用、HTTP尝试、输入/输出Token、费用、P50/P95耗时和峰值并发。
4. 复核相同输入重跑的结果一致性及Canonical唯一交付。
5. 浏览器验收运行/终末列表、单病历结果、证据定位、单/批HTML和筛选Excel。
6. 失败病例只回到对应单规则闭环，不在验收阶段进行公共引擎重构。

**准商用放行条件：**

- Task 0–5全部独立审核PASS。
- 完整后端规则测试、前端type-check及结果页测试全部通过。
- 正式启用规则均有人工验收依据；未验收规则保持不参与正式结论。
- 无Canonical状态冲突、无不可解释技术异常、无越权证据读取。
- 性能与Token实测在客户可接受预算内；报告明确客户机环境和数据规模。

---

### Task 7：清理Aggregator历史业务重判入口

**目标：** 在主链稳定后删除可重新启用的第二判定所有者，防止配置回退造成状态漂移。

**Files:**

- Modify: `backend/app/services/luxian_0609/luxian_0609_result_aggregator.py`
- Test: `backend/tests/unit/test_luxian_0609_result_aggregator.py`
- Verify callers with CodeGraph before editing.

**步骤：**

1. 用CodeGraph确认 `legacy_customer_display_rejudgment` 的所有生产调用者。
2. 若无生产调用，先补公开主链测试证明Decision状态原样通过。
3. 删除公开参数和历史重判分支；保留必要的历史数据迁移脚本时必须隔离到非生产入口。
4. 跑Aggregator、Finalizer、Canonical与结果页完整回归。
5. 提交：`移除聚合层历史业务重判入口`

---

## 三、每个闭环的统一交付清单

每个Task完成后必须同时提供：

1. 固定提交SHA和精确文件清单。
2. 修改前真实反例或公开入口红测。
3. 修改后状态、reason、关键事实、证据和客户文案对比。
4. LLM逻辑调用、HTTP尝试、输入/输出Token和耗时是否变化。
5. 聚焦测试、完整相关测试、Ruff/ESLint、编码和diff检查结果。
6. 未完成的真实数据或客户环境验收边界。
7. 独立审核结论；未获下一Task授权时暂停。

## 四、明确排除范围

- 不新增第二套Bundle、Canonical结果表、规则平台或统计系统。
- 不为修复059重写054–058。
- 不把旧phase文件直接变成大规模关闭开关。
- 不在Renderer、Finalizer、Aggregator或前端重新判定医疗业务状态。
- 不在没有客户政策依据时自行决定025条码等字段。
- 不在本轮处理无关UI、同步性能、权限体系或其他规则集。
