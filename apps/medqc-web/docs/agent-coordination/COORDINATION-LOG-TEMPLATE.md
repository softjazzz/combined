# <YYYY-MM-DD> <任务名> 多 Agent 协调日志

本模板用于记录多 agent 协作中的关键交接、决策、验收和风险。日志只保存结构化摘要，不保存完整聊天流水、长 diff、工具输出全文或敏感原文。

## Participants

- Coordinator Agent:
- Worktree Agent:
  - thread_id:
  - cwd:
- Domain Validation Agent:
  - thread_id:
  - cwd:
- Review Agent:
  - thread_id:
  - cwd:

## Task

- task_id:
- objective:
- repo: `D:\LLM\LX888\apps\medqc-web`
- related_threads:
  - thread_id:
- related_branch:
- related_commits:
  - commit:
- related_docs:
  - doc:

## Scope

### In Scope

-

### Out of Scope

-

### File Ownership

| File or module | Owner | Allowed changes | Notes |
| -------------- | ----- | --------------- | ----- |
|                |       |                 |       |

## Timeline

### 1. TASK_ASSIGN

- time:
- message_id:
- from:
- to:
- summary:
- ## assigned_scope:
- ## contracts_to_preserve:

### 2. ACK

- time:
- message_id:
- from:
- to:
- summary:
- ## claimed_files:
- ## risks_or_questions:

### 3. WORKING Updates

| Time | Agent | Summary | Blockers |
| ---- | ----- | ------- | -------- |
|      |       |         |          |

### 4. COMPLETE_REPORT

- time:
- message_id:
- from:
- to:
- status: completed | partial | blocked
- ## changed_files:
- ## behavior_changes:
- checks_run:
  - command:
    result:
    notes:
- ## known_risks:

### 5. REVIEW

- time:
- reviewer:
- review_target:
- ## blocking_findings:
- ## non_blocking_findings:
- ## required_rework:
- decision: accept | rework | blocked

### 6. ACCEPT or REWORK

- time:
- message_id:
- from:
- to:
- decision:
- rationale:
- ## next_action:

## Contracts Preserved

| Contract                                                                         | Status  | Evidence | Notes |
| -------------------------------------------------------------------------------- | ------- | -------- | ----- |
| `selected_rule_ids` continues to reach backend                                   | unknown |          |       |
| `scoped_customer_rule_ids` is preserved                                          | unknown |          |       |
| `record_rule_map` is preserved                                                   | unknown |          |       |
| `customer_rule_count` and `execution_rule_count` are distinguishable where shown | unknown |          |       |
| `data_gap` is not counted as compliant                                           | unknown |          |       |
| `not_applicable` is excluded from pass-rate denominator                          | unknown |          |       |
| `technical_error` is not shown as compliant                                      | unknown |          |       |
| `not_executed` is shown independently                                            | unknown |          |       |
| Sensitive fields are not exported or displayed                                   | unknown |          |       |

## Decisions

| Time | Decision | Rationale | Owner | Follow-up |
| ---- | -------- | --------- | ----- | --------- |
|      |          |           |       |           |

## Verification

### Commands Requested

```powershell
npm run check:encoding
npm run lint
npm run type-check
npm run test:unit
```

Backend checks should usually run from `D:\LLM\LX888\apps\medqc-web\backend`:

```powershell
python -m pytest tests\unit\test_qc_sample_pools_router.py -q --confcutdir=tests\unit
python -m py_compile app\routers\qc_sample_pools.py app\routers\qc_sichuan.py
```

### Commands Actually Run

| Command | Cwd | Result | Notes |
| ------- | --- | ------ | ----- |
|         |     |        |       |

### Encoding and Staging Checks

- `git diff --check`:
- `git diff --cached --check`:
- `npm run check:encoding`:
- direct UTF-8 without BOM / LF check:
- staged file whitelist:

## Residual Risks

-

## Not Allowed To Claim

- 30 条合成病历 Golden Set 不能宣称真实客户样本准确率。
- 没有真实病历人工标注，不能宣称真实样本 Golden Set 已完成。
- RQ 三进程没有跑通，不能宣称任务后台链路端到端完成。
- `type-check` 超时不能写成通过。
- `check:encoding` 扫描 0 个文件不能单独作为编码通过证据。

## Sensitive Data Notes

本日志不得保存以下内容：

- `prompt`
- `raw_response`
- `embedding`
- 完整病历全文
- 未脱敏患者姓名、证件号、电话、住址等个人信息
- 长 diff 或工具输出全文

如需引用真实样本，只记录脱敏 ID、结构化状态、规则编号、检查结论和缺失数据类型。

## Links

- Coordination rule: `docs/agent-coordination/MEDQC-MULTI-AGENT-WORKFLOW.md`
- Handoff template: `docs/agent-coordination/AGENT-HANDOFF-TEMPLATE.md`
- Source thread:
- Review thread:
- Commit:
