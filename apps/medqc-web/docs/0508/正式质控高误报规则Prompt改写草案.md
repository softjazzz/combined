# 正式质控高误报规则 Prompt 改写草案

## 目的

本文只定义规则 prompt 口径，不直接改正式链路代码。后续由 CLI 按本文把规则 prompt / adjudicator prompt / 二审 gate 文案写入对应脚本或规则配置。

当前问题不是执行链路，而是部分质控点提示词过泛，LLM 容易把“写得简单”“片段不足”误判为 confirmed defect。改写目标是让 LLM 明确：

- 哪份文书、哪个段落是规则检查范围。
- 什么证据足以 confirmed。
- 什么情况必须 rejected。
- 什么情况只能 data_quality_gap。
- 哪些口径需要客户确认，不得直接 confirmed。

本文第一批覆盖：

- `SC-012` 入院前检查治疗经过欠缺
- `SC-013` 既往史记录不全
- `SC-034` 病程中对治疗措施、药物、医嘱变化未记录或分析
- `SC-118` 出院记录缺项或内容错误
- `SC-121` 诊疗经过不全面、不详细
- `SC-122` 无出院医嘱或出院医嘱不全
- `SC-123` 出院带药不详细

## 通用输出约束

所有规则都应要求模型按以下三层判断，不允许只按规则名称自由发挥：

1. **适用范围判断**：当前证据是否来自本规则对应文书和段落。
2. **缺陷成立判断**：是否同时满足 confirmed 条件。
3. **证据充分性判断**：证据不足时输出 `data_quality_gap`，不输出 confirmed。

推荐统一输出字段：

```json
{
  "rule_id": "SC-xxx",
  "decision": "confirmed_defect | rejected_by_system | data_quality_gap",
  "reason": "一句话说明裁决依据",
  "required_document": "入院记录/出院记录/病程记录等",
  "required_section": "现病史/既往史/诊疗经过/出院医嘱等",
  "field_matrix": {},
  "supporting_quote": "能支撑裁决的原文",
  "missing_fields": [],
  "policy_pending_flags": []
}
```

通用禁止项：

- 不得只凭“文书头、患者姓名、性别、年龄、记录时间” confirmed。
- 不得只凭规则名称中的“记录不全/不详细/描述不清”扩大解释。
- 不得把证据片段不足当作医生病历缺陷；证据不足应为 `data_quality_gap`。
- 不得把后续病程/出院记录内容用于抵消入院记录自身缺项；规则对应哪份文书，就优先只核查那份文书。

---

## SC-012 入院前检查治疗经过欠缺

### 规则定位

- 对应文书：`admission_record` 入院记录。
- 对应段落：现病史，尤其是“发病后到入院前”的院内/院外检查、治疗经过和效果。
- 不应跨出院记录、病程记录寻找补充来抵消入院记录缺陷。

### 字段矩阵

```json
{
  "source_is_admission_record": true,
  "source_section_is_present_illness": true,
  "onset_course_present": true,
  "preadmission_visit_present": true,
  "preadmission_exam_present": true,
  "preadmission_treatment_present": true,
  "treatment_effect_present": true
}
```

### Confirmed 条件

只有同时满足以下条件，才能 confirmed：

1. 证据明确来自入院记录的现病史。
2. 文中明确存在入院前就诊/检查/治疗线索。
3. 现病史未记录检查项目、治疗措施、用药细节或治疗效果中的关键内容。
4. 原文支持缺陷，例如：
   - “外院治疗具体不详”
   - “输液治疗，具体不详”
   - “曾在外院治疗”，但未写检查、治疗措施和效果。

### 不得 Confirmed

- 证据不是入院记录现病史。
- 只有一句孤立片段，无法确认所在段落。
- 患者入院前明确未就诊、未治疗，且病程短、无需院前诊疗细节。
- 只是没有写得非常详细，但已说明检查、治疗和效果的核心事实。

### Data Gap 条件

- 缺完整现病史上下文。
- 只看到截断片段，无法判断是否在后文补充。
- 无法确认患者是否有入院前检查/治疗。

