# 任务详情账号隔离 Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 账号切换、注销或卸载时，任务抽屉不得继续显示上一账号的详情或接收旧读取结果。

**Architecture:** 复用 TaskDetailDrawer 已有 clearDetail 与请求序号失效机制；账号和角色上下文变化触发清空，并只在新账号有效时重新读取。不改变后端授权、任务处理状态或质控引擎。

**Tech Stack:** Vue、Pinia、TypeScript、Vitest。

## 证据与边界

- `src/components/qc/TaskDetailDrawer.vue` 当前末尾watch只观察props；详情、运行和作业的迟到校验未单独核对账号。
- 两个账号都在received页时runScope均为assigned，不能用scope相等证明账号相同。
- 本批只修生命周期隔离，不追加自动轮询，不确定重抽样政策，不据此提升PRD整项。

## 实施

1. 在 `tests/unit/components/qc/TaskDetailDrawer.spec.ts`（以实际现有测试路径为准）补账号切换迟到读取、注销和卸载反例。
2. 在TaskDetailDrawer观察账号ID和角色上下文，先清空并失效旧序号；无有效账号不读取，有效账号重新按现有入口加载。
3. 卸载调用现有清理，不新增并行状态owner。
4. 主协调审查diff，串行运行聚焦Vitest、type-check、只读ESLint及暂存编码检查，独立中文提交。

## 重抽样分支

已向用户询问是否仅未分配/未执行任务可原任务重抽样，或者允许撤销分配，或者仅复制新任务。未确认前不执行病例删除、分配撤销或重抽样写入。只读核对结论另行记录。

### 已核实的重抽样约束

- 原始逐模块对照表只要求编辑任务，未定义抽样后的替换行为；不能从原文推导应删除既有样本。
- `task_sampling_persistence.py` 对sampling状态只重放现有样本；`task_edit_service.py` 仅空draft开放完整规划。
- `task_qc_run_service.py` 和同步服务允许创建人在sampling状态操作，所以未分配不代表无执行或同步历史。
- task_record关联ID被人工缺陷、病历审核和同步事实引用，不能只删除任务病例行后重新插入。
- 若用户选择原任务重抽样，需要独立命令、任务行锁、配置CAS、无下游事实守卫、抽样修订历史及幂等回执；不能简单放宽现有draft PUT。
- 前端当前由editable_fields推断整组规划编辑，不能给sampling任务加单个字段就开放整组控件。需明确重抽样能力与影响确认，不由页面猜测状态。
