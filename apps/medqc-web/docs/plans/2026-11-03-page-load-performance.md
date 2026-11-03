# 登录后页面加载优化 Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 降低客户样本验证首屏等待，保持既有认证、范围、模型配置优先级和质控结果合同。

**Architecture:** 在a2cde7b5f的独立工作树实施。重抽屉首次打开才载入，并保留首次打开后的组件状态；列表只等待会影响筛选口径的规则集目录，不等待并发参数和完整规则说明。配置环境快照按环境与文件身份失效，调用方拿独立副本；数据库配置仍实时读取，慢同步操作在线程中执行。

**Tech Stack:** Vue 3 / Vite / Vitest，FastAPI / Pydantic Settings / AnyIO / pytest。

## 固定证据与取舍

原浏览器记录：212个脚本、14.03MB解码JS，首次Ant Design依赖优化触发重载；重载后列表/任务约6.9秒。只读剖析模型摘要0.35～0.90秒，SQL0.6～1.4毫秒，主要为重复Settings解析和冷导入，异步链未让出事件循环。这些不是生产包吞吐验收。

不改整个工作台路由或权限，不缓存用户授权/患者结果，不用未加载的并发上限启动任务，不直接给Settings加永不失效的全局单例。不打包或调整运行中服务，隔离固定应答验证后交付本地提交。

### Task 1: 环境配置快照与异步配置读取

- 修改`backend/app/core/settings.py`、`backend/app/services/llm_config_loader.py`。
- 新建`backend/tests/unit/test_settings_snapshot.py`，补配置加载器隔离反例。
- 先验证同输入重复解析、调用方可变对象污染、环境/文件/工作目录变化、错误配置、显式失效；验证慢数据库读取期间事件循环可继续处理独立任务。
- 最小实现仅复用环境解析；数据库模型选择每次读取，Provider错误仍失败关闭，不缓存失败或隐式换模型。
- 使用`python -B scripts/run_qc_scheduler_tests.py --profile offline ...`，阻断真实网络/数据库。

### Task 2: 首屏加载及初始化

- 修改`src/views/workstation-v4/customer-sample-validation/useCustomerSampleValidationController.ts`、`CustomerSampleValidationView.vue`及现有视图测试。
- 先用延迟Promise证明参数/规则说明/同步状态不应阻止列表，并验证目录仍先于范围相关请求、参数未就绪时不能启动任务。
- 保留原请求/结果所有者；同样本集已确定后独立读取并行，旧样本集及卸载后的响应失效。
- 大抽屉使用`defineAsyncComponent`，初次关闭状态不挂载；首次打开后保持组件，避免关闭重置导致交互回退。正文预览/对照工作台沿原条件按需载入。
- 固定响应验证打开、关闭、重开、结果轮询及错误提示，不调用真实质控。

### Task 3: 开发依赖预优化

- 修改`vite.config.mjs`，补已确认的Ant Design依赖入口，保持生产分包合同不变。
- 通过既有Vite合同测试及源码首屏依赖图验证；不生成生产包。

### Task 4: 收口

- 聚焦前后端测试、编码、Ruff、只读ESLint、类型检查及必要的范围/轮询回归。
- 用合成数据和固定响应比较请求顺序、首次渲染及模块依赖；不能用Mock宣称真实客户页面已加速多少。
- 只暂存本任务文件并本地提交。保持集成分支、现有服务、业务库和所有未提交材料不动；不调用模型、不运行患者质控。

## 实施与验收记录

实际基线为`a2cde7b5fcf0f36f8c82680fc2d8f488b1f38c87`，独立工作树`C:\medqc-page-load-20261103`，分支`codex/page-load-performance-20261103`。

