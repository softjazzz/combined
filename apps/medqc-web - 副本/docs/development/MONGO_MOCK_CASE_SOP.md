# Mongo 全量 Mock 病历 SOP（25集合 + 双 visit）

## 1. 目标

生成 1 个患者、2 条就诊（已出院 + 在院中）的全量 Mongo mock 病历，覆盖 `MONGO_COLLECTION_MAP` 全部 25 集合，并可直接用于 Mongo→PG→首页/医保质控联调。

---

## 2. 一键造数

在 `apps/medqc-web/backend` 目录执行：

```bash
python -m scripts.seed_mongo_mock_case \
  --patient-id P-MOCK-001 \
  --visit-id-discharged V-MOCK-D-001 \
  --visit-id-inpatient V-MOCK-I-001
```

说明：

- 默认使用 `etl_config` 中的 `mongo_uri` 和 `mongo_database`
- 默认 `upsert`，可重复执行不重复膨胀
- 已出院 visit 固定历史出院时间，可满足 Tier1 发现条件
- 默认同时写入 PG：`medical_insurance_settlement` + `medical_insurance_settlement_cost`

---

## 3. 仅验证（不写入）

```bash
python -m scripts.seed_mongo_mock_case \
  --verify-only \
  --patient-id P-MOCK-001 \
  --visit-id-discharged V-MOCK-D-001 \
  --visit-id-inpatient V-MOCK-I-001
```

输出报告字段：

- `case_meta`
- `write_summary`
- `pg_settlement_summary`
- `coverage_summary`
- `consistency_checks[]`
- `final_status`

报告目录：`apps/medqc-web/backend/reports/mock_seed/`

---

## 4. 与全链路脚本串联

先造数，再跑全链路验收：

```bash
python -m scripts.seed_mongo_mock_case \
  --patient-id P-MOCK-001 \
  --visit-id-discharged V-MOCK-D-001 \
  --visit-id-inpatient V-MOCK-I-001

python -m scripts.run_case_e2e \
  --patient-id P-MOCK-001 \
  --visit-id V-MOCK-D-001 \
  --tier all \
  --with-generate-qc
```

建议用“已出院 visit”做主链路验收；“在院 visit”用于观察系统首页/结算/质控差异行为。

---

## 5. 前端预期表现

1. 已出院 visit：

- 系统首页可读取
- 首页形式质控可执行
- 医保结算清单质控可执行

2. 在院 visit：

- 系统首页可读取（若同步成功）
- 结算相关结果可能部分缺失或提示不足（属于预期）

---

## 6. 常见问题排查

1. Mongo 连接失败

- 检查 `apps/medqc-web/backend/app/data/mongo_sync_config.json` 中 `mongo_uri`

2. Tier1 没发现病例

- 确认已出院 visit 的 `discharge_datetime` 早于 `now - discharge_stable_days`
- 确认 `target_departments` 未把对应科室过滤掉

3. 覆盖率不足

- 查看 `coverage_summary.per_collection`，定位缺失集合与对应 visit

4. 主键完整性失败

- 查看 `consistency_checks` 的 `pk_integrity_*` 项，补齐对应集合主键字段
