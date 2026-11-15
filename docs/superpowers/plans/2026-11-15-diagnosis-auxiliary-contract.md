# 诊断辅助字段合同修复

## 范围

基线 `4ce8b2d53073197bca787d8e5ec861880bb0522a`，独立分支 `codex/diagnosis-projection-contract-20261115`。
1026材料表不含新ORM可选列main_diag_flag，整实体诊断查询使材料捕获失败。本轮只修字段合同及消费缺口隔离，不补旧表、不填厂商标志、不改主诊断医学判据。

## 实现

- 主诊断辅助查询只投影排序/判定实际需要的序号、类别、编码和名称。编码/名称至少一列存在；保持原有编码优先、名称匹配分支，不要求main_diag_flag、审计列或首页。
- 同病种候选只读取患者/就诊、科室、诊断时间和实际匹配字段；首次病程只读取身份、正文及可用显示字段。沿原上限与排序，来源schema来自同一捕获事务。
- 对照首次病程按机构及患者+就诊联合匹配，防止同就诊号的其他患者混入。必要身份列缺失、空对照身份、源绑定/完整性错误保持拒绝。
- 缺表或必要业务字段抛SourceEvidenceUnavailable。material_query保存缺口；capture只隔离这种受控缺口，其他正文继续保存，权限/连接/身份错误仍停止。
- 已保存缺口在冻结读取中重放，不回查当前库。无诊断或无对照不构造正常可判定依据。
- CL-276在Bundle共享文书与旧单规则入口分别消费同一缺口：生成data_gap、is_compliant=None、受控source_unavailable；不调用该规则模型，其他规则继续。正常信号复用，权限等错误不被转换。
- 历史快照decorator、任务/结果存储、无首页取材和手术输血暂停未修改。已有历史查询结果原样读取，不补造旧证据。

## 必要验证

全程为合成数据/内存SQLite/受控替身，无业务数据库或真实模型、质控任务。

1. 新合同先红：5失败/1通过，复现旧表缺main_diag_flag、缺业务字段/身份列及缺表边界。
2. 投影、捕获、冻结与来源入口集合91通过：
   `test_diagnosis_auxiliary_contract.py`、`test_pdf_case_material_snapshot.py`、`test_validation_material_snapshot_aux.py`、`test_clinical_read_entrances.py`、`test_case_material_snapshot.py`。
   此后仅补消费隔离与移除未用import，未改该轮已验证的投影/捕获行为。
3. 独立复审发现Bundle共享消费及旧单规则入口仍会放大局部缺口，均已补修。
4. 最终定向18通过：新的诊断合同文件16项（含同文书/后续文书继续、全选仅缺口规则、权限不得降级、旧入口模型前缺口及正常路径），加旧SC070/SC146入口两项合成回归。手术规则测试仅验证入口替身，未启用暂停规则或执行真实病例。
5. 旧Bundle编排文件8项通过、1项失败。唯一 `test_service_facade_should_forward_running_final_bundle_options` 对转发参数的旧断言漏列execution_concurrency；在2c38aa61c工作树（与4ce8b2d53合并树相同）独立复现同一失败。本轮未改该旧断言，不称全套通过。
6. Python语法、UTF-8无BOM/LF、git diff --check通过。

验证分轮有重叠，不合并成虚高总数。未重复全量或远端CI。

## 独立复审及限制

独立复审确认两项消费边界发现闭合，最终未确认新增P1/P2。复审只读代码和合成用例，复用上述测试证据，不重复运行。

未验证真实PG权限、REPEATABLE READ并发及真实1026单病例链路，不能据此声称此前本地失败验收已通过。
未改运行中的本地API或配置、未连接业务库、未调用模型、未再次质控/重跑27份；未推送、合并、部署或打包。
