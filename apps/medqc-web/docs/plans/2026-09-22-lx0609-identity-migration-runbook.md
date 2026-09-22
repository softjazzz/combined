# LX0609 四段式历史身份迁移操作手册

本手册只适用于已发布的历史 `LX0609-001` 至 `LX0609-079`。唯一输入表是
`docs/plans/lx0609-four-part-rule-code-mapping-v1.csv`，工具固定校验其 79 条、旧新
身份双唯一、版本 `lx0609-four-part-rule-code-mapping-v1` 与 SHA-256。080/081 和 CT
新规则没有历史旧身份，预检遇到它们会阻断，不迁移。

工具位于 `backend/scripts/luxian_0609_identity_migration/`，不被运行时服务导入。
默认命令只读地生成内存计划和不含病历内容的摘要；不会连接默认 `backend/.env` 数据库，
必须显式给出快照 URL。迁移计划包含历史 JSON 原值，若要保存，只能写到
`.tmp/0910-full-audit/*-private.json`，严禁提交。

## 已核对的存储合同

`custom_qc_workspace_service.py:_batch_jobs_table()` 定义了
`custom_qc_batch_jobs.rule_code` 以及 `filters_json`、`items_json`、`summary_json`、
`failed_records_json`、`child_summary_json`；`_row_to_batch_job()` 会将这些 JSON 投影回任务、
子任务和规则结果。迁移仅处理上述列中的白名单身份字段、身份数组和已命名的规则结果字典键，包括
`mapped_rule_ids`、`execution_rule_ids`、`customer_rule_ids`、`scoped_customer_rule_ids`、
`gate_only_customer_rule_ids`、`paused_customer_rule_ids`、`planned_rule_ids`，以及失败补跑合同
`record_rule_map` 的**值**数组；后者的 key 是病历坐标，保持不变。决策和依赖结果在已保存任务 JSON 中
使用同一 `rule_id`/上述规则数组合同，不存在可安全独立替换的自由文本 binding 字段。
顶层 `rule_code` 只有在其精确等于冻结表内的单规则旧 ID 时才更新；批量、组合或非 LX 值原样保留。

`manual_problem_sample_pool_items.candidate_rule_ids_json` 是样本池 `_row_to_item()` 恢复并加入执行选择的
候选规则数组。客户自建和导入路径还会把 `selected_rule_ids` 放在同一行 `raw_payload_json`；工具只转换这个
白名单数组，保留其中的病历材料、人工问题文本和其它 payload 字段。缺少该表或这两个列会阻断，因为会造成
迁移后样本选择落空。

`custom_qc_rule_drafts.published_rule_id` 不是 LX0609 身份：发布链在
`custom_qc_workspace_service.py` 将它写为 `qc_rules.id` UUID（查询失败时的 `rule_code` 回退不能作为可安全
迁移合同）。工具不改写草稿或 `qc_rules`，但如果草稿 `rule_code` 或 `published_rule_id` 异常地等于旧
LX0609 ID，会报告并阻断，要求人工核对绑定关系。

`_record_result_envelopes_table()` 的
`luxian_0609_record_result_envelopes.envelope_json` 是 Canonical 结果的保存路径。
工具要求 `lx0609-record-result-envelope-v1`、`root_job_id`、`record_ref`、规则集键和版本完整，
要求行的 `root_job_id` 与 JSON 一致、`result_count` 与 items 数一致，并复核 item 的唯一规则身份、
状态/`result_status`/`display_status`/`is_compliant` 合同。这与
`qc_workspace/canonical_result_store.py` 的交付校验一致；不能验证的历史行不猜测。

`qc_result_feedback_demo` 由 `result_feedback_demo_store.py` 以
`root_job_id + record_ref + rule_id + created_by` 唯一定位。工具先在同一 `created_by` 的唯一
Canonical Envelope 中找到旧 item，要求 `original_status` 与 item 当前状态一致，并按该模块的
`_result_digest()` 输入（规则 ID、状态、原因码、客户展示事实、客户证据）验证旧摘要。只有通过后
才同时改反馈 `rule_id` 和新 digest。没有匹配、匹配多个、摘要不符或目标唯一键冲突都会阻断，所以旧反馈
不会被挂到后续重跑的结果上。

