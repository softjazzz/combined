# 样本池服务职责拆分只读审计（阶段 C）

日期：2026-09-05  
范围：`backend/app/services/custom_qc_sample_pool_service.py`（6718 行、178 个符号）。本文件是只读审计产物，不包含生产代码、数据库或接口变更。

## 结论

**建议下一独立任务只迁移“人工问题分类与候选规则推荐”到一个完整深模块；暂不迁移病例匹配、住院范围或同步。**

建议模块：`backend/app/services/sample_pool_issue_classification.py`。它的唯一职责是把人工问题文本与已知文书范围规范化为稳定的分类、场景和候选规则集合；不读写样本池表、不访问远端病例库、不创建任务，也不解释同步状态。该边界已由现有调用链和冻结测试覆盖，且没有其他生产模块直接调用该族函数。

同步链不能在同一任务顺手拆分：它已经委托 `CaseScopeService`、`CaseSetSyncService`、Bundle 刷新和病例索引，且其事务、锁、三坐标、同步水位及失败语义跨多个提交。拆出局部函数会制造第二个同步编排者，而不是消除一个完整所有者。

## 审计证据与调用链

CodeGraph 已在本地最新索引上审计：该服务被 90 个文件引用，但多数是服务模块或测试的间接关系；按具体入口检索，分类函数没有外部生产调用，匹配/范围/同步均由样本池路由和少数维护脚本进入。

| 业务职责               | 当前权威实现（精确位置）                                                                                                           | 主要入口/调用方                                                                                                   | 状态与外部依赖                                                                                    |
| ---------------------- | ---------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------- |
| Excel 导入与初始分类   | `load_manual_case_rows_from_excel` 2364–2442；`create_pool_with_items` 3927–4005                                                   | 路由 `import-manual-sheet` 522–548、`import-upload` 550–592；维护脚本 `import_customer_manual_case_items.py`      | Excel 行字段 → 分类字段 → 样本池/条目；建池、写条目、计数器在同一 session 中提交                  |
| 人工问题分类与规则推荐 | `_normalize_issue_text` 478–483、关键词判定 589–1033、LLM 家族合同 1035–1509、分类/候选规则 1510–2363                              | `create_pool_with_items` 3963–3999、`refresh_pool_item_classifications` 4516–4597、`get_runnable_items` 5243–5305 | 仅文本、映射 JSON 和已同步 Bundle 文书目录；不依赖 `pool_id`、事务、身份或远端库                  |
| 本地/源库病例匹配      | 评分函数 2444–2565；`match_pool_items` 5119–5241；`match_pool_items_from_source` 5359–5451；`_resolve_remote_visit_keys` 5548–5709 | 路由 `/match` 770–788；维护脚本 `match_customer_manual_case_items.py`；同步前解析                                 | 写入 `matched_{institute,patient,visit}_id`、match/sync/bundle 状态；依赖 CDM、远端 PG、`CaseRef` |
| 住院范围选择并追加条目 | 住院状态辅助函数 2571–3124；委托 `CaseScopeService` 5755–5775；预览 5804–5891；追加 5893–6020                                      | 路由预览 824–857、`sync-by-hospitalization` 860–898；旧入院过滤 900–946                                           | 以三坐标去重、回填和受控住院状态；范围结果随后进入同一异步同步任务                                |
| 同步任务与病例同步     | 作业状态 3676–3925；`sync_pool_records` 6276–6701；路由 worker `_run_sample_pool_sync_job` 336–479                                 | `/sync-records` 790–821、住院范围/入院过滤路由；公共 `CaseSetSyncService`                                         | advisory lock、任务状态、远端拉取、本地 upsert、Bundle 刷新、住院状态水位和后匹配                 |
| 池 CRUD / 任务归属     | list/get 3464–3528；最新任务唯一解析 3530–3567；删除 3569–3665；最新任务指针 6703–6717                                             | 样本池路由 481–769、同步/运行路由；四川工作台共享最新任务解析                                                     | 表计数器、删除保护、活跃任务阻断、共享结果只读定位                                                |

路由的统一角色门在 `backend/app/routers/qc_sample_pools.py:60–63`：只有 `admin`、`qc_manager`、`sync_admin` 可访问。`test_qc_sample_pool_permissions.py:30–43` 已冻结 `sync_admin` 允许而 `doctor` 拒绝；不应把权限判断下沉或复制进分类模块。

## 两个候选的比较