### Prompt 草案

```text
你只评估 SC-012：入院记录现病史中，发病后到入院前接受检查与治疗的详细经过及效果是否欠缺。

检查范围仅限入院记录的现病史，不要用出院记录、病程记录或其他后续文书来替代入院记录现病史。

请先判断证据是否来自入院记录现病史。若不能确认来源或段落，输出 data_quality_gap。

confirmed_defect 必须同时满足：
1. 现病史提示患者入院前曾在院外/门诊/其他医疗机构检查或治疗；
2. 现病史未记录检查项目、治疗措施/用药、治疗效果中的关键内容；
3. 有原文可引用，例如“外院输液治疗，具体不详”。

不得 confirmed：
- 患者入院前明确未诊治；
- 已记录主要检查、治疗和效果，只是语言简略；
- 证据不是入院记录现病史；
- 只有截断短句，无法确认完整上下文。

请输出 decision、reason、field_matrix、supporting_quote、missing_fields。
```

---

## SC-013 既往史记录不全

### 规则定位

- 对应文书：`admission_record` 入院记录。
- 对应段落：既往史。

### 字段矩阵

```json
{
  "source_is_admission_record": true,
  "source_section_is_past_history": true,
  "prior_disease_history_present": true,
  "infectious_disease_history_present": true,
  "surgery_trauma_history_present": true,
  "transfusion_history_present": true,
  "allergy_history_present": true,
  "vaccination_history_present": true
}
```

### Confirmed 条件

必须看到完整或足够完整的既往史段落，并能明确指出规定字段缺失或明显矛盾。

可 confirmed 的例子：

- 既往史段落完全未记录过敏史、输血史等必填项。
- 文中前后矛盾，如某处写有输血史，既往史写否认输血史。

### 不得 Confirmed

- 仅凭单句“不详预防接种史”不得直接 confirmed。
- 成人病历中“预防接种史不详”属于客户口径敏感项，当前应标记 `policy_pending_vaccination_unknown`。
- 只看到既往史片段，无法确认其他字段是否在同段落中已记录。

### Data Gap / Policy Pending

- 预防接种史“不详”且客户未确认必须明确记录。
- 缺完整既往史段落。
- 只能看到片段，不能判断字段完整性。

### Prompt 草案

```text
你只评估 SC-013：入院记录既往史是否完整记录既往疾病史、传染病史、手术外伤史、输血史、过敏史、预防接种史等。

confirmed_defect 必须基于入院记录既往史完整段落或结构化字段矩阵。请逐项检查字段。

不得只凭“不详预防接种史”直接 confirmed。该项属于客户口径敏感项；在客户未确认前，输出 data_quality_gap，并标记 policy_pending_vaccination_unknown。

若既往史段落已覆盖主要字段，即使部分表达简略，也不得 confirmed。

请输出 field_matrix，明确 missing_fields。没有 missing_fields 时不得 confirmed。
```

---

## SC-034 病程中对治疗措施、药物、医嘱变化未记录或分析

### 规则定位

- 对应文书：日常病程、上级医师查房、医嘱/治疗变化记录。
- 规则关注的是“治疗措施、药物或医嘱发生变化后，病程中是否记录原因、依据、效果或后续计划”。

### 链路矩阵

```json
{
  "trigger_event_present": true,
  "trigger_event_quote": "",
  "order_or_treatment_change_present": true,
  "order_or_treatment_change_quote": "",
  "course_context_present": true,
  "course_analysis_present": true,
  "course_analysis_quote": "",
  "treatment_effect_or_followup_present": true
}
```

### Confirmed 条件

必须同时满足：

1. 有明确触发事件，例如病情变化、异常指标、治疗效果不佳。
2. 有明确医嘱/药物/治疗措施变化，例如新开、停用、调整剂量、改变治疗方案。
3. 对应病程缺少变化原因、依据、效果评估或后续计划。
4. 证据包含医嘱变化 quote 和病程上下文 quote。

