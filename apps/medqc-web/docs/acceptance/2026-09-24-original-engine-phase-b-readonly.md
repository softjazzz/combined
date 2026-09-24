# 原始 0609 引擎阶段 B：生产入口只读事实清单

本记录只读核对集成树 `codex/lx0609-rule-id-integration` 的代码时点 `0c0ce16aee795deae7cec49602ea1032ce5a5887`。未访问患者库或模型，未运行会写入本地数据库的测试；“重复构造”是代码路径事实，“结果漂移”仅是待证风险。以下 `文件:行号` 均指该集成树。

## 三种生产使用方式与实际调用链

| 使用方式 | 规则选择和任务入口 | 到 `prepare` 的路径 |
| --- | --- | --- |
| 单病历正式 LX0609 | `routers/qc_sichuan.py:1854` 的 `/workspace/batch-jobs` 接受单份三坐标 `record_refs` 和客户规则 ID；`1865` 已把单病历用于正式诊断采集。`1879–1921` 校验并从当前规则集取得规则 ID、版本标签。 | 与下行共用 `qc_sichuan.py:1821–1845` → `sichuan_workspace_batch_worker.py:1240` → `2306` → `sichuan_qc_service.py:4515–4556` → `sichuan_qc/running_final_bundle_service.py:176` → `luxian_0609/execution.py:203`。 |
| 病历池批量 | 同一 `/workspace/batch-jobs` 冻结任务 `filters.rule_ids/rule_set_version/record_refs` (`qc_sichuan.py:2131–2170`)，按病例运行同一 Worker。 | 同上；Worker 按病例从 `record_rule_map` 或任务规则取得 `active_rule_ids` (`sichuan_workspace_batch_worker.py:1951–1960`)，逐病例调用正式 bundle 服务。 |
| 客户样本 | `routers/qc_sample_pools.py:985` 的样本运行入口；`1140–1235` 决定规则集与选择，`1365–1410` 写入 `job_filters`，`1540–1657` 可拆家族父/子任务，`1693–1709` 的单叶任务直接提交。 | 子任务或单叶任务都调用 `qc_sichuan._run_sichuan_workspace_batch_job`，随后与病历池共用 Worker 和 `prepare`。父任务本身不执行规则，Worker `1251–1253` 跳过。 |

容易误认的入口：`qc_sichuan.py:1540` 的 `/evaluate-rule-for-visit` 进入 `sichuan_qc/legacy_rule_service.py:18–97`，按旧单规则/旧 bundle 运行，调用 `_evaluate_rules_orchestrated` 时没有 LX0609 包 key；`/test-rule` 对 LX0609 文本测试明确返回 422 (`qc_sichuan.py:3528–3564`)。`luxian_0609/preproduction_runner.py` 是预生产验收入口，也不是上述第三条生产主链。`/evaluate-bundle` 的通用适配器默认 `rule_set_key=""` (`qc_input_adapters/running_final_bundle_runtime.py:72–111`)，不能仅凭它调用同一个服务方法就算正式 LX0609 包执行。

## 已冻结什么，未冻结什么

- **规则选择**：病历池创建时在任务 `filters` 保存 ID 和 `rule_set_version` (`qc_sichuan.py:1913–1933, 2131–2170`)；客户样本还保存选定样本、逐病例规则映射及家族子任务过滤器 (`qc_sample_pools.py:1220–1250, 1365–1410, 1588–1615`)。Worker 读取这些过滤器 (`sichuan_workspace_batch_worker.py:1270–1316`)，按病例选择 `active_rule_ids` (`1951–1960`)。原生规则包装器在 Worker 初始化时通过 `get_luxian_0609_rule` 逐项装载 (`1494–1531`)，目录加载在进程中用 `lru_cache` (`luxian_0609_rule_catalog.py:22–64`)；这不是每个任务保存的规则正文快照。
- **版本**：`rule_set_version` 是任务过滤器和结果观测的版本标签 (`sichuan_workspace_batch_worker.py:1313, 3111`)。未找到 Worker 按该标签重载、比对或锁定当时规则正文/依赖清单的路径。部署跨越排队任务时旧标签与新进程代码可能不一致，这是待验证风险；本次未证明真实任务已发生这种漂移。`load_luxian_0609_dependency_inventory` 在单进程 `lru_cache(maxsize=1)` (`native_package.py:277–287`)，因此同进程内重复计划构造通常共用目录对象。
- **Settings**：Worker 启动任务时调用 `resolve_mainline_rule_decision_settings(get_settings())` (`sichuan_workspace_batch_worker.py:1328`)，用此对象做正式包门禁和任务级计划 (`1330–1352`)。每份病例的 `running_final_bundle_service.py:79–84` 再调用 `get_settings()` 并解析一次，传给 `prepare` (`176–188`)；`get_settings` 每次新建 `Settings()` (`core/settings.py:376–383`)，不是缓存的任务配置。`prepare` 内部使用传入的同一 settings 构造自己的计划 (`execution.py:245–260`)，此局部不存在第三次读取环境。
- **评价时点**：新正式任务在创建时固定 `task_frozen_date` 并建立逐病例 `record_evaluation_snapshot` (`qc_sichuan.py:2035–2045`；样本 `qc_sample_pools.py:1345–1356`)，随后放入过滤器。Worker `1912–1944` 按病例解析 `evaluation_as_of_date` 与 horizon policy；`2288–2318` 将快照和时点传到正式 bundle 服务，最终 `execution.py:298–338` 传给 Evidence Session。对于升级前无逐病例快照的已排队任务，Worker 明确回退到过滤器中的旧 `evaluation_as_of_date`，不能把它与新任务同等称为已冻结。

