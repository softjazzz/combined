# 0609收尾执行队列

问题级队列包含缺陷、业务争议和复验证据缺口，不等同确认缺陷数。文件锁以closure-ownership.json为准。

D01已于集成提交e256e8ea9关闭限定工程问题；不代表整条化疗规则验收通过。当前最多四路生产修复、一个重测试进程，独立复核后由主代理串行集成。

|问题|状态|负责人|依赖|
|---|---|---|---|
|N12|queued_evidence_review|待分配||
|N10|queued_evidence_review|待分配||
|N13|repairing|/root/repair_chemo||
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
|imaging-laboratory:IML-01|committed_independent_review|/root/repair_iml01||
|imaging-laboratory:IML-02|committed_independent_review|/root/repair_iml02||
|imaging-laboratory:IML-D01|business_basis_review_no_code_decision|待分配||
|imaging-laboratory:IML-D02|business_basis_review_no_code_decision|待分配||
|rescue-remaining:RR-D01|queued_evidence_review|待分配||
|rescue-remaining:RR-D02|queued_evidence_review|待分配||
|rescue-remaining:RR-M01|queued_evidence_review|待分配||
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
|PRIV-004|20_offline_passed_preparing_fixed_commit|/root/repair_privacy_closure||
|PRIV-005|committed_independent_review_pending|/root/repair_privacy_closure||
