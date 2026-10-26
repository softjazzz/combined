from app.core.supabase_client import _Query


def test_multiple_order_calls_build_one_order_by_clause() -> None:
    query = (
        _Query(lambda: None, "qc_rules")
        .select("*")
        .order("primary_document_category")
        .order("execution_order")
        .order("name")
    )

    sql, params = query._build_select_sql()

    assert params == {}
    assert sql.count(" ORDER BY ") == 1
    assert (
        'ORDER BY "primary_document_category" ASC, ' '"execution_order" ASC, "name" ASC'
    ) in sql


def test_is_not_null_and_boolean_are_literals_not_untrusted_sql():
    import pytest
    from app.core.supabase_client import _Query

    query = (
        _Query(None, "qc_appeals").is_not("qc_result_id", None).is_not("active", False)
    )
    sql, params = query._build_where()
    assert '"qc_result_id" IS NOT NULL' in sql
    assert '"active" IS NOT FALSE' in sql
    assert params == {}
    with pytest.raises(ValueError):
        query.is_not("id", "untrusted")
