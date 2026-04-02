# AI 首页历史快照设计

日期：2026-03-31
范围：Workstation V4 病案首页 AI 生成结果长期保存与历史回看

## 1. 目标

目标不是字段核对，而是支持以下业务效果：

- 打开某一个历史病案
- 直接看到当时 AI 生成的首页是什么样
- 不覆盖原始 CDM 表
- 可以和原始 `mr` 做人工对照

因此，`frontpage_extracted_fields` 不能作为主读取模型，它更适合测试、审计、排障。
真正的长期读取模型应当是“按 CDM 首页结构对齐的 AI 快照附表”。

## 2. 结论

建议新增 4 张“AI 首页快照表组”成员表，而不是只新增 1 张：

1. `cdm.ai_mr_snapshot`
2. `cdm.ai_diagnosis_snapshot`
3. `cdm.ai_mr_surgery_snapshot`
4. `cdm.ai_mr_cost_snapshot`

原因：

- `mr` 只覆盖首页主表字段
- 首页页面实际还要展示诊断、手术、费用
- 如果只做 `ai_mr_snapshot`，前端仍然无法完整回显整页 AI 首页
- 拆成 4 张后，可以和现有 `mr / diagnosis / mr_surgery / mr_cost` 一一对照

## 3. 边界

### 3.1 原始 CDM 表保持只读

以下表继续保持只读，不允许前端或 AI 保存动作回写：

- `cdm.mr`
- `cdm.diagnosis`
- `cdm.mr_surgery`
- `cdm.mr_cost`

### 3.2 AI 结果写入系统附表

AI 生成结果写入：

- `cdm.ai_frontpage_draft`
  - 仅短期缓存，当前保留 1 天
- `cdm.frontpage_extraction_audit`
  - 主诊断、证据页判断、规则轨迹
- `cdm.frontpage_extracted_fields`
  - 字段级明细，便于测试与排障
- AI 首页快照表组
  - `cdm.ai_mr_snapshot`
  - `cdm.ai_diagnosis_snapshot`
  - `cdm.ai_mr_surgery_snapshot`
  - `cdm.ai_mr_cost_snapshot`
  - 长期可读的“AI 首页结构化快照”

## 4. 推荐表设计

### 4.1 `cdm.ai_mr_snapshot`

设计原则：尽量与 `cdm.mr` 对齐，但保留 AI 版本管理字段。

建议字段：

- 业务主键：`id`
- 关联键：`institute_id`、`patient_id`、`visit_id`
- 版本键：`snapshot_version`
- 状态：`status`
  - `generated`
  - `confirmed`
  - `superseded`
- 生成信息：`generated_at`、`generated_by`
- 确认信息：`confirmed_at`、`confirmed_by`
- 来源字段：`draft_id`、`audit_id`
- 首页主表字段：尽量对齐 `mr`

优先对齐字段：

- 机构信息：`institute_code`、`institute_county_desc`
- 身份信息：`visit_cnt`、`id_card_no`、`birthday`、`nationality`、`ethnicity`、`marital_status`、`occupation_category`
- 联系与地址：`nativeplace`、`currentaddress`、`contact_name`、`contact_relationship`、`contact_address`、`contact_telephone`、`work_unit`
- 住院信息：`medical_payment_method`、`admission_route`、`admission_datetime`、`admission_dept_name`、`admission_ward_name`、`transfer_dept_name`、`discharge_datetime`、`discharge_dept_name`、`discharge_ward_name`、`hospital_duration`
- 临床与签名辅助：`pathology_id`、`allergy_sign`、`abo_blood_code`、`rh_blood_code`、`medicalrecord_quality`、`leaving_hospital_way`
- 其它：`record_content` 可选，不建议首期必做

唯一约束建议：

- `visit_id + snapshot_version` 唯一

### 4.2 `cdm.ai_diagnosis_snapshot`

一行一诊断，结构对齐 `diagnosis`。

建议字段：

- `id`
- `snapshot_id`
- `institute_id`
- `patient_id`
- `visit_id`
- `seq_no`
- `diagnosis_type`
- `diagnosis_name`
- `diagnosis_code`
- `admission_condition`
- `is_main`
- `created_at`
- `updated_at`

作用：

- 支撑主诊断与其他诊断完整回显
- 支撑和原始 `diagnosis` 做差异对比

### 4.3 `cdm.ai_mr_surgery_snapshot`

