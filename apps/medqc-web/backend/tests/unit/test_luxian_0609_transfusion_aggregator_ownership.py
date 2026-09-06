from __future__ import annotations

import inspect

from app.services import luxian_0609_result_aggregator as aggregator


def test_transfusion_customer_fact_contracts_are_not_owned_by_aggregator() -> None:
    source = inspect.getsource(aggregator)

    assert all(
        f"LX0609-{number:03d}" not in source for number in range(41, 49)
    )
    assert "LX0609-049" not in source
