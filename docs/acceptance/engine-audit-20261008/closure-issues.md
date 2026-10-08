# 0609收尾执行队列

问题级队列含缺陷、争议与验证缺口，不等同确认缺陷数或规则通过数。原86条T0分类保留历史基线，最新问题动作以本表为准。文件锁见closure-ownership.json。

已集成D01、IML02、IML01确定子项、PRIV004/005、074合同元数据。集成305974e38上186项离线工程回归通过。PRIV002固定源独审49项通过，已集成26f4fe645待集成工程复跑；N13仍有6条原业务预期未达；CT/MRI联合事件合同仍开放。

|问题|状态|负责人|依赖|
|---|---|---|---|
|N12|queued_evidence_review|待分配||
|N10|queued_evidence_review|待分配||
|N13|conservative_repair_pending_final_review_six_business_oracles_open|/root/repair_chemo||
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
|rescue-remaining:RR-D01|read_only_minimal_design|/root/repair_iml01||
|rescue-remaining:RR-D02|read_only_minimal_design|/root/repair_iml01||
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
|PRIV-003|privacy_design_required_before_real_validation|/root/repair_privacy_closure||
|PRIV-004|integrated_engineering_closed|/root/repair_privacy_closure||
|PRIV-005|integrated_engineering_closed|/root/repair_privacy_closure||
|rescue-remaining:RR-PUB01|queued_shared_module|待分配|imaging-laboratory:IML-02|
|rescue-remaining:RR-SCOPE01|queued_test_expectation_reconciliation|待分配||
