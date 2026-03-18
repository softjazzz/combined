# Alembic 迁移说明

## 目标
- 统一 PostgreSQL schema 变更入口
- 让新环境可通过 `alembic upgrade head` 初始化数据库对象

## 目录
- `alembic.ini`
- `alembic/env.py`
- `alembic/versions/20260315_000001_baseline_pg_schema.py`

## 常用命令
```powershell
cd apps/medqc-web/backend
alembic upgrade head
alembic revision -m "your change"
alembic revision --autogenerate -m "your change"
```

## split schema 模式（第三批）
当需要启用“同库分 schema（qc/sys/cdm/legacy）”时，先配置：

```env
DB_SCHEMA_MODE=split
DB_SEARCH_PATH=public,qc,sys,cdm,legacy
```

然后执行：

```powershell
cd apps/medqc-web/backend
alembic upgrade head
```

## 存量库接入
如果数据库对象已经通过历史脚本创建，不希望重复执行 baseline，可先标记版本：

```powershell
cd apps/medqc-web/backend
alembic stamp 20260315_000001
```

然后从下一条 revision 开始做增量迁移。

## 说明
- baseline revision 当前采用 `Base.metadata.create_all()` + `qc_views.sql` 建视图。
- 后续增量迁移应避免继续使用 `create_all`，改为 `op.add_column/op.create_table/...` 的显式变更。
