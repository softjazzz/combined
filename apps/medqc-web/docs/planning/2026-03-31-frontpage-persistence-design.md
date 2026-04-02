# 首页生成结果持久化设计

## 目标

补齐 `workstation v4` 首页生成链路的持久化能力，覆盖 3 类数据：

1. 首页抽取草稿
2. 正式首页结构化结果
3. 主诊断判断与证据页判断的审计信息

目标不是替换现有 `mr/diagnosis/mr_surgery/mr_cost`，而是在现有正式结构化表之外，补一层“抽取审计 + 证据留痕”。

## 当前现状

当前仓库已经有两段能力，但中间缺审计层：

- 草稿保存
  - `POST /api/medical-records/ai-frontpage-draft`
  - 表：`cdm.ai_frontpage_draft`
- 正式首页保存
  - `PUT /api/medical-records/frontpage`
  - 表：`cdm.mr`

当前缺失点：

- `diagnoses/procedures/evidence` 没有完整、稳定的 PG 审计落点
- 主诊断最终为什么这么判，没有单独结构化留痕
- 证据页/证据片段从哪里来、是否验证通过，没有单独结构化留痕

## 设计原则

- `ai_frontpage_draft` 继续保存“抽取全文 JSON”
- `mr/diagnosis/mr_surgery/mr_cost` 继续保存“最终确认后的业务结构化结果”
- 新增一张审计主表，专门保存“主诊断与证据判断过程”
- 不强行把所有 evidence 拆散到十几张表，第一版先一主表 + 若干 JSON 字段
- 前端显式区分“保存草稿”和“确认写回正式首页”

## 新增表

建议新增：

- `cdm.frontpage_extraction_audit`

用途：

- 记录一次首页抽取/补全/人工确认的审计快照
- 把主诊断候选、主要诊断判定依据、证据页判断、来源文书、规则轨迹保存下来
- 给后续复核、追责、回放、模型调参使用

## 建议字段

### 主键与关联

- `id`
- `institute_id`
- `patient_id`
- `visit_id`
- `draft_id`
  - 关联 `ai_frontpage_draft.id`，可空
- `frontpage_version`
  - 版本号，便于多次生成/多次确认
- `status`
  - `draft` / `confirmed` / `superseded`

### 主诊断判断

- `main_diagnosis_text`
- `main_diagnosis_code`
- `main_diagnosis_source`
  - `llm` / `guideline_rule` / `clinician` / `manual_override`
- `main_diagnosis_confidence`
- `main_diagnosis_candidates_json`
  - 候选诊断及分值
- `guideline_rule_trace_json`
  - 主诊断规则轨迹
- `clinician_main_diagnosis_json`
  - 临床主诊断原始判断
- `coding_audit_llm_json`
  - LLM 编码审核说明

### 证据判断

- `evidence_json`
  - 证据总包，保留原始结构
- `evidence_verified`
  - 整体证据是否通过校验
- `evidence_summary`
  - 人类可读摘要
- `evidence_source_documents_json`
  - 命中的文书列表、页签、标题、文书类型
- `evidence_spans_json`
  - 证据片段与命中位置
- `evidence_page_judgement_json`
  - 证据页判断结果，包含“命中文书/页签/是否可信/原因”

### 结构化快照

- `diagnoses_json`
- `procedures_json`
- `basic_info_json`
- `hospitalization_json`
- `costs_json`

### 操作信息

- `generated_by`
- `confirmed_by`
- `created_at`
- `updated_at`

## 与现有表的关系

### `cdm.ai_frontpage_draft`

继续保存：

- 全量草稿 JSON
- 用于恢复编辑态

不负责：

- 审计解释
- 证据版本管理
- 主诊断候选留痕

### `cdm.mr`

继续保存：

- 最终首页主数据

不负责：

- 候选诊断
- 证据片段
- LLM 推理过程

### `cdm.diagnosis`

在“确认保存正式首页”时同步写入：

- 主诊断
- 其他诊断
- 诊断编码

