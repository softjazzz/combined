# SC099源库本地bundle覆盖验证报告

## 结论

- 本轮覆盖 SC-099 样本 `17` 份。
- source schema 状态：`local_public_schema_exists_but_empty`。
- dry-run bundle 组装方式：`dry_run_assemble_only_no_persisted_write`，未写正式质控结果表。
- public schema 对目标 visit 的 source 行数合计为 `0`；cdm/local 行数合计为 `60`。
- 本轮未证明客户真实远端源库覆盖；`public` 只是本机 source schema，当前目标表存在但样本行数为 0。
- 本轮只证明本机 `cdm/local` 与 bundle dry-run 覆盖闭环。
- pathology local 命中 `8` 份，dry-run bundle 命中 `8` 份，persisted bundle 命中 `0` 份。
- surgery local 命中 `17` 份，dry-run bundle 命中 `17` 份，persisted bundle 命中 `17` 份。
- 本轮只验证 source/local/bundle 覆盖，不注册 SC-099 gate，不开放 confirmed。

## 表级 source/local 覆盖

| table                       | source_hit_visit_count | source_total_rows | local_hit_visit_count | local_total_rows | root_cause                          |
| --------------------------- | ---------------------: | ----------------: | --------------------: | ---------------: | ----------------------------------- |
| pathology_exam_master       |                      0 |                 0 |                     8 |               12 | source_schema_empty_local_available |
| pathology_exam_report       |                      0 |                 0 |                     7 |                8 | source_schema_empty_local_available |
| surgery_record              |                      0 |                 0 |                    17 |               20 | source_schema_empty_local_available |
| postsurg_firstcourse_record |                      0 |                 0 |                    17 |               20 | source_schema_empty_local_available |

## persisted bundle 与 dry-run bundle 对比

| bundle/source_table                      | persisted_hit_visit_count | dryrun_hit_visit_count |
| ---------------------------------------- | ------------------------: | ---------------------: |
| course_bundle_has_pathology_exam_master  |                         0 |                      8 |
| course_bundle_has_pathology_exam_report  |                         0 |                      7 |
| final_bundle_has_pathology_exam_master   |                         0 |                      8 |
| final_bundle_has_pathology_exam_report   |                         0 |                      7 |
| final_bundle_has_surgery_record          |                        17 |                     17 |
| surgery_bundle_has_pathology_exam_master |                         0 |                      8 |
| surgery_bundle_has_pathology_exam_report |                         0 |                      7 |
| surgery_bundle_has_surgery_record        |                        16 |                     17 |

## 逐病历 dry-run bundle 覆盖

| root_cause                                  | count |
| ------------------------------------------- | ----: |
| local_surgery_only_pathology_source_missing |     9 |
| persisted_bundle_stale_for_pathology        |     8 |

## 根因判定

- `sync_gap`：source 有数据但 cdm/local 无数据，下一步修同步。
- `source_schema_empty_local_available`：public 目标表存在但样本无行，cdm/local 有行；该 public schema 不能作为有效远端源库覆盖结论。
- `persisted_bundle_stale_for_pathology`：pathology local 有行且 dry-run bundle 能命中，但 persisted bundle 未命中，下一步刷新目标 visit bundle 缓存。
- `local_surgery_only_pathology_source_missing`：本地有 surgery_record，但没有 pathology local 记录；SC-099 缺少病理对照来源，不能 confirmed。
- `pathology_assembly_or_bundle_gap` / `surgery_assembly_or_bundle_gap`：local 有数据但 dry-run bundle 未命中，下一步修 priority 或拼装。
- `source_or_local_no_data` / `source_no_data`：源和本地均无对应病理/手术记录，SC-099 只能 data_quality_gap/rejected 分流，不能 confirmed。

## 关键样本

| visit_id | patient_name | local_surgery_record_rows | local_pathology_rows | final_dryrun_surgery | final_dryrun_pathology | root_cause                                  |
| -------- | ------------ | ------------------------: | -------------------: | -------------------: | ---------------------: | ------------------------------------------- |
| 2229247  | 陈正权       |                         1 |                    0 |                    1 |                      0 | local_surgery_only_pathology_source_missing |
| 2310639  | 朱瑞银       |                         1 |                    0 |                    1 |                      0 | local_surgery_only_pathology_source_missing |
| 2191573  | 廖小平       |                         2 |                    0 |                    2 |                      0 | local_surgery_only_pathology_source_missing |
| 2142472  | 张泽芳       |                         1 |                    2 |                    1 |                      2 | persisted_bundle_stale_for_pathology        |
| 2200664  | 朱泰廷       |                         1 |                    4 |                    1 |                      4 | persisted_bundle_stale_for_pathology        |
| 2218469  | 刘光蓉       |                         2 |                    0 |                    2 |                      0 | local_surgery_only_pathology_source_missing |
| 2172686  | 胡启华       |                         2 |                    2 |                    2 |                      2 | persisted_bundle_stale_for_pathology        |
| 2327691  | 邹世科       |                         1 |                    0 |                    1 |                      0 | local_surgery_only_pathology_source_missing |
| 2214679  | 田正群       |                         1 |                    3 |                    1 |                      3 | persisted_bundle_stale_for_pathology        |
| 2263757  | 杨光中       |                         1 |                    0 |                    1 |                      0 | local_surgery_only_pathology_source_missing |
| 1961270  | 何维珍       |                         1 |                    0 |                    1 |                      0 | local_surgery_only_pathology_source_missing |
| 2270715  | 马建倡       |                         1 |                    1 |                    1 |                      1 | persisted_bundle_stale_for_pathology        |
| 1915580  | 雷德超       |                         1 |                    0 |                    1 |                      0 | local_surgery_only_pathology_source_missing |
| 2246915  | 黄金莲       |                         1 |                    4 |                    1 |                      4 | persisted_bundle_stale_for_pathology        |
| 1966656  | 周光容       |                         1 |                    2 |                    1 |                      2 | persisted_bundle_stale_for_pathology        |
| 2311318  | 范永勤       |                         1 |                    0 |                    1 |                      0 | local_surgery_only_pathology_source_missing |
| 1870471  | 蒲云鹏       |                         1 |                    2 |                    1 |                      2 | persisted_bundle_stale_for_pathology        |

## 收口建议

- 不应把历史 LLM issue evidence 中的“送病检/冰冻病理”当作源文书证据。
- 对于已有 pathology local 数据的样本，主因是 persisted bundle 未刷新。
- 对于没有 pathology local 数据的样本，仍是病理源数据缺口，不能 confirmed。
- SC-099 下一步应先刷新目标 visit 的 final/course/surgery bundle，再重跑 SC-099 只读 gate。
- 在 SC-099 gate 正式接入前，仍应只开放不适用/证据不足分流，不开放 direct confirmed。
