# LX0609 资料链与 LLM 调用收敛 Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 将原“大范围资料输入与 LLM 扩容计划”拆成两个可独立验收的小闭环，避免建立第二套 Native 证据来源。

**Architecture:** `EvidenceReadSession → EvidenceSnapshot → EvidenceMaterialStore` 是 LX0609 Native 的唯一权威资料链；Scene Bundle 只负责病例场景和展示锚点，旧 `evidence_payload` 仅保留兼容职责。先完成资料链收敛，再在单个规则族内验证事件级 LLM 复用。

**Tech Stack:** Python 3.10、FastAPI、SQLAlchemy/PostgreSQL、pytest、LX0609 Native Engine。

---

## 修订状态

原计划已被以下两个计划取代，不得继续执行原 Task 3～7：

1. [LX0609 EvidenceMaterialStore 完整资料链收敛计划](./2026-08-03-lx0609-evidence-materialstore-convergence.md)
2. [LX0609 会诊族事件级 LLM 试点计划](./2026-08-03-lx0609-consultation-event-llm-pilot.md)

## 不变的架构约束

- 不把 Domain Bundle 或 `programmatic_timeline` 建成第二套 Native 权威输入。
- 不修改 Canonical Envelope、数据库结果表和单一结果 API。
- 不新增 `decision_mode`；继续使用现有 `decision_authority` 和 `max_llm_calls_per_rule`。
- `semantic_fact_contract` 只能扩展现有 Rule Contract。
- `event_id` 只属于一次病例执行的运行时数据。
- 不一次改造手术、会诊、病程、输血等多个规则族。
- 不预设把医嘱读取上限提高到 1000；先统计，再按证据调整。
- 两份真实病例只承担功能回归，不能用于 P95、重复一致率或 off-focus 统计。

## 执行顺序

先完整执行并验收资料链计划。只有资料完整、规则实际输入路径清楚、真实病例功能回归通过后，才允许启动会诊族 LLM 试点。
