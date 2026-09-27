import json

import pytest
import sqlalchemy as sa

from scripts.luxian_0609_identity_migration.service import (
    MigrationBlocked,
    _digest,
    apply_plan,
    build_plan,
    load_mapping,
)


def _item(rule_id="LX0609-001"):
    return {
        "rule_id": rule_id,
        "rule_code": rule_id,
        "status": "non_compliant",
        "result_status": "non_compliant",
        "display_status": "non_compliant",
        "is_compliant": False,
        "reason_code": "missing_record",
        "customer_display_facts": {"fact": "synthetic"},
        "customer_evidence": [{"source_ref": "src_test"}],
        "comment": "评论中的 LX0609-001 必须保持原文",
        "raw_model_response": {"rule_id": "LX0609-001", "text": "原始归档不重写"},
    }


def _envelope(rule_id="LX0609-001", record_ref="rec_0123456789abcdef01234567"):
    return {
        "schema_version": "lx0609-record-result-envelope-v1",
        "root_job_id": "root-1",
        "record_ref": record_ref,
        "rule_set_key": "luxian_0609_qc_v1",
        "rule_set_version": "2026.09",
        "items": [_item(rule_id)],
    }


def _create_snapshot(tmp_path, *, second_batch=False, feedback=True):
    url = f"sqlite:///{tmp_path / 'snapshot.sqlite'}"
    engine, metadata = sa.create_engine(url), sa.MetaData()
    batch = sa.Table(
        "custom_qc_batch_jobs",
        metadata,
        sa.Column("id", sa.String, primary_key=True),
        sa.Column("status", sa.String, default="completed"),
        sa.Column("rule_code", sa.String),
        sa.Column("filters_json", sa.Text),
        sa.Column("items_json", sa.Text),
        sa.Column("summary_json", sa.Text),
        sa.Column("failed_records_json", sa.Text),
        sa.Column("child_summary_json", sa.Text),
    )
    envelopes = sa.Table(
        "luxian_0609_record_result_envelopes",
        metadata,
        sa.Column("id", sa.String, primary_key=True),
        sa.Column("root_job_id", sa.String),
        sa.Column("created_by", sa.String),
        sa.Column("envelope_json", sa.Text),
        sa.Column("result_count", sa.Integer),
    )
    feedback_table = sa.Table(
        "qc_result_feedback_demo",
        metadata,
        sa.Column("id", sa.String, primary_key=True),
        sa.Column("root_job_id", sa.String),
        sa.Column("record_ref", sa.String),
        sa.Column("rule_id", sa.String),
        sa.Column("original_status", sa.String),
        sa.Column("result_digest", sa.String),
        sa.Column("created_by", sa.String),
        sa.Column("comment", sa.Text),
    )
    sample_items = sa.Table(
        "manual_problem_sample_pool_items",
        metadata,
        sa.Column("id", sa.String, primary_key=True),
        sa.Column("candidate_rule_ids_json", sa.Text),
        sa.Column("raw_payload_json", sa.Text),
    )
    sa.Table(
        "custom_qc_rule_drafts",
        metadata,
        sa.Column("id", sa.String, primary_key=True),
        sa.Column("rule_code", sa.String),
        sa.Column("published_rule_id", sa.String),
    )
    metadata.create_all(engine)
    old_item, envelope = _item(), _envelope()
    with engine.begin() as conn:
        conn.execute(
            batch.insert(),
            {
                "id": "job-1",
                "rule_code": "LX0609-BATCH",
                "filters_json": json.dumps(
                    {
                        "selected_rule_ids": ["LX0609-001"],
                        "scoped_customer_rule_ids": ["LX0609-001"],
                        "execution_rule_ids": ["LX0609-001", "SC-001"],
                        "mapped_rule_ids": ["LX0609-001"],
                        "comment": "LX0609-001",
                    }
                ),
                "items_json": json.dumps(
                    [
                        {
                            "rule_id": "LX0609-001",
                            "rule_code": "LX0609-001",
                            "raw_model_response": {"rule_id": "LX0609-001"},
                        }
                    ]
                ),
                "summary_json": json.dumps(
                    {"rule_results": [{"rule_id": "LX0609-001"}]}
                ),
                "failed_records_json": json.dumps(
                    [
                        {
                            "failed_rule_ids": ["LX0609-001"],
                            "record_rule_map": {
                                "rec_0123456789abcdef01234567": ["LX0609-001"]
                            },
                        }
                    ]
                ),
                "child_summary_json": json.dumps(
                    {"results_by_rule_id": {"LX0609-001": {"rule_id": "LX0609-001"}}}
                ),
            },
        )
        if second_batch:
            conn.execute(
                batch.insert(),
                {
                    "id": "job-2",
                    "rule_code": "LX0609-001",
                    "filters_json": "{}",
                    "items_json": "[]",
                    "summary_json": "{}",
                    "failed_records_json": "[]",
                    "child_summary_json": "{}",
                },
            )
        conn.execute(
            envelopes.insert(),
            {
                "id": "env-1",
                "root_job_id": "root-1",
                "created_by": "admin-001",
                "envelope_json": json.dumps(envelope, ensure_ascii=False),
                "result_count": 1,
            },
        )
        if feedback:
            conn.execute(
                feedback_table.insert(),
                {
                    "id": "feedback-1",
                    "root_job_id": "root-1",
                    "record_ref": envelope["record_ref"],
                    "rule_id": "LX0609-001",
                    "original_status": "non_compliant",
                    "result_digest": _digest(old_item),
                    "created_by": "admin-001",
                    "comment": "反馈评论 LX0609-001 不能改变",
                },
            )
        conn.execute(
            sample_items.insert(),
            [
                {
                    "id": "sample-1",
                    "candidate_rule_ids_json": json.dumps(["LX0609-001"]),
                    "raw_payload_json": json.dumps(
                        {
                            "selected_rule_ids": ["LX0609-001"],
                            "medical_text": "脱敏原文中的 LX0609-001 不是身份字段",
                        },
                        ensure_ascii=False,
                    ),
                },
                {
                    "id": "sample-unchanged",
                    "candidate_rule_ids_json": "[ ]",
                    "raw_payload_json": '{ "comment": "LX0609-010" }',
                },
            ],
        )
    engine.dispose()
    return url


