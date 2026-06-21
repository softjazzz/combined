# MedQC 多 Agent 协作规则

本文档定义 `medqc-web` 多个 Codex agent 并行工作时的共同规则。目标是让协调、开发、验证、审查之间有稳定交接格式，避免重复改同一文件、误判验收状态或破坏 0609 质控集契约。

## 适用范围

- 仓库：`D:\LLM\LX888\apps\medqc-web`
- Codex worktree：同一仓库派生出的 `.codex\worktrees\*\LX888\apps\medqc-web`
- 典型协作场景：
  - 复杂 worktree 实现 agent 与领域验证 agent 并行工作。
  - 主 agent 在开发 agent 完成后审查，再下达下一步任务。
  - 0609 质控集、V3.6 任务链路、任务详情、导出、证据链等共享契约需要同步。

## 角色

### Coordinator Agent

唯一协调者。负责读线程状态、派单、压缩上下文、裁决文件归属、发起 review、决定 `ACCEPT` 或 `REWORK`，并在通过后下达下一张任务。

Coordinator Agent 不应在未声明的情况下直接抢开发 agent 的文件，也不应让两个开发 agent 自由互相改同一批文件。

### Worktree Agent

负责复杂 worktree 内的实现。必须按 `TASK_ASSIGN` 的 scope 工作，完成后只能声明 `ready for review`，不能自行宣布最终完成。

### Domain Validation Agent

负责领域口径验证，例如 LX0609 scoped run、Golden Set、状态口径、规则映射、验证报告。默认不接管复杂 worktree 的 UI 或任务系统实现。

### Review Agent

可选。负责独立代码审查或验收复核。输出必须区分 blocking findings、non-blocking findings 和 residual risks。

## 基本原则

- 开发 agent 只能声明 `ready for review`，最终是否完成由 Coordinator Agent 判定。
- 共享文件必须先声明 ownership，再修改。
- 不使用 `git add .`。
- 不恢复用户或其他 agent 的无关改动。
- 不把 lint 自动格式化的无关文件带入提交。
- UTF-8 without BOM，LF。
- commit message 使用中文。
- 不新增 `.vue.ts` mirror 文件。
- 不用宽泛 `any` 或 `@ts-ignore` 绕过类型边界。
- `npm run check:encoding` 可能只检查 staged 文件甚至显示 0 个文件；关键文件需要额外做 BOM/CRLF 直接检查。
- `npm run lint` 可能格式化无关 Vue 文件；提交前必须按任务白名单恢复无关格式化噪音。

## 消息状态机

```text
TASK_ASSIGN -> ACK -> WORKING -> COMPLETE_REPORT -> REVIEW -> ACCEPT / REWORK -> NEXT_ASSIGN
```

含义：

- `TASK_ASSIGN`：Coordinator Agent 下达任务。
- `ACK`：开发或验证 agent 确认范围、文件 ownership、阻塞点。
- `WORKING`：agent 执行中，可发送短状态更新。
- `COMPLETE_REPORT`：agent 完成当前任务并请求审查。
- `REVIEW`：Coordinator Agent 或 Review Agent 检查实现和验证证据。
- `ACCEPT`：通过，可提交或进入下一步。
- `REWORK`：未通过，必须按返工单修复。
- `NEXT_ASSIGN`：上一任务收口后下达新任务。

## 通用消息头

所有跨 agent 消息使用以下头部：

```text
[MEDQC-AGENT-MSG v1]

message_id:
from:
to:
type:
task_id:
repo:
thread_id:
related_threads:
```

字段说明：

- `message_id`：建议使用日期加序号，例如 `20260621-001`。
- `type`：只能使用本文档定义的消息类型。
- `task_id`：稳定任务标识，例如 `v36-p1-task-export`。
- `thread_id`：接收方线程 ID。
- `related_threads`：需要同步的其他线程 ID。

## TASK_ASSIGN

Coordinator Agent 下达任务时必须说明目标、范围、文件归属、保留契约、完成条件和检查命令。

