# 客户样本同步性能验收

## 当前状态

**待客户机实测。**

本地环境无法连接客户源库，因此本文不填写或推测任何性能数字。验收工具也不会把
密码、Token、客户源库地址或患者信息写入结果文件。

## 验收样本

分别准备 8、30、100 份真实脱敏病例的独立样本池。每组至少覆盖：

- 在院病例和出院病例；
- 手术病例；
- 输血病例；
- 包含检查、检验报告的病例。

“首次同步”必须使用尚未被当前版本同步过的新样本池；随后在源数据不变化的情况下，
立即执行第二次同步。

## 采集指标

- `source_resolve_ms`
- `primary_visible_ms`
- `detail_sync_ms`
- `bundle_refresh_ms`
- `total_duration_ms`
- `rows_pulled`
- `rows_upserted`
- `tables_skipped_unchanged`
- `visits_refreshed`
- `retry_count`

后端没有明确返回的指标保持 `null`，不得用估算值代替。

## 通过标准

- 病历首次可见时间相比旧版本基线下降至少 70%；
- 30 份病例第二次无变化同步耗时相比旧版本基线下降至少 70%；
- 首次完整同步耗时相比旧版本基线下降至少 40%；
- 第二次无变化同步的 `visits_refreshed` 为 0；
- 在院、出院病例均可见，资料完整性与当前全量同步一致；
- 客户源库连接错误率不增加。

缺少旧版本基线或新版实测值时，结论必须为 `pending`，不能标记通过。

## 使用命令

生成不含任何虚构数据的验收模板：

```powershell
python backend/scripts/benchmark_customer_sample_sync.py `
  --template-output C:\temp\customer-sample-sync-acceptance.json
```

将登录 Token 放入临时环境变量。Token 不会进入命令参数或结果文件：

```powershell
$env:MEDQC_BENCHMARK_TOKEN = '<临时访问令牌>'
```

执行 8、30、100 份病例的首次和第二次无变化同步：

```powershell
python backend/scripts/benchmark_customer_sample_sync.py `
  --run `
  --base-url 'http://localhost:8000' `
  --pool '8:八份病例样本池ID' `
  --pool '30:三十份病例样本池ID' `
  --pool '100:一百份病例样本池ID' `
  --output C:\temp\customer-sample-sync-acceptance.json
```

把旧版本基线填入 JSON 中的 `baseline_first` 和
`baseline_second_unchanged` 后，校验并重新计算结论：

```powershell
python backend/scripts/benchmark_customer_sample_sync.py `
  --validate C:\temp\customer-sample-sync-acceptance.json
```

工具返回码：`0` 表示完成且没有失败项，`1` 表示存在明确失败项，`2` 表示参数、
连接、权限、任务或文件错误。`pending` 会保留在结果中，不会被误报为通过。

## 本地回归证据

截至 2026-07-31：

- `sync_pool_records` Task 3–6 聚焦回归：15 项通过；
- Bundle assembly、scene cache、attention report 聚焦回归：21 项通过；
- 已覆盖无变化不刷新、仅变化病例刷新、多表变化单次刷新、Material Snapshot
  每表单次读取和出院收口失败不回写状态。

上述结果只能证明功能回归和查询复用逻辑，不能替代客户机真实源库的性能验收。