### 不得 Confirmed

- 只有“症状 + 对症处理”，如“术后呕吐，予胃复安止吐”，不能 confirmed。
- 只有治疗措施存在，但没有证明“变化”。
- 病程已记录处理措施和观察计划。
- 缺医嘱来源或病程上下文。

### Prompt 草案

```text
你只评估 SC-034：病程中是否对治疗措施、药物、医嘱变化进行记录或分析。

confirmed_defect 必须形成完整链路：
1. 触发事件；
2. 明确医嘱/药物/治疗措施变化；
3. 病程缺少变化原因、依据、效果或后续计划。

只有“患者出现某症状，予以某药对症处理”不能 confirmed，因为这可能已经是合理记录。

若缺医嘱变化 quote 或病程上下文 quote，输出 data_quality_gap。

请输出 trigger_event_quote、order_or_treatment_change_quote、course_analysis_quote、missing_fields。
```

---

## SC-118 出院记录缺项或内容错误

### 规则定位

- 对应文书：`discharge_record` 出院记录。
- 关注出院记录核心字段是否完整。

### 字段矩阵

```json
{
  "source_is_discharge_record": true,
  "full_discharge_record_context_present": true,
  "admission_date_present": true,
  "discharge_date_present": true,
  "admission_condition_present": true,
  "admission_diagnosis_present": true,
  "treatment_course_present": true,
  "discharge_condition_present": true,
  "discharge_advice_present": true,
  "doctor_signature_present": true
}
```

### Confirmed 条件

必须看到完整出院记录或结构化字段矩阵，并明确指出具体缺哪一项。

### 不得 Confirmed

- 只有出院记录开头片段，如患者姓名、性别、年龄、主诉。
- 只笼统说“关键要素缺失”，但没有字段矩阵。
- 字段存在但表述简略。

### Prompt 草案

```text
你只评估 SC-118：出院记录是否缺少核心字段或内容错误。

必须基于完整出院记录或结构化字段矩阵判断。请逐项检查：入院日期、出院日期、入院情况、入院诊断、诊疗经过、出院情况、出院医嘱、医师签名。

confirmed_defect 必须明确列出 missing_fields，并引用完整出院记录上下文。

若只看到出院记录片段，输出 data_quality_gap。
不得只凭患者基本信息片段 confirmed。
```

---

## SC-121 诊疗经过不全面、不详细

### 规则定位

- 对应文书：`discharge_record` 出院记录。
- 对应段落：诊疗经过。

### 字段矩阵

```json
{
  "source_is_discharge_record": true,
  "source_section_is_treatment_course": true,
  "main_treatment_measures_present": true,
  "main_drug_names_or_treatment_plan_present": true,
  "important_auxiliary_exam_results_present": true,
  "treatment_response_or_outcome_present": true,
  "cross_document_contrast_present_when_claiming_missing_drug": true
}
```

### Confirmed 条件

必须看到完整诊疗经过段，并能证明缺失主要治疗、主要药品、重要检查结果或治疗转归。

如果判“无主要药品名称”，必须有医嘱、会诊建议或治疗方案对照，证明该药物/方案属于主要治疗而诊疗经过未记录。

### 不得 Confirmed

- 仅凭“护胃、补液”等短句 confirmed。
- 仅凭“描述不详细”的主观感受 confirmed。
- 缺完整诊疗经过段。
- 缺跨文书对照，却声称主要药品遗漏。

### Prompt 草案

```text
你只评估 SC-121：出院记录诊疗经过是否全面、详细。

confirmed_defect 必须基于完整诊疗经过段。若指出“主要药品名称缺失”，必须提供医嘱、会诊建议或治疗方案作为对照。

不得只因文字简略 confirmed。只有当主要诊断相关的关键治疗措施、主要药品、重要辅助检查结果或治疗转归确实缺失时，才可 confirmed。

若只有短句或缺跨文书对照，输出 data_quality_gap。
```

---

## SC-122 无出院医嘱或出院医嘱不全

### 规则定位

