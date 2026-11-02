# 双数据抽取链路 Implementation Plan

**Goal:** 在系统配置中管理原 clinical_data/homology→业务CDM，以及 Caché→独立同步服务→独立CDM 两条链路。

**Architecture:** 保留原 PG 同步所有者，新增受持久管理员授权的独立服务适配器。应用只提交人工日期任务、查询、取消/重试；不实现第二套 Caché 抽取或开放定时。配置沿用业务库配置注册表，凭据由部署注入。读取独立 CDM 复用数据服务已验收的独立连接、三坐标和缓存合同；读取启用仍由部署配置控制，界面明确显示实际状态，不把选择抽取链路当成整个应用切源。

**Tech Stack:** Vue3 / TypeScript / Ant Design Vue、FastAPI、SQLAlchemy、httpx。

## 实施步骤

1. 从远端业务集成基线 e17ac959a6 新建 F 盘独立工作树，保留其他工作树。
2. 定向移植 b52aba103、dd2e167be、12f19c196 的读取适配与测试；不移植其迁移链，不覆盖 V7.1、Gateway、规则修复。解决 assembly 冲突时同时保留 PDF 状态列与独立CDM严格来源校验。
3. 新增 data_pipeline_settings 配置 owner：默认PG，独立链默认关闭；持久账号授权、版本竞争保护、损坏配置失败关闭；不保存密码、不在保存时联网。
4. 新增 sync_control_client，复用服务 /v1/interfaces 和 /v1/jobs；固定部署端点和部署token；禁止重定向、隐藏重试、异常内容泄漏；手工任务不自动质控。仅允许部署批准profile和远端批准接口，日期最多7天且不含医院当天。
5. 新增 data_pipelines API 和系统配置面板。原PG入口保留；两条链路任务与状态分开；显示实际读取源、覆盖限制，PDF材料仍归原业务库。
6. 严格离线验证：内存SQLite、模拟HTTP、固定应答；覆盖授权、幂等、失败/超时、取消、配置竞争、三坐标、切源/回滚缓存及既有入口。
7. 前端类型、编码、lint与定向组件/接口测试；本地提交，不推送、不合并、不部署。

## 边界及验收

- 不接触业务库、客户机、Caché或真实同步服务，不调用模型或执行质控。
- 页面载入和保存配置均不探测服务；连接检查必须显式点击。
- 读取源由 CDM_DATABASE_URL/CDM_PGPASSFILE 部署配置启用，需要重建进程连接池；抽取默认项可后台保存，不能误报所有列表/ORM已切源。
- 原业务库 engine/SessionLocal 及PDF归属保持；独立源错误不回退到业务同名表。
- 业务集成线现有062迁移链保持，不把CDM059迁移套到业务库。
- 真实服务、网络、应用身份只读授权、其他Bundle领域和完整住院材料覆盖仍待受控部署验收。

## 实现与配置说明

- 工作树：`F:\MedQC-worktrees\medqc-dual-data-pipeline-20261102`。
- 分支：`codex/dual-data-pipeline-settings-20261102`；基线：远端业务集成 `e17ac959a61ec9586e6d72708f290483def76525`。原本机集成工作树仍为 `a86da4f0b`，未移动。
- 入口：`/workstation-v5/system-config?tab=dataSync`。持久管理员（admin/sync_admin/super_admin）可设置默认展示链路、启用独立任务入口；原PG执行器、双源开关及其他已有调用者保持原职责。默认展示项不是对全站同步请求的隐式重路由。
- 独立链路的来源清单通过显式“检查服务与可用接口”读取。只使用部署批准的profile，支持已交接的字符串目录及常规对象目录；未批准或不可用接口禁止提交。
- 当前只接人工日期任务；预检默认 `dry,publish=false`，用户选择并确认后才可 `replay,publish=true`。不接自动增量、定时或同步后自动质控。
- 支持查询、取消及重试既有任务。任务状态、来源受限、失败与未返回计数如实显示；历史查询失败保留已读取记录。
- 提交超时等未知结果保留原操作UUID和请求，锁定范围；同账号同UUID发送同一远端幂等键。没有客户端隐藏重试；远端处理幂等与冲突。明确4xx拒绝允许修正范围。刷新浏览器会结束当前页面的未确认操作上下文，操作人员应先查看远端任务记录，不直接重复新建。
- 新配置仅存入原业务库既有 `qc.sync_config_registry`，命名空间 `sync/data_pipelines_v1`；带版本比较更新，配置损坏/读取失败不默认为另一个来源。无需增加迁移，不创建表。
- 部署提供 `SYNC_CONTROL_API_URL`（完整批准的origin，不带路径/凭据）、`SYNC_CONTROL_API_TOKEN`、`SYNC_CONTROL_PROFILE`（默认accepted_manual）。页面不接收任意URL、口令或客户端Token；上游重定向与环境代理关闭。
- `CDM_DATABASE_URL`、`CDM_PGPASSFILE`仍由部署管理。设置/撤下后按发布流程重建连接池；页面显示实际进程配置及静态校验，不宣称连接已通、全站已切源。无效配置不会回退业务库。
- 临床读取移植已有三键、同文书诊断栏目、唯一首页时间与报告/带药适配；保留当前目标分支的PDF状态和去重处理、规则修复。未移植独立数据分支的迁移、旧版前端或模型调用链。
- 同一CDM后续发布后的Bundle新鲜度、病例列表/旧ORM、首页V2及其他领域仍需部署范围内逐入口核对；本轮未建立发布成功后自动刷新全站Bundle的机制，不能据任务完成认定缓存全部更新。

