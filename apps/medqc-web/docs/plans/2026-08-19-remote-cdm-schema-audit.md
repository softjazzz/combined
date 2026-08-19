# Remote CDM Schema Audit Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 提供一个可在客户机上只读运行的源库盘点脚本，一次输出源表结构、正式同步映射、关键字段覆盖、索引/主键和无隐私数据的资料完整性摘要。

**Architecture:** 新增独立 CLI，直接读取既有 `REMOTE_DB_URL`、`remote_schema` 与 `list_sync_tables()`，以只读事务查询 PostgreSQL 元数据。默认只做元数据和规则来源覆盖；可选数据概要模式只输出行数、空值计数与时间水位，不输出患者、住院号、文书正文或任意原始记录。报告以 JSON 为机器可读主产物，同时输出 Markdown 便于现场粘贴回传。

**Tech Stack:** Python 3.10、psycopg2、既有 `etl_sync` 同步目录与 LX0609 `source_registry`、pytest。

---

### Task 1: 冻结只读审计合同

**Files:**

- Create: `backend/tests/unit/test_audit_remote_cdm_schema.py`
- Create: `backend/scripts/audit_remote_cdm_schema.py`

**Step 1: Write the failing test**

```python
def test_metadata_mode_uses_read_only_transaction_and_never_queries_patient_rows():
    report = audit_remote_schema(connection=fake_connection(), mode="metadata")

    assert report["read_only"] is True
    assert report["patient_data_returned"] is False
    assert "information_schema.columns" in fake_connection().executed_sql
    assert "SELECT *" not in fake_connection().executed_sql
```

**Step 2: Run test to verify it fails**

Run: `python -m pytest backend/tests/unit/test_audit_remote_cdm_schema.py -q`

Expected: FAIL because the CLI module and `audit_remote_schema` do not exist.

**Step 3: Write minimal implementation**

Create a CLI with these arguments:

```text
--remote-url <postgres-url>       # optional; otherwise use existing REMOTE_DB_URL
--remote-schema public            # optional; otherwise load existing sync config
--mode metadata|coverage|profile  # default metadata
--output-dir <path>               # default backend/reports/remote-schema-audit
--statement-timeout-ms <integer>  # default 30000
```

It must issue `BEGIN READ ONLY`, `SET LOCAL statement_timeout`, query only PostgreSQL catalog / information schema in `metadata` mode, and reject output paths outside the requested directory. It must never log the connection URL or raw source rows.

**Step 4: Run test to verify it passes**

Run: `python -m pytest backend/tests/unit/test_audit_remote_cdm_schema.py -q`

Expected: PASS.

**Step 5: Commit**

```bash
git add backend/scripts/audit_remote_cdm_schema.py backend/tests/unit/test_audit_remote_cdm_schema.py
git commit -m "新增源库CDM只读盘点脚本"
```

### Task 2: 输出同步目录与客户源表差异

**Files:**

- Modify: `backend/scripts/audit_remote_cdm_schema.py`
- Modify: `backend/tests/unit/test_audit_remote_cdm_schema.py`

**Step 1: Write the failing test**

```python
def test_coverage_mode_reports_actual_source_table_and_required_field_gaps(monkeypatch):
    monkeypatch.setattr(module, "list_sync_tables", lambda: [
        {"name": "consent_form", "source_table": "bloodtrans_inform_consent",
         "key_fields": ["patient_id", "visit_id", "document_id"]},
    ])
    report = audit_remote_schema(connection=fake_connection_without_document_id(), mode="coverage")

    row = report["sync_table_coverage"][0]
    assert row["source_table"] == "bloodtrans_inform_consent"
    assert row["status"] == "field_gap"
    assert row["missing_identity_fields"] == ["document_id"]
```

**Step 2: Run test to verify it fails**

Run: `python -m pytest backend/tests/unit/test_audit_remote_cdm_schema.py -k coverage -q`

Expected: FAIL because coverage rows are not yet computed.

**Step 3: Write minimal implementation**

Use the current `list_sync_tables()` result, including persisted overrides, to report each enabled logical table:

- local logical name, configured physical `source_table`, procedure and incremental strategy;
- source table existence, all columns, primary key and indexes;
- three-coordinate fields (`patient_id`, `visit_id`, optional configured institute mapping), configured key fields and time/watermark candidate availability;
- a status limited to `ready` / `source_table_missing` / `field_gap` / `disabled`.

Do not infer a replacement physical table. Similar-name candidates may be listed as advisory metadata only, never written back to configuration.

**Step 4: Run test to verify it passes**

Run: `python -m pytest backend/tests/unit/test_audit_remote_cdm_schema.py -k coverage -q`

Expected: PASS.

**Step 5: Commit**

```bash
git add backend/scripts/audit_remote_cdm_schema.py backend/tests/unit/test_audit_remote_cdm_schema.py
git commit -m "补充源表同步映射覆盖审计"
```

