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
        'ORDER BY "primary_document_category" ASC, '
        '"execution_order" ASC, "name" ASC'
    ) in sql
