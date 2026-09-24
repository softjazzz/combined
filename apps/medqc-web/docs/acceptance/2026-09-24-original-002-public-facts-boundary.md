# 原始 002 首次病程时限：公开事实边界收敛

范围固定为 `LX0609-01-02-01`（原始 002），基线代码 `b7f0e6e23`。权威目录 `docs/0602/luxian_0609_formal_rule_catalog.csv` 的 002 是入院后 8 小时内首次病程记录。本次不改规则执行器、8 小时判据、模型、门控、并发、Store/API 生产代码或其他医学规则。

## 复现及责任边界

修复前，已发布的正常事实带 `elapsed_hours=1.0, remaining_hours=999.0` 时，`validate_luxian_0609_published_customer_display_facts` 对 002 回落到内部 `safe_basic_timeliness_customer_display_facts`，把 999 静默改成 7.0。保存数据已损坏，却可能作为正常客户结果交付。实际持久化读取也沿这一公开校验边界；原受控校验只覆盖 001/004，未覆盖 002。另在同一次正式聚合中，002 的客户事实被重复投影。修复前新增定向测试 11 项中 8 项失败，包含异常事实未拒绝、SQLite 写后污染未拒绝及投影计数 2 次。

## 最小修复

002 的公开读取改为只校验已经发布的字段，合法映射精确原样返回；未知字段、错误 JSON 类型、非有限/布尔数值和无法自洽的剩余或逾期小时受控拒绝。001/002 复用同一纯技术时限字段校验，分别固定 24/8 小时及目标文书；001 专属的时间冲突和内容空白分支不开放给 002。保留内部投影的两次舍入容差，公开读取不重算已发布事实。同一次正式聚合把 002 加入已验证事实复用集合，避免第二次内部投影。没有新增合同注册器或改变判定所有者。

## 固定输入验证和限制

合成来源通过真实 Evidence Session → 原执行器 → reducer → 聚合发布。正常、超过 8 小时、缺少首次病程、缺少入院锚点分别保持 `compliant/requirement_within_threshold`、`non_compliant/threshold_exceeded`、`non_compliant/required_document_missing`、`data_gap/authoritative_time_missing`，模型调用和 Token 均为 0。正常分支的完整发布结果与修复前 `b7f0e6e23` 固定输出逐字段相等，包括状态、原因码、事实、证据 `first_course_record/FC-1/record_content`、文案和版本字段；正式聚合内部投影调用由 2 次变为 1 次。

公开读取另覆盖正常/超时/缺文书三种已发布事实，以及阈值附近的两次舍入；合法事实严格相等。SQLite 内存库真实写入 Canonical Envelope 后读取合法事实，再将逾期小时污染为 999，后续 `load_selected` 受控抛 `ValueError`，不修改存储。原 001/004 投影与架构冻结测试一起运行，105 项通过，1 条警告；使用不可连接的 fake PG 地址和 `--confcutdir=tests/unit`，没有客户库或模型调用。复跑命令：

```powershell
$env:JWT_SECRET='unit-test-secret-only'; $env:DATABASE_URL='postgresql://test:test@127.0.0.1:1/test'; python -m pytest tests/unit/test_luxian_0609_original_002_public_boundary.py tests/unit/test_luxian_0609_basic_timeliness_customer_projection.py tests/unit/test_luxian_0609_basic_timeliness_architecture_freeze.py --confcutdir=tests/unit -q --disable-warnings --tb=line
```

这些是固定技术回放，不证明临床判据正确，也不替代真实病例保护集。主协调已另行冻结 13 个本机 PG 来源形态候选用于跨代码根比对；本提交不引用其患者原文，也不将候选当作独立临床金标准。

提交前 Ruff、暂存区 UTF-8/LF 与 `git diff --cached --check` 通过。该独立 worktree 无 `node_modules`，`npm run lint` 因找不到 `eslint` 退出 1；前端 lint/type-check/unit 未在此树执行。本次没有前端改动，此环境缺口不冒充测试通过。
