# 泸县0609真实样本Golden Set候选报告

- 来源文件：`D:/LLM/LX888/apps/medqc-web/docs/0602/luxian_0609_first_pass_review_sheet.csv`
- coverage 文件：`D:/LLM/LX888/apps/medqc-web/docs/0602/luxian_0609_candidate_coverage.json`
- 复核队列：`D:/LLM/LX888/apps/medqc-web/docs/0602/luxian_0609_golden_review_queue_merged.csv`
- 规则目录：`D:/LLM/LX888/apps/medqc-web/docs/0602/luxian_0609_formal_rule_catalog.json`
- 候选数量：28
- 人工状态：pending
- 系统状态：pending_system_run；需要后续在客户样本验证任务中回填系统结果。
- 边界：本报告只建立人工标注和系统对比框架，不声明真实样本准确率。

## 分层分布

- 时限: 3（真实候选 3）
- 查房/病重病危: 3（真实候选 3）
- 检查检验: 1（真实候选 0）
- 会诊: 4（真实候选 4）
- 手术麻醉: 7（真实候选 7）
- 输血: 1（真实候选 0）
- 肿瘤病理/化疗: 1（真实候选 0）
- 其他: 8

## 缺口

- 当前候选源未发现这些规则族的真实 visit_id：检查检验、输血、肿瘤病理/化疗。
- 这些规则族已在 CSV/JSON 中以 `sample_gap` 明确标注，不能用合成样本或 `其他` 替代真实准确率。

## 七族候选与缺口明细

### 时限

- 覆盖状态：`candidate_ready`
- 候选 visit_id：2328493、1915580、1966656
- 待人工标注规则：LX0609-006
- 数据来源：luxian_0609_candidate_coverage.json、luxian_0609_first_pass_review_sheet.csv
- 触发依据：4月8日，陈光怀副主任医师查房记录，内容却是郑凤金主治医师查房的相关处理。；已有部分候选，仍需补齐 negative、boundary 候选样本。；已有部分候选，仍需补齐 negative、boundary 候选样本。

### 查房/病重病危

- 覆盖状态：`candidate_ready`
- 候选 visit_id：1966729、2240022、2236769
- 待人工标注规则：LX0609-017
- 数据来源：luxian_0609_first_pass_review_sheet.csv
- 触发依据：两份病程记录相似度 0.99，疑似重复复制。；两份病程记录相似度 0.66，接近重复阈值。；病程记录最高相似度 0.23，未见明显重复。

### 检查检验

- 覆盖状态：`sample_gap`
- 候选 visit_id：sample_gap
- 待人工标注规则：LX0609-010、LX0609-011、LX0609-012、LX0609-014、LX0609-015
- 数据来源：luxian_0609_candidate_coverage.json;luxian_0609_formal_rule_catalog.json
- 缺失依据：LX0609-010: coverage=no_candidates, sample_visit_ids=0, 当前没有可复核候选，需先从样本池发现阳性、阴性和边界样本。；LX0609-011: coverage=no_candidates, sample_visit_ids=0, 当前没有可复核候选，需先从样本池发现阳性、阴性和边界样本。；LX0609-012: coverage=no_candidates, sample_visit_ids=0, 当前没有可复核候选，需先从样本池发现阳性、阴性和边界样本。；LX0609-014: coverage=no_candidates, sample_visit_ids=0, 当前没有可复核候选，需先从样本池发现阳性、阴性和边界样本。；LX0609-015: coverage=no_candidates, sample_visit_ids=0, 当前没有可复核候选，需先从样本池发现阳性、阴性和边界样本。；LX0609-010: 检查前窗口和未检查原因需规则化；LX0609-011: 报告时间到病程记录窗口未接入规则包；LX0609-012: 阳性结果识别和分析充分性需语义判断；LX0609-014: 培养项目识别和24小时窗口未稳定接入；LX0609-015: 阳性菌识别和分析充分性需语义判断

### 会诊

