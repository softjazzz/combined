# CT-04 固定提交独立有限关闭复审

结论：建议在固定提交 `515bcec6dc7ebcf11a8f54699aeb7b7f4dba663e` 关闭 CT-04 工程缺陷。未发现确认阻断。原 CT-03 保留的未满七天且有讨论行反例现已真实恢复 NA/trigger_absent_complete；原 CT-04 与 CT-03 冻结预期未改。此结论不代表 CT-01、CT-R02 或临床语义验收关闭。

修复树 `F:/MedQC-worktrees/qc-fix-critical-v2-20261008`，执行前 clean、HEAD 固定。完整生产 diff 只有 mapping 将 `if not records and discussion_count == 0` 改为 `if not records`，其余提交为专属测试和文档。运行前后当前提交三路径及 native/renderer/finalizer 三个保护文件与固定 Git 字节一致，source SHA256 不漂移。公开 NA 允许的是 sanitizer 已确认的非负整数讨论数，不能把非法类型或非空成熟时间放宽为 NA。

| 验收项 | 独立观察 | 结论 |
|---|---|---|
| 原反例与正文类型 | N01 未成熟强病程+有效讨论、N02 缺正文、N03 空白、N04 非字符串、N05 多行讨论全部 NA/trigger_absent_complete。facts 保留实际 discussion_count=1/2，成熟时间为空，文案说明未见满七天触发而非“没有讨论” | 通过 |
| 正常旧保护 | N06 无讨论行旧 NA、N07 无候选已有讨论 NA；N08 恰满七天无讨论 NC，N09 满七天有效讨论 C。N10 pure time gap、N11 local scope uncertain、N12 mature body gap 保持 | 通过 |
| 非空成熟时间不准伪 NA | 原15公开组合 C04/C05 分别成熟时间+count0/1伪 NA均拒绝；空时间伪 C/NC拒绝。成熟 count0仅NC、count正数仅C，错误C/NC组合拒绝 | 通过 |
| 公开非法矩阵 | 原15组合加状态、缺必需字段、非法时间列表、讨论数与 gap 数零/负/bool/小数/字符串/null、摘要矛盾共87项；全部符合预期。body/time/body+time只允许data_gap，成熟缺时摘要不能借空时间NA分支放行；3私有字段过滤无透传 | 通过 |
| CT-03 原冻结保护 | 原28组完整复验28/28，包括原 T03_before_seven_days_plus_empty_discussion，现公开 NA，不再 technical_error。正文缺口类型、多空、无ID来源锚、混合正文旧路径预期保持 | 通过 |
| CT-02 原冻结保护 | 原28+root补充2组复验30/30；缺时不误NA、已成熟C/NC保留、时间别名/时区/优先级未松动 | 通过 |
| 新实例保存 | N01 NA、N09 C、N12 body gap各新SQLite、新engine、新Store写入后重新加载，status/reason/facts/findings/suggestion一致，无原ID透传。body gap成熟病程来源、时间、field_path和原合成摘录独立assert通过；空讨论只保留实际来源/时间锚，无伪摘录 | 通过 |

正式公开合同分层说明：87项调用 safe facts sanitizer、difficult_case_customer_fact_status_is_valid 及 published facts helper。旧 published helper 本身不是旧kind状态校验入口，不冒称它单独拒绝全部旧kind矛盾；旧状态矛盾由明确 status validator 拒绝，正常主链由 native→Binding→Finalizer/Renderer实测。新gap kind的published helper硬状态门禁另直接观察。这样保留旧技术错误sentinel与额外键过滤合同，不扩大修复。

保存具体证据：N01 NA 的 safe evidence 列表为空，decision_facts保留empty mature time及discussion_count=1；这是现有NA投影能力边界，不伪造讨论精确卡。N09成熟C保存病程2026-06-08 08:00:00和讨论2026-06-08 09:00:00的实际摘录及安全锚。N12正文gap保存成熟病程2026-06-08 09:00:00、field_path=record_content、摘录“目前诊断仍不明确。”，讨论行同一实际时间有安全锚且没有正文摘录。没有将原generic evidence字符串与safe evidence列表形状差异当作丢证据。

旧C/NC建议不变由唯一一行固定diff及成熟非空时间分支静态证明，运行观察实际C/NC文案正常；本轮没有另执行完整基线逐字段差分。原CT-03报告的27/28保留其25406版本测量，当前28/28为515bcec上的新增复验记录，不追改历史报告。

边界：全部输入为合成，PG/真实模型/.env/网络零访问，防护零触发。未执行owner测试套件，不改生产、共享测试或原冻结。SQLite工程合同和合成fixture不等于真实源适配、真实脱敏病例、浏览器及临床语义验收。CT-01与CT-R02继续开放，0916用户排除不计本验收。

原CT04 expected-v1.json SHA256 `818456501701e3f3088902e647bed7302d5e510ae130ac7fd668f1b10d724505`；原CT03冻结 `c92061e62c1d0049f4d68ea007e774cb43ef54c81672289dba78134afe29ad9e`。脚本probe-v1.py、observed-v1.json及三合成SQLite均在本目录。独立探针单轮完成，无探针准备失败；测试槽已释放，无运行进程。