```text
[MEDQC-AGENT-MSG v1]

message_id: 20260621-001
from: coordinator
to: worktree-agent
type: TASK_ASSIGN
task_id: v36-p1-task-filters-export
repo: D:\LLM\LX888\apps\medqc-web
thread_id: 019ee423-37f2-7f03-afa0-e5db17e90c90
related_threads:
- 019ecfed-6c4b-7c51-b7ff-75298e957902

objective:
- 收口 V3.6 P1 任务列表筛选、导出、队列提示。

scope:
- 可改：
  - backend/app/routers/tasks.py
  - backend/app/services/task_export_service.py
  - src/api/tasks.ts
  - src/views/dashboard/tasks/MyTasksView.vue
  - src/views/dashboard/tasks/AllTasksView.vue
- 不要改：
  - backend/app/routers/qc_sample_pools.py
  - backend/app/routers/qc_sichuan.py
  - src/views/workstation-v4/customer-sample-validation/*

contracts_to_preserve:
- selected_rule_ids 必须继续传到后端。
- scoped_customer_rule_ids / record_rule_map 不能丢。
- data_gap 不算合规。
- not_applicable 不进合格率分母。
- 30 条合成病历 Golden Set 不能宣称真实客户样本准确率。

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

## ACK

接收任务后，agent 必须先确认理解，不应直接开始大改。

```text
[MEDQC-AGENT-MSG v1]

type: ACK
from:
to:
task_id:

understood_scope:
- ...

claimed_files:
- ...

risks_or_questions:
- ...

will_not_touch:
- ...
```

## COMPLETE_REPORT

开发 agent 完成后必须输出完整报告。报告不等于最终完成，只是请求审查。

```text
[MEDQC-AGENT-MSG v1]

type: COMPLETE_REPORT
from:
to: coordinator
task_id:

status: completed | partial | blocked

changed_files:
- backend/app/routers/tasks.py
- src/api/tasks.ts

behavior_changes:
- 增加任务列表导出接口。
- 增加任务详情队列状态提示。

contracts_checked:
- selected_rule_ids 未改动：是/否/不适用
- scoped_customer_rule_ids 未改动：是/否/不适用
- record_rule_map 未改动：是/否/不适用
- data_gap 口径未破坏：是/否/不适用
- not_applicable 口径未破坏：是/否/不适用
- 未导出 prompt/raw_response/embedding/full text：是/否/不适用

checks_run:
- command: npm run lint
  result: passed | failed | timeout | not_run
  notes:
- command: npm run type-check
  result: passed | failed | timeout | not_run
  notes:

known_risks:
- ...

needs_review:
- ...

next_recommended_task:
- ...
```

## REVIEW_REQUEST

Coordinator Agent 发起审查时使用。

```text
[MEDQC-AGENT-MSG v1]

type: REVIEW_REQUEST
from: coordinator
to: review-agent
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

## ACCEPT

审查通过后由 Coordinator Agent 发送。

```text
[MEDQC-AGENT-MSG v1]

type: ACCEPT
from: coordinator
to:
task_id:

decision: accepted

accepted_scope:
- ...

allowed_next_actions:
- 精确 staging。
- 中文 commit。
- 或等待 NEXT_ASSIGN。

notes:
- ...
```

## REWORK

审查未通过时必须给出具体返工项。

```text
[MEDQC-AGENT-MSG v1]

type: REWORK
from: coordinator
to:
task_id:

decision: rejected

blocking_findings:
- [P1] backend/app/routers/tasks.py 导出字段包含 raw_response，必须移除。

required_changes:
- 移除 raw_response / prompt / embedding / full_text。
- 补测试断言导出不包含这些字段。

do_not_change:
- 0609 scoped run 文件。

required_checks:
- ...

output_format:
- 修复后重新输出 COMPLETE_REPORT。
```

## NEXT_ASSIGN

只有上一任务 `ACCEPT` 后才能下达下一张开发任务。

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
- ...