- 环境配置只缓存已验证的解析快照；环境、工作目录或dotenv文件身份变化即失效，显式失效入口为`clear_settings_snapshot()`。返回深拷贝，失败配置不缓存，文件密钥目录启用时跳过快照。账号、授权、数据库模型配置及患者结果不缓存。
- 模型配置数据库读取及环境配置冷加载在线程池执行，仍沿用原持久配置优先级和失败关闭合同。
- 列表仅等待决定筛选范围的规则集目录；并发设置和规则说明并行加载，同步状态与病历列表并行读取。配置加载期间禁用启动操作，保留原有配置读取失败的既定回退。旧请求及卸载后响应不能覆盖当前列表。
- 结果、审核、比较抽屉及文书工作台按需载入；抽屉首次打开后保留实例。补加载和失败反馈，关闭后不残留错误占位。不改V7.1布局、导航和权限。
- Vite预优化仅补本次实际发现的Ant Design入口，生产分包不变。不能保证所有其他页面未来都不会触发开发依赖优化。

### 隔离验证

后端在`backend`执行（Python 3.10）：

```text
python -B scripts/run_qc_scheduler_tests.py --profile offline tests/unit/test_settings_snapshot.py tests/unit/test_llm_config_loader.py tests/unit/test_settings_llm_env_alias.py tests/unit/test_strata_admin_configuration.py tests/unit/test_llm_config_permissions.py tests/unit/test_luxian_0609_task_settings_snapshot.py tests/unit/test_luxian_0609_family_children_settings_readonly.py
```

150项通过。另执行以下兼容保护：

```text
python -B scripts/run_qc_scheduler_tests.py --profile offline --suite context-budget-p5b tests/unit/test_settings_snapshot.py tests/unit/test_llm_request_observation.py tests/unit/test_qc_llm_client_thinking_budget.py
```

497项通过。两组存在重叠，不能相加为独立覆盖数量。使用隔离Runner、合成配置和固定应答，不连接业务库或模型。

前端在`apps/medqc-web`执行：

```text
node node_modules/vitest/vitest.mjs run --config vitest.page-load.config.ts tests/unit/views/workstation-v4/CustomerSampleValidationView.spec.ts tests/unit/views/workstation-v4/customer-sample-validation/deferredComponent.spec.ts tests/unit/router/customer-sample-validation-permissions.spec.ts tests/unit/services/llm-config-service.spec.ts tests/unit/vite-manual-chunks.spec.ts
```

5文件90项通过，0跳过。额外网络阻断覆盖fetch、HTTP、HTTPS、socket和TLS；组件及接口使用固定响应。验证待配置/慢同步不阻塞列表、筛选依赖顺序、过期响应失效、抽屉真实打开/关闭/重开、异步资源失败。既有测试原先仅检查隐藏抽屉存在，现改为检查任务卡片和实际打开状态，避免把始终挂载误当自动打开。

完整`vue-tsc --noEmit`通过；改动Python的Ruff、定向ESLint及全量`src`只读ESLint通过。未执行带`--fix`的lint命令，避免改动无关文件。未运行全量前后端测试、浏览器候选版本验收、生产构建或部署；本轮聚焦测试没有失败或跳过。

### 性能证据及限制

同一Vite转换配置、只递归静态应用源码依赖（不含第三方库和样式），基线首屏104模块、1897KB，候选47模块、657KB。重抽屉及首页表单不再进入首屏静态依赖图。此项是依赖削减证据，不等于实际浏览器传输量或登录耗时。

同一份300键合成dotenv、禁网络、连续10次读取：基线总360.27ms、热读均值36.01ms；候选总35.84ms、热读均值0.16ms，首次解析约34ms。该微基准不能代表真实账号或客户数据库性能。

运行中的前后端保持集成工作树的`a2cde7b5f`，本轮没有重启。优化需要用户后续选择加载独立分支后再验证实际首屏耗时，不能声称线上页面已经加速。集成工作树原有6项未跟踪材料保留，未推送、合并、写业务库、调用模型或重跑质控。

## 5750b8c48启动后只读观测与科室503

用户随后授权切换服务，前后端均已在独立工作树加载5750b8c48，P5-B关闭、启动跳过DDL/预热/恢复；未提交材料保留。以下是既有浏览器Performance记录，非新增登录试验：

