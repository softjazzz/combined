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