def _rows(url, table):
    engine = sa.create_engine(url)
    metadata = sa.MetaData()
    result = [
        dict(row)
        for row in engine.connect()
        .execute(sa.text(f"SELECT * FROM {table}"))
        .mappings()
    ]
    engine.dispose()
    return result


def test_migrates_nested_jobs_envelope_and_feedback_without_touching_archived_text(
    tmp_path,
):
    url = _create_snapshot(tmp_path)
    plan = build_plan(url)
    assert plan.ready, [issue.code for issue in plan.issues]
    assert {operation.table for operation in plan.operations} == {
        "custom_qc_batch_jobs",
        "luxian_0609_record_result_envelopes",
        "qc_result_feedback_demo",
        "manual_problem_sample_pool_items",
    }

    apply_plan(url, plan, expected_mapping_digest=plan.mapping_digest)
    new_id = load_mapping().legacy_to_new["LX0609-001"]
    job = _rows(url, "custom_qc_batch_jobs")[0]
    assert job["rule_code"] == "LX0609-BATCH"
    assert json.loads(job["filters_json"])["selected_rule_ids"] == [new_id]
    assert json.loads(job["filters_json"])["scoped_customer_rule_ids"] == [new_id]
    assert json.loads(job["filters_json"])["execution_rule_ids"] == [new_id, "SC-001"]
    assert json.loads(job["filters_json"])["comment"] == "LX0609-001"
    item = json.loads(job["items_json"])[0]
    assert item["rule_id"] == item["rule_code"] == new_id
    assert item["raw_model_response"]["rule_id"] == "LX0609-001"
    assert new_id in json.loads(job["child_summary_json"])["results_by_rule_id"]
    retry_scope = json.loads(job["failed_records_json"])[0]["record_rule_map"]
    assert list(retry_scope) == ["rec_0123456789abcdef01234567"]
    assert retry_scope["rec_0123456789abcdef01234567"] == [new_id]

    envelope = json.loads(
        _rows(url, "luxian_0609_record_result_envelopes")[0]["envelope_json"]
    )
    migrated_item = envelope["items"][0]
    assert migrated_item["rule_id"] == migrated_item["rule_code"] == new_id
    assert migrated_item["comment"] == "评论中的 LX0609-001 必须保持原文"
    assert migrated_item["raw_model_response"]["rule_id"] == "LX0609-001"
    feedback = _rows(url, "qc_result_feedback_demo")[0]
    assert feedback["rule_id"] == new_id
    assert feedback["result_digest"] == _digest(migrated_item)
    assert feedback["comment"] == "反馈评论 LX0609-001 不能改变"
    sample_rows = {
        row["id"]: row for row in _rows(url, "manual_problem_sample_pool_items")
    }
    assert json.loads(sample_rows["sample-1"]["candidate_rule_ids_json"]) == [new_id]
    assert json.loads(sample_rows["sample-1"]["raw_payload_json"])[
        "selected_rule_ids"
    ] == [new_id]
    assert "LX0609-001" in sample_rows["sample-1"]["raw_payload_json"]
    # 没有白名单身份字段变动时原始 JSON 字节串不得因格式化而被重写。
    assert sample_rows["sample-unchanged"]["candidate_rule_ids_json"] == "[ ]"
    assert (
        sample_rows["sample-unchanged"]["raw_payload_json"]
        == '{ "comment": "LX0609-010" }'
    )