## 部署和回滚

1. 本轮不修改实际配置或数据库，不部署。正式接入前核对原业务库已具备027配置表及目标应用迁移链；独立CDM的059不能直接套到业务库。
2. 按实际主机/容器网络配置服务URL、受保护token、CDM只读账号/passfile；不可直接放宽同步服务root凭据权限。独立链路开关默认关闭。
3. 发布应用后先显式检查服务目录，再按批准日期范围提交预检。数据发布与真实质控需按其范围授权，不能因配置保存自动执行。
4. 回退时将默认入口设回原PG、关闭独立任务入口；独立任务可查询/取消。撤下两个CDM环境项、按发布流程重建进程连接池。保留本版本来源校验，不删除任务、结果、PDF副本或CDM数据。

## 验证命令与限制

```powershell
cd F:\MedQC-worktrees\medqc-dual-data-pipeline-20261102\apps\medqc-web\backend
python scripts/run_qc_scheduler_tests.py --suite data-pipelines
cd ..
npx vitest run src/api/__tests__/dataPipelines.spec.ts tests/unit/views/workstation-v4/DataPipelineSettingsPanel.spec.ts tests/unit/views/workstation-v4/DataSyncConfigPage.spec.ts tests/unit/views/workstation-v4/useDataSync.spec.ts
npm run type-check
npm run check:encoding
npx eslint src --ext .vue,.js,.jsx,.cjs,.mjs,.ts,.tsx,.cts,.mts --no-fix
```

后端入口隔离dotenv、真实网络、子进程和非合成数据库，仅使用内存SQLite与HTTP固定应答。CI追加同一suite并使用Linux `unshare --net`，不放宽已有门禁。前端调用全部Mock，新增面板保护集额外拒绝fetch；没有连接真实后端或数据服务。

未执行真实PG并发/迁移、真实API、Caché/CDM服务器连通、真实病例/模型质控、浏览器端到端或完整前后端回归。内存SQLite证明SQL/CAS及账号owner逻辑，不代替PostgreSQL并发验收。服务端既有幂等/恢复由独立同步服务负责，本轮没有重做服务器三天抽取。

## 本轮实际结果

- 统一后端 `data-pipelines` suite：738通过，0失败、0跳过；包含读取依赖、PDF、缓存、原规则及首页V2加载兼容。之后为HTTP请求增加15秒总截止时间（除分阶段超时和1MiB响应限制外），定向复验 `test_data_pipelines.py`：35通过，包含新增总截止/调用方取消保护；分批结果不重复累加。
- 前端4文件：48通过，包含新面板/API、原PG页面和原同步composable。父页测试保留原断言，只等待配置就绪；新增独立链路隐藏旧PG执行/诊断入口的检查。
- 全量 `npm run type-check` 通过；暂存27个文本文件编码检查通过；全量src只读ESLint 0错误（存在格式警告），新增API/面板严格0警告检查通过；相关Ruff、`git diff --check`通过。
- 已将隔离suite加入CI，但本轮未推送，未取得远端CI结果；Linux network namespace步骤未在Windows本机执行。
- 本机集成工作树HEAD仍为 `a86da4f0b`，数据服务工作树仍为 `f230e820e`。V7.1 Layout/导航/main.ts/公共主题及迁移目录无修改；分角色模型和每日质控的其他本地分支未纳入或覆盖。
- 未启用任何真实开关，未连接业务库、客户机、Caché、独立服务或模型，未启动同步、质控或前后端服务。
