# 0609收尾执行队列

问题级队列包括缺陷、争议、复验证据缺口及既有工程边界，不等同确认缺陷数，也不等同规则通过数。文件锁以closure-ownership.json为准。

已串行集成D01 e256e8ea9、IML02 a8ad74e69、PRIV005 1225aff95；IML01与N13独立复核发现回退，保持开放。

|问题|状态|负责人|依赖|
|---|---|---|---|
|N12|queued_evidence_review|待分配||
|N10|queued_evidence_review|待分配||
|N13|independent_review_blocked_same_drug_association_followup|/root/repair_chemo||
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
|discharge-death:DD-F01|queued_shared_module|待分配|imaging-laboratory:IML-02|
|discharge-death:DD-F02|queued_evidence_review|待分配||
|discharge-death:DD-F05|business_basis_review_no_code_decision|待分配||
|imaging-laboratory:IML-01|independent_review_blocked_followup_repair|/root/repair_iml01||
|imaging-laboratory:IML-02|integrated_engineering_closed|/root/repair_iml02||
|imaging-laboratory:IML-D01|business_basis_review_no_code_decision|待分配||
|imaging-laboratory:IML-D02|business_basis_review_no_code_decision|待分配||
|rescue-remaining:RR-D01|queued_evidence_review|待分配||
|rescue-remaining:RR-D02|queued_evidence_review|待分配||
|rescue-remaining:RR-M01|existing_model_contract_metadata_repair|/root/repair_iml02||
|treatment-consultation:TC-01|queued_evidence_review|待分配||
|treatment-consultation:TC-02|queued_shared_module|待分配|imaging-laboratory:IML-02|
|treatment-consultation:TC-03|queued_evidence_review|待分配||
|tumor-pathology:TP-D01|integrated_engineering_closed|/root/repair_chemo||
|tumor-pathology:TP-D02|design_before_semantic_changes|/root/repair_chemo||
|tumor-pathology:TP-D03|design_before_semantic_changes|/root/repair_chemo||
|tumor-pathology:TP-D04|queued_shared_module|待分配|imaging-laboratory:IML-02|
|tumor-pathology:TP-D05|queued_shared_module|待分配|imaging-laboratory:IML-02|
|PRIV-002|privacy_design_required_before_real_validation|/root/repair_privacy_closure||
|PRIV-003|privacy_design_required_before_real_validation|/root/repair_privacy_closure||
|PRIV-004|committed_independent_review_pending|/root/repair_privacy_closure||
|PRIV-005|integrated_engineering_closed|/root/repair_privacy_closure||
|rescue-remaining:RR-PUB01|queued_shared_module|待分配|imaging-laboratory:IML-02|
|rescue-remaining:RR-SCOPE01|queued_test_expectation_reconciliation|待分配||