| 区间/请求 | 耗时 |
| --- | --- |
| 客户样本页面模块开始加载→病历列表响应完成 | 2319.7ms |
| 客户样本页面模块开始加载→最近任务响应完成 | 2872.4ms |
| 初始化API开始→病历列表响应完成 | 998.8ms |
| 初始化API开始→最近任务响应完成 | 1551.5ms |
| 模型配置摘要/规则集目录/规则说明，并行请求 | 551.0/428.0/429.1ms |
| 样本池 | 85.0ms |
| 同步状态/病历列表，并行请求 | 425.4/427.1ms |
| 最近任务 | 338.1ms |

同一导航先加载系统配置页，约21.3秒时才进入客户样本页。因此不能把navigation的24.2秒当成样本页加载时间，也不能用与此前6.9秒不同的导航/缓存条件计算加速比例。尚未重新登录测量。脚本传输量受浏览器缓存和此前页面共同影响，不能当作首屏模块图的直接验收。

系统配置页的源科室接口为503，日志明确是源PG的10秒连接超时。`list_remote_departments`固定读取源PG的`discharge_record`，不是本机业务库科室表；路由在async函数直接执行同步连接，造成同批其他配置请求也等待约10.5秒。本地副本不能代替源端同步筛选范围，因此不伪造200或空列表。

最小修复仅把源科室读取放到已有Starlette线程池，保留来源元数据、权限、500条上限、503/422语义，不新增重试、缓存或数据库写入。新增固定应答反例已在旧代码得到1失败/2通过，准确复现事件循环阻塞。源PG可达性仍需部署网络/连接配置恢复，应用改动不能使不可达的源库自行恢复；本轮不更改连接配置、不主动重试源PG、不重启服务加载这项后续修复。

修复后隔离命令：`python -B scripts/run_qc_scheduler_tests.py --profile offline tests/unit/test_sync_departments_async.py tests/unit/test_sync_router.py::TestSyncRouter::test_departments_value_error_maps_422 tests/unit/test_sync_router.py::TestSyncRouter::test_read_permission_matrix tests/unit/test_sync_router.py::TestSyncRouter::test_write_permission_matrix`。6项通过、0跳过；涵盖独立请求可继续执行、元数据、无重复重试、源失败保持503及配置错误422、原读写权限矩阵。Ruff通过，编码及diff检查通过；本次仅Python一处调用修改，沿用上一提交已通过的全量前端lint/类型和90项隔离前端结果，不重复运行未改动的前端。未执行全量后端、真实源库恢复或新版本浏览器耗时验收。

## 源科室静默后台加载

用户确认科室仍必须连接原服务器，本次只改变读取时机和等待方式。在同一独立分支以e51639753为基线实施，沿用工作台字段提示和按钮，不更换导航、布局、模型或医学合同。

选择独立异步任务，不采用本地旧表回退、永续轮询或持久科室缓存：打开系统设置即发起读取，科室Promise不再进入控制台初始化等待链；同页重复读取合并为一次请求。保留原源PG接口、权限和服务端503/422，客户端沿用原30秒HTTP超时。读取中/失败仅在科室字段旁显示轻提示和手动重试，不弹窗，不改变已选科室或扩大为全院。

离开页面时通过AbortSignal结束前端HTTP等待，并失效旧结果和finally；这不承诺强行中止服务端已在进行的PG连接，它仍受原有连接超时限制。保存新连接成功后失效旧科室请求并后台刷新；页面已离开时，旧保存响应不会再启动科室读取。默认系统设置页和直接进入模型等页签均启动后台读取，但不阻止其他页签使用。

先在原实现运行新增固定应答保护：4项均失败，分别证明初始化阻塞、重复读取、失败弹窗、卸载后旧响应污染。实现后最终隔离命令：

