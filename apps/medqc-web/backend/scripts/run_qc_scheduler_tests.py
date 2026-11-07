"""QC 调度器 M0-M2 测试入口；默认严格离线且不读取业务配置。"""

from __future__ import annotations

import argparse
from contextlib import contextmanager
import os
from pathlib import Path
import sys
from types import ModuleType
from tempfile import TemporaryDirectory

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool


SUITES: dict[str, tuple[str, ...]] = {
    "strata-p9d": (
        "tests/unit/test_p9d_package_scope.py",
        "tests/unit/test_p9d_isolated_smoke.py",
        "tests/unit/test_llm_counter_installation.py",
        "tests/unit/test_strata_handoff.py",
        "tests/unit/test_strata_p9d.py",
        "tests/unit/test_strata_p9b.py",
        "tests/unit/test_context_token_budget.py",
        "tests/unit/test_context_budget_review_regressions.py",
        "tests/unit/test_gateway_context_budget.py",
    ),
    "strata-p9b": (
        "tests/unit/test_strata_p9b.py",
        "tests/unit/test_strata_admin_configuration.py",
        "tests/unit/test_llm_config_loader.py",
        "tests/unit/test_qc_llm_client_thinking_budget.py",
        "tests/unit/test_context_token_budget.py",
        "tests/unit/test_context_budget_review_regressions.py",
        "tests/unit/test_gateway_context_budget.py",
        "tests/unit/test_strata_observation_client.py",
        "tests/unit/test_llm_dispatch_routing.py",
        "tests/unit/test_strata_prefix_fixed_flow.py",
    ),
    "context-budget-p5b": (
        "tests/unit/test_luxian_0609_engine.py",
        "tests/unit/test_failed_rule_retry.py",
        "tests/unit/test_luxian_0609_canonical_result_finalizer.py",
        "tests/unit/test_luxian_0609_privacy_request_scope.py",
        "tests/unit/test_context_token_budget.py",
        "tests/unit/test_context_budget_review_regressions.py",
        "tests/unit/test_gateway_context_budget.py",
        "tests/unit/test_exam_context_budget.py",
        "tests/unit/test_luxian_0609_native_exam_lab_execution.py",
        "tests/unit/test_luxian_0609_second_stage_freeze_completion.py",
        "tests/unit/test_exam_result_pair_recovery.py",
        "tests/unit/test_luxian_0609_exam_targeted_retry.py",
        "tests/unit/test_exam_result_input_completeness.py",
    ),
    "data-pipelines": (
        "tests/unit/test_discharge_horizon_document_fallback.py",
        "tests/unit/test_case_material_snapshot.py",
        "tests/unit/test_clinical_sources.py",
        "tests/unit/test_data_pipelines.py",
        "tests/unit/test_independent_cdm_connection.py",
        "tests/unit/test_cache_visit_time_source.py",
        "tests/unit/test_cache_rule_input_adapters.py",
        "tests/unit/test_luxian_0609_evidence_snapshot_provider.py",
        "tests/unit/test_luxian_0609_independent_pacs_reports.py",
        "tests/unit/test_validation_material_selection.py",
        "tests/unit/test_frontpage_qc_v2_loader.py",
        "tests/unit/test_luxian_0609_native_extended_document_execution.py",
    ),
    "dual-model-exam": (
        "tests/unit/test_frozen_exam_identity_protection.py",
        "tests/unit/test_exam_result_comparison_context.py",
        "tests/unit/test_exam_result_pair_recovery.py",
        "tests/unit/test_exam_hard_poc.py",
        "tests/unit/test_exam_poc_acceptance.py",
        "tests/unit/test_exam_result_input_completeness.py",
        "tests/unit/test_bailian_exam_poc.py",
        "tests/unit/test_exam_result_model_route.py",
        "tests/unit/test_luxian_0609_exam_targeted_retry.py",
        "tests/unit/test_luxian_0609_second_stage_freeze_completion.py",
        "tests/unit/test_llm_experiment_freeze.py",
        "tests/unit/test_strata_prefix_fixed_flow.py",
        "tests/unit/test_luxian_0609_task_runtime_identity.py",
    ),
    "llm-request-audit": (
        "tests/unit/test_p9d_package_scope.py",
        "tests/unit/test_p9d_isolated_smoke.py",
        "tests/unit/test_llm_counter_installation.py",
        "tests/unit/test_strata_handoff.py",
        "tests/unit/test_strata_p9d.py",
        "tests/unit/test_strata_p9b.py",
        "tests/unit/test_qc_cold_start_probe.py",
        "tests/unit/test_luxian_0609_preproduction_runner.py::test_preproduction_runner_cold_process_does_not_load_sichuan_service",
        "tests/unit/test_llm_request_observation.py",
        "tests/unit/test_llm_experiment_freeze.py",
        "tests/unit/test_strata_observation.py",
        "tests/unit/test_strata_observation_client.py",
        "tests/unit/test_strata_cache_cost.py",
        "tests/unit/test_strata_prefix_adapter.py",
        "tests/unit/test_strata_prefix_fixed_flow.py",
        "tests/unit/test_strata_case_cache_gateway.py",
        "tests/unit/test_llm_dispatch_routing.py",
        "tests/unit/test_llm_dispatch_runtime_identity.py",
        "tests/unit/test_llm_gateway_api.py",
        "tests/unit/test_llm_gateway_cancellation.py",
        "tests/unit/test_llm_observability.py",
    ),
    "strata-admission": (
        "tests/unit/test_strata_package_continuation.py",
        "tests/unit/test_strata_case_admission.py",
        "tests/unit/test_strata_client_binding.py",
        "tests/unit/test_llm_gateway_admission.py",
        "tests/unit/test_llm_gateway_cancellation.py",
        "tests/unit/test_llm_gateway_api.py",
        "tests/unit/test_llm_dispatch_routing.py",
        "tests/unit/test_llm_dispatch_runtime_identity.py",
        "tests/unit/test_strata_admin_configuration.py",
        "tests/unit/test_strata_prefix_adapter.py",
        "tests/unit/test_strata_prefix_fixed_flow.py",
        "tests/unit/test_strata_cache_cost.py",
        "tests/unit/test_strata_case_cache_gateway.py",
    ),
    "strata-prefix": (
        "tests/unit/test_strata_case_cache_gateway.py",
        "tests/unit/test_strata_prefix_adapter.py",
        "tests/unit/test_strata_cache_cost.py",
        "tests/unit/test_strata_prefix_fixed_flow.py",
        "tests/unit/test_strata_observation.py",
        "tests/unit/test_strata_observation_client.py",
        "tests/unit/test_strata_request_inventory.py",
        "tests/unit/test_llm_observability.py",
        "tests/unit/test_llm_dispatch_routing.py",
    ),
    "strata-p0": (
        "tests/unit/test_strata_observation.py",
        "tests/unit/test_strata_observation_client.py",
        "tests/unit/test_strata_request_inventory.py",
        "tests/unit/test_llm_observability.py",
        "tests/unit/test_llm_dispatch_routing.py",
    ),
    "m2-infra": ("tests/infra/test_qc_m2_real_infra.py",),
    "m0-isolation": (
        "tests/unit/test_qc_scheduler_isolation.py",
        "tests/unit/test_qc_infra_isolation.py",
    ),
    "m1-admission": (
        "tests/unit/test_llm_http_proxy.py",
        "tests/unit/test_llm_gateway_admission.py",
        "tests/unit/test_llm_gateway_cancellation.py",
        "tests/unit/test_llm_gateway_api.py",
        "tests/unit/test_qc_scheduler_execution_policy.py",
        "tests/unit/test_llm_execution_concurrency.py",
        "tests/unit/test_llm_dispatch_routing.py",
        "tests/unit/test_llm_dispatch_runtime_identity.py",
    ),
    "compatibility": (
        "tests/unit/test_shared_http_client.py",
        "tests/unit/test_luxian_0609_task_runtime_identity.py",
        "tests/unit/test_failed_rule_retry.py",
        "tests/unit/test_qc_sichuan_batch_cancel.py",
        "tests/unit/test_latest_full_record_result.py",
        "tests/unit/test_luxian_0609_record_result_read_model.py",
        "tests/unit/test_qc_sichuan_record_result_exports.py",
        "tests/unit/test_qc_execution_timing.py",
        "tests/unit/test_record_execution_timing.py",
        "tests/unit/test_luxian_0609_canonical_result_finalizer.py",
        "tests/unit/test_luxian_0609_execution_privacy_identity.py",
        "tests/unit/test_luxian_0609_privacy_request_scope.py",
        "tests/unit/test_luxian_0609_production_extension_boundary.py",
        "tests/unit/test_luxian_0609_059_shadow_execution.py",
        "tests/unit/test_luxian_0609_native_treatment_order_consistency.py",
    ),
    "compatibility-restart": (
        "tests/unit/test_luxian_0609_task_restart_persistence.py",
    ),
    "m2-outbox": (
        "tests/unit/test_qc_dispatch_outbox.py",
    ),
    "m2-transport": (
        "tests/unit/test_qc_rabbitmq_transport.py",
        "tests/unit/test_qc_outbox_publisher.py",
    ),
    "m2-worker": (
        "tests/unit/test_qc_batch_consumer.py",
        "tests/unit/test_qc_worker_recovery.py",
    ),
    "m2-entrypoints": (
        "tests/unit/test_qc_dispatch_entrypoints.py",
    ),
    "m2-release": (
        "tests/unit/test_qc_runtime_settings.py",
        "tests/unit/test_qc_partial_failure_persistence.py",
        "tests/unit/test_qc_sichuan_batch_throughput.py::test_formal_customer_sample_model_failure_automatically_retries_failed_rule",
        "tests/unit/test_qc_sichuan_batch_throughput.py::test_partial_failed_retry_executes_only_failed_pairs_and_merges_to_completed",
        "tests/unit/test_qc_outbox_maintenance.py",
        "tests/unit/test_qc_dispatch_outbox.py",
        "tests/unit/test_qc_rabbitmq_transport.py",
        "tests/unit/test_qc_outbox_publisher.py",
        "tests/unit/test_qc_batch_consumer.py",
        "tests/unit/test_qc_worker_recovery.py",
        "tests/unit/test_qc_dispatch_entrypoints.py",
        "tests/unit/test_qc_m2_fixed_flow.py",
    ),
}

