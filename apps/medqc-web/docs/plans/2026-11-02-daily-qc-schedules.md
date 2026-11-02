# 每日定时批量质控实施计划

**Goal:** 管理员为运行/终末病历池设置每日计划，默认关闭，复用现有质控链且可安全恢复。

**Architecture:** 新增计划和逐日触发账本，CAS租约领取计划，唯一(plan_id, local_date)去重。每次触发以固定UUID形成既有批量任务ID，任务、MQ Outbox仍由原任务owner创建；崩溃恢复先查该任务，禁止重复创建或替换成功结果。后台轮询默认关闭，不绑定浏览器定时器。

**Tech Stack:** Python/FastAPI/SQLAlchemy、Alembic、Vue 3、Ant Design Vue、pytest/Vitest。

基线98a987aba；新分支codex/qc-daily-schedule-20261102。保留前一分角色模型功能，不改其分支或业务集成分支。

## 步骤与验收

1. 实现时间计算、配置合同及持久化表owner；063迁移仅新增qc计划/触发表。计划默认disabled；显式时区、每日HH:mm、机构、科室、场景、滚动日期窗口、规则集、单次病历上限。
2. 复用正式批量任务接纳函数，添加仅内部可传的定时来源。原HTTP请求不能注入该来源；旧手动任务行为不变。按可信持久管理员重新授权并以SQL机构谓词选病历，保留三坐标、适用门槛、规则过滤、冻结、产品授权及Gateway/MQ模式。
3. CAS租约＋逐日唯一账本；重叠明确skipped_overlap；超过宽限不补跑，记录missed。停机恢复以固定任务ID查找已有任务并复用，queued legacy恢复仍使用原Worker领取CAS；MQ只沿原Outbox，不另投重复消息。
4. 管理API和系统配置页签：创建默认关闭、编辑/启停、下次执行及最近触发记录、任务编号（在既有质控记录中查看）。无“立即执行”按钮，避免误触发真实质控。仅持久管理账号可管理自己的计划。
5. 后台启用开关QC_DAILY_SCHEDULER_ENABLED=false；normal启动且显式开启才运行；acceptance模式不启动。提供独立进程入口，多实例由数据库去重。
6. 隔离验证：合成SQLite/固定任务应答、禁止网络，覆盖同日去重、并发CAS、运行重叠、无候选、旧任务恢复、创建后崩溃、超时租约、取消/停用、账号失效/机构越权、日期/DST边界、静态迁移和前端CRUD/异步失败。不得在业务PG执行迁移或计划。

## 首版口径

到点动态筛选全部符合计划条件的病历，不宣称已有“材料变更增量质控”。终末默认昨日出院；运行默认最近30天入院的在院病历，范围在表单中明确可改。宽限60分钟，旧周期合并记录为missed，不追补历史批次。每计划最多1000份，超限明确失败，不静默截断。时间以计划明确选择的IANA时区为准，不取服务器本地时区。


## 实现与使用

入口为V5「系统配置 → 定时质控」，可直接打开 `/workstation-v5/system-config?tab=dailyQc`。配置页与API均限定管理权限；API从有效持久账号重新读取权限，HTTP角色声明不能提权。账号仅管理自己创建的计划，触发前再次校验；机构、科室来自本地临床读取owner，到点通过同一owner按机构SQL过滤后选择病历，并防御性校验返回机构。

- 服务端开关：`QC_DAILY_SCHEDULER_ENABLED=false`，默认关闭；每条计划也默认关闭。保存配置不会执行质控。
- 每日时间按计划所选IANA时区解释，前端明确显示时区。初始医院时区为Asia/Shanghai，可选浏览器当前时区、America/Chicago或UTC；不依赖部署主机时区。DST回拨一天只执行一次，跳时顺延到首个有效分钟。
- 所有计划先安装063迁移才能保存。此迁移仅新增 `daily_qc_plans` 和 `daily_qc_runs`；split模式在qc schema，single模式在默认schema。**本轮未执行本机或客户机PG迁移。**
- 后台正常启动且显式开启开关后，每30秒领取计划，最多20项/轮；acceptance启动不运行调度器。也可用 `python scripts/run_daily_qc_scheduler.py` 独立运行，但仍需同一开关。多个调度实例依赖数据库租约和唯一身份，不能靠进程内定时器去重。
- 任务使用当时的正式规则、产品授权、模型设置/运行快照和Gateway准入，不修改规则、Prompt、模型或并发配置。legacy沿原Worker，RabbitMQ沿原任务/Outbox事务；不安装MQ也可以继续使用legacy。
- 每计划每个当地日期最多一个触发身份；前一轮非终态或状态未知则跳过新周期，失败/完成/取消为终态。**重叠保护以计划为单位，不是全站锁**；不同计划可能有交叠病历，应避免重复配置相同范围。重叠时不排出额外补发任务。
- 提交最多3次尝试；临时503与回执中断保留固定身份，租约过期再恢复。已创建任务只补回账本，未创建且超过60分钟宽限则记错过，不补发旧周期。多日停机合并跳过历史积压；不会逐日回放。
- 已提交的任务不随计划停用而取消；计划停用阻止新任务，已存在的任务与成功结果保留。账号失效后可补登记原任务，但不会重新投递。任务已创建而回执丢失时，恢复始终使用原ID；legacy重复投递仍由既有Worker领取CAS控制，MQ不重复创建Outbox。
- 最近30次触发记录显示空候选、超限拒绝、重叠、错过、等待恢复及失败，不把失败显示为零或成功。“已提交”仅表示进入原质控任务链，任务最终状态和结果在既有质控记录中查看。
- 回滚：关闭部署开关并停用计划，保留账本及已创建任务；不需要删除或回滚临床数据/结果。代码可回到98a987aba，新增表可保留，不建议自动downgrade删除历史。