scope:
- ...
```

## 0609 scoped run 共享契约

0609 相关功能必须保护以下行为：

- 前端保存并验证必须传递 `selected_rule_ids`。
- `selected_rule_ids` 只允许用于 `luxian_0609_qc_v1`。
- 后端必须把客户质控点映射到底层可执行规则。
- 后端必须保存 `record_rule_map`。
- 后端必须保存或传递 `scoped_customer_rule_ids`。
- 最终客户侧输出必须按 `scoped_customer_rule_ids` 过滤。
- 用户修改勾选质控点后，旧草稿必须过期，不能用旧病历配新规则保存或验证。
- 如果展示规则数量，必须区分：
  - `customer_rule_count`：用户勾选的 LX0609 客户质控点数。
  - `execution_rule_count`：底层实际执行规则数。
- 可以接受任务级 `rule_count` 暂时显示底层执行规则数，但必须在详情或报告中补充客户质控点数，避免误解为多跑客户点。

## 0609 状态口径

- `non_compliant`：缺陷或不符合。
- `compliant`：明确符合。
- `data_gap`：数据缺口，不算合规。
- `not_applicable`：不适用，不进入合格率分母，也不算缺陷。
- `technical_error`：技术错误，不能伪装成符合。
- `not_executed`：未执行，必须独立展示。
- `uncertain`：不确定，必须独立展示。

## Golden Set 命名与结论边界

- 30 条合成病历只能称为 `0609 合成病历 Golden Set` 或 `合成回归集`。
- 合成病历可以用于规则回归、端到端链路、证据链和 scoped run 验证。
- 合成病历不能宣称真实客户样本准确率。
- 没有真实病历人工标注时，不能宣称真实样本 Golden Set 已完成。
- 真实样本 Golden Set 必须来自客户真实病历，并有人工结论、证据片段、复核人和复核时间。

## 敏感字段和导出边界

导出、证据链、任务详情默认不得暴露：

- `prompt`
- `raw_response`
- `embedding`
- 完整病历全文
- 未脱敏原始工具上下文

推荐只展示结构化来源、状态、证据片段、缺失字段、规则版本、executor 类型和人工复核状态。

## 共享文件处理

以下文件经常成为冲突点，必须在 `TASK_ASSIGN` 中明确 ownership：

- `backend/app/routers/tasks.py`
- `backend/app/routers/qc_sample_pools.py`
- `backend/app/routers/qc_sichuan.py`
- `backend/app/services/sichuan_qc_service.py`
- `src/api/tasks.ts`
- `src/views/dashboard/tasks/MyTasksView.vue`
- `src/views/dashboard/tasks/AllTasksView.vue`
- `src/views/workstation-v4/customer-sample-validation/*`
- `tests/unit/views/workstation-v4/SyntheticCaseBuilder.spec.ts`
- `backend/tests/unit/test_qc_sample_pools_router.py`

如果两个 agent 都需要修改同一文件，Coordinator Agent 必须先拆出先后顺序或指定一个 agent 合并。

## 验收要求

开发 agent 的 `COMPLETE_REPORT` 必须说明：

- 改动文件。
- 行为变化。
- 验证命令和结果。
- 是否有 timeout。
- 是否有未验证风险。
- 是否影响 0609 scoped run。
- 是否存在未提交或未跟踪文件。

常用命令：

```powershell
npm run check:encoding
npm run lint
npm run type-check
npm run test:unit
```

后端单测通常从 `backend` 目录运行：

```powershell
cd backend
python -m pytest tests\unit\test_qc_sample_pools_router.py -q --confcutdir=tests\unit
python -m py_compile app\routers\qc_sample_pools.py app\routers\qc_sichuan.py
```

如果 full checks 太重，至少执行并报告：

```powershell
npm run check:encoding
npm run lint
git diff --check
```

## 不允许宣称的结论

- 未做 RQ 三进程端到端验收，不得宣称任务后台链路端到端完成。
- 只有合成病历通过，不得宣称真实客户样本准确率达标。
- 只有 UI 路径能点通，不得宣称后端 scoped run 已闭合。
- `type-check` 超时不得写成通过。
- `check:encoding` 扫描 0 个文件不得单独作为编码通过证据。