## 重复计划与证据等级

`native_package.py:290–420` 的 `build_luxian_0609_package_plan` 仅据传入的 inventory、规则集合和开关构造不可变计划；`421–487` 的 settings 包装只读取传入对象。**没有证据显示该纯构造函数自身有业务副作用或必须重写。**当前确有多处构造：Worker 任务级 `1344` 用于门禁；逐病例 `1964` 用于展示执行阶段批次（失败仅影响展示）；正式 bundle 服务 `running_final_bundle_service.py:104` 用于选兼容规则和门禁；真正执行的 `execution.py:254` 再构造一次，随后读取证据并执行。任务级与服务级还分别读取 Settings。重复次数随病例数增加，这是可确认的计算/一致性边界；本次没有运行时计数、耗时或规则结果差异，不能宣称性能回归或医学错判。

已有失败关闭门禁：Worker 任务级检查正式计划不可落入兼容执行 (`sichuan_workspace_batch_worker.py:1344–1352`)，服务级同样检查 (`running_final_bundle_service.py:103–112`)，而 `prepare` 按其本次计划派发。这减小了配置不一致被静默交付的风险；是否存在“Worker 计划通过、服务读取另一配置后改判或失败”的真实序列仍须受控复现。客户样本多家族子任务分别启动 Worker，故不同启动时点读取配置的边界同样是待验证风险，不是已发生缺陷。

## 阶段 B 最小证伪试验

1. 使用纯内存 Worker/服务替身，固定一份和两份病历的 `filters.rule_ids`、`record_rule_map`、`rule_set_version`、逐病例 horizon。猴补计划构造、`get_settings`、`prepare` 与 Evidence reader，只记规则集合、开关、评价时点和计划调用次数；禁止真实 DB/LLM。先确认单病历与样本子任务共用调用链、展示侧额外计划不会影响执行计划。
2. 在同一假任务中使 Worker 首次 settings 与服务逐病例 settings 返回不同的某个原生家族开关，观察是服务门禁失败、计划身份变化还是结果仍正常；对比任务版本标签与实际计划。只有出现可复现的客户状态/原因/调用量差异，才认定为需修的结果缺陷；单纯重复纯函数不够。
3. 固定新任务逐病例 snapshot，并给旧任务仅 `evaluation_as_of_date`，断言两条传参路径到 `prepare` 与 Evidence Session 的时点一致或明确不同。再核对同一病例两条生产提交方式的选中规则、状态/原因、证据引用、调用/Token 与耗时。

现成测试入口可复用：`tests/unit/test_luxian_0609_native_package.py` 的纯计划与 pending/compatibility 边界；`tests/unit/test_luxian_0609_mainline_services.py:2352` 的正式开关及 as-of 传递、`2446` 的单次内部快照；`tests/unit/test_qc_sichuan_batch_throughput.py:323` 的 Worker 运行期家族漂移失败关闭、`2969` 的逐病例时点缺口，以及 `2691/3658/3789` 的原生批量入口；`tests/unit/test_qc_sample_pools_router.py:1934/2396/2431` 的客户样本规则范围和子任务。上述用例不等于本任务提出的“双次 settings 返回不同对象”证伪试验。

阶段 B 目前无需为纯计划构造新增框架；先运行上述最小试验取得是否漂移、是否失败关闭、调用量与耗时证据，再决定有无必要收敛配置/计划的所有权。
