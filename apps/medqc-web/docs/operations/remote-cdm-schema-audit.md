# 客户源库 CDM 只读盘点

## 目的

在开始同步配置、数据库升级或质控验收前，一次核对客户源库的实际表结构与 MedQC 当前同步目录，避免逐表猜测物理表名、把“表为空”误判为“表不存在”，或因字段丢失导致规则证据错位。

脚本只读取 PostgreSQL 元数据和可选汇总统计：不会写入源库或本地库，不返回患者姓名、住院号、文书正文、检查结论等原始数据。

## 客户机执行

在后端目录运行。默认从 `.env` 的 `REMOTE_DB_URL` 读取源库连接信息，报告写入当前后端的 `reports` 目录。

```powershell
Set-Location -LiteralPath "D:\medqc\medqc-web-customer-R24.x\backend"

python .\scripts\audit_remote_cdm_schema.py `
  --remote-schema public `
  --mode coverage `
  --output-dir .\reports\remote-schema-audit
```

先运行 `metadata`（最快）或 `coverage`（推荐）。不要一开始使用 `--exact-count`：客户源库的检验明细等大表可能需要较长时间扫描。

```powershell
# 只盘点全部表、字段、主键、索引和估算行数
python .\scripts\audit_remote_cdm_schema.py --mode metadata

# 在结构盘点之外，输出已配置同步表的汇总水位；仍不输出原始记录
python .\scripts\audit_remote_cdm_schema.py --mode profile

# 仅在需要精确行数时使用；会对每张可执行同步表运行 COUNT(*)
python .\scripts\audit_remote_cdm_schema.py --mode profile --exact-count
```

如不使用 `.env`，可传入连接串；脚本不会将密码写进 JSON、Markdown 或控制台输出。

```powershell
python .\scripts\audit_remote_cdm_schema.py `
  --remote-url "postgresql://audit_user:***@10.0.0.10:5432/source_db" `
  --remote-schema public `
  --mode coverage
```

## 交付物

每次运行会生成两个同名时间戳文件：

```text
reports/remote-schema-audit/
├── remote-cdm-schema-audit-YYYYMMDD-HHMMSS.json
└── remote-cdm-schema-audit-YYYYMMDD-HHMMSS.md
```

重点查看 Markdown 的三个部分：

- **同步映射差异**：`source_table_missing` 表示当前物理表名不存在；`field_gap` 表示源表存在但无法满足同步主键合同。
- **LX0609 来源覆盖**：`source_capability_gap` 表示正式规则所需来源未被当前源库/同步目录证明可用，不能把它当作临床内容缺失。
- **数据概要**：仅包含行数、三坐标完整行数和最新业务时间；空表是正常业务状态，不等于来源缺失。

## 当前已知边界

- 配置覆盖（系统设置保存的同步表映射）优先于代码默认值；报告以运行时 `list_sync_tables()` 为准。
- `profile` 模式的估算行数来自 PostgreSQL 统计信息，可能有延迟；需要精确统计时才显式加 `--exact-count`。
- 脚本只做发现与报告，不会自动修改映射。任何“相似表名”都必须由人核对字段和三坐标后，再通过同步配置或代码修复接入。

## 一键同步并质控的资料范围

`/api/v1/sync/trigger` 在 `auto_qc_after_sync=true` 时固定使用
`luxian_0609_formal` 资料集。该资料集与 `sample_full_domain` 共用同一份
已纳管证据表清单，但不会依赖客户历史 `sync/sync_tables` 覆盖配置中的
`enabled` 值。

这用于兼容早期客户机“仅启用核心 9 表”的旧配置：一键质控会显式同步
检查、检验、医嘱、会诊、手术与同意书等正式来源。普通手动同步仍遵循
管理员保存的启用开关。

客户升级并重启后，应重新执行本审计脚本；确认 `luxian_0609_formal` 中的
检查、检验、医嘱、会诊、手术、输血资料均能完成预检后，再进行真实病例
的“源库 → CDM → Bundle → 规则证据”对账。
