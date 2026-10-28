# Caché 同步库正式初始化

## 目的与边界

`backend/scripts/bootstrap_cache_sync_database.py` 用于把以下两类 PostgreSQL
数据库初始化到 MedQC Alembic `20261026_000055`：

1. 全新空库；
2. 仅含 POC 原始层的库：`cache_raw.source_record`、五张 `sync_ops` 表和空的
   `cdm` schema。

工具不修改历史迁移文件。它在 `000029`、`000047` 之前分别按冻结的 runtime
合同建立 `qc.sync_job_state`、`qc.visit_index`，再继续执行正式 Alembic 链。

工具不会：

- 连接远端 PostgreSQL；
- 从命令行或连接 URL 接收口令；
- 修改 Caché 数据；
- 给 `medqc_sync` 授权；
- 自动恢复中断后留下的部分迁移库。

## 安全保护

- 只接受 `postgresql+psycopg2` 和 `127.0.0.1`；
- 数据库名、端口和登录名必须显式给出；
- 口令只能由 root-only `PGPASSFILE` 提供；
- 初始对象清单必须是空库或精确的 POC 清单，多一个对象也拒绝执行；
- 迁移前后比较 `cache_raw`、`sync_ops` 的列、约束、索引、行数和行内容摘要；
- 使用 PostgreSQL advisory lock 阻止同库并发初始化；
- 完成后核对 Alembic head、两张先决表、`cdm.mr` 的 78 列、三坐标主键、
  属主和 `public.mr` 不存在；
- 对已完成库再次运行时只做校验，不再执行 DDL/DML。

## 前置条件

- 已完成并校验 `pg_dump -Fc` 逻辑备份；
- PostgreSQL 容器健康，端口只发布到 `127.0.0.1:5432`；
- `medqc_owner` 已存在且为 `NOLOGIN`；
- 迁移登录账号可 `SET ROLE medqc_owner`；
- `medqc_owner` 对目标数据库有 `CREATE`，对 `public` 有 `CREATE, USAGE`；
- Python 3.10 环境包含项目要求版本的 SQLAlchemy、Alembic、
  python-dotenv 和 psycopg2；
- 项目包中的 Alembic 单 head 必须是 `20261026_000055`。

## 正式执行顺序

服务器命令由交付包中的 `SERVER-COMMANDS.md` 提供。执行顺序固定为：

1. 校验交付包 SHA256；
2. 只读核对容器、备份和目标库对象清单；
3. 建立 `/run` 下的临时 root-only pgpass 文件；
4. 执行初始化器；
5. 再次执行初始化器，确认输出“已完成，本次只读核验”；
6. 单独执行 `medqc_sync` 的最小授权 SQL，仅授权 `cdm.mr` DML；
7. 核对 POC 行数、批次、断点、Alembic head、`cdm.mr` 合同和权限负例；
8. 删除临时 pgpass 文件。

授权不写入 Alembic。部署时必须显式执行并验收：

```sql
REVOKE ALL ON ALL TABLES IN SCHEMA cdm FROM medqc_sync;
REVOKE ALL ON ALL SEQUENCES IN SCHEMA cdm FROM medqc_sync;
GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE cdm.mr TO medqc_sync;
```

不得给 `medqc_sync` `CREATE`、schema 属主或 `medqc_owner` 成员资格。

## 失败处理

- 任何一步失败后立即停止，不继续授权或投影；
- 不在原库手工补版本号、删表或重跑中间迁移；
- 保留错误输出，但不得记录连接口令、Caché payload 或患者字段；
- 用执行前的逻辑备份恢复到新库，核对后再决定是否替换原库；
- 初始化器发现已有非 head 的 `alembic_version` 时会拒绝继续，必须先完成事故核查。

## 开发机验收

测试公共入口为 `initialize()` 和 CLI `main()`，不直接测试私有实现。隔离
PostgreSQL 验收覆盖：

- 全新空库升级至 000055；
- POC 克隆升级至 000055，raw/sync_ops 结构和数据不变；
- 非白名单对象在 Alembic 前被拒绝；
- URL 明文口令被拒绝；
- 远端数据库地址被拒绝；
- 完成库重复运行只读返回。
