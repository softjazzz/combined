# PR20／PR21 业务线独立适配计划与验收

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 在独立工作树整合 RabbitMQ／Outbox／Worker 与 Strata Gateway，不移动业务集成分支。

**Architecture:** 从远端业务线建立适配分支，顺序合入 PR20 和其后继 PR21。执行器继续独占临床判断；保留业务线补跑、选轮和 UI 修复。默认 legacy、缓存关闭，不部署或启用新服务。

**Tech Stack:** Python 3.10、FastAPI、SQLAlchemy／Alembic、aio-pika、Vue 3；隔离测试仅用固定应答、ASGI／MockTransport、内存 SQLite 和 FakeBroker。

---

## 固定输入及保护范围

- 工作树：`C:/medqc-strata-business-adapt-20261031`。
- 分支：`codex/strata-business-adapt-20261031`，不跟踪业务分支以避免误推。
- 业务基线：`63b57c1c231412208d39a9a0cb89c382834737bd`。
- PR20：`af914704fb2427fc1e41e4dd3814b85d2a5dabf1`。
- PR21：`100c443607b6223a32afd262e1db16ab135366d0`，已包含 PR20。
- 本机业务工作树 `C:/medqc-agent-merge`：HEAD `cedb9c10a017c30b767e7ed449b8c9b90e356a54`，原六项未跟踪路径保留。
- 不改实际业务分支、快照 Base 或 PR；不写业务库、调用真实模型、连接 Strata 或运行病历质控。

## 步骤一：保留双方补跑语义

文件：`backend/app/services/sichuan_workspace_batch_worker.py`。

1. 比较共同祖先及双方改动。
2. 唯一文本冲突位于自动补跑入队。复用业务线 `_enqueue_automatic_failed_rule_retry` 的同代 CAS 失败标记，同时传递 MQ 的 `retry_delay_seconds`。
3. 只调用一次入队；MQ 下一代 Outbox 同事务后返回，不递归执行；legacy 保持原延迟和递归。
4. 在 `backend/tests/unit/test_qc_partial_failure_persistence.py` 增加真实内存 owner 的交叉保护，覆盖下一代延迟／已有结果／失败标记，并加入 m2-release 门禁。

## 步骤二：核对整合依赖

- 核对 `llm_dispatch` → Gateway、Worker → dispatcher／repository／Outbox 的实际调用和默认开关。
- 核对 `requirements-qc-worker.txt` 的显式可选依赖，禁止启用时偷偷降级或 auto-DDL。
- 静态检查 Alembic 单 head 与 `055 → 056 → 057`，不运行 env.py、不连接 PG。
- 比较双方修改重叠文件与 V7.1 Layout／导航／主题；仅保留 PR21 已声明的模型配置组件改动。
- 测试计划加回业务线 PR18 的输血、检查、会诊、首程时间与选轮反例，避免语义自动合并回退。

## 步骤三：隔离定向验收

在 `apps/medqc-web/backend` 执行：

```powershell
py -3.10 scripts/run_qc_scheduler_tests.py --profile m2-synthetic --suite m2-release
py -3.10 scripts/run_qc_scheduler_tests.py --profile offline --suite strata-admission
py -3.10 scripts/run_qc_scheduler_tests.py --profile offline --suite llm-request-audit
py -3.10 scripts/run_qc_scheduler_tests.py --profile offline --suite compatibility
```

按真实重叠补选必要的 PR18 固定应答测试，不默认跑全仓。网络、DNS、业务 DB、dotenv 和普通进程启动护栏保持；受控冷启动子进程先验签再安装同样隔离。

前端只运行模型配置及业务线相关结果／轮询测试、完整类型检查和只读 ESLint；提交前检查编码与 diff。真实 PG／RabbitMQ 隔离基础设施历史证据与本轮固定应答结果分别记录，不能混称本轮实测。

## 步骤四：交付

完成本地中文提交，记录整合 SHA、双方祖先完整性、保护文件差异和实际测试结果。不推送、不合并 PR、不打包、不部署。列明未执行的真实基础设施、现场模型、完整 HTTP／Worker／Gateway 联调与医学质量验收。

## 实际结果

### 合成与依赖

- 第一轮本地合成提交 `acf3b090f` 合入 PR20。PR21 自动合成后保留检查冻结 v2 及实验目录分区，不把 v2 降回旧版本。
- 三个双方都修改的文件：`custom_qc_workspace_service.py`、`sichuan_workspace_batch_worker.py`、`luxian_0609/exam_analysis_freeze.py`。仅 Worker 自动补跑发生文本冲突；其余检查真实语义及回归。
- Worker helper 新增可选 `retry_delay_seconds`，legacy 不额外传参；MQ 向原事务 owner 传递延迟，不复制第二套重试。成功、None、抛错三条真实内存事务回归验证结果保留、CAS 失败提示、代次及 Outbox 数量；正式 Worker 固定应答补跑同时覆盖 legacy 与 MQ。
- `QC_TASK_DISPATCH_MODE=legacy`、`LLM_DISPATCH_MODE=direct`、`STRATA_CASE_CACHE_MODE=off`、`LLM_REQUEST_OBSERVATION_ENABLED=false` 默认保留。没有复制部署 `.env` 或自动切换模式。
- 独立 MQ Worker 要求 rabbitmq＋gateway、有效 Gateway token/profile；通过 `run_batch_dispatch_job` 进入原批 Worker，批内最多4病例。Web 不领取 MQ 任务；消费者仍按持久终态／恢复提交后 ACK。
- `requirements-qc-worker.txt` 仍是显式可选的 `aio-pika==9.5.8`、`aiormq==6.9.4`；不升级 Web requirements、不安装生产服务。
- Gateway 保持单活动 owner、所有 Strata profile 共用一个 resource／endpoint、2槽与同病例串行、公平有界队列、失败不降级云端。缓存和实验不改变医学结果 owner。
- 对所有迁移文件做 AST 图检查：57 个 revision、无重复或缺失父节点、唯一 head `20261030_000057`，尾部为 `20261026_000055 → 20261030_000056 → 20261030_000057`。056／057 的 owner 模式／缺表失败保护由既有合成测试覆盖；未加载 env.py、执行 PG 迁移或 stamp。
- 对比业务基线，前端产品源码仅新增原 PR21 的 `src/components/LLMApiConfig.vue` 修改；V7.1 Layout／导航／主题／图标／助手与目标线一致。业务线既有轮询、任务状态和结果读取 UI 没有被覆盖。

