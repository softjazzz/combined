# V3.6 筛选模板与审核状态默认筛选合同（P1-A）

> 日期：2026-09-27。对应 PRD 第 3 节中的“筛选：新建/快捷/修改/重置筛选”“筛选模板”“默认筛选与快捷筛选”。本批只覆盖 V5 运行/终末病历列表（`/api/medical-records/workstation`）；门急诊的结果身份尚未核实，不纳入。

## 1. 列表按审核状态筛选

- 接口新增可选参数 `review_state`：逗号分隔的多个值，取值限定为 `pending_review`、`pending_recheck`、`approved`、`doubtful`，非法值返回 422。
- 筛选的依据是审核服务的批量推导 `batch_review_states`，也就是列表上显示的同一个值，服务端不另行判定。
  - 只有 ready 的结果才有审核状态；
  - 未质控、技术错误的病例在这个参数下一律不命中。
- 执行顺序：在“其他筛选条件得出的完整集合”上先按审核状态过滤，再分页。`total` 与 `qc_summary` 都按过滤后的集合计算。
- 失败语义：带了 `review_state` 时，如果审核状态批量读取失败，整个请求返回 503，因为无法兑现筛选，也不能返回未过滤的结果。不带这个参数时，维持 P0-2 的降级语义（审核状态显示为“未知”）。
- 性能：审核状态批量读取按 visit 分块查询；在 PG 隔离库上用合成数据实测耗时。

## 2. 筛选模板存储（迁移 59，`qc`/`public` 双建）

表 `qc_user_filter_templates`：

| 列 | 约束 |
|---|---|
| `id` | VARCHAR(36) 主键 |
| `owner_id` | VARCHAR(64)，非空、非空白 |
| `page_key` | VARCHAR(48)，非空，取值限定为 `v5_records_inpatient`、`v5_records_discharged` |
| `name` | VARCHAR(50)，非空、非空白 |
| `filters_json` | TEXT，非空 |
| `is_default` | BOOLEAN，非空，默认 false |
| `version` | INTEGER，非空，默认 1，用于 CAS |
| `created_at` / `updated_at` | 非空 |

- 唯一约束 `(owner_id, page_key, name)`。
- 部分唯一索引 `(owner_id, page_key) WHERE is_default`：每个用户在每个页面最多一个默认模板。
- 每个用户每个页面最多 20 个模板，由服务端在事务内加行锁计数校验。
- `filters_json` 只允许以下白名单键，服务端逐键校验类型和取值：
  - `dept`、`doctor`、`keyword`：字符串，≤100；
  - `start_date`、`end_date`：ISO 日期；
  - `date_field`：`visit`/`admission`/`discharge`/`updated`；
  - `inpatient_sort`：`default`/`longest`/`recent`；
  - `review_state`：上述四值的数组。
- 未知键或非法值返回 422。模板不保存页码和分页大小。

## 3. 模板接口（需登录；只能操作本人的模板，访问他人模板一律返回 404）

- `GET /api/v1/filter-templates?page_key=`：本人该页全部模板，按 `is_default` 降序再按 `name` 排序。
- `POST /api/v1/filter-templates`：请求体 `{page_key, name, filters, is_default?}`。
  - 设为默认时，在同一事务内取消该页原来的默认；
  - 重名返回 409 `name_conflict`，超出上限返回 409 `limit_reached`。
- `PUT /api/v1/filter-templates/{id}`：请求体 `{version, name?, filters?, is_default?}`。
  - CAS：`version` 不一致返回 409 `version_conflict`；成功后 `version+1`。
- `DELETE /api/v1/filter-templates/{id}?version=`：CAS 删除。
- 数据库故障返回固定脱敏的 503。

## 4. 前端（V5 `QcRecordResultListView`）

- **快捷筛选**，内置、不入库：
  - “全部”；
  - “待审核”（`review_state=pending_review`）；
  - “待复审”（`pending_recheck`）；
  - “审核中”（前两者合并）。
  - 后三项只对 admin/qc_manager 显示。
- **系统默认**：
  - 审核角色首次进入时，默认使用“审核中”，对应手册“病历默认覆盖待审核、待复审”；
  - 其他角色默认“全部”；
  - 用户设置了默认模板时，以默认模板为准。
- **模板操作**：应用、另存为、更新当前模板、设为或取消默认、删除、“重置”（回到系统默认）。
  - 409 冲突时提示并刷新列表；
  - 模板加载失败不阻塞列表，只提示模板不可用。
- **切页**：URL 的 query 仍是当前筛选的唯一来源；应用模板等同于写入 query。
