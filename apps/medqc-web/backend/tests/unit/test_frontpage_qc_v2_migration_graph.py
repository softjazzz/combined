"""首页质控与 homology 迁移链衔接，只读脚本图，不连接数据库。"""
from pathlib import Path

import pytest
from alembic.script import ScriptDirectory


HEAD = "20261105_000063"
FRONTPAGE = "20261013_000048"
HOMOLOGY = "20261016_000049"


def _scripts():
    return ScriptDirectory(str(Path(__file__).resolve().parents[2] / "alembic"))


def test_frontpage_and_homology_have_one_upgrade_head():
    scripts = _scripts()
    assert scripts.get_heads() == [HEAD]
    assert scripts.get_current_head() == HEAD
    assert scripts.get_revision(HEAD).down_revision == "20261102_000062"
    assert set(scripts.get_revision("20261102_000062").down_revision) == {'20261102_000060', '20261102_000061'}
    assert set(scripts.get_revision('20261102_000061').down_revision) == {FRONTPAGE, '20261030_000057'}
    assert scripts.get_revision('20261020_000050').down_revision == HOMOLOGY


@pytest.mark.parametrize("current,expected", [
    (FRONTPAGE, {"20261016_000048", HOMOLOGY, HEAD}),
    (HOMOLOGY, {FRONTPAGE, HEAD}),
    ((FRONTPAGE, HOMOLOGY), {HEAD}),
])
def test_upgrade_from_either_existing_branch_does_not_repeat_applied_migrations(current, expected):
    steps = _scripts()._upgrade_revs("head", current)
    actual = {step.revision.revision for step in steps}
    assert expected <= actual
    assert FRONTPAGE not in actual if current == FRONTPAGE or isinstance(current, tuple) else FRONTPAGE in actual
    assert '20261030_000057' in actual


def test_existing_migration_numbers_and_parents_are_preserved():
    scripts = _scripts()
    assert scripts.get_revision(FRONTPAGE).down_revision == "20261006_000047"
    assert scripts.get_revision("20261016_000048").down_revision == "20261006_000047"
    assert scripts.get_revision(HOMOLOGY).down_revision == "20261016_000048"
