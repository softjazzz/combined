# V3.6 规则集版本发布合同（P1-E1 后端）

> 日期：2026-09-27。用户已确认：质控点的上线、下线和启停不直接改动正在执行的规则，而是先存为草稿，再发布成新的规则集版本。已建任务继续使用冻结时的版本，新任务选用新版本。改动只在规则目录和版本发布这一层，不改执行器的判定逻辑。

## 1. 证据（已核实）

- `qc_rule_sets.SICHUAN_RULE_SETS` 是静态字典，每个 key 只有一个版本（0609 为 `2026-06-09`，0916 为 `2026-09-16`）。`get_sichuan_rule_set` 只按 key 查找。
- `task_qc_run_service.py:84-86` 要求任务冻结的版本等于当前目录版本。版本一变，已建任务就无法运行。
- `sichuan_workspace_batch_prepare.py` 按静态的 phase 划分和 `LUXIAN_0609_CUSTOMER_EXCLUDED_RULE_IDS` 生成 filters 中的 `rule_ids` 和 `paused_customer_rule_ids`。
- `sichuan_workspace_batch_worker.py:1601-1619` 输出结果投影时，又按**当前**的静态 phase 和 EXCLUDED 名单做了一次补充和过滤。
- 执行器只接受规则主表 JSON 中已有的规则（`phase_scope.py:171-172`）。只有 `phase_1_target` 的规则可以执行。

## 2. 版本存储（迁移 61，`qc`/`public` 双建）

表 `qc_rule_set_versions`：

| 列 | 约束 |
|---|---|
| `id` | VARCHAR(36) 主键 |
| `rule_set_key` | VARCHAR(96)，非空 |
| `version` | VARCHAR(64)，非空 |
| `status` | `draft` / `published` / `retired` |
| `base_version` | VARCHAR(64)，非空，记录从哪个版本派生 |
| `entries_json` | TEXT，非空：`[{rule_id, state: active\|paused\|offline}]`，按 rule_id 排序且不重复 |
| `content_digest` | VARCHAR(64)，发布时写入；entries 的规范化 SHA-256，用于检测发布内容的完整性和漂移 |
| `note` | TEXT |
| `version_seq` | INTEGER，CAS 用 |
| `created_by`、`created_at`、`published_by`、`published_at`、`retired_by`、`retired_at` | — |

约束：

- 唯一 `(rule_set_key, version)`。
- 部分唯一索引 `(rule_set_key) WHERE status='draft'`：每个规则集最多一份草稿。
- CHECK：非 draft 状态必须有 `content_digest` 和 `published_at`。
- 已发布的版本不可修改，服务端用条件更新保证；只允许从 `published` 变成 `retired`。

## 3. 解析（只有一个 owner：`rule_set_version_service.resolve_rule_set_version(key, version)`）

返回值：

```
{
  "rule_set_key", "version",
  "source": "builtin" | "published" | "retired",
  "active_rule_ids", "paused_rule_ids", "excluded_rule_ids",
  "content_digest"
}
```

- **内置版本**：`SICHUAN_RULE_SETS` 当前的 version。解析结果必须与现有静态逻辑**完全一致**：
  - active 为现行执行的规则；
  - paused 为 phase 未就绪的规则；
  - excluded 为 `LUXIAN_0609_CUSTOMER_EXCLUDED_RULE_IDS`；
  - `content_digest` 用同一算法对等价的 entries 计算。
  - 表里没有任何行时，系统行为与现在逐字节相同。
- **已发布或已下线的版本**：取自 `entries_json`。
- `current_version(key)`：最近一次 `published` 的版本；没有时取内置版本。
- 不存在的版本抛出 `RuleSetVersionNotFound`。
- 0916 本批只支持内置版本：创建 0916 草稿返回 409 `unsupported_rule_set`；解析仍返回内置版本。

## 4. 发布校验（草稿 → published）

- entries 必须覆盖基础版本的全部规则。不能引入规则主表之外的新规则，也不能漏掉已有规则。
- `active` 只允许用于当前可执行的规则（phase 可执行，并且执行器有实现）；其余规则只能是 `paused` 或 `offline`。
- 至少要有 1 条 active。
- 发布与 digest 写入在同一事务内完成。版本号由发布人填写，不能与已有版本重复。

## 5. 接入运行链

以下改动都不改变判定逻辑：

