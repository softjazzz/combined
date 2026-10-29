# 独立迁移说明

此目录只初始化独立的 ingest PostgreSQL，不属于 `apps/medqc-web` 的 Alembic 链。

由数据库管理员使用具备建 schema/table 权限的部署身份执行：

```text
psql --set ON_ERROR_STOP=1 --file migrations/001_ingest_contract.sql medqc_ingest
psql --set ON_ERROR_STOP=1 --file migrations/002_major_document_contracts.sql medqc_ingest
psql --set ON_ERROR_STOP=1 --file migrations/003_daily_record_datetime_contract.sql medqc_ingest
psql --set ON_ERROR_STOP=1 --file migrations/004_orders_lab_exam_and_versions.sql medqc_ingest
```

脚本可重复执行，不删除数据。运行身份只需被授予 `cache_raw`、`sync_ops` 的必要
`SELECT/INSERT/UPDATE` 以及 identity sequence 使用权；不要授予业务库权限。
最小授权示例位于 `deploy/postgres/least-privilege.example.sql`，其中 ingest 与 publisher
使用两个独立角色变量，不包含地址或口令。

新环境按文件名前缀升序执行全部 SQL；已有环境只执行尚未登记的
更高版本脚本，并由部署系统在外部记录已应用版本。升级脚本必须保持前向、幂等，
不得并入 `apps/medqc-web` 的 Alembic revision，也不得由工作进程自动执行。

`001` 同时创建正式抽取表和隔离观察平面：`source_snapshot`、字段画像、关联画像及
源到目标合同表。观察平面与 `source_record/sync_checkpoint` 没有写入触发器，运行
`inspect/profile` 不会推进正式同步状态。

`002` 注册 7 个已有证据的正式接口，并把证据版本写入抽取、发布批次。业务库 CDM 表
继续由现有应用 Alembic 管理，本服务不会创建或修改它。发布前只读核对目标主键、
required 核心列和实际类型；可选列不存在时保持 raw-only，不强迫升级业务迁移。

`003` 仅登记日常病程 `record_datetime` 的源到目标映射；目标新增列由应用
Alembic `20261029_000056` 管理。登记不执行应用迁移，不回填已有 raw/CDM，不推进断点。

`004` 是 0.2.0 必需升级：登记六个已验收接口，并增加 raw 版本表。
执行前停止该 ingest 库的工作进程，升级与授权核对完成后再启用 0.2.0 worker。
schema、当前 raw、变化版本和断点由工作进程在同一个数据事务提交。升级已有正式库时，
只保存升级时仍可见的快照版本；不会恢复已经丢失的旧版本，也不触碰 DSH 临时版本表。
该脚本检查正式存储列 `column_names/source_window_start`，不满足即整体退出。

DSH 现有验收库使用 `column_names_json` 等不同列合同，禁止在该库执行 001–004 试图
自动兼容。当前验证只读。后续应在新建独立克隆上验证显式存储迁移，保留所有原始历史，
确认成功后才讨论部署；本次未提供或执行该数据迁移。