```text
node node_modules/vitest/vitest.mjs run --config vitest.page-load.config.ts tests/unit/views/workstation-v4/useDataSync.background.spec.ts tests/unit/views/workstation-v4/useDataSync.spec.ts tests/unit/views/workstation-v4/DataSyncConfigPage.spec.ts tests/unit/services/sync-departments.spec.ts tests/unit/views/workstation-v4/components/qc/QcSyncAndRunControl.spec.ts
```

5文件82项通过，0跳过。包含真实composable初始化与固定网络应答、字段重试、慢科室时切换模型设置、AbortSignal适配、源错误不转换为空成功、原同步权限/范围及既有同步控件。完整vue-tsc、全量src只读ESLint、改动测试定向ESLint、编码和diff检查通过；未执行全量单元集或新版本真实浏览器源连接验收。本次测试主动阻断网络，不访问业务数据库、源PG或模型，没有真实同步或质控任务。

未重启前后端。运行后端仍是5750b8c48，需后续重启加载e51639753的配套线程池修复，才能消除源连接超时对后端其他请求的阻塞；前端开发服务器会按Vite机制热更新源文件。未改集成分支及其未提交材料，未推送、合并或部署。

## PR #30 CI复核与补充门禁

复核固定Head为6842e5c65，Base仍a2cde7b5f，PR保持Draft且未合并。四个PR工作流均成功：零模型质量门实际日志为11961通过、0失败、0超时；前端类型检查通过，各定向批次131/54/43通过；调度器分批通过，既有双模型组保留2个私有材料跳过；一次性基础设施检查及故障矩阵通过。不能把这些重叠批次相加为独立验收数。

确认的覆盖缺口：前端工作流没有明确运行样本主页面、静默后台composable及API测试；调度器工作流没有明确运行新增配置快照和科室非阻塞测试。补入原工作流，保留全部原步骤；前端及后端新步骤仍在Linux的`unshare --net`内执行，并叠加既有Node传输层阻断/前端隔离配置或后端offline Runner，不放宽隔离。补齐相关文件触发条件，独立修改入口/API/测试时也会触发前端检查。

增加2项快照边界测试：工作目录变化不能沿用相对dotenv快照；文件密钥目录启用时必须每次解析。只使用合成环境及临时空目录，未读取真实密钥或dotenv内容。本轮不改运行逻辑或医学合同。

本机重跑新前端CI步骤（Windows不执行Linux命名空间包装，保留其余相同命令）：

```text
node --require ./scripts/frontpage-v2-no-network.cjs node_modules/vitest/vitest.mjs run --config vitest.page-load.config.ts tests/unit/views/workstation-v4/CustomerSampleValidationView.spec.ts tests/unit/views/workstation-v4/customer-sample-validation/deferredComponent.spec.ts tests/unit/router/customer-sample-validation-permissions.spec.ts tests/unit/services/llm-config-service.spec.ts tests/unit/vite-manual-chunks.spec.ts tests/unit/views/workstation-v4/useDataSync.background.spec.ts tests/unit/views/workstation-v4/useDataSync.spec.ts tests/unit/views/workstation-v4/DataSyncConfigPage.spec.ts tests/unit/services/sync-departments.spec.ts tests/unit/views/workstation-v4/components/qc/QcSyncAndRunControl.spec.ts
```

10文件172项通过、0跳过。新后端步骤在相同offline Runner执行配置快照、环境别名、科室异步、422及原读写权限矩阵：57项通过、0跳过。Ruff、定向只读ESLint、两份workflow YAML解析与网络隔离命令检查、编码和diff检查通过。类型检查由原Head CI完整执行通过；本轮没有TypeScript修改，不重复全量检查。未在本机重跑全量零模型门或一次性PG/MQ；新提交的远端CI另行跟踪，不能沿用旧Head状态声称新Head已通过。

未连接业务库、源PG或模型，不运行患者质控、不改集成分支、不重启服务。现有源PG不可达、真实成功返回科室链路及生产包/多用户性能限制仍保留。
