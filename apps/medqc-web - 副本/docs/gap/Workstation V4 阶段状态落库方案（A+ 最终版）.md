# Workstation V4 阶段状态落库方案（A+ 最终版）

## Summary

采纳 A+ 方向，并补齐 `unknown`、`queue_status_source`、`updated_by` 口径。  
本轮统一 4 条 workflow（`frontpage_generate / coding_qc / frontpage_qc / settlement_qc`）状态来源，避免前端写死和后端常量状态；使用 `run_id` + CAS 防止并发重入覆盖。

## Goals

- 为 `workstation-v4` 四个阶段提供单一、可追踪、跨会话一致的状态来源。
- 消除前端写死文案与后端固定常量 `queue_status`。
- 保证批量执行、单条执行、重复点击时状态不被旧请求覆盖。
- 在不引入异步任务队列的前提下，完成状态落库与读取口径统一。

## Scope

纳入本轮的 workflow：

- `frontpage_generate`
- `coding_qc`
- `frontpage_qc`
- `settlement_qc`

不在本轮范围内：

- 异步任务队列改造
- 新增独立状态查询分叉接口
- 改造 `mr / diagnosis / mr_surgery / mr_cost` 写入语义

## Key Changes

### 1. 状态总表与状态机

新增表：`qc.workflow_queue_state`

唯一键：

- `(workflow_type, visit_id)`

核心字段：

- `id`
- `workflow_type`
- `visit_id`
- `patient_id`
- `institute_id`
- `queue_status`：`unknown | pending | running | succeeded | failed`
- `queue_status_source`：`backfill | runtime`
- `run_id`：后端内部并发保护字段，不对前端暴露
- `last_error`
- `last_started_at`
- `last_finished_at`
- `last_success_at`
- `updated_at`
- `updated_by`

`updated_by` 固定口径：

- 回填写：`system_backfill`
- 运行时写：`runtime:<user_id>`
- 无用户上下文时：`runtime:anonymous`

建议索引：

- `ux_workflow_queue_state_workflow_visit(workflow_type, visit_id)` 唯一索引
- `ix_workflow_queue_state_workflow_status_updated(workflow_type, queue_status, updated_at)`
- `ix_workflow_queue_state_visit(visit_id)`

建议约束：

- `queue_status` 加 check constraint，仅允许 `unknown/pending/running/succeeded/failed`
- `queue_status_source` 加 check constraint，仅允许 `backfill/runtime`

### 2. 并发更新规则（CAS）

状态服务必须采用 compare-and-set 语义。

开始执行：

- 生成新的 `run_id`
- upsert 当前 `(workflow_type, visit_id)` 为 `running`
- 写入 `last_started_at`
- 清空 `last_error`
- `queue_status_source = runtime`

结束执行：

- 仅允许“请求携带的 `run_id` 与表中当前 `run_id` 相同”时更新状态
- 成功时写 `succeeded`
- 失败时写 `failed + last_error`
- 更新 `last_finished_at`
- 成功时额外写 `last_success_at`

拒绝覆盖规则：

- 若 `run_id` 不匹配，拒绝本次 finish 更新
- 只记 debug/info 日志，不抛业务错误
- 目的：防止旧请求晚返回覆盖新请求状态

### 3. 执行链路接入（四阶段全覆盖）

现有正式执行入口统一接入 `workflow_queue_state_service`：

- `frontpage_generate`：`POST /api/v1/frontpage/auto-generate-draft`
- `coding_qc`：`POST /api/v1/qc/coding-qc/check`
- `frontpage_qc`：`POST /api/v1/qc/formal-qc/validate`
- `settlement_qc`：`POST /api/medical-records/settlement/.../qc`

统一流程：

1. 进入执行前：`start_run(...)`
2. 成功结束：`finish_success(run_id, ...)`
3. 异常结束：`finish_failed(run_id, error, ...)`

要求：

- 不改变现有业务返回结构主干
- 不改变现有质控、通知、缺陷持久化职责
- 状态写入只作为统一状态源补充，不替代业务结果表

### 4. 回填策略（最近一次优先）

回填统一写 `queue_status_source = backfill`，目标是得到“最近一次已知稳定状态”，而不是“最近一次执行结果”。

回填规则：

- `frontpage_generate`
  - 取 `ai_frontpage_draft.updated_at` 最新记录
  - 存在则回填 `succeeded + last_success_at`
- `coding_qc`
  - 从 `qc_results` 中取 `record_id` 前缀为 `coding::{visit_id}` 的最新一条
  - 使用 `analysis_date`，无则退回 `created_at`
- `frontpage_qc`
  - 从 `qc_results` 中取 `record_id` 前缀为 `frontpage::{visit_id}` 的最新一条
- `settlement_qc`
  - 从 `qc_results` 中取 `record_id` 前缀为 `settlement::{visit_id}` 的最新一条

状态判定：