| 维度         | 人工问题分类与规则推荐                                                                                | 病例匹配 / 住院范围 / 同步                                                                                                                          |
| ------------ | ----------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------- |
| 完整职责     | 文本与文书可见范围 → `coverage_type`、`issue_category`、`expected_scene`、候选规则                    | 样本条目 → 三坐标病例 → 范围、源表同步、Bundle、状态回写                                                                                            |
| 生产调用面   | 只由当前服务内部的导入、刷新、可运行条目三处使用；无其他生产文件直接调用                              | 2 个路由入口及维护脚本，还与 `qc_sichuan` 的最新任务归属、公共病例同步相连                                                                          |
| 共享可变状态 | 无；输入/输出均为普通字典和列表                                                                       | 样本池/条目/同步任务表、CDM 表、远端源库、Bundle、病例索引、任务指针                                                                                |
| 已有冻结测试 | 分类、家族推荐、动态候选、Excel、刷新：`test_custom_qc_sample_pool_service.py:189–1186`、4120–4128    | 匹配 1842–1939、2168–2254、4236–4328；住院范围 1294–1941；同步 1942–3702、3738–3798；路由 668–854                                                   |
| 历史证据     | 分类映射与动态候选来自 2026-04-23/24（`e31bab944`、`41ab3a464f`），近期同步重构未改其独立输入输出合同 | 2026-07-31 `b2dee3375` 单次新增约 2713 行，2026-08-09 `4eafb71d9` 将 725 行同步逻辑移交 `CaseSetSyncService`，2026-08-10 `17500014f` 继续统一住院链 |
| 迁移判断     | 可作为一个完整、可测试的深模块迁移                                                                    | 证据支持暂缓：边界横跨公共服务与多阶段持久化，当前拆分收益不足以抵消安全风险                                                                        |

这里的选择不以文件行数为理由；决定性证据是分类职责没有持久化/远端/作业状态的共享所有者，而同步职责拥有这些不可分割的合同。

## 推荐的后续任务（不在本阶段实施）

### 模块合同与白名单

新模块只提供以下公共语义入口（名称可在开工前复核，行为不可改变）：

```python
classify_manual_issue_text(text) -> Classification
build_sample_pool_item_classification_update(row) -> dict
derive_dynamic_candidate_rule_ids_from_source_tables(source_tables) -> list[str]
derive_document_scope_labels_from_source_tables(source_tables) -> list[str]
apply_sample_sc_rule_whitelist(items) -> list[dict]
normalize_admission_consistency_llm_output(...)
build_admission_issue_family_prompt(...)
resolve_admission_consistency_rule_recommendations(...)
normalize_consultation_family_llm_output(...)
build_consultation_family_prompt(...)
resolve_consultation_family_rule_recommendations(...)
```

实施文件白名单：

1. 新增 `backend/app/services/sample_pool_issue_classification.py`。
2. 修改 `backend/app/services/custom_qc_sample_pool_service.py`：删除被迁移的分类职责，导入上述入口；保留 `create_pool_with_items` 3927–4005、`refresh_pool_item_classifications` 4516–4597、`get_runnable_items` 5243–5305 作为数据库编排者。
3. 修改 `backend/tests/unit/test_custom_qc_sample_pool_service.py`：将纯函数测试移至新模块或直接导入新模块；保留服务级持久化测试。
4. 如需要，新增 `backend/tests/unit/test_sample_pool_issue_classification.py`。不修改路由、数据库 schema、`CaseScopeService`、`CaseSetSyncService`、Bundle 或前端。

迁移单元应覆盖服务现有的 478–2363 分类族（约 1,886 行连续业务职责）。开工前还要先解决一个已确认的依赖边界：分类代码使用 `_safe_text`（341–350）、`_safe_json_dumps/_loads`（352–368）和 `_sanitize_json_value`（418–427），但这些基元也被服务前半段的任务签名、选中范围以及后半段的匹配、同步、状态回写大量使用，不能简单下移后再让主服务反向依赖“分类”模块。首次迁移应保留父服务现有基元，并在新模块内使用命名受限、测试冻结的私有输入正规化；不得让新模块反向导入主服务。若实测证明 JSON 安全语义必须全局单一，再另行评审中性的已有工具归属，不能在本次结构迁移中顺手新增公共平台层。预计父服务删除约 1,850–1,900 行、新模块新增约 1,860–1,920 行、导入和测试搬迁后生产代码净变化约 0 至 +40 行。该估计须在实际 diff 中复算；不以添加样板代码凑行数。

### 冻结验收

在迁移前后对同一输入逐项比较，不比较随机时间或任务 ID：

1. `coverage_type`、`issue_category`、`expected_scene`、`candidate_rule_ids`、`include_in_batch_1`、`exclude_reason` 完全相同。
2. 入院与会诊家族的白名单过滤、非法 LLM rule ID → `uncertain/review_required`、`no_hit` 时子项状态的合同完全相同。
3. 空问题、时效问题、复制粘贴、入院一致性、会诊执行、手术/输血/交接班等既有样本保持结果；运行现有 `test_custom_qc_sample_pool_service.py` 中 189–1186 和 4120–4128 的相关测试。
4. 导入 → 创建条目与刷新分类的持久化测试仍通过：`test_refresh_pool_item_classifications_should_update_existing_items`（1133 起）及 Excel 用例（1192–1283）。
5. `get_runnable_items` 的动态文书候选和 SC 白名单仍通过：`test_get_runnable_items_sc_should_*`（4518 起）。
6. 迁移后做一次路由导入/上传的聚焦测试；不得为保持测试而留下从主服务到新模块再回主服务的循环导入或转发壳。

