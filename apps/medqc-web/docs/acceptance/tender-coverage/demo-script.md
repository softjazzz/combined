# 投标验收演示脚本

> 所有演示均为只读或草稿/模拟结果，不写病案首页、医保结算清单、正式质控结果或正式 DRG/DIP 结果。

## 1. 首页自动生成与结算清单

- 演示病例：`TENDER-FP-001` / `ZS-001`
- 入口：`/workstation-v4/worklist`，进入病案详情后打开 `病案首页` 和 `结算清单`
- 验收点：
  - 首页字段覆盖分组可见，按患者基本信息、住院信息、诊断手术、其他医疗信息、人员和费用展示完成度。
  - 缺少真实文书输入时返回 `requires_data`，不使用假成功结果。
  - 正式保存入口保留人工复核门槛。

## 2. 质控规则与编码内涵质控

- 演示病例：`TENDER-CODING-QC-001` / `MV2-REAL-001`
- 入口：`/workstation-v4/rules`、`/workstation-v4/icd`
- 验收点：
  - 首页和医保结算清单规则可按标准来源、字段、规则类型统计。
  - 肿瘤病理编码、病理费一致性、阑尾炎伴腹膜炎合并编码、冠脉支架附加编码返回结构化质控问题。
  - ICD 查询只展示候选编码、版本、匹配方式、置信度和映射关系。

## 3. 诊断/手术完整性与问题概览

- 演示病例：`TENDER-COMPLETE-001` / `2298532`
- 入口：`/workstation-v4/qc-overview`
- 验收点：
  - 病案问题概览按当天问题集中点推送，支持点击定位病历。
  - `GET /api/v1/clinical-completeness/{visit_id}` 返回诊断时间轴、手术计划和执行验证。
  - 漏填、错填、无依据提示只进入草稿建议，不写正式首页。

## 4. DRG/DIP 预入组、付费监测与综合分析

- 演示病例：`TENDER-DRG-DIP-001` / `LS-002`
- 入口：`/workstation-v4/drg/pre`、`/workstation-v4/drg/payment`、`/workstation-v4/drg/post`、`/workstation-v4/grouper`
- 验收点：
  - 入院记录完成事件生成只读模拟入组版本，并展示变更字段。
  - DIP 使用 `backend/app/data/luzhou_dip_groups.json`，DRG 使用 `backend/app/data/drg_weights.json`。
  - 未入组和更优入组选项返回编码修正建议，不自动写入编码。
  - 付费监测展示预计支付、实际费用、盈亏、支付率、基础组/费用极高组/费用极低组和控费建议。
  - 综合分析支持院级、科级、病区、主诊医师组、个人、诊断组和 DRG 维度，并支持 Excel/PDF/DOCX 导出。
