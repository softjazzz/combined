# ADR-0001：MedQC 数据接入模块化单体

- 状态：已接受
- 日期：2026-10-28

## 决策

在 `apps/medqc-data-integration` 建立独立 Python 包，由同一个 CLI 调度两个核心
worker：Caché 抽取器与 CDM 发布器。核心层只依赖 Python 标准库和端口协议；
`pyodbc`/`JayDeBeApi`/`psycopg` 只存在适配器层并且是可选依赖。

## 数据流

```text
Caché web.mr
  -> 流式 fetchmany / 类型规范化 / 键与 schema 校验
  -> ingest PostgreSQL: cache_raw.source_record + sync_ops
  -> 发布合同预检 / 幂等 upsert
  -> CDM PostgreSQL: cdm.mr
```

raw 按 `interface_name + source_key_hash` 隔离，每个接口保留完整 payload，不在 raw
层合并不同接口的重复字段。实体归一只在 CDM 发布层执行。

字段验证使用独立观察平面 `cache_raw.source_snapshot`，按
`inspection_batch + interface + window + ordinal` 保留隔离样本，不复用正式 raw 主键，
因此不会跨接口去重。画像表只保存字段名、类型、计数、日期范围和显式关联键统计。
候选接口目录不是生产注册表，未注册接口只记录 `blocked`，绝不建立源连接。

字段验证使用独立观察平面 `cache_raw.source_snapshot`，按
`inspection_batch + interface + window + ordinal` 保留隔离样本，不复用正式 raw 主键，
因此不会跨接口去重。画像表只保存字段名、类型、计数、日期范围和显式关联键统计。
候选接口目录不是生产注册表，未注册接口只记录 `blocked`，绝不建立源连接。

## 配置与凭据

非敏感配置使用环境变量；Caché、ingest PG 和 CDM PG 的密码分别使用
root/service-account-only 文件。不接受带口令 DSN，不在日志中输出主机、账号、
连接串、驱动异常原文或 payload。

Windows 正式源边界是 64 位 `InterSystems ODBC35` + `pyodbc`。Linux 使用
JDBC/JayDeBeApi 适配器边界；未安装可选驱动时返回受控错误而不泄露导入异常。

## 事务和恢复

- 每个接口使用由名称派生的稳定 PostgreSQL advisory lock。
- `running` 批次通过 autocommit 控制连接先独立落库。
- schema、所有 raw 分块与 checkpoint 在单个数据事务中；任一分块失败整批回滚。
- 成功/失败状态通过控制连接独立回写；陈旧 `running` 只由 `check`报告，
  不自动改写。
- 发布跨两个 PG 实例，不使用分布式事务。CDM 写入是单库原子、可幂等重试的
  upsert；发布审计在 ingest 库独立回写。如 CDM 已提交但审计回写失败，
  下次重试不会制造重复业务行。

## 合同与 fail-closed

`web.mr` 业务键固定为 `institute_id + patient_id + visit_id`。schema hash 使用
`ordered-column-names-v1`。空键、批内重复键（包括跨 fetch 块）、多个待发布 schema、
源字段不足、目标 `cdm.mr` 78 列合同漂移、锁冲突或配置不完整都在写数据前失败。

## 错误和日志

领域错误只携带允许列表中的 `error_kind` 和静态 `error_location`。驱动异常文本不会
进入日志或批次表。CLI 只记录运行模式、接口名、行数、checkpoint 结果和受控错误代码。

## 部署形态

以 wheel 安装到专用虚拟环境，由 Windows Task Scheduler、systemd timer 或作业平台执行
`medqc-ingest`。它不对外提供 Web API，不拆分微服务。