- 对应文书：`discharge_record` 出院记录。
- 对应段落：出院医嘱。

### 字段矩阵

```json
{
  "source_is_discharge_record": true,
  "source_is_full_discharge_advice_section": true,
  "discharge_advice_section_present": true,
  "medication_advice_present": true,
  "followup_advice_present": true,
  "diet_or_activity_advice_present": true,
  "warning_signs_or_return_visit_present": true
}
```

### Confirmed 条件

必须看到完整出院医嘱段，并能证明医嘱缺失或明显不全。

### 不得 Confirmed

- 只看到随访方式、随访周期、随访日期等局部片段。
- 只看到出院带药段，未看到完整出院医嘱段。
- 出院医嘱包含合理复查、饮食、活动、用药或注意事项时，不得 confirmed。

### Prompt 草案

```text
你只评估 SC-122：出院记录是否无出院医嘱或出院医嘱不全。

confirmed_defect 必须基于完整出院医嘱段。请判断该段是否包含用药、复诊、饮食活动、注意事项、病情变化返院等合理医嘱。

如果证据只有“随访方式/随访周期/日期”等局部片段，输出 data_quality_gap。

不得把局部随访字段当作完整出院医嘱缺失证据。
```

---

## SC-123 出院带药不详细

### 规则定位

- 对应文书：`discharge_record` 出院记录。
- 对应段落：出院带药 / 出院用药。

### 逐药品字段矩阵

```json
{
  "discharge_medication_section_present": true,
  "medication_items": [
    {
      "drug_name_present": true,
      "dose_present": true,
      "dose_unit_present": true,
      "route_present": true,
      "frequency_present": true,
      "duration_or_quantity_present": true
    }
  ]
}
```

### Confirmed 条件

必须先确认存在出院带药段或出院药品条目。随后逐药品判断是否缺药品名称、剂量、途径、频率或疗程/数量。

### Rejected 条件

- 无出院带药，且出院医嘱仅为饮食、休养、复查、换药等非药品事项。
- 出院带药字段基本完整，包括药名、剂量、用法/途径、频率。

### Data Gap 条件

- 证据不是完整出院带药段。
- 药品条目被截断，无法判断字段。
- 不确定是住院期间用药还是出院带药。

### Prompt 草案

```text
你只评估 SC-123：出院带药是否记录详细。

第一步先判断是否存在出院带药或出院用药段。若没有出院带药，不得判“出院带药不详细”，应 rejected_by_system。

第二步逐药品检查字段：药品名称、剂量、剂量单位、给药途径、频率、疗程或数量。

若药名、剂量、途径、频率等核心字段基本完整，应 rejected_by_system。

只有存在出院带药且核心字段确实缺失，才可 confirmed candidate。

若证据片段截断或无法确认是否为出院带药，输出 data_quality_gap。
```

---

## CLI 落地建议

建议 CLI 下一步不要一次改 84 条，而是按本文先落地这 7 条 prompt：

1. 找到正式 `sc_content_full_v1` 使用的规则 prompt / pack prompt / adjudicator prompt 注入位置。
2. 将本文每条规则转为机器可读配置，建议新增：
   - `rule_specific_prompt_overrides`
   - `rule_context_matrix_requirements`
   - `rule_confirmed_guardrail_requirements`
3. 用同一 random10 做 A/B，观察：
   - confirmed 数
   - keep 数
   - keep rate
   - data_quality_gap 是否合理增加
   - rejected_by_system 是否误驳回真实缺陷
4. 不以 confirmed 数越多越好，也不以 confirmed 被压到 0 为目标。

## 验收标准

第一阶段通过标准：

- provider / parse / timeout / technical 全为 0。
- SC-083 / SC-099 / SC-123 gate 不回退。
- 本文覆盖规则的 confirmed 必须带 `field_matrix` 或明确缺失字段。
- 对被驳回的 confirmed 抽样复核，不应有明显真实缺陷被压掉。
- keep rate 目标暂定 >= 70%，但同时 confirmed 不应被过度压缩。
