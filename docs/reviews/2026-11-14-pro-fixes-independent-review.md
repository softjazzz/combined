# A1/A2/A3 与无首页合同：独立复审记录

审查模型：Astra 6 high，独立只读复审。原始基线 `3893a93c3193d6733c02a4425498fbc32ebe736c`，首次固定实现 `cdcf5eb46e2d998bac710ac34be2f86b8bb6e711`。

## 首次复审：有阻断

| 级别 | 发现 | 首次固定提交下的位置 |
| --- | --- | --- |
| P1 | qc-detail 前置机构授权不能约束后续单号 legacy 缓存及全局批次返回；同住院号跨机构可能泄露旧结果 | `app/routers/records.py`：`_resolve_visit_identity`、`_load_review_items_from_latest_batch`、`get_record_qc_detail` |
| P2 | 003已有手术记录缺结束时间时，麻醉补齐分支未检查结束不早于开始，倒序时刻仍可产生超时阳性及独立豁免 | `app/services/luxian_0609/native_surgery_gate_execution.py`：003麻醉补齐分支 |
| P2 | 003缺记录分支将明确取消／尚未实施正文中的预填严格时间标签当实施依据 | 同文件：`_labeled_anesthesia_surgery_time` 与003缺记录分支 |

以上由固定源码调用链确认，首次复审没有运行这三个新反例。A3写入前拒绝、其他结果入口机构校验、新来源与历史注册分离、070实际消费原行、目录非手术汇总范围及新场景冻结已检查，未另确认P1/P2。

## 集中补修与复核

三项已集中补修，等待固定新提交后的逐项复核；首次复审的阻断记录保留。

- **P1**：单号身份解析先按完整三坐标去重并拒绝歧义/不完整/查询失败；已授权身份贯穿 bundle 与 Canonical。作用域管理账号和医生关闭无法证明归属的 Supabase、内存及全局 batch 回退，全局角色的原有读取合同保留。首页零行仍可由原始文书给出唯一身份。
- **P2 时间**：麻醉补齐先检查起止顺序；倒序保持 `data_gap / authoritative_time_conflict`，只绑定实际冲突的两份原文书，阳性引用为空，不改通用 guard。
- **P2 实施**：两处时间借用共用明确实施声明协议；取消、预填、尚未实施及肯否冲突保持待核。纯标签不证明实施；“按计划顺利实施并已完成”“未取消，已完成”等正例保留。无法用该窄协议证明的自由文本继续待核，没有新增模型调用。

### 必要隔离验证

- 修复前：新反例 **26 failed / 12 passed**（真实断言失败，非环境错误），分别复现三项发现并保留正向对照。
- 修复后003直接边界：**47 passed / 70 deselected**。
- 新反例、独立阳性、Canonical历史交付、机构权限与医生入口相邻集合：**82 passed**。仅已有弃用/字段遮蔽告警。
- UTF-8无BOM、LF、Python AST及 `git diff --check` 通过；不把合成 SQLite 验证表述为真实PG验收。

```powershell
python -B apps/medqc-web/backend/scripts/run_pr8_offline_tests.py tests/unit/test_003_anesthesia_time_fix_wave.py::test_anesthesia_end_before_matching_begin_is_conflict_through_finalizer tests/unit/test_luxian_0609_native_surgery_gate_execution.py -k '003' --tb=short
python -B apps/medqc-web/backend/scripts/run_pr8_offline_tests.py tests/unit/test_qc_detail_fix_wave.py tests/unit/test_003_anesthesia_time_fix_wave.py tests/unit/test_surgery_independent_positive_scope.py tests/unit/test_records_qc_detail_canonical.py tests/unit/test_qc_record_read_permissions.py::test_legacy_qc_detail_cannot_bypass_manager_institute tests/unit/test_qc_record_read_permissions.py::test_resolved_canonical_identity_is_authorized_before_dto tests/unit/test_doctor_case_scope.py::test_qc_detail_uses_authorized_identity_and_never_legacy_unscoped_results --tb=short
```

逐项独立复核结论待补。

## 范围说明

首页专属063暂停为用户明确批准的口径；普通首页查看和历史来源支持保留。A5模型4xx重试、既有术后开始时间估算及更广的医学事件识别不在本轮追加修复范围。

没有读取真实材料、配置或凭据，没有连接真实库、调用模型、运行质控、重跑27份、推送、合并或部署。真实PG并发、完整worker、现场SQL/浏览器/医学质量未验收；复审不以这些未验证项虚构缺陷。
