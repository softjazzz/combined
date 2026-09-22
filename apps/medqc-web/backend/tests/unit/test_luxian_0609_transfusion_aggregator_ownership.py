from __future__ import annotations

import inspect

from app.services import luxian_0609_result_aggregator as aggregator


def test_transfusion_customer_fact_contracts_are_not_owned_by_aggregator() -> None:
    source = inspect.getsource(aggregator)

    assert all(
        rule_id not in source
        for rule_id in (
            "LX0609-11-03-01", "LX0609-11-03-02", "LX0609-07-01-01",
            "LX0609-07-01-02", "LX0609-07-02-01", "LX0609-07-02-02",
            "LX0609-07-03-01", "LX0609-07-04-01",
        )
    )
    assert "LX0609-07-04-02" not in source
