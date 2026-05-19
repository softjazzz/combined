# SC099病理证据bundle刷新后回放报告

## 执行范围

- 刷新 visit 数：`17`。
- 刷新表：`final_record_bundle`、`course_domain_bundle`、`surgery_domain_bundle`。
- 刷新来源：`sc099_source_local_bundle_coverage.json` 中的 SC-099 visit_id。
- 本轮只写 bundle 缓存表，不写正式 QC 结果表，不注册 SC-099 gate，不开放 confirmed。

## 覆盖前后对比

| 指标                                | 刷新前 | 刷新后 |
| ----------------------------------- | -----: | -----: |
| pathology_local_hit_visit_count     |      8 |      8 |
| pathology_dryrun_hit_visit_count    |      8 |      8 |
| pathology_persisted_hit_visit_count |      0 |      8 |
| surgery_local_hit_visit_count       |     17 |     17 |
| surgery_dryrun_hit_visit_count      |     17 |     17 |
| surgery_persisted_hit_visit_count   |     17 |     17 |

## root_cause 前后对比

- 刷新前：{"local_surgery_only_pathology_source_missing": 9, "persisted_bundle_stale_for_pathology": 8}
- 刷新后：{"local_surgery_only_pathology_source_missing": 9, "persisted_bundle_already_current": 8}

## SC-099 gate 回放前后对比

- 刷新前 gate 分流：{"rejected_by_system": 1, "data_quality_gap": 16}
- 刷新后 gate 分流：{"rejected_by_system": 9, "pass_to_second_gate": 8}
- 刷新后 pathology local 8 个样本 gate 分流：{"pass_to_second_gate": 8}

## 收口结论

- pathology persisted 命中已从 0 提升到 dry-run 同口径的 8，bundle 缓存刷新闭环已验证。
- 8 个本地已有 pathology 的样本刷新后均进入 pass_to_second_gate，说明 gate 已能读取 persisted bundle 中的病理证据。
- 9 个本地没有 pathology 的样本继续保持 rejected/data_gap 分流是合理的，不应强推 confirmed。
- 本轮未开放程序化 confirmed；若 gate 输出出现 confirmed_defect，应视为失败并修正。
