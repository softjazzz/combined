# 0609收尾执行队列

问题级队列含缺陷、争议与验证缺口，不等同确认缺陷数或规则通过数。原86条T0分类保留历史基线，最新问题动作以本表为准。文件锁见closure-ownership.json。

当前生产集成880a433b0。305974e38上186项聚焦回归通过；PRIV002集成后67项隐私回归通过（20项与前者重合，不叠加为独立总数）。N13有限防误判子项已集成，但6项状态预期、2项计数预期未达，整项开放。无真实模型/PG/客户验收结论。

|问题|状态|负责人|依赖|
|---|---|---|---|
|N12|queued_evidence_review|待分配||
|N10|queued_evidence_review|待分配||
|N13|limited_engineering_repair_integrated_business_acceptance_open|/root/repair_chemo||
|TR-044-MULTI|queued_evidence_review|待分配||
|SURGERY-029030|queued_evidence_review|待分配||
|PREOP-MEDICAL|business_basis_review_no_code_decision|待分配||
|CT-INPUT-CHANGE|revalidation_evidence_preparation|待分配||
|PATH-INPUT-CHANGE|revalidation_evidence_preparation|待分配||
|PROMPT-074|revalidation_evidence_preparation|待分配||
|SURGERY-FREEZE|revalidation_evidence_preparation|待分配||
|TR-048-REAL|revalidation_evidence_preparation|待分配||
|course-timing:CT-01|queued_shared_module|待分配|imaging-laboratory:IML-02|
|course-timing:CT-02|queued_shared_module|待分配|imaging-laboratory:IML-02|
|course-timing:CT-03|queued_shared_module|待分配|imaging-laboratory:IML-02|
|discharge-death:DD-F01|frozen_red_then_limited_repair|/root/repair_iml02|imaging-laboratory:IML-02|
|discharge-death:DD-F02|queued_evidence_review|待分配||
|discharge-death:DD-F05|business_basis_review_no_code_decision|待分配||
|imaging-laboratory:IML-01|integrated_confirmed_subissues_joint_ct_mri_contract_open|/root/repair_iml01||
|imaging-laboratory:IML-02|integrated_engineering_closed|/root/repair_iml02||
|imaging-laboratory:IML-D01|business_basis_review_no_code_decision|待分配||
|imaging-laboratory:IML-D02|business_basis_review_no_code_decision|待分配||
|rescue-remaining:RR-D01|evaluation_horizon_material_visibility_contract_pending|/root/repair_iml01||
|rescue-remaining:RR-D02|independent19_frozen_waiting_serial_test_slot|/root/repair_iml01||
|rescue-remaining:RR-M01|integrated_engineering_contract_closed|/root/repair_iml02||
|treatment-consultation:TC-01|queued_evidence_review|待分配||
|treatment-consultation:TC-02|queued_shared_module|待分配|imaging-laboratory:IML-02|
|treatment-consultation:TC-03|queued_evidence_review|待分配||
|tumor-pathology:TP-D01|integrated_engineering_closed|/root/repair_chemo||
|tumor-pathology:TP-D02|design_before_semantic_changes|/root/repair_chemo||
|tumor-pathology:TP-D03|design_before_semantic_changes|/root/repair_chemo||
|tumor-pathology:TP-D04|queued_shared_module|待分配|imaging-laboratory:IML-02|
|tumor-pathology:TP-D05|queued_shared_module|待分配|imaging-laboratory:IML-02|
|PRIV-002|integrated_limited_source_boundary_engineering_closed|/root/repair_privacy_closure||
|PRIV-003|existing_three_entry_source_design_in_progress|/root/repair_privacy_closure||
|PRIV-004|integrated_engineering_closed|/root/repair_privacy_closure||
|PRIV-005|integrated_engineering_closed|/root/repair_privacy_closure||
|rescue-remaining:RR-PUB01|queued_shared_module|待分配|imaging-laboratory:IML-02|
|rescue-remaining:RR-SCOPE01|queued_test_expectation_reconciliation|待分配||
