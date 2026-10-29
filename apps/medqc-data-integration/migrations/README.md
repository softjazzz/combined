# 独立迁移说明

此目录只初始化独立的 ingest PostgreSQL，不属于 `apps/medqc-web` 的 Alembic 链。

由数据库管理员使用具备建 schema/table 权限的部署身份执行：

```text
psql --set ON_ERROR_STOP=1 --file migrations/001_ingest_contract.sql medqc_ingest
```

脚本可重复执行，不删除数据。运行身份只需被授予 `cache_raw`、`sync_ops` 的必要
`SELECT/INSERT/UPDATE` 以及 identity sequence 使用权；不要授予业务库权限。
最小授权示例位于 `deploy/postgres/least-privilege.example.sql`，其中 ingest 与 publisher
使用两个独立角色变量，不包含地址或口令。

当前只有 `001`。新环境按文件名前缀升序执行全部 SQL；已有环境只执行尚未登记的
更高版本脚本，并由部署系统在外部记录已应用版本。升级脚本必须保持前向、幂等，
不得并入 `apps/medqc-web` 的 Alembic revision，也不得由工作进程自动执行。

`001` 同时创建正式抽取表和隔离观察平面：`source_snapshot`、字段画像、关联画像及
源到目标合同表。观察平面与 `source_record/sync_checkpoint` 没有写入触发器或外键，
运行 `inspect/profile` 不会推进正式同步状态。

`001` 同时创建正式抽取表和隔离观察平面：`source_snapshot`、字段画像、关联画像及
源到目标合同表。观察平面与 `source_record/sync_checkpoint` 没有写入触发器，运行
`inspect/profile` 不会推进正式同步状态。

业务库 `medqc` 的 `cdm.mr` 继续由现有应用迁移管理，本服务不会创建或修改它。
发布前会只读核对 78 列的精确顺序和
`(institute_id, patient_id, visit_id)` 主键，然后才开始写事务。