def test_rerun_is_idempotent_after_successful_apply(tmp_path):
    url = _create_snapshot(tmp_path)
    first = build_plan(url)
    apply_plan(url, first, expected_mapping_digest=first.mapping_digest)
    second = build_plan(url)
    assert second.ready
    assert second.operations == []
    apply_plan(url, second, expected_mapping_digest=second.mapping_digest)


def test_unknown_legacy_id_blocks_apply_without_writes(tmp_path):
    url = _create_snapshot(tmp_path)
    engine = sa.create_engine(url)
    with engine.begin() as conn:
        conn.execute(
            sa.text("UPDATE custom_qc_batch_jobs SET filters_json = :value"),
            {"value": json.dumps({"selected_rule_ids": ["LX0609-080"]})},
        )
    engine.dispose()
    plan = build_plan(url)
    assert any(issue.code == "unknown_lx0609_identity" for issue in plan.issues)
    before = _rows(url, "custom_qc_batch_jobs")
    with pytest.raises(MigrationBlocked, match="plan_has_blocking_issues"):
        apply_plan(url, plan)
    assert _rows(url, "custom_qc_batch_jobs") == before


def test_conflicting_identity_fields_block_apply(tmp_path):
    url = _create_snapshot(tmp_path)
    engine = sa.create_engine(url)
    broken = _envelope()
    broken["items"][0]["rule_code"] = "LX0609-002"
    with engine.begin() as conn:
        conn.execute(
            sa.text(
                "UPDATE luxian_0609_record_result_envelopes SET envelope_json = :value"
            ),
            {"value": json.dumps(broken)},
        )
    engine.dispose()
    plan = build_plan(url)
    assert any(issue.code == "conflicting_identity_fields" for issue in plan.issues)
    with pytest.raises(MigrationBlocked):
        apply_plan(url, plan)


def test_old_and_new_identity_dictionary_keys_are_a_conflict(tmp_path):
    url = _create_snapshot(tmp_path)
    engine = sa.create_engine(url)
    mixed = {
        "results_by_rule_id": {
            "LX0609-001": {"rule_id": "LX0609-001"},
            "LX0609-01-01-01": {"rule_id": "LX0609-01-01-01"},
        }
    }
    with engine.begin() as conn:
        conn.execute(
            sa.text("UPDATE custom_qc_batch_jobs SET child_summary_json = :value"),
            {"value": json.dumps(mixed)},
        )
    engine.dispose()
    plan = build_plan(url)
    assert any(issue.code == "identity_map_key_collision" for issue in plan.issues)
    with pytest.raises(MigrationBlocked):
        apply_plan(url, plan)


