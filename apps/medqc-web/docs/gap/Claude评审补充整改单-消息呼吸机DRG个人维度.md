# Claude评审补充整改单：消息、呼吸机字段、DRG个人维度

## Summary

本整改单用于修正对 `workstation v4` 的 3 条评审表述，避免把“未完全实现”误写成“完全缺失”，同时保留真正应整改的内容。

涉及条目：

- `4.1.2` 当日质控批量消息推送
- 呼吸机使用时间字段
- DRG 五级评价第 5 级“个人”维度

---

## 1. 4.1.2 消息推送

### 现状

- 已有消息框架、通知表、通知列表与概览接口。
- 单病历、单 workflow 的聚合消息已实现。
- 工作台也已能读取最新通知状态。

### 真实结论

缺的不是“消息能力”，而是“当日质控批量汇总推送”能力。

### 建议改写

`消息基础能力已存在，但缺少“当日质控结果 -> 批量汇总消息推送”能力。`

### 代码依据

- [notifications.py](d:/LLM/lx0222/health-qc-monorepo/apps/medqc-web/backend/app/routers/notifications.py)
- [qc_persistence_service.py](d:/LLM/lx0222/health-qc-monorepo/apps/medqc-web/backend/app/services/qc_persistence_service.py)
- [worklist_service.py](d:/LLM/lx0222/health-qc-monorepo/apps/medqc-web/backend/app/services/workstation/worklist_service.py)

### 修复建议

- 新增“批量执行汇总消息”生成逻辑。
- 汇总维度至少包含：
  - 日期
  - workflow
  - 执行数
  - 成功数
  - 失败数
  - 高风险数
- 与当前单病历聚合消息并存，不替代现有 `notifications` 机制。

### 优先级

`P0`

---

## 2. 呼吸机使用时间字段

### 现状

- schema 中已有 `ventilation_hours` 字段。
- 抽取 prompt 中已明确要求输出该字段。
- 结算组装服务已将该字段映射到 `ventilator_usetime`。
- CDM 字段已存在数据库模型定义。

### 真实结论

不是“完全缺失”。

真实问题是：该字段虽然已进入抽取与映射链路，但缺少更强的规则兜底和专项验证，字段可靠性不足。

### 建议改写

`呼吸机使用时间字段已纳入抽取与映射链路，但缺少规则兜底和专项验证。`

### 代码依据

- [frontpage.py](d:/LLM/lx0222/health-qc-monorepo/apps/medqc-web/backend/app/schemas/frontpage.py)
- [frontpage_extraction_service.py](d:/LLM/lx0222/health-qc-monorepo/apps/medqc-web/backend/app/services/frontpage_extraction_service.py)
- [settlement_assembly_service.py](d:/LLM/lx0222/health-qc-monorepo/apps/medqc-web/backend/app/services/settlement_assembly_service.py)
- [cdm.py](d:/LLM/lx0222/health-qc-monorepo/apps/medqc-web/backend/app/database/models/cdm.py)

### 修复建议

- 增加专项测试样本，覆盖：
  - 无创呼吸机
  - 有创机械通气
  - ICU 转入转出
- 增加抽取后校验规则：
  - 病历存在“机械通气/呼吸机辅助通气”证据但字段为空时标红
  - 通气时长格式异常时进入人工复核
- 在首页抽取结果和结算组装结果之间增加一致性校验。

### 优先级

`P1`

---

## 3. DRG 五级评价第 5 级“个人”维度

### 现状

- 类型定义中已有 `person`。
- demo 分析页中已有“个人”维度展示。
- 但不同位置仍存在 `person / doctor / chief_group` 等命名混用。

### 真实结论

不是“代码里没有”。

真实问题是：第 5 级“个人”维度已部分实现，但正式口径仍存在命名混用，以及 demo/正式链路未完全统一。

### 建议改写

`DRG 五级评价第5级“个人”维度已部分实现，但正式口径仍存在命名混用与 demo/正式未统一的问题。`

### 代码依据

- [drg-analysis.ts](d:/LLM/lx0222/health-qc-monorepo/apps/medqc-web/src/types/drg-analysis.ts)
- [PostEventAnalysisView.vue](d:/LLM/lx0222/health-qc-monorepo/apps/medqc-web/src/views/demo/frontpage/components/PostEventAnalysisView.vue)

### 修复建议

- 统一枚举与命名口径，明确正式标准：
  - 推荐统一为 `person`
- 收口以下链路：
  - 前端类型
  - 图表维度映射
  - 后端分析数据结构
  - 导出文案
- 在正式页中补齐“个人”维度的真实数据来源与排序逻辑，不再只停留在 demo 视图。

### 优先级

`P1`

---

## 建议对外结论

### 保留为 P0

- `当日质控批量汇总消息缺失`

### 保留并改写为 P1

- `呼吸机使用时间缺少规则兜底与专项验证`
- `DRG 第5级个人维度命名和正式口径未统一`

### 不建议继续使用的原始表述

- `呼吸机使用时间字段完全缺失`
- `DRG 五级评价第5级“个人”维度代码里没有`

---

## 备注

本整改单的目标不是降低问题严重性，而是把问题表述从“错误诊断”修正为“可执行整改项”，避免后续开发和验收在错误前提上推进。
