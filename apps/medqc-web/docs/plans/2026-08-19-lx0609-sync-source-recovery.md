# LX0609 同步资料恢复 Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 让客户机能从已验证存在的源表恢复 LX0609 正式规则所需资料同步，并避免可选来源缺失时继续使用旧 Bundle。

**Architecture:** 数据库保存的同步开关继续只约束手工同步，避免静默覆盖医院的人工配置；一键“同步并质控”由服务端固定选择受控的 `luxian_0609_formal` 资料集，不接受客户端自定义表范围。病例集同步保留现有“任一已选明细来源不可用就不刷新 Bundle”的失败关闭行为，避免继续使用旧 Bundle。

**Tech Stack:** FastAPI、SQLAlchemy、PostgreSQL 配置表、pytest。

---

### Task 1: 冻结一键同步并质控的正式资料集合同

**Files:**

- Modify: `backend/app/services/etl_sync.py`
- Test: `backend/tests/unit/test_sync_consistency.py`

**Step 1: Write the failing test**

覆盖“一键质控使用固定正式资料集、不能被旧保存配置缩减、不能由请求自定义表或分组”。

**Step 2: Run test to verify it fails**

Run: `python -m pytest backend/tests/unit/test_sync_consistency.py -k recommended_luxian_sync_profile -q`

Expected: FAIL，因为当前一键请求仍会使用旧保存配置筛选出的表。

**Step 3: Write minimal implementation**

定义正式资料集，并只在 `auto_qc_after_sync=true` 时由路由显式传入；不得把医院手动关闭的表自动改回开启。

**Step 4: Run test to verify it passes**

Run: `python -m pytest backend/tests/unit/test_sync_consistency.py -k recommended_luxian_sync_profile -q`

Expected: PASS。

### Task 2: 保持 Bundle 失败关闭语义

**Files:**

- Test: `backend/tests/unit/test_case_set_sync_service.py`

**Step 1: Write the failing test**

覆盖“任一已选明细表不可用时不刷新 Bundle”，避免本地文书已更新但证据 Bundle 继续读取旧快照。

**Step 2: Run test to verify it fails**

Run: `python -m pytest backend/tests/unit/test_case_set_sync_service.py -q`

Expected: PASS，当前失败关闭合同不在本闭环中放松。

**Step 3: Write minimal implementation**

不修改实现；客户审计已证明本次正式资料集所涉物理表存在。源表缺失属于后续客户映射能力问题，不能用“可选”掩盖。

**Step 4: Run test to verify it passes**

Run: `python -m pytest backend/tests/unit/test_case_set_sync_service.py -q`

Expected: PASS。

### Task 3: 校准输血同意书与检查主表的客户源映射

**Files:**

- Modify: `backend/app/services/etl_sync.py`
- Modify: `backend/app/database/models/cdm.py`
- Test: `backend/tests/unit/test_sync_consistency.py`

**Step 1: Write the failing test**

以客户已审计的字段冻结：`bloodtrans_inform_consent` 映射为 `consent_form`，`exam_id` 是检查主表唯一标识。

**Step 2: Run test to verify it fails**

Run: `python -m pytest backend/tests/unit/test_sync_consistency.py -k 'consent_form or exam_master' -q`

Expected: FAIL，如有遗漏。

**Step 3: Write minimal implementation**

只补经过客户源审计确认的别名与结构化字段；不得捏造 `physician_change_event`。

**Step 4: Run test to verify it passes**

Run: `python -m pytest backend/tests/unit/test_sync_consistency.py -k 'consent_form or exam_master' -q`

Expected: PASS。

### Task 4: 端到端回归与客户机复验指引

**Files:**

- Modify: `docs/operations/remote-cdm-schema-audit.md`
- Test: `backend/tests/unit/test_sync_consistency.py`
- Test: `backend/tests/unit/test_case_set_sync_service.py`

**Step 1: Run focused regression**

Run: `python -m pytest backend/tests/unit/test_sync_consistency.py backend/tests/unit/test_case_set_sync_service.py backend/tests/unit/test_custom_qc_sample_pool_service.py -q --disable-warnings`

Expected: PASS。

**Step 2: Document customer verification**

记录应用推荐资料集后重跑只读审计的目标：已验证 LX0609 来源为 `available`；独立医师变更事件仍明确显示为不支持/资料不足。

**Step 3: Commit**

Run: `git add <only scoped files> && git commit -m "fix: 恢复LX0609正式资料同步"`