M2_SUITES = frozenset(
    {"m2-outbox", "m2-transport", "m2-worker", "m2-entrypoints", "m2-release"}
)


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--profile",
        default="offline",
        choices=("offline", "m2-synthetic", "isolated-infra"),
        help=(
            "m2-synthetic 复用严格离线护栏并标记 FakeBroker/合成 SQLite 验收；"
            "isolated-infra 尚未实现，当前会明确拒绝"
        ),
    )
    parser.add_argument("--suite", choices=tuple(SUITES))
    parser.add_argument("--infra-manifest", help="仅接受驱动新建容器后生成的 owner manifest")
    parser.add_argument(
        "--allow-reviewed-restart-probe",
        action="store_true",
        help="仅允许固定 hash 的合成跨进程重启 probe；默认严格禁止子进程",
    )
    parser.add_argument("tests", nargs="*", help="附加的显式 pytest node id")
    return parser.parse_args(argv)


def _selected_tests(args: argparse.Namespace) -> list[str]:
    selected = list(SUITES.get(args.suite, ()))
    selected.extend(args.tests)
    if not selected:
        raise SystemExit("请通过 --suite 或位置参数显式选择测试，拒绝默认运行全仓")
    restart_test = "tests/unit/test_luxian_0609_task_restart_persistence.py"
    selects_restart = any(
        node_id.split("::", 1)[0].replace("\\", "/") == restart_test
        for node_id in selected
    )
    if selects_restart and not args.allow_reviewed_restart_probe:
        raise SystemExit(
            "跨进程重启保护集默认禁用；必须显式传入 "
            "--allow-reviewed-restart-probe"
        )
    missing = sorted(
        {
            node_id.split("::", 1)[0]
            for node_id in selected
            if not Path(node_id.split("::", 1)[0]).is_file()
        }
    )
    if missing:
        raise SystemExit("测试清单包含尚不存在的文件：" + ", ".join(missing))
    return selected


