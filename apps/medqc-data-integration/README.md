# MedQC 数据接入服务

这是可独立安装和调度的 Python 模块化单体，包含两个 worker 角色：

- Caché 抽取器：流式调用已注册接口，把每个接口的完整 payload 写入 `cache_raw`；
- CDM 发布器：将已验证的 raw 数据按显式合同投影到业务 CDM。

正式注册表包含已通过非 PHI 三天字段研究验证的 `web.mr` 与六类主要文书接口。其他
接口仍会在读取配置密码或建立网络连接前拒绝；在院接口尚未验证，不在注册表中。

## 安装与命令

```text
python -m pip install ".[postgres,odbc]"
medqc-ingest extract --interface web.mr --date 2026-09-17 --mode dry
medqc-ingest extract --interface web.mr --date 2026-09-17 --mode incremental
medqc-ingest replay --interface web.mr --start 2026-09-01 --end 2026-09-17
medqc-ingest publish --interface web.mr
medqc-ingest extract --interface web.admission_record --date 2026-09-17 --mode incremental
medqc-ingest publish --interface web.admission_record
medqc-ingest check
medqc-ingest inspect --all --start 2026-09-15 --end 2026-09-17
medqc-ingest profile --batch 123
medqc-ingest coverage --target cdm,bundle,qc
medqc-ingest contract-export --output major-document-contracts.json
```

`dry` 不连接 PostgreSQL，不建批次。`replay` 写 raw 和批次审计但不推进 checkpoint。
`incremental` 只在新窗口结束时间更晚时单调推进 checkpoint，日志使用实际
rowcount 输出 `advanced` 或 `held`。

`inspect` 是独立观察平面：只把正式注册接口的样本写入
`cache_raw.source_snapshot`，不写正式 `source_record`、不推进 checkpoint、也不连接
业务库。`--all` 会把未注册候选接口记为 `blocked`，不会调用它们。
单日接口逐日调用；双日期接口只有显式声明 `range_inclusive` 后才可调用，未知语义一律
`blocked/unverified_date_semantics`。`profile` 只持久化字段名、类型和计数；
`coverage` 的状态只允许 `direct/derived/partial/missing/blocked`，名称相同仍默认阻断。

客户机真实全接口字段探查由既有 DSH/v5-final 环境完成；其非 PHI 字段清单和画像用于
复核候选目录与覆盖合同。候选清单本身不是生产调用授权。

`contract-export` 不加载配置或驱动，可输出 7 个正式接口的完整有序源列、显式 alias、
目标类型、required 核心列和 raw-only 字段。可独立交付的 JSON、纯标准库转换模块及
DSH 使用说明见 [DSH 主要文书映射桥接](docs/dsh-major-document-bridge.md)。

合同 v2 增加日常病程同名 `record_datetime` 投影。应用迁移 `20261029_000056`
提供可空、无默认值的独立记录时间列；旧目标缺列时仍明确报告 raw-only。
既有 raw 无需重抽，后续部署获准后可定向重投影；不从提交或签署时间补值。

运行配置来自环境变量，密码只从独立文件读取。详见 `.env.example`。迁移 DDL 在
`migrations/`；它不会自动运行。

## 数据库与事务边界

- ingest DB 只承载 `cache_raw`、`sync_ops` 和发布血缘，抽取器只写这个库；
- business DB `medqc` 只由发布器通过独立连接写现有 CDM 表，业务系统不读取 raw；
- `running` 审计先通过控制连接独立提交，raw 分块、schema 与 checkpoint 在同一
  数据事务中，任一块失败整批回滚；
- 发布器先验证 raw 单一 schema、目标主键、核心列与类型，只更新合同拥有且目标实际
  存在的列；核心列缺失时阻断，可选新列缺失时保持 raw-only；
- 入院、出院 raw 使用病例三键加文档编号保留每份文书，但 CDM 仍是病例三键；发布前
  发现同病例多文书即整批拒绝。病程类表使用病例三键加文档编号发布；
- CDM 提交后再提交 ingest 发布血缘；若第二次提交失败，重试仍按目标主键幂等；
- `replay` 按闭区间逐日建立批次和写 raw，但永远不推进 checkpoint；`dry` 不加载
  PostgreSQL 密码、不连接 PostgreSQL。

初始化/升级方法见 [migrations/README.md](migrations/README.md)。该 DDL 与
`apps/medqc-web` Alembic 完全独立。业务库 CDM 表仍由业务应用迁移维护；本服务不会
要求客户为验收升级或手工补列。

## 调度示例

- Windows：`deploy/windows/run-daily.ps1` 与任务计划 XML 示例；导入前替换服务账号；
- Linux：`deploy/systemd` 中的 oneshot service/timer 示例；systemd unit 运行时计算
  当天日期且不保存密码；
- `check` 只读核对 ingest 关系、checkpoint 数量、陈旧 running 批次以及全部已注册
  目标表的核心列、类型与主键合同。任何 failed 检查均返回非零退出码。

## 设计与覆盖边界

- [ADR-0001](docs/ADR-0001-data-integration-service.md)
- [Caché 接口到 bundle/CDM/质控来源覆盖矩阵](docs/cache-interface-coverage-matrix.md)

## 开发校验

```text
python -m pytest
python -m ruff check .
python -m mypy src
python -m build
```

测试使用 fake 端口，不连接真实 Caché 或 PostgreSQL。
