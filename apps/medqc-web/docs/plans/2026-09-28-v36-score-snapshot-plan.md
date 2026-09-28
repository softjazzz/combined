# 评分引用与只读快照 Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 补齐评分申诉依赖的真实结果引用、标准版本引用和服务端重算快照，不提前开放申诉写接口。

**Architecture:** 沿用 Canonical Envelope 与现有评分服务作为事实来源。标准在调用方 session 内精确读取，核对版本及默认状态；快照只读生成，不替代后续对象授权和申诉创建事务。

**Tech Stack:** Python、SQLAlchemy、pytest、Vue、TypeScript、Vitest。

## 1. 计分响应引用

- 修改 `backend/app/services/scoring_service.py` 及对应单元测试。
- 为成功响应增加可空的 `result_ref` 和 `standard_ref`，具体字段遵循 `2026-09-28-v36-appeal-score-reference-audit.md`。
- 先补完整引用、缺失引用和锚点冲突测试，再实现搬运。缺失引用不伪造，也不把合法只读分数变为零。
- 不要求 Canonical 规则版本与评分标准版本相等。

## 2. 标准读取与快照

- 修改 `backend/app/services/scoring_standard_service.py`，新增 `backend/app/services/appeal_score_snapshot_service.py` 和专属测试。
- 显式接收调用方 session，沿用场景锁先于标准行锁的顺序；核对标准 ID、版本、更新时间、场景、启用及默认状态。
- 使用已核实来源重新计分，不信任客户端分数，不提交或关闭调用方事务。
- 无新迁移，无真实数据库写入，无申诉创建接口。只读快照不宣称整个创建流程已经原子化。

## 3. 前端引用

- 修改 `src/api/scoring.ts`、现有 `CaseScorePanel.vue` 及其单测。
- 严格声明可缺引用，展示可信标准版本；历史响应继续正常只读展示。
- 不添加申诉按钮；病例或场景切换丢弃迟到响应，不用路由拼造引用。

## 4. 独立反例与审查

- 新增 `backend/tests/unit/test_appeal_score_reference_contract.py`。
- 覆盖版本及默认状态漂移、不同版本轴、同 session、无提交，以及不信任客户端数据。
- 第五代理只读审查锁顺序、来源校验、兼容性和未完成边界。各代理仅改各自文件，主协调独立检查关键 diff。

## 5. 集成门禁

- 聚焦 pytest 与变更 Python 文件 Ruff；Node 检查仅由主协调串行运行。
- 运行 `npm run type-check`、对应前端聚焦 `npm run test:unit -- --maxWorkers=1 --minWorkers=1`、只读全量 ESLint。
- 精确暂存本批文件后运行 `npm run check:encoding -- --staged`、`git diff --cached --check`，核对暂存名单，中文提交、不推送。
- 更新滚动计划与证据；本批前置能力不提升整项完成数。Goal 保持 4/10，直到原 PRD 整项验收成立。
