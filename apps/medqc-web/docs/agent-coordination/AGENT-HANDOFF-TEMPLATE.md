# MedQC Agent 交接模板

本文件只放高频复制模板。完整规则见 `docs/agent-coordination/MEDQC-MULTI-AGENT-WORKFLOW.md`。

## 1. TASK_ASSIGN

```text
[MEDQC-AGENT-MSG v1]

message_id:
from: coordinator
to:
type: TASK_ASSIGN
task_id:
repo: D:\LLM\LX888\apps\medqc-web
thread_id:
related_threads:
-

objective:
-

scope:
- 可改：
  -
- 不要改：
  -

contracts_to_preserve:
- selected_rule_ids 必须继续传到后端。
- scoped_customer_rule_ids / record_rule_map 不能丢。
- data_gap 不算合规。
- not_applicable 不进合格率分母。
- 30 条合成病历 Golden Set 不能宣称真实客户样本准确率。
- 不导出 prompt/raw_response/embedding/full text。

done_when:
- 实现完成。
- 精确列出改动文件。
- 跑完 required_checks 或说明阻塞。
- 输出 COMPLETE_REPORT。
- 不自行扩大范围。

required_checks:
- npm run check:encoding
- npm run lint
- npm run type-check
- npm run test:unit
- 从 backend 目录运行相关 pytest。

output_format:
- 必须按 COMPLETE_REPORT 格式回复。
```

## 2. ACK

```text
[MEDQC-AGENT-MSG v1]

type: ACK
from:
to: coordinator
task_id:

understood_scope:
-

claimed_files:
-

risks_or_questions:
-

will_not_touch:
-
```

## 3. COMPLETE_REPORT

```text
[MEDQC-AGENT-MSG v1]

type: COMPLETE_REPORT
from:
to: coordinator
task_id:

status: completed | partial | blocked

changed_files:
-

behavior_changes:
-

contracts_checked:
- selected_rule_ids 未改动：是/否/不适用
- scoped_customer_rule_ids 未改动：是/否/不适用
- record_rule_map 未改动：是/否/不适用
- data_gap 口径未破坏：是/否/不适用
- not_applicable 口径未破坏：是/否/不适用
- 未导出 prompt/raw_response/embedding/full text：是/否/不适用

checks_run:
- command:
  result: passed | failed | timeout | not_run
  notes:

known_risks:
-

needs_review:
-

next_recommended_task:
-
```

## 4. REVIEW_REQUEST

```text
[MEDQC-AGENT-MSG v1]

type: REVIEW_REQUEST
from: coordinator
to:
task_id:

review_target:
- thread_id:
- branch:
- commit_or_worktree:
- changed_files:

review_focus:
- 是否破坏 0609 scoped run。
- 是否引入敏感字段导出。
- 是否有宽 any / @ts-ignore。
- 是否包含无关 lint 格式化。
- 是否满足 UTF-8 LF。
- 验证命令是否可信。

expected_output:
- blocking_findings
- non_blocking_findings
- required_rework
- accept_or_reject
```

## 5. ACCEPT

```text
[MEDQC-AGENT-MSG v1]

type: ACCEPT
from: coordinator
to:
task_id:

decision: accepted

accepted_scope:
-

allowed_next_actions:
- 精确 staging。
- 中文 commit。
- 或等待 NEXT_ASSIGN。

notes:
-
```

## 6. REWORK

```text
[MEDQC-AGENT-MSG v1]

type: REWORK
from: coordinator
to:
task_id:

decision: rejected

blocking_findings:
-

required_changes:
-

do_not_change:
-

required_checks:
-

output_format:
- 修复后重新输出 COMPLETE_REPORT。
```

## 7. NEXT_ASSIGN

```text
[MEDQC-AGENT-MSG v1]

type: NEXT_ASSIGN
from: coordinator
to:
task_id:

previous_task:
- accepted_task_id:
- accepted_commit:

objective:
-

scope:
- 可改：
  -
- 不要改：
  -

contracts_to_preserve:
-

required_checks:
-
```

## 8. 给复杂 worktree agent 的同步请求

```text
[MEDQC-AGENT-MSG v1]

type: TASK_ASSIGN
from: coordinator
to: worktree-agent
task_id: sync-worktree-state

objective:
- 暂停新增实现，只输出当前 worktree 的同步摘要。

scope:
- 不改代码。
- 只读检查当前分支、HEAD、git status、已修改/新增文件、验证缺口。

required_output:
- 当前分支、HEAD、git status --short。
- 已修改/新增文件清单，按后端、前端、迁移、测试分类。
- 哪些改动会影响 0609 质控集验证链路。
- 需要 0609 验证 agent 回答的具体问题。
- 当前最小可提交边界。
- 还缺哪些验证命令。
- 哪些文件已经改过、后续不希望另一个 agent 同时改。
```

## 9. 给 0609 验证 agent 的同步请求

```text
[MEDQC-AGENT-MSG v1]

type: TASK_ASSIGN
from: coordinator
to: domain-validation-agent
task_id: sync-lx0609-validation-contract

objective:
- 从 LX0609 验证角度给出 V3.6 P1 任务链路的约束。

scope:
- 不改代码。
- 只输出验证约束、风险和最小验收命令。

required_output:
- 0609 scoped run 必须保住哪些字段和行为。
- 30 条合成病历 Golden Set 接入任务链路时，任务详情、导出、状态统计必须展示哪些字段。
- data_gap / not_applicable / technical_error / not_executed 的验收口径。
- 哪些接口字段、文件或行为不能被 P1 worktree 改坏。
- 0609 侧建议的最小验证命令。
- 当前能否接受任务级 rule_count 显示底层执行规则数，同时额外展示客户质控点数。
```
