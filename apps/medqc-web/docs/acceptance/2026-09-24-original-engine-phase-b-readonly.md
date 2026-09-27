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

## 后续最小证伪结果（本树独立测试）

新测试 `backend/tests/unit/test_luxian_0609_task_plan_freeze_probe.py` 使用与上文集成树哈希相同的 Worker、bundle 服务和 `execution.py` 生产文件，真实调用 `run_sichuan_workspace_batch_job → SichuanQCService.evaluate_running_final_bundle_input → prepare_luxian_0609_execution`。任务仅有一份合成病历，选择原始 `LX0609-01-01-01` 与原始 004 `LX0609-09-01-01`，逐病例评价时点固定为 `2026-07-20`。Settings 使用两个真实 `Settings` 实例；测试只控制 Worker 和服务两处 `get_settings` 返回顺序并记录读取次数。计划探针调用原生产构造函数再记录返回值，不替代计划。Evidence Session 仍由原构造函数创建，源表 reader、bundle 加载与证据组装的源表/详情回退 I/O 返回空合成材料；模型客户端一旦调用即抛异常。Workspace 是既有测试中的内存替身。

| 配置路径 | 计划构造调用 | 选中规则/评价时点 | 任务结果 |
| --- | --- | --- | --- |
| Worker 与逐病例服务均启用 basic timeliness | Worker 任务级、Worker 展示侧、bundle 服务、`prepare`，共 4 次 | 四次计划同选原始 001/004；`prepare` 与 Evidence Session 均收到 `2026-07-20` 和同一逐病例 horizon | `completed`；无模型调用 |
| Worker 启用、服务关闭该家族 | Worker 两次、bundle 服务一次，共 3 次；未进入 `prepare` | 前两次为原生 001/004；服务级计划把两条归入兼容范围，正式门禁拒绝 | `failed`，无 Evidence Session 读取、无客户 items；未观察到“改变成功结果后继续交付” |

因此已证实**当前这一种家族开关漂移路径失败关闭**；不能推论所有开关组合、跨进程部署或多病例并发都如此，也不能据此把阶段 A 医学验收标为完成。四次纯计划构造是可重复的调用量事实；未测 CPU 耗时或客户病历准确率，不将其称为性能缺陷。第一轮搭建探针时发现证据组装会主动回退到源表：曾对故意不可连接的本机 `127.0.0.1:1` 测试地址发起连接并失败，没有接触客户库或写入；随后明确替换此 I/O。最终可复跑命令从 `backend` 目录运行：

```powershell
@'
import os, pytest
os.environ['JWT_SECRET'] = 'plan-probe-only'
os.environ['DATABASE_URL'] = ''
raise SystemExit(pytest.main([
    'tests/unit/test_luxian_0609_task_plan_freeze_probe.py',
    '--confcutdir=tests/unit', '-q', '--disable-warnings', '--tb=short',
]))
'@ | python -X utf8 -
```

最终运行 2/2 通过，`--confcutdir=tests/unit` 避免全局 `conftest` 初始化持久化依赖；`DATABASE_URL` 为空，测试中所有数据库与模型 I/O 边界均被替换。本次仅增加测试与报告，未改生产代码。

## 后续最小生产修复（本树独立提交）

上述只读结论保留为修复前基线。经独立审查后，只收敛已复现的两次 Settings 所有权：Worker 在任务开始解析 `resolve_mainline_rule_decision_settings(get_settings())` 后，仅正式 LX0609 bundle 调用把该对象显式传入 `SichuanQCService.evaluate_running_final_bundle_input`；门面透传给 running/final bundle 服务。服务对显式传入的正式任务直接使用这一对象，继续执行既有 `assert_luxian_0609_customer_native_delivery_ready` 与正式 native 计划门禁，并把同一对象交给 `prepare`。独立调用未传参数、以及非 LX0609 调用，仍走原 `get_settings` 路径。逐病例规则选择、版本标签、评价时点、医学判据、Prompt、并发值与计划构造位置均未改；三个大文件只加入口参数和单处配置选择，因为已证问题恰在这些入口的重读边界，不做结构拆分。

同一探针扩展为两份合成病历，均选原始 001/004，Worker 初次配置启用 basic timeliness，服务的受控 `get_settings` 在后续可返回相同或关闭此族的另一对象。两种路径均 `completed`，服务读配置 0 次，`prepare` 对两份病例都收到 Worker 的同一 settings 对象、同一规则集合、原任务逐病例 horizon 和 `2026-07-20` 时点。每份病例原始 001 为 `data_gap / authoritative_time_missing`，004 为 `not_applicable / trigger_absent_complete`；两路径完全相同。计划仍共构造 7 次：Worker 任务级一次，逐病例 Worker 展示、bundle 服务、`prepare` 各一次。独立正式入口不传参数时读取配置一次；显式传入非法非主链配置不读取环境但仍被门禁拒绝；非 LX0609 即使收到可选参数也仍读取自己的配置一次。生产文件中未找到对 `settings` 对象的赋值或 `setattr` 写入。

本修复仅消除**单个已接纳任务内** Worker 与服务重复读取环境导致的失败关闭路径，不能冻结部署后规则代码、跨子任务启动的配置，也不能据合成病例断言真实临床准确率或阶段 A 验收完成。测试 4/4 通过且全部数据库/模型 I/O 被替换，复跑命令仍为上节命令。该文件名沿用只读审计名；本节仅记录审计后获授权的独立最小修复，历史基线数字不得当作修复后表现。

收尾回归发现既有服务门面测试精确比较参数：未显式传入任务配置时，若转发 `task_settings=None` 会改变旧调用形状。现仅在非空时透传；Worker 也仅对正式 LX0609 bundle 传该参数。修复后，任务配置探针、服务门面和冻结评价时点入口共 17/17 通过；原生主链配置相关用例 3/3、Worker 的非 LX0609 bundle 和时点/正式入口相关用例 5/5 通过。另有 `test_full_luxian_batch_worker_uses_unified_customer_package_entry[programmatic]` 与 `[customer]` 两个旧测试仍使用三位 `LX0609-001` 等编号，在 Worker 第 1314 行的既有四段式编号门禁失败，未到本次第 2316 行配置透传；它们不计入通过。Python 编译检查通过。Ruff 对本次新增代码未报错；`sichuan_qc_service.py` 全文件的 7 处旧告警在修改前的 `HEAD` 文件中已复现。前端 `npm run lint`、`npm run type-check` 因本工作树未安装 `eslint`、`vue-tsc` 而无法启动，未作为通过项。