- 有最近稳定记录：`succeeded`
- 无历史且数据完整可判定：`pending`
- 数据异常、历史不可判定、回填过程缺关键字段：`unknown`

文档口径：

- 回填结果不是“最近一次执行结果”
- 回填只代表“系统当前能确认的最近稳定状态”

### 5. 读取统一（不新增分叉接口）

不新增 `queue-status/batch` 之类的新读取口径。  
直接在现有 `worklist` 与 `snapshot` 中统一返回：

- `queue_status`
- `queue_status_source`

后端改造要求：

- `worklist_service` 不再使用固定 `QUEUE_STATUS_LABELS` 直接回填状态
- `snapshot` 同步返回真实 `queue_status`
- 仅在状态表无记录时保留默认兜底文案

前端改造要求：

- `workstation-v4` 四阶段状态以后端 `queue_status` 为主
- 本地运行态仅在请求未返回前作瞬时覆盖
- 接口返回后立即以后端真实状态为准

### 6. 文案映射规范

前端按 `workflow_type + queue_status` 统一映射文案：

- `frontpage_generate`
  - `pending -> 待生成`
  - `running -> 生成中`
  - `succeeded -> 已生成`
  - `failed -> 生成失败`
  - `unknown -> 状态未知`
- `coding_qc`
  - `pending -> 待编码质控`
  - `running -> 质控中`
  - `succeeded -> 质控完成`
  - `failed -> 质控失败`
  - `unknown -> 状态未知`
- `frontpage_qc`
  - `pending -> 待首页质控`
  - `running -> 质控中`
  - `succeeded -> 质控完成`
  - `failed -> 质控失败`
  - `unknown -> 状态未知`
- `settlement_qc`
  - `pending -> 待结算清单质控`
  - `running -> 质控中`
  - `succeeded -> 质控完成`
  - `failed -> 质控失败`
  - `unknown -> 状态未知`

## Public API / Type Changes

保持现有路径不变：

- `/api/v1/workstation/*/worklist`
- `/api/v1/workstation/*/snapshot`

返回体新增或稳定字段：

- `queue_status`
- `queue_status_source`

前端类型新增：

- `QueueStatusCode = 'unknown' | 'pending' | 'running' | 'succeeded' | 'failed'`
- `QueueStatusSource = 'backfill' | 'runtime'`

说明：

- `run_id` 不对前端暴露，仅后端内部使用

## Sorting Strategy

若状态表有记录，worklist 默认排序建议优先按状态优先级，再按时间倒序：

- `running`
- `failed`
- `pending`
- `succeeded`
- `unknown`

同级内再按：

- `updated_at desc`

目的：

- 正在执行与失败项优先暴露
- 已完成项自然下沉
- 未知项保留但不压过显式失败

## Implementation Plan

### Phase 1. 数据库与服务层

- 新增 Alembic migration：创建 `qc.workflow_queue_state`
- 新增 `workflow_queue_state_service`
- 实现：
  - `start_run(...)`
  - `finish_success(...)`
  - `finish_failed(...)`
  - `backfill_from_existing_data(...)`

### Phase 2. 执行链路接入

- 接入首页生成路由
- 接入编码质控路由
- 接入首页质控路由
- 接入结算质控路由

### Phase 3. worklist / snapshot 读取改造

- `worklist_service` 读取状态表
- `snapshot` 返回状态字段
- 删除或收敛常量状态依赖

### Phase 4. 前端状态显示统一

- V4 阶段状态按状态码映射
- 减少或删除前端写死兜底文案逻辑
- 请求进行中可短暂显示本地运行态，接口回包后切回真实状态

## Test Plan

### 1. 并发重入

- 同一 `visit_id + workflow_type` 连续触发两次
- 旧执行晚返回不能覆盖新执行状态
- 验证 CAS：错误 `run_id` 的 finish 更新被拒绝

### 2. 回填准确性

- 最近记录优先，不允许“存在即成功”
- 数据异常路径落到 `unknown`
- `updated_by` 与 `queue_status_source` 按规范写入

### 3. 接口一致性

- 四个 workflow 的 worklist / snapshot 都返回真实 `queue_status + queue_status_source`
- 前端阶段状态刷新后保持一致，不回退为写死文案

### 4. 回归

- 批量与单条执行保持原行为
- 详情联动不回归
- 通知、缺陷、质控结果持久化不回归
- 不新增读取口径分叉接口

## Risks

- 若部分历史数据时间字段不完整，回填会落到 `unknown`
- 若某些执行路由提前 return 或异常分支未接 finish，可能遗留 `running`
- 前端若仍保留强写死文案，会覆盖真实状态展示

## Assumptions

- 本轮只做“状态落库 + 状态读取统一”，不引入异步任务队列
- `unknown` 仅用于数据不足、回填异常、历史不可判定，不作为正常业务终态
- 文案映射由前端按 `workflow + 状态码` 统一处理