def test_orphan_or_digest_mismatched_feedback_blocks_apply(tmp_path):
    url = _create_snapshot(tmp_path)
    engine = sa.create_engine(url)
    with engine.begin() as conn:
        conn.execute(
            sa.text("UPDATE qc_result_feedback_demo SET result_digest = 'bad'")
        )
    engine.dispose()
    plan = build_plan(url)
    assert any(
        issue.code == "feedback_digest_or_status_mismatch" for issue in plan.issues
    )
    with pytest.raises(MigrationBlocked):
        apply_plan(url, plan)


def test_changed_snapshot_is_rejected_before_updates(tmp_path):
    url = _create_snapshot(tmp_path, second_batch=True, feedback=False)
    plan = build_plan(url)
    assert plan.ready
    engine = sa.create_engine(url)
    with engine.begin() as conn:
        # 让最后一个 Envelope 更新无法匹配，模拟迁移窗口内的并发写入。
        conn.execute(
            sa.text(
                "UPDATE luxian_0609_record_result_envelopes SET envelope_json = envelope_json || ' '"
            )
        )
    engine.dispose()
    with pytest.raises(MigrationBlocked, match="compare_and_swap_failed"):
        apply_plan(url, plan, expected_mapping_digest=plan.mapping_digest)
    rows = _rows(url, "custom_qc_batch_jobs")
    assert rows[0]["rule_code"] == "LX0609-BATCH"
    assert rows[1]["rule_code"] == "LX0609-001"
    assert json.loads(rows[0]["filters_json"])["selected_rule_ids"] == ["LX0609-001"]


def test_failed_envelope_update_rolls_back_already_updated_jobs(tmp_path):
    url = _create_snapshot(tmp_path, second_batch=True)
    plan = build_plan(url)
    before = {op.table: _rows(url, op.table) for op in plan.operations}
    engine = sa.create_engine(url)
    with engine.begin() as conn:
        # 在真正执行到后面的Envelope UPDATE时返回零行，验证此前任务写入也回滚。
        conn.execute(
            sa.text(
                "CREATE TRIGGER block_envelope BEFORE UPDATE ON "
                "luxian_0609_record_result_envelopes BEGIN SELECT RAISE(IGNORE); END"
            )
        )
    engine.dispose()
    with pytest.raises(
        MigrationBlocked,
        match="compare_and_swap_failed:luxian_0609_record_result_envelopes",
    ):
        apply_plan(url, plan)
    assert {table: _rows(url, table) for table in before} == before


def test_mapping_version_mismatch_is_rejected_before_database_planning(tmp_path):
    url = _create_snapshot(tmp_path)
    with pytest.raises(MigrationBlocked, match="mapping_version_mismatch"):
        build_plan(url, expected_mapping_version="unexpected-v2")


def test_legacy_identity_in_custom_draft_blocks_instead_of_rewriting_uuid_binding(
    tmp_path,
):
    url = _create_snapshot(tmp_path)
    engine = sa.create_engine(url)
    with engine.begin() as conn:
        conn.execute(
            sa.text(
                "INSERT INTO custom_qc_rule_drafts (id, rule_code, published_rule_id) "
                "VALUES ('draft-1', 'LX0609-001', 'a2a3d0e1-9b24-49a0-8d1a-a3f4e7a0c122')"
            )
        )
    engine.dispose()
    plan = build_plan(url)
    assert any(issue.code == "legacy_identity_in_custom_draft" for issue in plan.issues)
    with pytest.raises(MigrationBlocked):
        apply_plan(url, plan)


