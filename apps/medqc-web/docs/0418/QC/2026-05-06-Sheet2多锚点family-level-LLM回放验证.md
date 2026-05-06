# Sheet2 多锚点 family-level LLM 回放验证

日期：2026-05-06

## 结论

- 本轮验证 6 条：真实调用 LLM 5 条，单 prompt 多 subitem 验证通过 4 条，失败 2 条。
- 5 条入院记录问题族走客户样本验证页同链路：`build_admission_issue_family_bundle` -> `build_admission_issue_family_prompt` -> LLM -> `normalize_admission_consistency_llm_output`。
- R0220 属 SC-069 会诊记录质量缺陷，当前客户样本验证页没有 family-level 多 subitem prompt；不能算“真实可跑”，需新增对应 family prompt 后再验。

## 逐条结果

| row_id       | 链路                         | LLM | overall_result | recommended_rule_ids               | sub_items | 结论                  |
| ------------ | ---------------------------- | --- | -------------- | ---------------------------------- | --------: | --------------------- |
| Sheet2-R0021 | admission_issue_family_level | yes | no_hit         | SC-009                             |         5 | pass                  |
| Sheet2-R0069 | admission_issue_family_level | yes | no_hit         | SC-020                             |         1 | fail                  |
| Sheet2-R0103 | admission_issue_family_level | yes | partial_hit    | SC-008,SC-010,SC-012,SC-018,SC-020 |         5 | pass                  |
| Sheet2-R0110 | admission_issue_family_level | yes | partial_hit    | SC-009,SC-011,SC-012,SC-010        |         5 | pass                  |
| Sheet2-R0210 | admission_issue_family_level | yes | partial_hit    | SC-018,SC-008,SC-010               |         3 | pass                  |
| Sheet2-R0220 | consultation_record_quality  | no  | not_run        | SC-069                             |         0 | fail_no_family_prompt |

## 子项摘要

### Sheet2-R0021

- `SC-009` `compliant`：现病史-咽痛性质/持续时间/缓解方式；人工问题与原文冲突。原文已明确记录疼痛性质为持续性，持续时间为10+天，缓解方式虽未提及但注明治疗效果欠佳，记录完整。
- `SC-009` `compliant`：现病史-咳痰性状/频率/伴随症状；人工问题与原文冲突。原文已详细记录痰液性状（白色粘痰）、频率特点（夜间更甚）及伴随症状（咽痒、异物感、无咳血/发热等）。
- `SC-009` `compliant`：现病史-院外治疗经过；人工问题与原文冲突。原文已记录治疗方式（输液），并客观标注具体药物及剂量不详，符合病历书写规范，非缺项。
- `SC-009` `compliant`：现病史-门诊检查项目及结果；人工问题与原文冲突。原文已明确记录门诊检查项目（间接喉镜）及初步诊断结果。
- `SC-009` `compliant`：现病史-一般情况/体重变化；人工问题与原文冲突。原文已明确记录体重无明显变化。

### Sheet2-R0069

- `SC-020` `compliant`：初步诊断完整性/准确性；当前初步诊断已完整覆盖患者本次急性发作的核心阳性证据（结石、积水、绞痛）。前列腺仅‘稍大’属常见伴随改变，尿检仅轻度白细胞升高且无尿路刺激征及明确感染指标，均不支持作为本次急性入院的主要诊断。人工问题所指漏诊缺乏临床依据，与病历实际情况冲突。

### Sheet2-R0103

- `SC-008` `non_compliant`：主诉规范性；主诉未完整反映主要症状及持续时间，不符合书写规范。
- `SC-012` `non_compliant`：诊治经过；现病史中门诊/院外诊治经过记录不全。
- `SC-010` `non_compliant`：既往史完整性；既往史缺失高血压确诊或发病时间，记录不规范。
- `SC-018` `compliant`：查体完整性/前后矛盾；人工问题指控与原文记录冲突，原文已完整描述右手截肢情况，该项实际合规。
- `SC-020` `compliant`：入院诊断完整性；人工问题指控与原文记录冲突，原文已包含右手截肢诊断，该项实际合规。

### Sheet2-R0110

- `SC-011` `non_compliant`：现病史阳性/阴性症状采集不全；现病史阴性症状采集确实不全面，未覆盖血液系统疾病核心鉴别点，符合SC-011缺陷特征。
- `SC-012` `compliant`：诊治经过记录；病历已清晰记录院外未治疗及院内输血史，人工问题称“无诊治经过”与原文直接冲突。
- `SC-009` `compliant`：现病史针对性描述；病历原文未涉及头痛症状，人工问题所指症状不存在，属无效指控/冲突。
- `SC-009` `compliant`：入院记录完整性；病历已记录门诊初步诊断，人工问题称“无门诊初步诊断”与原文冲突。
- `SC-010` `compliant`：既往史规范性；既往史书写条理清晰、分类规范，人工问题称“混乱无条理”与原文冲突。

### Sheet2-R0210

- `SC-008` `non_compliant`：主诉规范性；主诉未严格遵循“症状/体征+时间”的标准书写规范，建议规范为“左膝疼痛3月”。
- `SC-010` `non_compliant`：既往史完整性；既往史仅笼统提及“有慢病病史”，未规范记录慢病具体诊断、用药及控制情况；生命体征仅记录脉搏，未记录心率，存在记录不全/不一致。
- `SC-018` `compliant`：查体专科/前后矛盾；人工指出的“腹部手术史查体未做描述”与原文“腹部见长约3cm手术瘢痕”冲突；人工指出的“四肢检查记录为四肢关节活动正常”与原文“四肢检查：:见专科”冲突。原文查体记录完整且无前后矛盾，故该项判定为合规。

### Sheet2-R0220

- 客户样本验证页当前仅入院记录问题族具备 family-level 多 subitem prompt；SC-069 会诊记录质量没有同等 family prompt，不能证明真实可跑。