### 本轮验证（集合有重叠，不相加）

| 检查 | 实际结果 |
| --- | --- |
| `offline / strata-admission` | 197通过，20.88秒 |
| `offline / m1-admission` | 68通过，8.06秒 |
| `offline / llm-request-audit` 加两份网络／DB隔离保护 | 238通过，11.27秒；包括受控冷启动，不放宽进程或网络护栏 |
| 最终 `m2-synthetic / m2-release` | 169通过，13.96秒；增加真实保存 owner 与 MQ／legacy 补跑交叉保护，进入现有必跑 CI 步骤 |
| `offline / compatibility` | 260通过，24.59秒 |
| 业务线检查长文／拆批、会诊拒绝、输血关联与时间、冻结完成、结果导出等9文件扩大集合 | 240通过、2项跨进程测试被offline护栏拒绝；不能记为全部通过 |
| Worker补跑／失败／资料不足／双病例计数5个节点 | 8通过，4.53秒；legacy重试和MQ只入队不递归均验证 |
| 前端模型选择、任务进度、结果抽屉、失败轮询6文件 | 119通过，15.54秒；另配置服务1项通过 |
| 完整 `vue-tsc --noEmit` | 通过，exit 0 |
| 全src只读 ESLint | 0错误，3401项既有warning；未使用fix |
| 适配相关Python Ruff | 通过 |

前端测试另通过临时 Node preload 拦截 net／tls／http(s)／DNS／fetch，使用线程池及固定响应。临时日志、基线源码快照及网络护栏均放 `.tmp`，不提交。

### 验证中修正的旧夹具

1. `test_latest_full_record_result.py` 原夹具只填摘要，没有顶层 `items_json`，与业务线修复后的权威读取合同不一致。对固定业务基线服务源码离线加载同样失败；现补顶层成功项，另增加摘要有值但权威项缺失仍失败关闭的反例，没有放宽产品读取。
2. `test_qc_sichuan_batch_throughput.py` 共用夹具没有创建时冻结的配置与运行身份。固定业务基线 Worker 同样拒绝这两项测试。现在复用该文件已有的合法快照初始化，保留正式准入验证；抽成夹具 helper，未跳过身份校验。
3. `test_verify_consultation_family_acceptance.py` 的 `test_variant_subprocess_decodes_utf8_json_output`、`test_variant_subprocesses_compare_prompt_bytes_with_one_session_key` 尝试普通 subprocess，被 `OfflineIsolationError` 拒绝。脚本／测试与业务基线一致；未删测、skip、mock通用进程开关或新增白名单，本轮只记录未完成的跨进程证据。

### 限制与后续门槛

- 本分支尚未推送，因此没有本适配 Head 的远端 CI；PR20／21 原 CI 不作为本分支 CI 通过证明。
- 没有重新执行一次性真实 PG／RabbitMQ、全历史迁移、完整 HTTP→生产Worker→Gateway 联调或现场模型验收。PR20 曾有的真实隔离基础设施记录仅为历史证据。
- 没有真实模型或 Strata 连接、患者质控、27例重跑、部署、打包或业务库写入；不声称完整病历吞吐或医学质量验收完成。
- 两项跨进程回放尚未在保持等价隔离的受控入口验收；不能据本次合成宣称所有扩大回归全绿。正式发布仍需目标适配分支 CI、真实隔离基础设施与部署配置验收。
# 2026-11-01 合并前同步PR19

用户授权按PR19、PR22、PR23顺序合入业务线。PR19已由GitHub合并为`d6d0fa5151571d8b7e2e54de24c64b8459459240`；本适配分支同步该最新业务提交，无文本冲突。PR19的30个差异文件中28个与来源提交完全一致，仅`custom_qc_workspace_service.py`及`test_qc_partial_failure_persistence.py`同时保留MQ生命周期和最新失败轮次保护；没有用整文件覆盖任一方。

必要交叉验收：`run_qc_scheduler_tests.py --profile m2-synthetic --suite m2-release tests/unit/test_qc_partial_failure_persistence.py tests/unit/test_luxian_0609_remaining_fact_freeze.py`，233项通过，3项既有告警。实际验证内存事务、失败结果读取、MQ补跑与冻结协议；不连接模型或业务库。当前提交的远端CI需重新核对，旧86315b746的绿灯不冒充新Head验收。

本机integration工作树的3个未推送同步工具提交及6组未跟踪资料已在私有临时目录备份，原工作树保持不动，不混入这次PR。默认开关、迁移代码、V7.1页面以及现场部署边界保持原约束。
