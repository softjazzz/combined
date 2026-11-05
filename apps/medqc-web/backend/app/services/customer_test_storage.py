"""自建病例仅写业务本地材料；缺结构/权限失败，禁止静默漏写。"""

from functools import wraps
import sqlalchemy as sa


class CustomerTestStorageError(RuntimeError):
    pass


def business_material_operation(function):
    @wraps(function)
    def wrapped(*args, **kwargs):
        from .clinical_sources import legacy_snapshot
        from ..database import clinical_connection

        with clinical_connection.selected(legacy_snapshot()):
            return function(*args, **kwargs)

    return wrapped


def local_schema():
    from ..database import connection

    return "cdm" if str(connection.DB_SCHEMA_MODE).lower() == "split" else "public"


def reflect_materials(session, rows_by_table):
    connection = session.connection()
    schema = local_schema()
    metadata = sa.MetaData()
    result = {}
    try:
        if connection.dialect.name != "postgresql":
            raise CustomerTestStorageError("customer_material_requires_postgresql")
        for name, rows in rows_by_table.items():
            # 仅接收自建入口内部映射生成的名字，不接受请求schema/table。
            table = sa.Table(name, metadata, schema=schema, autoload_with=connection)
            required = {"institute_id", "patient_id"}
            if name == "diagnosis":
                required.update({"diagnosis_id", "diagnosis_name"})
            else:
                required.add("record_content")
            if name != "patient_information":
                required.add("visit_id")
            if name in ("mr", "inpat_registration"):
                required.add("admission_datetime")
            if name not in (
                "patient_information",
                "mr",
                "inpat_registration",
                "diagnosis",
            ):
                required.add(
                    {
                        "inpat_nondrug_order": "order_id",
                        "blood_application": "application_id",
                    }.get(name, "document_id")
                )
                if name in ("exam_item_report", "labtest_item_report"):
                    required.add("report_time")
                elif name != "inpat_nondrug_order" and "record_datetime" in rows[0]:
                    # 不同文书有不同权威时钟；至少保留显式输入时间，而非丢弃后补零点。
                    if not ({"record_datetime", "record_time"} & set(table.c.keys())):
                        raise CustomerTestStorageError(
                            "customer_material_time_column:" + schema + "." + name
                        )
            missing = required - set(table.c.keys())
            if missing:
                raise CustomerTestStorageError(
                    "customer_material_missing_columns:"
                    + schema
                    + "."
                    + name
                    + ":"
                    + ",".join(sorted(missing))
                )
            pk = {column.name for column in table.primary_key.columns}
            if not pk or not pk <= set(rows[0]):
                raise CustomerTestStorageError(
                    "customer_material_primary_key:" + schema + "." + name
                )
            for c in table.columns:
                if (
                    not c.nullable
                    and c.name not in rows[0]
                    and c.server_default is None
                    and not c.identity
                    and not c.computed
                    and not (c.primary_key and c.autoincrement is True)
                ):
                    raise CustomerTestStorageError(
                        "customer_material_unpopulated_required_column:"
                        + schema
                        + "."
                        + name
                        + "."
                        + c.name
                    )
            allowed = connection.execute(
                sa.text(
                    "SELECT has_schema_privilege(current_user,:schema,'USAGE') AND has_table_privilege(current_user,:name,'SELECT') AND has_table_privilege(current_user,:name,'INSERT') AND has_table_privilege(current_user,:name,'UPDATE')"
                ),
                {"schema": schema, "name": f'"{schema}"."{name}"'},
            ).scalar()
            if not allowed:
                raise CustomerTestStorageError(
                    "customer_material_permissions:" + schema + "." + name
                )
            # 旧表使用record_time时，显式映射原输入，不丢失真实记录时刻。
            if "record_datetime" not in table.c and "record_time" in table.c:
                for row in rows:
                    row["record_time"] = row.get("record_datetime")
            result[name] = table
        return result
    except CustomerTestStorageError:
        raise
    except Exception:
        raise CustomerTestStorageError(
            "customer_material_reflection_failed:" + schema + "." + name
        ) from None
