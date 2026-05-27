# 同步明细成功但缺 mr 修复说明

## 根因

本次问题的直接表现是：一键同步返回 `success`，明细表已有数据，但病历池不新增。客户机样本中，`2404019`、`2404311`、`2406109`、`2412559` 在 `admission_record`、`discharge_record`、`orders`、`course` 等明细表存在数据，但 `cdm.mr=0`、`public.visit_index=0`。

代码策略层面的根因是：

- 同步策略可以先从 `discharge_record` 等明细表生成 `eligible_visit_ids`。
- `mr` 主病历虽然会按 `visit_id` 拉取，但当远端返回 0 行时，后续明细表仍可继续同步成功。
- 旧 summary 没有输出 `missing_mr_visit_ids`、`detail_only_visit_count` 等关键诊断字段。
- 缺 `mr` 时 `visit_index` 无法生成病历池记录，但旧结果仍可能表现为静默 `success`。
- 幂等 key 只覆盖粗粒度参数，不同 `date_window`、`target_departments`、`table_groups` 存在复用旧结果风险。

## 修复策略

### 1. 强制 mr by visit_id backfill

当 PG 表同步使用明细表生成 `eligible_visit_ids` 后，同步任务会确保 `mr` 在目标表列表中优先执行，并以 `eligible_visit_ids` 为范围拉取主病历记录。

这避免只依赖 `mr` 自身日期字段或科室字段过滤导致漏拉。

### 2. detail-only visit 显式 partial

如果某些 eligible visit 在明细表中有数据，但 `mr` 未拉到，不再静默成功。同步结果保留已写入的明细数据，但状态至少为 `partial`，并输出 warning：

```json
{
  "success": true,
  "status": "partial",
  "eligible_visit_count": 8,
  "mr_rows_pulled": 4,
  "mr_rows_upserted": 4,
  "detail_only_visit_count": 4,
  "missing_mr_visit_ids": ["2404019", "2404311", "2406109", "2412559"],
  "detail_only_visit_ids": ["2404019", "2404311", "2406109", "2412559"],
  "detail_tables_with_rows": ["admission_record", "discharge_record", "inpat_drug_order"],
  "visit_index_upserted_count": 4,
  "visit_index_failed_count": 0,
  "visit_index_skipped_missing_mr_count": 4,
  "warnings": ["同步部分完成：部分病历缺少 mr 主记录，病历池暂不可见"]
}
```

`success=true` 表示明细同步本身没有回滚；`status=partial` 表示病历池可见性未完全达成，需要处理缺失 `mr`。

### 3. visit_index 结果进入 summary

同步 summary 新增：

- `visit_index_upserted_count`
- `visit_index_failed_count`
- `visit_index_skipped_missing_mr_count`

如果 `visit_index` 写入失败或全部跳过，不阻断明细同步，但会进入 warnings。

### 4. 幂等 key 收紧

新幂等 key 纳入以下范围参数：

- `source` / `tier`
- `date_window.start` / `date_window.end`
- `target_departments`
- `table_groups` / `tables`
- `scene`
- `policy_version`
- `operator`

旧幂等记录不迁移；新触发使用新 key，避免不同同步范围复用旧结果。

### 5. 前端 partial 处理

前端同步触发结果支持 `status=partial`：

- partial 显示 warning，不再显示“同步任务未启动”。
- `idempotent_reused=true` 时显示“已返回已有同步结果”。
- 成功和 partial 都会刷新状态统计并进入轮询。

## 客户机验证命令

以下 SQL 均为只读检查示例，按客户机实际 schema 调整。

### 1. 检查 mr 是否补拉

```sql
select visit_id, count(*) as rows
from cdm.mr
where visit_id in ('2404019','2404311','2406109','2412559')
group by visit_id
order by visit_id;
```

### 2. 检查明细表是否为 detail-only

```sql
select 'admission_record' as table_name, visit_id, count(*) as rows
from cdm.admission_record
where visit_id in ('2404019','2404311','2406109','2412559')
group by visit_id
union all
select 'discharge_record' as table_name, visit_id, count(*) as rows
from cdm.discharge_record
where visit_id in ('2404019','2404311','2406109','2412559')
group by visit_id
order by visit_id, table_name;
```

### 3. 检查病历池索引

```sql
select visit_id, sync_status, sync_scene, source_table
from public.visit_index
where visit_id in ('2404019','2404311','2406109','2412559')
order by visit_id;
```

### 4. 检查同步接口返回

重新触发同一范围同步后，重点查看返回 JSON：

- `status` 是否为 `partial` 或 `success`。
- `detail_only_visit_count` 是否为 0。
- `missing_mr_visit_ids` 是否为空。
- `warnings` 是否包含缺 `mr` 主记录提示。
- `idempotency_key` 是否随 `date_window`、`target_departments`、`table_groups` 变化。

## 边界

- 不伪造 `mr` 主病历记录。
- 不回滚已成功同步的明细表。
- `detail_only_visit_count > 0` 时不再静默 success。
- 病历池仍以真实 `mr` 主记录为可见性前提；缺 `mr` 的 detail-only visit 只作为同步缺口暴露。

## 后续建议

如果客户机仍出现 `detail_only_visit_count > 0`：

1. 先确认远端源库按 `visit_id` 查询 `mr` 是否存在。
2. 如果远端有 `mr` 但本地没拉到，继续排查 `mr` 字段映射、schema 和权限。
3. 如果远端也没有 `mr`，应按源数据缺口处理，不能由同步服务伪造主记录。
