# LX0609 两份真实病例数据不足根因复核

日期：2026-08-04

## 运行口径

- 使用当前生产入口 `SichuanQCService.evaluate_running_final_bundle_input`。
- 规则集为 Dependency Inventory 当前全部 75 条：`LX0609-001～075`。
- 使用 `final` Scene、完整三坐标、`source_schema=cdm`。
- 禁用本次调用的执行缓存，不使用旧 49 条验证脚本。
- 报告使用 `case_a/case_b`，不记录姓名、患者 ID 或原始坐标。
- 用户提供的第二个编号是病案号，不是 visit ID；重跑使用从主记录唯一解析出的真实 visit 坐标。

## 汇总

| 病例 | 总数 | 合规 | 不合规 | 不适用 | 数据不足 | 待确认 | 未执行/技术异常 |
|---|---:|---:|---:|---:|---:|---:|---:|
| case_a | 75 | 17 | 6 | 12 | 38 | 2 | 0 |
| case_b | 75 | 14 | 6 | 39 | 16 | 0 | 0 |

两份病例均读取到 75 条真实执行结果，不再存在“补齐规则 ID 但实际未执行”的占位问题。

## 共同资料观测

两份病例的权威 Snapshot 均显示：

- `inpat_drug_order`：`available + truncated`，只读取前 100 行；
- `inpat_nondrug_order`：`available + truncated`，只读取前 100 行；
- `exam_attention_report`、`lab_attention_report`、`medical_order`、`physician_change_event`、`surgery_risk_assessment`：`unavailable + unproven`。

Task 4 的 258 例冻结审计也证明，前两张物理表确实存在真实触顶，不是本病例的偶发状态。

## case_a：38 条数据不足

| 规则 | 当前原因码 | 根因分类 | 当前可确认的缺口 |
|---|---|---|---|
| 011、012 | `required_field_missing` | 必填字段/内容缺失 | CT/MRI 报告时间、结果属性或关联病程事实未闭合 |
| 014、015 | `required_field_missing` | 必填字段/内容缺失 | 细菌培养报告时间、阳性菌结果或分析记录未闭合 |
| 025 | `required_field_missing` | 必填字段/内容缺失 | 植入物事实及手术记录所需字段不完整 |
| 028 | `required_field_missing` | 必填字段/内容缺失 | 切口等级、预防用药属性、起止时间或延长依据不完整 |
| 029、031、032 | `association_failed` | 事件/文书关联失败 | 手术事件未与术前小结、签名医生或安全核查表稳定绑定 |
| 033 | `required_field_missing` | 资料来源/内容未证明 | 已确认实施手术，但手术知情同意书来源未被证明 |
| 034～039 | `association_failed` | 事件/文书关联失败 | 麻醉/手术事件与同意书、访视、麻醉单、术前讨论未稳定绑定 |
| 043 | `required_field_missing` | 必填字段/内容缺失 | 输血前检查项目或有效时间不完整 |
| 048 | `required_field_missing` | 必填字段/内容缺失 | 手术、麻醉、术后首次病程的输血比较事实不完整 |
| 049 | `source_unavailable` | 数据源合同缺失 | 缺可关联的输血医嘱、实际输注和收费明细 |
| 051、060 | `applicability_source_gap` | 适用性来源缺失 | 死亡/出院状态的权威适用性事实不足 |
| 054～059 | `source_truncated` | 资料读取上限 | 抗菌药、诊疗医嘱族受药品/非药品医嘱 100 行截断影响 |
| 062、063 | `required_field_missing` | 必填字段/内容缺失 | 出院带药或出院/死亡诊断比较字段不完整 |
| 064～066 | `association_failed` | 事件/文书关联失败 | 7 台手术与术后三日记录、上级查房、2 份术后首次病程未完成逐台关联 |
| 069、070 | `authoritative_time_missing` | 权威时间缺失 | 会诊或输血前九项缺少可用于时限判断的权威时间 |
| 071 | `source_unavailable` | 数据源合同缺失 | 经治医师变更事件源未接入/不可证明 |
| 072、073、075 | `source_truncated` | 资料读取上限 | 转科及有创操作门控受非药品医嘱 100 行截断影响 |

## case_b：16 条数据不足

| 规则 | 当前原因码 | 根因分类 | 当前可确认的缺口 |
|---|---|---|---|
| 043 | `required_field_missing` | 必填字段/内容缺失 | 输血前检查项目或有效时间不完整 |
| 049 | `source_unavailable` | 数据源合同缺失 | 缺可关联的输血医嘱、实际输注和收费明细 |
| 052、053 | `required_field_missing` | 同步/字段映射缺口 | 已有 43 份检验报告主记录，但缺 `labtest_item_report` 结果明细，无法识别 PL/PH 危急值 |
| 054～059 | `source_truncated` | 资料读取上限 | 抗菌药、诊疗医嘱族受药品/非药品医嘱 100 行截断影响 |
| 069、070 | `authoritative_time_missing` | 权威时间缺失 | 会诊或输血前九项缺少可用于时限判断的权威时间 |
| 071 | `source_unavailable` | 数据源合同缺失 | 经治医师变更事件源未接入/不可证明 |
| 072、073、075 | `source_truncated` | 资料读取上限 | 转科及有创操作门控受非药品医嘱 100 行截断影响 |

## 根因统计与处置边界

按规则结果计数（同一结构性缺陷可影响多条规则）：

| 根因类别 | case_a | case_b | 本轮能否直接解决 |
|---|---:|---:|---|
| 必填字段/内容缺失 | 11 | 3 | 否，需补字段映射、同步或规则事实说明 |
| 事件/文书关联失败 | 12 | 0 | 否，进入后续逐族关联修复 |
| 资料读取上限 | 9 | 9 | 可提出调整，但 Task 4 未授权修改生产上限 |
| 数据源不可用 | 2 | 2 | 否，需接入收费/医师变更等源 |
| 权威时间缺失 | 2 | 2 | 否，需明确并同步时间字段 |
| 适用性来源缺失 | 2 | 0 | 否，需补死亡/出院权威事实 |

分类存在语义重叠，表中以结果的首要失败原因为准；总数以逐条表为准。

## 额外发现：数据不足解释合同仍不合格

54 条 `data_gap` 结果中，绝大多数只有 `reason_code`，以下交付字段为空：

- `data_gap_details`；
- `missing_sources`；
- `missing_fields`；
- 客户可懂的缺口摘要。

少数规则通过 `customer_display_facts` 暴露了细节（例如 049、052、053），但不是统一合同。因此当前能够在审计中判断根因，不代表前端已经能清楚告诉客户“具体缺什么”。

建议后续优先级：

1. 经确认后单独调整两类医嘱源上限，并用两病例重跑验证 054～059、072、073、075；
2. 手术/麻醉族先处理 case_a 的 11 条关联失败；
3. 修复 `labtest_item_report` 明细同步/映射，解除 case_b 的 052、053；
4. 为所有 `data_gap` 强制生成受控的 `missing_sources/missing_fields/customer_message`，不改变状态判定。
