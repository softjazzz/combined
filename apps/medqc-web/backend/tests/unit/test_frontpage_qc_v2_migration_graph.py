"""首页质控与 homology 迁移链衔接，只读脚本图，不连接数据库。"""
from pathlib import Path

import pytest
from alembic.script import ScriptDirectory


HEAD = "20261020_000050"
FRONTPAGE = "20261013_000048"
HOMOLOGY = "20261016_000049"


def _scripts():
    return ScriptDirectory(str(Path(__file__).resolve().parents[2] / "alembic"))


def test_frontpage_and_homology_have_one_upgrade_head():
    scripts = _scripts()
    assert scripts.get_heads() == [HEAD]
    assert scripts.get_current_head() == HEAD
    assert set(scripts.get_revision(HEAD).down_revision) == {FRONTPAGE, HOMOLOGY}


@pytest.mark.parametrize("current,expected", [
    (FRONTPAGE, {"20261016_000048", HOMOLOGY, HEAD}),
    (HOMOLOGY, {FRONTPAGE, HEAD}),
    ((FRONTPAGE, HOMOLOGY), {HEAD}),
])
def test_upgrade_from_either_existing_branch_does_not_repeat_applied_migrations(current, expected):
    steps = _scripts()._upgrade_revs("head", current)
    assert {step.revision.revision for step in steps} == expected


def test_existing_migration_numbers_and_parents_are_preserved():
    scripts = _scripts()
    assert scripts.get_revision(FRONTPAGE).down_revision == "20261006_000047"
    assert scripts.get_revision("20261016_000048").down_revision == "20261006_000047"
    assert scripts.get_revision(HOMOLOGY).down_revision == "20261016_000048"
