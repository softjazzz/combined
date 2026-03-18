# 现网平滑迁移到 Alembic + 同库分 schema（执行脚本清单）

## 目标
- 将现网库纳入 Alembic 版本管理
- 启用同库分 schema：`qc / sys / cdm / legacy`
- 不中断业务（短时只读窗口）

## 前置约束
- 应用版本已包含 revision:
  - `20260315_000001` baseline
  - `20260315_000002` split schema
- 数据库已完成备份

## 步骤 0：只读窗口（建议 5-10 分钟）
1. 暂停写入任务（抽取、质控执行、申诉/整改写操作）。
2. 保留读接口，避免迁移期间对象变更冲突。

## 步骤 1：迁移前检查
```powershell
cd apps/medqc-web/backend
psql "$env:DATABASE_URL" -f scripts/db_migration/01_precheck_split_schema.sql
```

检查点：
- `alembic_version` 可读
- 关键对象当前位置可见（大概率在 `public`）

## 步骤 2：接管 Alembic 版本（存量库）
如果现网已有人工建表，不希望重复跑 baseline：

```powershell
cd apps/medqc-web/backend
alembic -c alembic.ini stamp 20260315_000001
```

## 步骤 3：执行 split schema 迁移
```powershell
cd apps/medqc-web/backend
alembic -c alembic.ini upgrade head
```

## 步骤 4：应用配置切换
在部署环境设置：

```env
DB_SCHEMA_MODE=split
DB_SEARCH_PATH=public,qc,sys,cdm,legacy
```

然后滚动重启应用。

## 步骤 5：迁移后检查
```powershell
cd apps/medqc-web/backend
psql "$env:DATABASE_URL" -f scripts/db_migration/02_postcheck_split_schema.sql
```

检查点：
- `alembic_version = 20260315_000002`
- QC 表在 `qc`，SYS 表在 `sys`
- `medical_records/medical_documents` 在 `cdm`
- 6 个统计视图在 `qc`

## 步骤 6：接口冒烟
1. `GET /api/v1/scoring-rules`
2. `GET /api/v1/scoring-config`
3. `GET /api/v1/notifications`
4. `GET /api/v1/reports/qc-summary`
5. `GET /api/v1/staff-ranking`

预期：全部 200，且无 `relation not found`。

## 回滚（紧急）
1. 执行对象回滚：
```powershell
cd apps/medqc-web/backend
psql "$env:DATABASE_URL" -f scripts/db_migration/03_rollback_to_public.sql
```
2. 版本回滚：
```powershell
cd apps/medqc-web/backend
alembic -c alembic.ini downgrade 20260315_000001
```
3. 配置回滚：移除 `DB_SCHEMA_MODE/DB_SEARCH_PATH`，重启应用。