## 同步链的不可拆分合同与风险门禁

以下不是本阶段要修复的缺陷；它们是任何未来同步重构必须保持或先单立修复的事实。

| 合同 / 风险          | 当前证据                                                                                                                                                            | 对未来迁移的约束                                                                                                               |
| -------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------ |
| 同池排他             | `create_sync_job` 3676–3752 在 PG 使用事务级 advisory lock（72–86），对 queued/running 作业冲突失败；并发测试在 3738–3798                                           | 作业创建与排他检查必须仍在同一个数据库事务中，不能拆为“检查后异步插入”                                                         |
| 作业状态与删除       | delete 3569–3665 锁定池行并拒绝 active QC/sync 作业；路由把冲突映射为 409（672–694）                                                                                | 不得把同步作业状态移出池删除保护；`latest_job_*` 以真实任务表状态覆盖缓存字段（3267–3289）                                     |
| 取消 / 重试          | 同步作业 API 只有 create/get/latest/mark/progress/finish/fail（3676–3925）；样本池路由没有 cancel/retry 端点。`cancel_requested` 仅被删除保护识别                   | 当前取消/重试语义**未实现，不能假设存在**；若未来增加，须另立任务定义 CAS 状态迁移、重复 worker 投递与幂等键，并补失败重放测试 |
| worker 重入          | `_run_sample_pool_sync_job` 336–479 直接 `mark_sync_job_running`，该方法 3777–3811 不以 queued 状态 compare-and-swap                                                | 当前依赖一次 BackgroundTask 投递；未来抽离 worker 前应先证明并修复重复投递不会并发执行同一 job                                 |
| 三坐标身份           | 源匹配和同步使用 `CaseRef(institute_id, patient_id, visit_id)`；`_resolve_remote_visit_keys` 5548–5709 拒绝不完整坐标/冲突场景；范围去重也用同一三元组（5776–5802） | 禁止退化为仅 `visit_id` 或 `(patient_id, visit_id)`；默认机构号只可经过现有 `stamp_source_rows_institute_id` 入口              |
| 住院状态 / 水位      | 2571–2821 读写受控 `_sample_sync_state`；同步仅接受明确 active → discharged 转换，Bundle 刷新成功后才持久化（见 2873–3132 的测试）                                  | 不得将水位或状态回写提前到 Bundle 刷新之前；失败保持可重试状态而非假完成                                                       |
| 多阶段提交           | worker 先可能追加范围条目，后进入 `CaseSetSyncService.sync_case_set`，再回写匹配/状态；每个服务有自己的 session/提交                                                | 这是一条有明确补偿/失败语义的业务流程，不可宣称为单数据库事务；迁移时不得任意拆成更多提交或改变已存在提交次序                  |
| 主记录与详情失败语义 | 6276–6701 对无主记录、可选详情源表不可用、Bundle 刷新失败分别 fail-closed；覆盖于 2255–2367、2633–3327                                                              | 保持主记录可见、详情不完整、Bundle 未就绪三类结果的区别，不能把失败降为 ready/synced                                           |

## 已知剩余风险

1. 分类映射读取 `backend/data/synthetic_qc/sheet2_intrinsic_issue_mapping.json`（1510–1528）；它是候选规则的资料源，不是同步状态，迁移时须保留路径与失败时空映射的既有语义。
2. 分类族部分 LLM prompt/normalizer 当前主要由测试引用；迁移前须以 `rg`/CodeGraph 复核是否存在运行时动态调用。不能因“当前无直接调用”删除，除非另立行为删除任务。
3. `create_pool_with_items`、刷新分类和匹配各自负责各自 session 的计数器更新；推荐模块绝不能取得 SQLAlchemy session 或调用 `_update_pool_counters`。
4. 本审计没有对真实远端病例执行读写，也没有把合成测试等同于生产同步验收；同步、取消或重试的真实业务验收仍未完成。

## 本阶段验收记录

- 已检查计划指定的服务、三个指定测试文件和共享最新任务权限测试，以及 `qc_sample_pools.py` 与 `qc_sichuan.py` 的任务归属接口。
- 已检查历史提交：`41ab3a464f`、`b2dee3375`、`4eafb71d9`、`17500014f`、`0e663fc17`。
- 本阶段未运行会写数据库的同步测试、未修改生产代码、数据库、接口或前端。