- 覆盖状态：`candidate_ready`
- 候选 visit_id：1872902、1915580、2207195、2312534
- 待人工标注规则：LX0609-021、LX0609-022
- 数据来源：luxian_0609_first_pass_review_sheet.csv
- 触发依据：会诊申请/记录存在泛化表述，未见明确会诊目的或理由。；会诊申请段可见明确目的、理由或需要协助解决的问题。；会诊记录存在但目的字段不清晰，需要人工判断是否明确。

### 手术麻醉

- 覆盖状态：`candidate_ready`
- 候选 visit_id：2270715、2305896、2291788、1919190、1967916、1931889、2328501
- 待人工标注规则：LX0609-018、LX0609-029、LX0609-031、LX0609-032、LX0609-033、LX0609-040
- 数据来源：luxian_0609_first_pass_review_sheet.csv
- 触发依据：既往史中有直肠癌手术病史，但入院诊断无相关诊断；术前小结、术前讨论新建后未书写；手术记录病历记录时间早于手术结束时间涉嫌伪造病历

### 输血

- 覆盖状态：`sample_gap`
- 候选 visit_id：sample_gap
- 待人工标注规则：LX0609-041、LX0609-042、LX0609-043、LX0609-044、LX0609-045、LX0609-046、LX0609-047、LX0609-049
- 数据来源：luxian_0609_candidate_coverage.json;luxian_0609_formal_rule_catalog.json
- 缺失依据：LX0609-041: coverage=no_candidates, sample_visit_ids=0, 当前没有可复核候选，需先从样本池发现阳性、阴性和边界样本。；LX0609-042: coverage=no_candidates, sample_visit_ids=0, 当前没有可复核候选，需先从样本池发现阳性、阴性和边界样本。；LX0609-043: coverage=no_candidates, sample_visit_ids=0, 当前没有可复核候选，需先从样本池发现阳性、阴性和边界样本。；LX0609-044: coverage=no_candidates, sample_visit_ids=0, 当前没有可复核候选，需先从样本池发现阳性、阴性和边界样本。；LX0609-045: coverage=no_candidates, sample_visit_ids=0, 当前没有可复核候选，需先从样本池发现阳性、阴性和边界样本。；LX0609-046: coverage=no_candidates, sample_visit_ids=0, 当前没有可复核候选，需先从样本池发现阳性、阴性和边界样本。；LX0609-047: coverage=no_candidates, sample_visit_ids=0, 当前没有可复核候选，需先从样本池发现阳性、阴性和边界样本。；LX0609-049: coverage=no_candidates, sample_visit_ids=0, 当前没有可复核候选，需先从样本池发现阳性、阴性和边界样本。；LX0609-041: 输血触发源需统一；LX0609-042: 同意书结构字段可能只在全文中；LX0609-043: 输血前必要检验项目清单需定义；LX0609-044: 评估记录字段和适应证判定需稳定；LX0609-045: 输血发生时间和病程记录窗口需统一；LX0609-046: 完整性字段清单需固化；LX0609-047: 输血后评价时间窗口需定义；LX0609-049: 费用明细与医嘱项目映射未完成

### 肿瘤病理/化疗

- 覆盖状态：`sample_gap`
- 候选 visit_id：sample_gap
- 待人工标注规则：LX0609-013、LX0609-019、LX0609-027
- 数据来源：luxian_0609_candidate_coverage.json;luxian_0609_formal_rule_catalog.json
- 缺失依据：LX0609-013: coverage=no_candidates, sample_visit_ids=0, 当前没有可复核候选，需先从样本池发现阳性、阴性和边界样本。；LX0609-019: coverage=no_candidates, sample_visit_ids=0, 当前没有可复核候选，需先从样本池发现阳性、阴性和边界样本。；LX0609-027: coverage=no_candidates, sample_visit_ids=0, 当前没有可复核候选，需先从样本池发现阳性、阴性和边界样本。；LX0609-013: 病理报告结构化字段需确认覆盖率；LX0609-019: 取材关键词和病理报告关联需稳定；LX0609-027: 需肿瘤患者触发和治疗计划语义判定

## 待办

1. 质控员逐行填写 `human_status`、`evidence_ok`、`error_type`。
2. 运行系统质控后回填 `system_status` 和 `system_evidence_summary`。
3. 只有完成对比后，才能计算真实样本准确率。
