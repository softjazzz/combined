# v0.4并行开发共享合同（开发时固定）

根目录：`C:/medqc-data-integration-service/apps/medqc-data-integration`。
现有抽取/发布服务、原13注册表、旧CLI、应用后端和001..005迁移不改。
本合同用于并行实现；必须兼容后由主协调合并调整，不得各模块重新发明任务格式。

## 模型与受理

- `control.models.ControlError(code: str, location: str, status_code: int=400)`：只含受控文本，`str`不带驱动或输入原文。
- `Actor(actor_id: str, permissions: frozenset[str])`，权限`read/run/schedule`；run允许读，schedule允许读/运行/计划操作。
- `AdmissionService(catalog, repository)`：`prepare(payload: dict, actor: Actor, origin="manual") -> dict`，完整验证返回纯JSON规范请求；`submit(payload, actor, idempotency_key, origin="manual") -> dict`调用prepare然后repo.submit。
- payload仅`profile/interfaces/mode/start_date/end_date/publish`。默认mode=replay；dry必须publish=false；publish_only不带日期，直接发布。起止包含两端，医院时区，人工最多7天，不允许未来/当天未完整日期。
- 规范请求包含同名字段与`units`有序数组。unit为`{interface_name,source_date: ISO日期或null,phase:extract|publish}`，每接口所有日期后接一个publish单元。没有任意连接信息。
- 受理幂等由repo对规范JSON排序后的SHA256判断；同key同请求返回已有任务，异请求409。
- `ProfileCatalog`提供`get(profile_id)`、`validate(profile_id, interfaces, mode, origin)`和`describe()`，只保存白名单/readiness/policy元数据，不读凭据。core13固定原13；periop13固定第二批13、4来源禁用；periop默认ready=false。增量及定时仅批准的mr策略。

## 仓储统一接口

所有返回值为JSON友好的dict/list，UUID和日期时间使用字符串，不包含lease token的公开结果。
构造`PostgresJobRepository(settings)`，沿用`PassfilePostgresSettings`；另有纯fake `MemoryJobRepository()`供单测。

```text
submit(request, actor_id, idempotency_key, source="manual") -> job
get_job(job_id) -> job|None
list_jobs(limit=50) -> list[job]
claim(worker_id, lease_seconds=180) -> job|None       # 仅内部结果有lease_token
heartbeat(job_id, token, lease_seconds=180) -> bool
cancel(job_id, actor_id) -> job
retry(job_id, actor_id) -> job
units(job_id) -> list[unit]
start_unit(job_id, token, unit_id) -> bool
finish_unit(job_id, token, unit_id, status, result) -> bool
finish_job(job_id, token, status, error=None) -> bool
mark_recovery(job_id, token, reason) -> bool
list_recovery() -> list[job]
reconcile(job_id, actor_id, decision, proof) -> job
```

job公开字段至少`job_id/request/status/cancel_requested/created_at/updated_at`，claim增加lease_token。
unit至少`unit_id/sequence/interface_name/source_date/phase/status/result`，start/finish必须核对job的token和running状态。
父状态queued/running/recovery_required/succeeded/completed_with_source_limitations/failed/cancelled。
unit状态queued/running/succeeded/source_limited/failed/cancelled。
retry只把失败单元及阻塞的后续未成功单元归queued；不重置succeeded/source_limited或原尝试记录。
queued取消可立即结束；running只设置请求，安全边界由runner完成取消。
所有token CAS失配返回false且不写入。未确认旧进程终止前，不自动把过期running变queued；claim先隔离为recovery_required。
全局最多一个running/recovery_required作业，保护源端并发1；pending recovery未核对前不继续领取别的作业。

## 计划仓储

```text
create_schedule(config, actor_id) -> schedule        # 强制disabled/version=1
list_schedules() -> list[schedule]
get_schedule(schedule_id) -> schedule|None
update_schedule(schedule_id, version, changes, actor_id) -> schedule
set_schedule_enabled(schedule_id, version, enabled, actor_id) -> schedule
due_schedules(now: ISO-UTC) -> list[schedule]
enqueue_schedule(schedule_id, version, fire_at, request, next_fire_at) -> job|None
```

schedule为`{schedule_id,version,enabled,config,next_fire_at,...}`。
config包含`request`(任务模板，日期由调度器生成)、`frequency:daily|weekly`、`local_time:HH:MM`、`weekday:0..6(weekly)`、`window_days:1..7`、`timezone:Asia/Shanghai`。
首版支持最近完整N天；mr60天策略可暂标未开放，不能未经合同扩window。计划默认不启用。
enqueue_schedule必须在单事务中锁计划/核对version与fire_at/唯一(schedule_id,fire_at)/入队与更新next_fire_at；改版本不能重发同一fire_at。
API/调度器先用AdmissionService.prepare(origin="schedule")验证模板；API保存计划时也校验策略。

## runner/worker

- `JobRunner(repository, executor)`：`run(claimed_job) -> dict`，executor是`execute(job, unit) -> dict`。返回result字段可含counts/batch_id/publish_batch_id/checkpoint_state，绝不含payload。
- runner只按顺序跑未成功单元；已知限制用受控`SourceLimited`或返回`{"source_limited":true,...}`；其余异常终止并保持审计。
- 核心适配`PipelineExecutor(catalog, bindings)`复用ExtractService/PublishService；bindings在worker执行侧加载，API不得读取。阶段关联evidence_version加入job/unit UUID，失败时不猜最新batch。
- worker supervisor负责心跳、调度与进程；每次一个执行子进程，子进程仅传job_id/token与配置路径，不能传明文凭据。
- `Scheduler(repository, admission, clock=...)`提供`tick(now=None)`；只调用prepare和enqueue，不直接连接Caché。

## API/CLI/装配

- `create_app(admission, repository, auth, catalog)`无全局配置/驱动副作用。auth从token文件绑定Actor，不信任客户端actor header。
- CLI `main(argv=None)`委托`control.bootstrap`装配（主协调负责bootstrap/runtime、pyproject入口）；命令组按开发计划。
- 运行配置接口由主协调实现，其他模块先使用注入服务/fake：`ControlRuntime.load(path)`得到control PG settings、catalog metadata、api token file和worker bindings文件引用；不会自动读取bindings/源秘密。
- 启动配置禁止带明文口令/DSN，控制数据库名只允许`medqc_sync_control`或`medqc_sync_control_acceptance_<14位>`；初始化器禁止业务/旧库名。

## 文件归属

1. 合同代理：control/models.py、profiles.py、admission.py、ports.py及对应测试。
2. 存储代理：control/postgres.py、memory.py、control_migrations/001_job_control.sql、initialize_sync_control.py及存储测试。
3. 执行代理：control/runner.py、worker.py、recovery.py、pipeline.py及执行测试。
4. 入口代理：control/scheduler.py、api.py、auth.py、cli.py及对应测试。
5. 部署代理：新disabled部署配置、验收/打包工具、DSH与运行说明及部署测试。
主协调：control/__init__.py、runtime.py、bootstrap.py、pyproject.toml、最终端到端与集成修复。
所有代理共享工作树；不得撤销别人的修改，不做并行git提交，主协调验收后统一提交。
