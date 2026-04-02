# MongoDB→PG→Workstation V4 全链路测试

这套文档和脚本用于跑一条固定的双层验收链路：

1. 自动化：`MongoDB -> PG -> 首页/结算质控接口`
2. 人工核对：`Workstation V4` 同病例页面验收

核心入口：

- [run_mongo_pg_v4_e2e.py](/d:/LLM/lx0222/health-qc-monorepo/apps/medqc-web/backend/scripts/run_mongo_pg_v4_e2e.py)
- [执行说明.md](/d:/LLM/lx0222/health-qc-monorepo/apps/medqc-web/docs/testing/e2e-mongo-pg-v4/执行说明.md)
- [持久化验收口径.md](/d:/LLM/lx0222/health-qc-monorepo/apps/medqc-web/docs/testing/e2e-mongo-pg-v4/持久化验收口径.md)
- [前端人工核对清单.md](/d:/LLM/lx0222/health-qc-monorepo/apps/medqc-web/docs/testing/e2e-mongo-pg-v4/前端人工核对清单.md)

## 推荐执行命令

```powershell
cd d:\LLM\lx0222\health-qc-monorepo\apps\medqc-web\backend
py -3.10 -m scripts.run_mongo_pg_v4_e2e `
  --backend-base-url http://localhost:8001 `
  --frontend-base-url http://localhost:3006 `
  --api-email admin@medqc.com `
  --api-password <PASSWORD> `
  --with-persistence-checks
```

## 输出物

每次执行会在 `backend/reports/mongo_pg_v4/<run_id>/` 下生成：

- `mock_seed_report.json`
- `case_e2e_report.json`
- `summary.json`
- `summary.md`

## 状态解释

- `PASS`：自动化链路通过，且人工核对也已完成
- `WARN`：自动化链路通过，但有差异告警，或人工核对尚未完成
- `FAIL`：同步、落库、质控接口或关键环境预检失败

当前脚本默认只会给出：

- 自动化 `PASS/WARN/FAIL`
- 总体 `WARN/FAIL`

原因是前端人工核对默认还处于 `pending`。

## 持久化验收

如果要把数据库写入一起纳入自动化验收，执行时加：

```powershell
py -3.10 -m scripts.run_mongo_pg_v4_e2e --with-persistence-checks
```

当前脚本会真实验证：

- `qc_results`
- `qc_defects`
- `notifications`
- `ai_frontpage_draft`
- `frontpage_extracted_fields`
- AI 首页快照表组
  - `ai_mr_snapshot`
  - `ai_diagnosis_snapshot`
  - `ai_mr_surgery_snapshot`
  - `ai_mr_cost_snapshot`

具体断言口径见 [持久化验收口径.md](/d:/LLM/lx0222/health-qc-monorepo/apps/medqc-web/docs/testing/e2e-mongo-pg-v4/持久化验收口径.md)。
