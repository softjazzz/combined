# 测试库 PG Schema 整合 Runbook

目标：

- 将测试库里残留在 `public` 的 CDM 主表迁入 `cdm`
- 将同步状态表迁入 `sys`
- 保持 `qc` 现有对象不变

适用范围：

- 仅测试库
- 不直接用于生产库

## 目标落位

迁入 `cdm`：

- `mr`
- `diagnosis`
- `mr_surgery`
- `mr_cost`
- `admission_record`
- `discharge_record`
- `medical_insurance_settlement`
- `medical_insurance_settlement_cost`
- 以及本次 Alembic revision 中列出的其余 CDM 表

迁入 `sys`：

- `sync_visit_status`
- `sync_watermarks`

保留不动：

- `qc.*`
- `public.qc_result`
- `public.alembic_version`
- `public.llm_*`
- `public.user_profiles`

## 执行前

1. 备份测试库

```powershell
pg_dump -Fc -d medqc -f medqc_before_cdm_sys_realign.dump
```

2. 跑迁移前检查

```powershell
cd apps/medqc-web/backend
psql "$env:DATABASE_URL" -f scripts/db_migration/05_precheck_cdm_sys_realign.sql
```

3. 建议设置 split schema

```env
DB_SCHEMA_MODE=split
DB_SEARCH_PATH=qc,sys,cdm,public,legacy
```

## 执行

```powershell
cd apps/medqc-web/backend
alembic -c alembic.ini upgrade head
```

本次新增 revision：

- `20260330_000005`

## 执行后

1. 跑迁移后检查

```powershell
cd apps/medqc-web/backend
psql "$env:DATABASE_URL" -f scripts/db_migration/06_postcheck_cdm_sys_realign.sql
```

2. 跑接口/链路冒烟

- 登录
- `/api/v1/sync/status`
- `/api/v1/sync/preflight`
- Workstation V4 病例详情
- 首页质控
- 结算质控

3. 跑全链路总控脚本

```powershell
cd apps/medqc-web/backend
py -3.10 -m scripts.run_mongo_pg_v4_e2e `
  --backend-base-url http://localhost:8001 `
  --frontend-base-url http://localhost:3000 `
  --api-email admin@medqc.com `
  --api-password <PASSWORD>
```

## 回滚

优先方案：

- 直接恢复测试库备份

脚本化方案：

```powershell
cd apps/medqc-web/backend
alembic -c alembic.ini downgrade 20260327_000004
```

这会把本次迁移移动过的表回到 `public`。