### Task 3: 输出LX0609正式来源覆盖和可选数据概要

**Files:**

- Modify: `backend/scripts/audit_remote_cdm_schema.py`
- Modify: `backend/tests/unit/test_audit_remote_cdm_schema.py`
- Modify: `backend/app/services/luxian_0609/source_registry.py` only if it lacks a machine-readable formal source export helper; otherwise do not modify it.

**Step 1: Write the failing test**

```python
def test_formal_rule_source_gap_is_reported_without_claiming_rule_is_broken(monkeypatch):
    monkeypatch.setattr(module, "formal_source_requirements", lambda: {
        "LX0609-071": ("physician_change_event", "inpat_nondrug_order"),
    })
    report = audit_remote_schema(connection=fake_connection_without_change_event(), mode="coverage")

    assert report["formal_source_coverage"]["LX0609-071"]["status"] == "source_capability_gap"
```

**Step 2: Run test to verify it fails**

Run: `python -m pytest backend/tests/unit/test_audit_remote_cdm_schema.py -k formal -q`

Expected: FAIL because formal-source coverage is not included.

**Step 3: Write minimal implementation**

Report each formal source as `available`, `unavailable`, or `not_proven`; show the associated rule IDs and fallback sources. In `profile` mode only, emit aggregate, non-PII fields for tables with known supported time columns:

```text
estimated_row_count
exact_count (only when --exact-count is explicitly supplied)
identity_complete_count
latest_business_time
candidate_time_column
```

For very large tables use `pg_class.reltuples` by default. Exact `COUNT(*)` must be opt-in per table or globally with `--exact-count`, and the report must label it as an expensive scan.

**Step 4: Run test to verify it passes**

Run: `python -m pytest backend/tests/unit/test_audit_remote_cdm_schema.py -q`

Expected: PASS.

**Step 5: Commit**

```bash
git add backend/scripts/audit_remote_cdm_schema.py backend/tests/unit/test_audit_remote_cdm_schema.py backend/app/services/luxian_0609/source_registry.py
git commit -m "增加正式质控来源覆盖盘点"
```

### Task 4: 固化报告格式和客户机运行说明

**Files:**

- Create: `docs/operations/remote-cdm-schema-audit.md`
- Modify: `backend/scripts/audit_remote_cdm_schema.py`
- Test: `backend/tests/unit/test_audit_remote_cdm_schema.py`

**Step 1: Write the failing test**

```python
def test_report_writes_json_and_markdown_without_raw_patient_values(tmp_path):
    paths = write_report(sample_report(), output_dir=tmp_path)

    assert paths.json.exists()
    assert paths.markdown.exists()
    assert "patient_name" not in paths.markdown.read_text(encoding="utf-8")
```

**Step 2: Run test to verify it fails**

Run: `python -m pytest backend/tests/unit/test_audit_remote_cdm_schema.py -k report -q`

Expected: FAIL because report writers do not exist.

**Step 3: Write minimal implementation**

Produce timestamped JSON and Markdown files with these sections:

```text
运行参数与只读保证
总览（已配置、可执行、缺表、缺字段）
同步目录差异
LX0609正式来源覆盖
可选数据概要
部署阻断项与下一步
```

Document an exact customer-machine PowerShell invocation. The report must redact passwords from every connection string and must not include raw identifiers, patient names, document text, or sampled rows.

**Step 4: Run test to verify it passes**

Run: `python -m pytest backend/tests/unit/test_audit_remote_cdm_schema.py -q`

Expected: PASS.

**Step 5: Commit**

```bash
git add docs/operations/remote-cdm-schema-audit.md backend/scripts/audit_remote_cdm_schema.py backend/tests/unit/test_audit_remote_cdm_schema.py
git commit -m "补充客户源库盘点运行说明"
```

### Task 5: 完成验证

**Files:**

- Verify only: files from Tasks 1–4

**Step 1: Run focused verification**

Run:

```bash
python -m pytest backend/tests/unit/test_audit_remote_cdm_schema.py -q
python -m ruff check backend/scripts/audit_remote_cdm_schema.py backend/tests/unit/test_audit_remote_cdm_schema.py
python -m compileall -q backend/scripts/audit_remote_cdm_schema.py
git diff --check
```

Expected: all commands pass.

**Step 2: Perform a local metadata-only smoke run**

Run:

```powershell
Set-Location D:\medqc\medqc-web-customer-R24.x\backend
python .\scripts\audit_remote_cdm_schema.py --mode metadata --output-dir .\reports\remote-schema-audit
```

Expected: report files are produced; no tables are written, and the report contains no raw patient data.

**Step 3: Commit**

```bash
git add backend/scripts/audit_remote_cdm_schema.py backend/tests/unit/test_audit_remote_cdm_schema.py docs/operations/remote-cdm-schema-audit.md
git commit -m "完成源库CDM盘点工具"
```
