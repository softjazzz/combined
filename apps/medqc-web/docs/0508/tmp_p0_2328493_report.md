# 正式质控 gate 接入后随机 10 病历重跑验收报告

生成时间：2026-05-19 18:28:29

## 执行范围

- 链路：正式原链路 `final fast_screen_full / sc_content_full_v1`，一审后走正式后处理与二轮裁决。
- 本轮已启用生产 gate：SC-099、SC-123；SC-100/101、SC-083 未注册。
- 运行方式：只读审计脚本，不写正式 QC 结果表，不接页面，不使用 structured evidence POC。
- 失败版随机 10 的问题是 provider 运行环境失败（tokens=0），不作为质量结论；本轮在 minimal probe 与 2122521 c1/c3 门禁通过后复用同一批 visit_id 重跑。
- 完成病历：1 份；失败：0 份。
- 与历史固定/前三批随机样本重复：无；与上一轮失败版随机 10 完全一致，便于对比。

## 抽样清单

| visit_id | patient_name | department | 手术 | 会诊 | pathology | SC-099/SC-123触发 | bundle                 |
| -------- | ------------ | ---------- | ---- | ---- | --------- | ----------------- | ---------------------- |
| 2328493  | 陈梅琳       | 耳鼻咽喉科 | 是   | 否   | 是        | SC-099;SC-123     | final_bundle_available |

## 稳定性与性能

- 总墙钟耗时：39.95s；平均：39.95s；最慢：39.95s。
- LLM 调用数：20；总 token：82492；平均 token：82492。
- provider_error=0，provider_connection_error=0，upstream_http_error=0，parse_error=0，timeout=0，rate_limit=0，technical_error_internal=0。
- 稳定性门禁：未通过。

## 四层终态统计

- 确认缺陷 confirmed_defect：0。
- 数据缺口 data_quality_gap：13。
- 系统驳回 rejected_by_system：7。
- 技术异常 technical_error_internal：0。

## Gate 影响

- SC-099: 触发 1 条；decision={"data_quality_gap": 1}；终态={"data_quality_gap": 1}；pass_to_second_gate=0；programmatic_confirmed=0。
- SC-123: 触发 1 条；decision={"rejected_by_system": 1}；终态={"rejected_by_system": 1}；pass_to_second_gate=0；programmatic_confirmed=0。
- 非 SC-099/SC-123 gate metadata 异常：0。

## 质量抽查

- confirmed 全量复核建议：{}。
- rejected 抽样复核建议：{"possible_over_reject_convert_to_data_gap": 1, "rejected_keep": 6}。
- data_quality_gap 归因 Top：{"其他": 1, "证据短片段/截断": 4, "适用性无法证明": 1, "需跨文书对照": 7}。
- evidence 过短数量：8；quote 缺失数量：6；confirmed 疑似误报初筛：0。
- 疑似重复问题数量：0。

## 结论

- 稳定性未通过，本轮不做质量可演示结论，也不建议扩大到 20 份；应先处理 provider/parse/timeout/technical_error。
- SC-099/SC-123 gate 未出现程序化 confirmed；terminal gate 能把不适用/证据不足分流到 rejected/data_gap，pass_to_second_gate 仍交给二轮 LLM。
- 下一步：若 confirmed 误报仍多，优先补对应规则 gate/evidence；若 data_gap 高，优先补同步、bundle、结构化字段；若稳定性失败，先处理 provider 稳定性。