def _validate_profile(args: argparse.Namespace) -> None:
    if args.profile == "isolated-infra":
        if args.suite != "m2-infra" or not args.infra_manifest or args.tests:
            raise SystemExit("isolated-infra requires m2-infra and an owned manifest")
    elif args.infra_manifest:
        raise SystemExit("infra manifest is forbidden outside isolated-infra")
    if args.suite == "m2-infra" and args.profile != "isolated-infra":
        raise SystemExit("m2-infra requires explicit isolated-infra profile")
    if args.profile == "m2-synthetic" and args.suite not in M2_SUITES:
        raise SystemExit("m2-synthetic profile 只允许显式选择 M2 suite")


def _install_legacy_demo_db_seam(engine, sessions) -> None:
    """隔离无关 demo import 的磁盘建库副作用，不替换 QC workspace owner。"""

    module_name = "app.database.demo_db"
    demo_db = ModuleType(module_name)
    demo_db.DATABASE_URL = "sqlite:///:memory:"
    demo_db.engine = engine
    demo_db.SessionLocal = sessions

    def get_db():
        session = sessions()
        try:
            yield session
        finally:
            session.close()

    @contextmanager
    def get_db_context():
        session = sessions()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    demo_db.get_db = get_db
    demo_db.get_db_context = get_db_context
    demo_db.init_db = lambda: None
    sys.modules[module_name] = demo_db

    import app.database as database_package

    database_package.demo_db = demo_db


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(list(sys.argv[1:] if argv is None else argv))
    _validate_profile(args)

    root = Path(__file__).resolve().parents[1]
    os.chdir(root)
    sys.path.insert(0, str(root))

    if args.profile == "isolated-infra":
        from tests.scheduler_support.infra_runner import main as run_infra
        return run_infra(args.infra_manifest)

    from tests.scheduler_support import OfflineIsolation

    selected = _selected_tests(args)
    with OfflineIsolation(
        allow_reviewed_restart_probe=args.allow_reviewed_restart_probe
    ), TemporaryDirectory(prefix='medqc-qc-dispatch-test-') as control_dir:
        # 后台运行开关及服务心跳始终使用一次性目录，不能继承部署中的模式文件。
        os.environ['QC_DISPATCH_STATE_DIR'] = control_dir
        os.environ["MEDQC_QC_SCHEDULER_TEST_PROFILE"] = args.profile
        if args.profile == "m2-synthetic":
            os.environ["MEDQC_QC_SCHEDULER_M2_SYNTHETIC"] = "1"
        # 某些旧 persistence 模块要求导入后存在 SessionLocal；这里只绑定无表的内存库。
        from app.database import connection
        import app.database as database_package

        # TestClient/async fixtures may import the legacy connection owner from a
        # worker thread.  A single synthetic connection keeps the in-memory seam
        # thread-safe and lets the runner dispose it without sqlite thread errors.
        engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        synthetic_sessions = sessionmaker(
            autocommit=False,
            autoflush=False,
            bind=engine,
        )
        # 旧 workspace 模块会在导入时复制 connection.engine/SessionLocal；两者必须
        # 同时指向同一个合成内存库，不能只替换会话工厂后让只读表元数据看到 None。
        connection.engine = engine
        connection.SessionLocal = synthetic_sessions
        database_package.engine = engine
        database_package.SessionLocal = synthetic_sessions
        _install_legacy_demo_db_seam(engine, synthetic_sessions)
        try:
            return pytest.main(
                [
                    "--confcutdir=tests/unit",
                    "-p",
                    "tests.scheduler_support.pytest_plugin",
                    "-q",
                    "--tb=short",
                    "-o",
                    "addopts=",
                    *selected,
                ]
            )
        finally:
            engine.dispose()


if __name__ == "__main__":
    raise SystemExit(main())
