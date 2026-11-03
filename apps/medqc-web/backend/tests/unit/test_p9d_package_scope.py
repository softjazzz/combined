"""打包范围：Git干净也可能包含历史运行资料，必须显式排除。"""
import importlib.util
from pathlib import Path

import pytest


SPEC = importlib.util.spec_from_file_location('p9d_packager', Path(__file__).resolve().parents[3]
    / 'scripts/package-p9d-isolated.py')
packager = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(packager)


@pytest.mark.parametrize('path', [
    'app/data/sessions/old.db-journal', 'app/data/mongo_sync_config.json',
    'app/data/sync_run_history.json', 'data/manual_qc_runs/old.json',
    'app/data/luxian_0609_rules_v1.json.backup', 'config/.env', 'config/private.pem',
    'data/synthetic_qc/templates/old.json', '.env', 'app/storage/qc_diagnostics/old.json'])
def test_only_code_and_reviewed_static_assets_are_packaged(path):
    assert not packager.allowed_backend(path)


@pytest.mark.parametrize('path', ['app/services/strata_handoff.py',
    'app/data/luxian_0609_rules_v1.json', 'app/data/product_activation_public_key.pem',
    'config/strata-qwen36-p9c-approved.json', 'scripts/p9d_isolated_smoke.py', 'alembic/env.py',
    'services/pdf_parser.py', 'app/services/qc_diagnostics/capture.py'])
def test_counter_and_formal_runtime_dependencies_are_kept(path):
    assert packager.allowed_backend(path)
