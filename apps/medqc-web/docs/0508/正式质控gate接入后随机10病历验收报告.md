# 正式质控 gate 接入后随机 10 病历验收报告

生成时间：2026-05-19 11:33:35

## 执行范围

- 链路：正式原链路 `final fast_screen_full / sc_content_full_v1`，一审后走正式后处理与二轮裁决。
- 本轮已启用生产 gate：SC-099、SC-123；SC-100/101、SC-083 未注册。
- 运行方式：只读审计脚本，不写正式 QC 结果表，不接页面，不使用 structured evidence POC。
- 完成病历：10 份；失败：0 份。
- 与历史固定/随机样本重复：无。

## 抽样清单

| visit_id | patient_name | department   | 手术 | 会诊 | pathology | SC-099/SC-123触发 | bundle                 |
| -------- | ------------ | ------------ | ---- | ---- | --------- | ----------------- | ---------------------- |
| 2122521  | 李才均       | 泌尿血管外科 | 是   | 否   | 是        | SC-099;SC-123     | final_bundle_available |
| 2307459  | 史春秀       | 普通外科     | 是   | 否   | 是        | SC-099;SC-123     | final_bundle_available |
| 2281076  | 蒋光琼       | 泌尿血管外科 | 是   | 否   | 是        | SC-099;SC-123     | final_bundle_available |
| 2097406  | 唐在芳       | 骨科烧伤科   | 否   | 是   | 是        | SC-099;SC-123     | final_bundle_available |
| 2289796  | 杨上伦       | 老年医学科   | 否   | 是   | 是        | SC-099;SC-123     | final_bundle_available |
| 2104927  | 温远明       | 神经内科     | 是   | 否   | 是        | SC-099;SC-123     | final_bundle_available |
| 2030069  | 柯贤林       | 外四科       | 是   | 是   | 是        | SC-099;SC-123     | final_bundle_available |
| 2328493  | 陈梅琳       | 耳鼻咽喉科   | 是   | 否   | 是        | SC-099;SC-123     | final_bundle_available |
| 2218096  | 张厚易       | 疼痛科       | 否   | 是   | 是        | SC-099;SC-123     | final_bundle_available |
| 2208257  | 万先富       | 肿瘤科       | 否   | 否   | 是        | SC-099;SC-123     | final_bundle_available |

## 稳定性与性能

- 总墙钟耗时：66.35s；平均：6.63s；最慢：8.56s。
- LLM 调用数：257；总 token：0；平均 token：0。
- provider_error=127，upstream_http_error=0，parse_error=0，timeout=0，rate_limit=0，technical_error_internal=441。
- 稳定性门禁：未通过。

## 四层终态统计

- 确认缺陷 confirmed_defect：0。
- 数据缺口 data_quality_gap：15。
- 系统驳回 rejected_by_system：2。
- 技术异常 technical_error_internal：441。

## Gate 影响

- SC-099: 触发 10 条；decision={"data_quality_gap": 5, "pass_to_second_gate": 3, "rejected_by_system": 2}；终态={"data_quality_gap": 5, "rejected_by_system": 2, "technical_error_internal": 3}；pass_to_second_gate=3；programmatic_confirmed=0。
- SC-123: 触发 10 条；decision={"data_quality_gap": 10}；终态={"data_quality_gap": 10}；pass_to_second_gate=0；programmatic_confirmed=0。
- 非 SC-099/SC-123 gate metadata 异常：0。

## 质量抽查

- confirmed 全量复核建议：{}。
- rejected 抽样复核建议：{"rejected_keep": 2}。
- data_quality_gap 归因 Top：{"其他": 3, "适用性无法证明": 12}。
- evidence 过短数量：458；quote 缺失数量：449；confirmed 疑似误报初筛：0。
- 疑似重复问题数量：0。

## 结论

- 稳定性未通过，本轮不做质量可演示结论，也不建议扩大到 20 份；应先处理 provider/parse/timeout/technical_error。
- SC-099/SC-123 gate 未出现程序化 confirmed；terminal gate 能把不适用/证据不足分流到 rejected/data_gap，pass_to_second_gate 仍交给二轮 LLM。
- 下一步：若 confirmed 误报仍多，优先补对应规则 gate/evidence；若 data_gap 高，优先补同步、bundle、结构化字段；若稳定性失败，先处理 provider 稳定性。