一行一手术，结构对齐 `mr_surgery`。

建议字段：

- `id`
- `snapshot_id`
- `institute_id`
- `patient_id`
- `visit_id`
- `seq_no`
- `surgery_name`
- `surgery_code`
- `surgery_begin_datetime`
- `surgical_level`
- `surgeon`
- `first_assistant`
- `second_assistant`
- `anesthesia_method`
- `anesthesiologist`
- `surgical_incisionheal_level`
- `is_main`
- `created_at`
- `updated_at`

### 4.4 `cdm.ai_mr_cost_snapshot`

一条首页一条费用快照，结构对齐 `mr_cost` 常用口径。

建议字段：

- `id`
- `snapshot_id`
- `institute_id`
- `patient_id`
- `visit_id`
- `total_cost`
- `self_pay`
- `created_at`
- `updated_at`

## 5. 与现有表的关系

### 5.1 读取优先级

前端打开历史病案时建议按以下优先级读取：

1. AI 首页快照表组
   - 如果存在，优先展示“AI 首页历史快照”
2. `ai_frontpage_draft`
   - 仅在 1 天缓存窗口内可用于恢复最近草稿
3. `mr / diagnosis / mr_surgery / mr_cost`
   - 作为原始系统首页展示源

### 5.2 各表职责

- `ai_frontpage_draft`
  - 短期缓存
- `frontpage_extraction_audit`
  - 主诊断和证据判断留痕
- `frontpage_extracted_fields`
  - 字段级明细核查
- AI 首页快照表组
  - 长期历史回看与页面回显

## 6. 保存链路建议

### 6.1 生成后保存草稿

点击“保存草稿与审计”时：

1. 保存 `ai_frontpage_draft`
2. 保存 `frontpage_extraction_audit`
3. 保存 `frontpage_extracted_fields`
4. upsert `ai_mr_snapshot`
5. upsert `ai_diagnosis_snapshot`
6. upsert `ai_mr_surgery_snapshot`
7. upsert `ai_mr_cost_snapshot`

### 6.2 状态规则

- 初次保存：`status = generated`
- 人工确认：`status = confirmed`
- 再次重生成并覆盖旧结果：旧版本置 `superseded`，新版本为 `generated` 或 `confirmed`

如果你们近期不做多版本，首期也可以先简化成：

- 一个 `visit_id` 只保留一套最新快照
- `snapshot_version = v1`
- 每次保存都 upsert 覆盖

## 7. 前端读取建议

Workstation V4 首页标签读取逻辑建议增加：

1. 先请求 `GET /api/medical-records/ai-frontpage-snapshot/{visit_id}`
2. 如果有结果，直接组装成当前 `FrontpageSheet` / `FrontpageWorkspacePanel` 需要的数据结构
3. 如果没有，再回退：
   - 读 `ai_frontpage_draft`
   - 再回退到 `frontpage-sheet` 读取原始 CDM 首页

这样可以满足“历史病案看 AI 首页样式”的需求，同时不影响当前正式首页逻辑。

## 8. 为什么不只保留 `frontpage_extracted_fields`

因为它解决的是：

- 这个字段有没有抽出来
- 抽出来的值是什么

但它不能很好解决：

- 这一整页 AI 首页当时长什么样
- 前端如何最低成本回显历史 AI 首页
- 如何和 `mr` 结构直观对比

所以 `frontpage_extracted_fields` 应保留，但它是辅助表，不是主展示表。

## 9. 首期最小实现建议

如果只做第一期，建议按下面顺序：

1. 新增 `ai_mr_snapshot`
2. 新增 `ai_diagnosis_snapshot`
3. 新增 `ai_mr_surgery_snapshot`
4. 新增 `ai_mr_cost_snapshot`
5. 后端新增一个聚合读取接口：`GET /api/medical-records/ai-frontpage-snapshot/{visit_id}`
6. 前端历史病案页优先读取该接口

这样就能先满足最核心目标：

- 历史病案可回看 AI 首页样式

## 10. 最终建议

你的判断是对的：

- 不应只依赖 `draft_json`
- 也不能只依赖字段级明细表
- 最合适的是新增一套“按 `mr` 及其关联表结构对齐”的 AI 快照附表

一句话结论：

- `mr` 继续只读
- AI 首页快照表组承担 AI 首页长期回显
- `frontpage_extraction_audit` 承担主诊断与证据审计
- `frontpage_extracted_fields` 承担字段级核查