## 隔离验证（2026-11-02）

后端命令（backend目录）：

```powershell
python -B scripts/run_qc_scheduler_tests.py --profile offline tests/unit/test_daily_qc_schedules.py tests/unit/test_qc_dispatch_entrypoints.py tests/unit/test_qc_scheduler_isolation.py
```

最终 **74项通过**。使用合成内存SQLite、固定任务/模型替身；进程级隔离剥离凭据、禁dotenv、禁真实socket和子进程、拒绝非内存数据库。Windows asyncio内部socketpair沿现有窄例外，不放行一般localhost。CI另使用unshare网络隔离。验证包括每日去重、运行/终末、租约CAS、同日恢复、创建后丢失回执、旧周期不补发、已有成功结果保留、真实任务创建+单条Outbox事务、账号撤权、编辑竞态、候选越机构/超上限/空/三坐标缺失、DST边界、临时503及有界恢复。未把固定应答称为真实模型质量验收。

前端命令（apps/medqc-web目录）：

```powershell
node --require ./scripts/frontpage-v2-no-network.cjs node_modules/vitest/vitest.mjs run tests/unit/components/DailyQcSchedulePanel.spec.ts tests/unit/views/workstation-v4/DataSyncConfigPage.spec.ts --maxWorkers=1 --minWorkers=1
node node_modules/vue-tsc/bin/vue-tsc.js --noEmit
node node_modules/eslint/bin/eslint.js src --ext .vue,.js,.jsx,.cjs,.mjs,.ts,.tsx,.cts,.mts --no-fix --quiet
```

前端 **30项通过**；完整类型检查与全src只读ESLint无错误，新组件/服务严格零warning检查通过。现有DataSyncConfigPage有60项格式warning，未为此整页重排。新页签直达不初始化数据同步；非管理账号不能直达；失败、版本冲突及目录异步响应有保护。编码、差异空白检查和相关Ruff通过。已补CI入口，远端CI尚未运行（未推送）。

### 扩大回归与基线失败

扩大到 `test_qc_sichuan_batch_throughput.py`、`test_qc_sichuan_batch_cancel.py` 后出现28项旧失败；本次当时结果96通过/28失败。使用git对象读取98a987aba的原 `qc_sichuan.py`、`custom_qc_workspace_service.py`，只在独立测试进程中通过模块loader替换这两个文件，在同一严格隔离入口重跑三份旧文件，得到 **66通过/相同28项失败**。基线其他文件与本分支一致；未reset、覆盖工作区或放宽断言。主要涉及旧夹具缺失既有任务执行快照和旧入口断言，未改旧失败或伪称全量绿；基线产物位于未提交 `.tmp/daily-qc-baseline-98a987aba/`。

### 尚未执行及边界

- 未运行全量前后端测试；未运行浏览器端到端或定时到点真实质控。
- 063执行与唯一约束仅在内存SQLite验证，未在一次性PG验证真实SKIP LOCKED/跨进程竞争、进程强杀和真实Broker重投。SQLite租约测试不能代替PG并发验收。
- 未连接业务库、客户机、Strata或百炼，未调用真实模型、读取新患者数据或重跑质控。
- 未改集成分支、启动中的服务、现有患者结果或模型配置，未部署、推送或合并。
- 本分支基于未合并的分角色模型提交98a987aba；后续PR应明确携带该前置依赖或单独适配，不能假设正式集成线已包含。
