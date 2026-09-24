from __future__ import annotations

from pathlib import Path

import sqlalchemy as sa

from scripts import import_visit_export as import_module


def test_resolve_csv_target_defaults_to_cdm_for_plain_table_name() -> None:
    schema, table = import_module._resolve_csv_target(Path("mr.csv"), default_schema="cdm")

    assert schema == "cdm"
    assert table == "mr"


def test_resolve_csv_target_preserves_explicit_schema() -> None:
    schema, table = import_module._resolve_csv_target(Path("qc.manual_problem_sample_pools.csv"), default_schema="cdm")

    assert schema == "qc"
    assert table == "manual_problem_sample_pools"


def test_collect_refresh_keys_dedupes_and_skips_incomplete_rows() -> None:
    rows = [
        {"institute_id": "H1", "patient_id": "P1", "visit_id": "V1"},
        {"institute_id": "H1", "patient_id": "P1", "visit_id": "V1"},
        {"institute_id": "H1", "patient_id": "P2", "visit_id": "V2"},
        {"institute_id": "H1", "patient_id": "", "visit_id": "V3"},
    ]

    keys = import_module._collect_refresh_keys(rows)

    assert keys == [
        {"institute_id": "H1", "patient_id": "P1", "visit_id": "V1"},
        {"institute_id": "H1", "patient_id": "P2", "visit_id": "V2"},
    ]


def test_import_visit_export_supports_plain_csv_names_and_multi_patient_bundle_refresh(
    tmp_path: Path,
    monkeypatch,
) -> None:
    export_dir = tmp_path / "0426"
    export_dir.mkdir(parents=True, exist_ok=True)
    csv_path = export_dir / "mr.csv"
    csv_path.write_text(
        "\n".join(
            [
                "institute_id,patient_id,visit_id,name",
                "H1,P1,V1,Alice",
                "H1,P2,V2,Bob",
            ]
        ),
        encoding="utf-8",
    )

    engine = sa.create_engine("sqlite:///:memory:")
    with engine.begin() as conn:
        conn.execute(
            sa.text(
                """
                create table mr (
                    institute_id text,
                    patient_id text,
                    visit_id text,
                    name text
                )
                """
            )
        )

    refresh_calls: list[dict[str, object]] = []
    domain_refresh_calls: list[dict[str, object]] = []

    monkeypatch.setattr(import_module, "DATABASE_URL", "sqlite:///:memory:")
    monkeypatch.setattr(import_module.sa, "create_engine", lambda _: engine)
    monkeypatch.setattr(import_module, "_ensure_schema", lambda conn, schema: None)
    monkeypatch.setattr(import_module, "_qualified_table", lambda schema, table: f'"{table}"')

    def _fake_refresh_scene_bundles_for_rows(**kwargs):
        refresh_calls.append(kwargs)
        count = len(kwargs.get("rows") or [])
        return {"processed": count, "updated": count, "failed": 0}

    def _fake_refresh_domain_bundles_for_rows(**kwargs):
        domain_refresh_calls.append(kwargs)
        count = len(kwargs.get("rows") or [])
        return {"processed": count, "updated": count, "failed": 0}

    monkeypatch.setattr(import_module, "refresh_scene_bundles_for_rows", _fake_refresh_scene_bundles_for_rows)
    monkeypatch.setattr(import_module, "refresh_domain_bundles_for_rows", _fake_refresh_domain_bundles_for_rows)

    result = import_module.import_visit_export(export_dir=export_dir, default_schema="cdm")

    assert result["refresh_key_count"] == 2
    assert result["visit_ids"] == ["V1", "V2"]
    assert result["tables"][0]["table"] == "cdm.mr"
    assert len(refresh_calls) == 2
    assert len(domain_refresh_calls) == 6
    assert {call["domains"][0] for call in domain_refresh_calls} == set(import_module._DOMAINS)
    assert refresh_calls[0]["rows"] == [
        {"institute_id": "H1", "patient_id": "P1", "visit_id": "V1"},
        {"institute_id": "H1", "patient_id": "P2", "visit_id": "V2"},
    ]
    assert all(call["rows"] == refresh_calls[0]["rows"] for call in domain_refresh_calls)
    assert all(call["policy_version"] == refresh_calls[0]["policy_version"] for call in domain_refresh_calls)

    with engine.begin() as conn:
        rows = conn.execute(sa.text("select institute_id, patient_id, visit_id, name from mr order by visit_id")).fetchall()
    assert rows == [("H1", "P1", "V1", "Alice"), ("H1", "P2", "V2", "Bob")]


def test_import_visit_export_adds_missing_columns_for_existing_table(
    tmp_path: Path,
    monkeypatch,
) -> None:
    export_dir = tmp_path / "0426"
    export_dir.mkdir(parents=True, exist_ok=True)
    csv_path = export_dir / "surgery_record.csv"
    csv_path.write_text(
        "\n".join(
            [
                "institute_id,patient_id,visit_id,document_id,record_content,surgery_process,surgery_name",
                "H1,P1,V1,D1,摘要,完整手术经过,全髋关节置换术",
            ]
        ),
        encoding="utf-8",
    )

    engine = sa.create_engine("sqlite:///:memory:")
    with engine.begin() as conn:
        conn.execute(
            sa.text(
                """
                create table surgery_record (
                    institute_id text,
                    patient_id text,
                    visit_id text,
                    document_id text,
                    record_content text
                )
                """
            )
        )

    monkeypatch.setattr(import_module, "DATABASE_URL", "sqlite:///:memory:")
    monkeypatch.setattr(import_module.sa, "create_engine", lambda _: engine)
    monkeypatch.setattr(import_module, "_ensure_schema", lambda conn, schema: None)
    monkeypatch.setattr(import_module, "_qualified_table", lambda schema, table: f'"{table}"')
    refreshed = {"processed": 1, "updated": 1, "failed": 0}
    monkeypatch.setattr(import_module, "refresh_scene_bundles_for_rows", lambda **kwargs: refreshed)
    monkeypatch.setattr(import_module, "refresh_domain_bundles_for_rows", lambda **kwargs: refreshed)
    monkeypatch.setattr(
        import_module,
        "inspect",
        lambda _engine: type(
            "FakeInspector",
            (),
            {
                "has_table": staticmethod(lambda table, schema=None: table == "surgery_record"),
                "get_columns": staticmethod(
                    lambda table, schema=None: [
                        {"name": "institute_id", "type": "text"},
                        {"name": "patient_id", "type": "text"},
                        {"name": "visit_id", "type": "text"},
                        {"name": "document_id", "type": "text"},
                        {"name": "record_content", "type": "text"},
                    ]
                ),
            },
        )(),
    )

    result = import_module.import_visit_export(export_dir=export_dir, default_schema="cdm")

    assert result["altered_tables"] == [
        {
            "table": "cdm.surgery_record",
            "added_columns": ["surgery_process", "surgery_name"],
        }
    ]

    with engine.begin() as conn:
        row = conn.execute(
            sa.text(
                """
                select institute_id, patient_id, visit_id, document_id, record_content, surgery_process, surgery_name
                from surgery_record
                """
            )
        ).fetchone()
    assert row == ("H1", "P1", "V1", "D1", "摘要", "完整手术经过", "全髋关节置换术")