这里存的是“最终确认结果”，不是推理过程。

## 后端改造点

### 1. 草稿保存接口扩展

现有：

- `POST /api/medical-records/ai-frontpage-draft`

建议扩展请求体，除 `draft_json` 外支持：

- `evidence_json`
- `main_diagnosis_candidates_json`
- `guideline_rule_trace_json`

第一版也可以不改原接口，只新增：

- `POST /api/medical-records/frontpage-audit`

用于保存审计快照。

### 2. 正式首页保存接口扩展

现有：

- `PUT /api/medical-records/frontpage`

建议拆成两步语义：

- `PUT /api/medical-records/frontpage`
  - 只写 `mr`
- `POST /api/medical-records/frontpage/confirm`
  - 写 `mr`
  - 写 `diagnosis`
  - 写 `mr_surgery`
  - 写 `mr_cost`
  - 写 `frontpage_extraction_audit`
  - 回写 `status=confirmed`

如果不想加新接口，至少要让现有 `save_frontpage` 在提交正式首页时同时接收：

- `diagnoses`
- `procedures`
- `evidence`
- `audit_meta`

并把这些同步写入审计表。

### 3. 新增审计读取接口

建议新增：

- `GET /api/medical-records/frontpage-audit/{visit_id}`

用于：

- 前端“查看主诊断判断依据”
- 前端“查看证据页判断”
- 测试与排障

## 前端保存链路

### 1. 生成草稿

用户点击“生成首页”后：

- 调抽取接口
- 返回 `draft + diagnoses + procedures + evidence`
- 前端本地展示
- 同时调用 `POST /api/medical-records/ai-frontpage-draft`

保存内容：

- `draft_json`
- `patient_id`
- `visit_id`

### 2. 草稿编辑

用户修改主诊断、编码、费用等字段时：

- 仅更新前端状态
- 点击“保存草稿”时再次保存 `ai_frontpage_draft`

### 3. 查看判断依据

前端在“主诊断”区域提供：

- “查看判断依据”
- “查看证据页”

数据优先来自：

- `frontpage_extraction_audit`

如果尚未确认正式首页，则回退到：

- 当前草稿中的 `evidence`

### 4. 确认保存正式首页

点击“确认保存”时：

- 写正式首页主数据
- 写诊断/手术/费用明细
- 写审计快照

确认后页面应能看到：

- 最终主诊断
- 最终主诊断编码
- 审计版本号
- 证据判断摘要

## 推荐落地顺序

### Phase 1

- 新增 `frontpage_extraction_audit`
- 补后端 service + router
- 把草稿保存和正式确认保存分开

### Phase 2

- 正式首页确认时同步写 `diagnosis`
- 审计读取接口落地
- 前端“查看依据/证据页”联通

### Phase 3

- 增加版本比对
- 增加人工 override 审计
- 增加 evidence span 高亮回放

## 验收标准

### 数据库

- 生成草稿后 `ai_frontpage_draft` 有记录
- 确认保存后 `frontpage_extraction_audit` 有记录
- 确认保存后 `mr/diagnosis/mr_surgery/mr_cost` 与页面一致

### 接口

- 能读回草稿
- 能读回审计快照
- 能区分 `draft` 与 `confirmed`

### 前端

- 可查看主诊断判断依据
- 可查看证据页判断
- 修改后再次确认能生成新版本

## 不建议的做法

- 只把 `evidence` 塞进 `mr.metadata`
- 只保存草稿，不保存确认时的审计快照
- 直接覆盖诊断，不保留主诊断判断来源

这样做后面会出现两个问题：

- 无法解释“为什么最后选这个主诊断”
- 无法验证“证据页判断是否可信”

## 结论

最小闭环应该是：

- `ai_frontpage_draft`
- `frontpage_extraction_audit`
- `mr/diagnosis/mr_surgery/mr_cost`

三层并存，各司其职：

- 草稿层：恢复编辑
- 审计层：解释判断
- 正式层：业务结果