@pytest.mark.parametrize("tamper", ["omit_operation", "rewrite_non_identity"])
def test_reviewed_plan_cannot_omit_updates_or_rewrite_clinical_text(tmp_path, tamper):
    url = _create_snapshot(tmp_path)
    plan = build_plan(url)
    assert plan.ready
    before = {op.table: _rows(url, op.table) for op in plan.operations}
    if tamper == "omit_operation":
        plan.operations.pop()
    else:
        operation = next(
            op for op in plan.operations if op.table == "custom_qc_batch_jobs"
        )
        change = operation.changes["items_json"]
        items = json.loads(change["after"])
        items[0]["comment"] = "不允许通过迁移计划改写诊疗内容"
        change["after"] = json.dumps(items, ensure_ascii=False)
    with pytest.raises(MigrationBlocked, match="plan_stale_or_modified"):
        apply_plan(url, plan)
    assert {table: _rows(url, table) for table in before} == before


@pytest.mark.parametrize("root_already_migrated", [False, True])
def test_feedback_digest_matches_runtime_after_nested_evidence_migration(
    tmp_path, root_already_migrated
):
    from app.services.qc_workspace.result_feedback_demo_store import _result_digest
    from app.services.qc_workspace.canonical_result_store import (
        canonical_envelope_items_are_consistent,
    )

    url = _create_snapshot(tmp_path)
    envelope = _envelope()
    item = envelope["items"][0]
    if root_already_migrated:
        item["rule_id"] = item["rule_code"] = "LX0609-01-01-01"
    item["customer_display_facts"]["rule_id"] = "LX0609-001"
    item["customer_evidence"][0]["rule_id"] = "LX0609-001"
    engine = sa.create_engine(url)
    with engine.begin() as conn:
        conn.execute(
            sa.text(
                "UPDATE luxian_0609_record_result_envelopes SET envelope_json=:value"
            ),
            {"value": json.dumps(envelope, ensure_ascii=False)},
        )
        conn.execute(
            sa.text(
                "UPDATE qc_result_feedback_demo SET rule_id=:rule, result_digest=:digest"
            ),
            {"rule": item["rule_id"], "digest": _result_digest(item)},
        )
    engine.dispose()
    plan = build_plan(url)
    assert plan.ready, plan.issues
    apply_plan(url, plan)
    saved_item = json.loads(
        _rows(url, "luxian_0609_record_result_envelopes")[0]["envelope_json"]
    )["items"][0]
    assert saved_item["customer_evidence"][0]["rule_id"] == "LX0609-01-01-01"
    assert canonical_envelope_items_are_consistent([saved_item])
    assert _rows(url, "qc_result_feedback_demo")[0]["result_digest"] == _result_digest(
        saved_item
    )
    assert build_plan(url).operations == []


@pytest.mark.parametrize("status", ["queued", "running", "unknown"])
def test_nonterminal_jobs_block_migration_instead_of_invalidating_scope_hash(
    tmp_path, status
):
    url = _create_snapshot(tmp_path)
    engine = sa.create_engine(url)
    with engine.begin() as conn:
        conn.execute(
            sa.text("UPDATE custom_qc_batch_jobs SET status=:status"),
            {"status": status},
        )
    engine.dispose()
    plan = build_plan(url)
    assert any(issue.code == "active_or_unknown_job_status" for issue in plan.issues)
    with pytest.raises(MigrationBlocked, match="plan_has_blocking_issues"):
        apply_plan(url, plan)
    assert _rows(url, "qc_result_feedback_demo")[0]["rule_id"] == "LX0609-001"


def test_cli_returns_failure_for_blocked_dry_run(tmp_path, monkeypatch, capsys):
    from scripts.luxian_0609_identity_migration.__main__ import main

    url = _create_snapshot(tmp_path)
    engine = sa.create_engine(url)
    with engine.begin() as conn:
        conn.execute(sa.text("UPDATE custom_qc_batch_jobs SET status='running'"))
    engine.dispose()
    monkeypatch.setattr("sys.argv", ["migration", "--database-url", url])
    assert main() == 2
    assert json.loads(capsys.readouterr().out)["ready"] is False