原始模型响应、执行快照、提示词和评论字段被视为不透明归档。工具从不做字符串替换，例如评论里的
`LX0609-010` 保持不变；除明确身份位置和依赖身份重建的反馈 digest 外，诊疗内容和非身份字段不变。
`lx0609-rule-master-v2` / `2026-09-22-identity-v1` /
`lx0609-defined-scope-2026-09-22-identity-v1` 是当前规则目录与定义版本合同，不是历史结果身份字段。
迁移保留历史 `rule_set_version`、规则版本和 schema 版本原值，不把旧结果冒充为按新定义重跑的结果。

## 预检与演练

迁移窗口必须先停止任务接入，并排空全部在途任务；工具发现 `queued`、`running` 或未知任务状态会阻断。
不得把“版本绑定在途任务”当作此工具已支持的替代方案。复制客户库快照到隔离环境后运行；本仓库
没有授权该命令指向客户库或本地业务库。

```powershell
Set-Location backend
$env:PYTHONPATH = (Get-Location)
C:\Python310\python.exe -m scripts.luxian_0609_identity_migration `
  --database-url $env:ISOLATED_LX0609_SNAPSHOT_URL --schema qc `
  --summary-out ..\.tmp\0910-full-audit\lx0609-identity-dry-run-summary.json `
  --plan-out ..\.tmp\0910-full-audit\lx0609-identity-plan-private.json
```

实际 URL 只从隔离环境的 `backend/.env` 读取后作为进程环境变量提供，不写入脚本、计划或文档。先审阅摘要：
必须 `ready: true`、`issue_count: 0`；同时人工检查保护集合中的 `compliant`/`non_compliant` 结果、失败重试、
父子任务和反馈。任何 `unknown_lx0609_identity`、`conflicting_identity_fields`、不完整表、Envelope 合同、反馈
归属或 digest 问题都必须先修复数据或明确归档策略，不能绕过。

通过副本验收后，显式读取已审阅的私有计划才可申请执行。工具先重新盘点并比较完整操作集合，拒绝删掉部分操作、
改写非身份内容或过期的计划，再在一个事务中执行每列旧值 compare-and-swap；任一更新失败全部回滚。
维护窗口内仍须保持服务停止接入和后台任务停止写入，预检不能代替维护隔离。重跑会产生零操作。

反馈摘要由完整的迁移后结果计算，包含证据及展示事实里的身份字段，并与运行时反馈摘要算法对照测试。
`execution_scope_hash` 包含规则范围，仅用于活跃任务去重，因此不把旧任务摘要伪造为新摘要；排空任务是硬前提。
`decision_fingerprint` 和预生产 `evidence_hash` 未进入本工具所迁移的生产保存合同，原始诊断归档保持不变。

```powershell
C:\Python310\python.exe -m scripts.luxian_0609_identity_migration `
  --database-url $env:ISOLATED_LX0609_SNAPSHOT_URL --schema qc `
  --plan-in ..\.tmp\0910-full-audit\lx0609-identity-plan-private.json `
  --apply --confirm-apply
```

在客户库执行前仍需单独发布授权和维护窗口。此工具没有自动备份、没有回写原始归档、也没有运行时旧 ID 回退服务；
回滚应恢复维护窗口前的数据库快照，而不是把四段式 ID 机械替换回旧字符串。

## 本地验证

以下测试只创建 pytest 临时 SQLite 文件，不读取或写入业务数据库：

```powershell
$env:PYTHONPATH = (Join-Path (Get-Location) 'backend')
C:\Python310\python.exe -m pytest --noconftest backend\tests\unit\test_luxian_0609_identity_migration.py -q
```

覆盖嵌套任务 JSON、样本池候选/客户自建 payload、完整 Canonical 结果与反馈同步、重跑幂等、未知 ID、冲突、
原文和评论保留、反馈摘要/归属、异常草稿绑定、计划删改拒绝、活跃任务阻断，以及后续更新失败时先前任务写入的真实事务回滚。
预检阻断时命令返回非零退出码。它不构成客户库演练或
真实模型回归；后两项仍是上线前门槛。
