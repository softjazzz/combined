# 第二轮肿瘤三规则独立审计（2026-10-07）

结论：确认两项工程漏报，达到“两项确认缺陷即交付”的停止条件。未修改生产代码、未调用真实模型、未写 PostgreSQL、未提交/推送或重启服务。不能据此宣称三规则通过临床验收。

## 范围与依据

代码基线为 `c3a87a4f820259bca37a01764522ea1f3f485a3c`，已核对当前 HEAD 一致。遵循 AGENTS，先调用 CodeGraph，再定位执行器。以当前 `backend/app/data/luxian_0609_rule_master_v1.json` 的 `qc_point` 为准，同时核对0609规则目录和业务标准基线。

| 规则                  | 当前质控点                                         | 本轮覆盖                                         |
| --------------------- | -------------------------------------------------- | ------------------------------------------------ |
| LX0609-04-02-03 / 024 | 恶性肿瘤手术记录未书写淋巴结清扫情况               | 源记录人工预期冻结、代码门控阅读；未执行真实模型 |
| LX0609-05-02-01 / 026 | 化疗病程药物名称、剂量、使用方法、时间与医嘱不一致 | 两个工程用例经过正式执行器和最终输出             |
| LX0609-08-01-04 / 027 | 恶性肿瘤患者出院记录中无出院后肿瘤相关治疗计划     | 两个工程用例经过正式执行器和最终输出             |

## 源先行与覆盖限制

在 PostgreSQL 事务内执行 `SET TRANSACTION READ ONLY`，再以 `SHOW transaction_read_only` 确认 `on`。独立读取0910池30例的诊断、出院诊断、病理、正式手术、药物医嘱、日常病程、出院及住院登记源记录；未读取系统结论或按照命中结果抽样。患者原文仅保存在 `.tmp/0910-full-audit/round2-tumor-private/`。

本轮源审阅发现两例明确恶性肿瘤；其中一例有正式恶性肿瘤手术及明确淋巴结清扫，另一例无正式手术。两例均未找到本次化疗类药物医嘱，因此026真实适用例为0，024为1，027为2，未凑满6例。两例出院源预期中，一例明确辅助化疗安排，另一例为基因结果后评估靶向，后者治疗计划具体性的业务边界保留复核，不计确认缺陷。

在执行任何工程回放前，于 `2026-10-07T13:28:19.937346+00:00` 冻结两例源预期、四个合成工程用例及完整源文件哈希。冻结预期 SHA-256：`2d47ee4e08b3df8c0f119e03379ba169addd713ed5c5ddc66c9ac69f759c20f5`。原始冻结文件未回改。已读取生产代码后设计的工程反例明确属于白盒边界验证，不冒充盲测或真实病例结果。

## 确认缺陷

### TUMOR-01（P1）：026把不同剂量的数字子串当成一致

合成医嘱为奥沙利铂130mg静滴，时间2026-04-26。正常对照病程写130mg，反例仅把剂量改成1130mg，药名、用法、日期均相同。

冻结预期分别为 `compliant` / `non_compliant`。两者实际均为 `compliant`，最终 `reason_code=requirement_satisfied`，公开事实均声称 `dose=matched`，客户文案均声称四项一致。

根因：`backend/app/services/luxian_0609/native_tumor_pathology_execution.py:1325` 用规范化后的字符串包含判断剂量，`130mg` 是 `1130mg` 的子串，未核对数值与单位边界。错误合规已穿过绑定归约和最终输出，非仅辅助函数返回差异。

最小修复方向：保留每次化疗事件关联，按数值和单位解析剂量并比较；不能以整段文本中出现预期剂量字符串作为一致证据。增加同药同日期130/1130这对保护例，另需验证小数、单位换算及多疗程，后者本轮未扩展。

### TUMOR-02（P2）：027把住院期间已完成治疗当成出院后计划

正常对照出院文本为“出院后继续化疗。”；反例治疗经过为“入院后继续化疗，治疗结束后病情好转出院。”，出院嘱仅“注意休息，加强营养。”。材料完整，反例仅描述住院已实施治疗，未给出出院后肿瘤治疗计划。

冻结预期分别为 `compliant` / `non_compliant`。两者实际均为 `compliant`，最终 `reason_code=requirement_satisfied`，公开事实均为 `future_plan=true`、`tumor_treatment=true`、`requirement_met=true`。

根因：同文件185行把“继续”纳入未来计划词，1383–1405行在出院记录各段落中仅匹配同句未来词+肿瘤治疗词，未区分“治疗经过”中住院历史与出院后的时间范围。反例“入院后继续化疗”因此获得出院后计划肯定事实。

最小修复方向：确认计划属于出院后时间范围，保留出院记录不同字段的语义；既往/住院已完成治疗不能单独证明未来计划。增加上述有/无出院后计划保护例。对“待结果后评估”“拒绝治疗”等真实边界须另行明确口径，不将无法抽取等同缺失。

## 执行链与复核产物

工程脚本直接导入生产模块，构建 `build_luxian_0609_evidence_read_session`，调用 `execute_luxian_0609_native_tumor_pathology_rules`，随后调用 `bind_and_reduce_luxian_0609_rule_decisions` 与 `finalize_luxian_0609_reduced_customer_result`。没有复制判定函数。合成恶性ICD编码使适用性走确定性路径；禁止模型客户端一旦被调用即抛错，四例调用量全部为0。

| 工程用例        | 冻结预期      | 正式最终输出 | 结论         |
| --------------- | ------------- | ------------ | ------------ |
| dose_control    | compliant     | compliant    | 正常对照通过 |
| dose_substring  | non_compliant | compliant    | 漏报         |
| future_control  | compliant     | compliant    | 正常对照通过 |
| historical_only | non_compliant | compliant    | 漏报         |

私有目录包含 `read_sources_private.py`、`sources30-private.json`、`expectations-frozen-private.json`、`expectations-sha256-private.txt`、`run_engineering_private.py`、`engineering-results-private.json`、`artifact-hashes-private.json`。复核命令在仓库根目录执行：`python .tmp/0910-full-audit/round2-tumor-private/run_engineering_private.py`。回放仅离线读取冻结用例，不连接数据库或模型。

本轮在两项确认缺陷后停止扩展，未跑多疗程、完整良恶性门控矩阵或真实模型回放，024未形成全链执行结论。真实适用样本不足已明确记录，不将工程反例算作真实病例。后续修复需要主协调独立复核本报告、冻结预期、原始结果及关键代码行。