1. **任务创建**：冻结 `current_version(key)`。
2. **`task_qc_run_service`**：把“冻结版本等于当前版本”改为“冻结版本能被解析（builtin/published/retired 均可）”。历史上版本为 NULL 的任务保持现有拒绝语义。
3. **`prepare_workspace_batch_job`**：
   - 任务运行按冻结版本解析，其他入口按 `current_version` 解析。
   - 用解析结果生成 `rule_ids`（active ∩ 调用方所选规则）、`paused_customer_rule_ids`，并排除 excluded。
   - filters 新增 `rule_set_content_digest`，同时写入 `idempotency_payload`。
4. **worker 投影**：filters 中带 `rule_set_content_digest` 的新 job，以 filters 里的 paused/excluded 为准，不再读取当前的静态名单。没有 digest 的历史 job 保持原逻辑（兼容逻辑只留在旧路径）。
5. Canonical 完整性校验本来就按 filters 中的集合做，这里不改。

**等价性要求**：表为空（只有内置版本）时，同一输入下的 prepare filters（除新增的 digest 字段外）、worker 投影、Canonical 结果与改动前完全相同。必须有金样对比测试。

## 6. 接口（管理规则的权限沿用现有规则管理路由的写法：admin/qc_manager）

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/api/v1/rule-set-versions?rule_set_key=` | 版本列表，标明当前版本 |
| GET | `/api/v1/rule-set-versions/{key}/{version}` | 版本详情 |
| POST | `/api/v1/rule-set-versions/{key}/draft` | 从指定基础版本创建草稿，已有草稿返回 409 `draft_exists` |
| PUT | `/api/v1/rule-set-versions/{key}/draft` | 修改草稿，按 version_seq 做 CAS |
| DELETE | `/api/v1/rule-set-versions/{key}/draft` | 删除草稿 |
| POST | `/api/v1/rule-set-versions/{key}/draft/publish` | 发布，请求体 `{version, note}` |
| POST | `/api/v1/rule-set-versions/{key}/{version}/retire` | 下线；不能下线当前版本，也不能下线内置版本 |

## 7. 不在本批

- 前端质控点列表和发布界面放在 P1-E2。
- 测试病历放在 P1-E3。
- “新建质控点”要让它真正执行，需要先有执行器实现和规则主表条目，这属于质控引擎范围，只能标为需要执行器配合。

## 8. P1-E1c：读取侧版本化（移除发布闸门的前提）

### 8.1 证据

`custom_qc_workspace_service.py` 读取侧的多个入口默认 `rule_set_version=RULE_SET_VERSION`（静态值），并用静态的 `LUXIAN_0609_CUSTOMER_EXCLUDED_RULE_IDS` 过滤条目：

- 病历池摘要 `build_luxian_0609_completed_record_result_summaries`
- 单病历 DTO `build_latest_single_record_result_dto`
- 批量 DTO `build_latest_luxian_0609_record_result_dtos`
- 统计分析等其余入口

同样用静态名单过滤的还有 `qc_sichuan.py:3108`。发布新版本后，新 job 的 `rule_set_version` 与静态值不一致，会被这些选择器排除。

### 8.2 合同

- **版本集合**：读取侧不再用单一静态版本，改为“该规则集的已知版本集合”：内置版本，加上全部 `published`/`retired` 版本（草稿除外）。
  - 由 `rule_set_version_service.known_versions(key)` 提供，只有一个 owner。
  - 同一请求内只读库一次；版本表为空时直接返回 `{内置}`，不读库。
- **最新结果选择**：在已知版本集合内做，跨版本仍按现有的代次/完成时间规则取最新一次。
  - `select_latest_authoritative_record_result_job` 的比较逻辑不变，只是候选范围从单一版本放宽为版本集合。
- **条目排除**：
  - job 的 filters 带 `rule_set_content_digest` 时，以 filters 中的 `excluded_customer_rule_ids` 为准；
  - 否则沿用静态名单（历史 job）。
  - 被版本暂停的规则按 worker 投影的 not_executed 原样展示，读取侧不再重新判定。
- **版本号展示**：结果 DTO 中的版本号取所选 job 的 filters 版本，不再写死静态值。
- **等价性**：版本表为空时，上述每个入口在同一输入下的输出与改动前逐键相同（金样对比，方法同 P1-E1b）。
- **发布闸门**：以上全部完成并验证后，删除 `PUBLISH_ENABLED` 及其测试开关。补充端到端用例：发布暂停一条规则的新版本，新 job 结果能在病历池摘要、单病历 DTO 和导出中看到，且该规则显示为未执行；历史 job 仍可见。
