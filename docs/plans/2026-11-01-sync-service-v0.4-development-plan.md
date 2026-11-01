# MedQC独立数据同步服务开发计划 v0.4

状态：开发计划，尚未实施。编制日期：2026-11-01（用户时区America/Chicago）。

**目标：** 把现有Caché抽取器和CDM发布器升级为可持续运行、可定时执行、可人工发起和可追踪恢复的独立后端服务。

**架构：** 保留已验收的抽取/发布引擎和字段合同，新增轻量任务控制层。API/CLI提交任务到PostgreSQL持久队列，常驻worker执行，调度器只生成同类任务。第一版不依赖Redis/Celery，不另建前端，不改变质控规则或业务数据源。

**技术：** Python3.10、现有ODBC/JDBC适配器、psycopg2/PostgreSQL16；人工HTTP入口采用独立FastAPI应用，依赖版本在开发时与现有环境核对并锁定，新增依赖一次性离线交付。

本计划只安排开发，不授权在客户机迁移、启用定时任务或切换业务库。实施时沿用本工作树；各项先写失败测试，再实现、验证并提交。客户环境只做最后一次集中验收，失败仅修复受影响项。
本期客户验收平台固定为Windows客户机；Linux只交付后续迁移模板，不把恢复SSH或另一轮服务器部署作为本期收口前置条件。

## 1. 先固定成果与范围

已确认代码目录：`C:\medqc-data-integration-service\apps\medqc-data-integration`。

| 现有资产 | 本次处理 |
| --- | --- |
| `src/medqc_ingest/service.py`的ExtractService / PublishService | 原样复用执行语义；控制层直接调用，不复制算法 |
| `adapters/cache.py`与`repositories/postgres.py` | 复用真实连接、流式写入、幂等、锁及事务；必要扩展另做保护回归 |
| `domain.py`第一批13接口注册表 | 保留，不直接混入第二批或改变旧CLI行为 |
| `periop_replay.py / periop_live.py`第二批合同与限定失败分类 | 通过独立profile解析器接入；不放宽既有白名单 |
| `contracts/`及已通过的CDM迁移 | 复用，不重新做字段探查/映射，不为本服务修改应用Alembic |
| ingest的批次、schema、历史和发布血缘 | 保留为数据执行的权威审计；新任务表仅关联这些批次 |
| 既有Windows/systemd调度示例 | 可复用路径/凭据经验，但新常驻进程另出明确部署配置 |

业务范围固定为两批26个有非空样本的接口。另4个来源继续禁用，不自动扩到55个过程。
第一批13已通过真实源验收；第二批13的新真实源验证回传尚待确认。第二批可做开发和合成测试，接入客户任务执行前必须核对真实源结果；结果若带源限制，按接口/窗口保留限制，不宣称全部刷新。

第一版支持：人工dry、显式日期补取/replay、抽取后发布、仅发布、任务查询/重试/取消、经批准的定时计划、健康检查。
本次不包含：新前端、指定visit_id的服务端查询、源端删除传播、HIS/PACS关联、其他25接口、质控规则/模型、业务源切换或生产PG实例拆分。

## 2. 推荐运行形态与隔离

```text
人工CLI ─────┐
管理HTTP API ├─→ 控制库：任务 / 执行单元 / 尝试 / 计划 / 事件
内部调度器 ─┘                  │
                         常驻worker（默认源端并发1）
                               │
                     profile绑定与启用闸门
                               │
             原样ExtractService → profile对应ingest库
                               │
             原样PublishService → profile对应CDM库
```

- 两个长期进程：管理API、worker。调度tick由worker监督层承担，所有触发方式都经过同一个任务受理入口。
- worker监督层负责心跳和调度；一个独立执行子进程运行当前任务，连接和凭据只在执行进程内创建。API请求不直接运行Caché查询。
- 建一个独立控制库，采用`sync_control` schema，仅存操作元数据；不含payload、患者键、正文或凭据值。
- 第一批、第二批继续通过不同profile绑定各自ingest/CDM，第一版不要求把历史资产合并进同一库。
- API角色只访问控制库；执行进程使用运行身份访问绑定库，数据库初始化用独立部署身份，管理员口令不进入常驻进程。
- 客户验收使用一套固定的控制库和目标绑定。必要的基线复制只在环境建立时做一次，不为每个小功能新建一批数据库。
- 不在已接受的原13接口现场自动执行新迁移；新库、凭据及目标绑定由部署清单明确指定。

选择轻量PG队列的原因：现有PG已可用，任务量有限，能够持久化并在进程重启后继续管理，无需额外队列服务。具体权衡见`ADR-0002-task-control-and-scheduling.md`。

## 3. 任务合同：人工和定时共用

人工提交示例（合同示意，命令/API尚未实现）：

```json
{
  "profile": "core13",
  "interfaces": ["web.mr"],
  "start_date": "2026-10-26",
  "end_date": "2026-10-28",
  "mode": "replay",
  "publish": true
}
```

- 日期为医院Asia/Shanghai语义，范围包含首尾；不使用开发机/服务器本地时区猜日期。人工抽取必须显式给日期，初始单次最多7天，长回补拆批。
- 接口按profile白名单解析。客户端只能提交profile ID，不能传SQL、过程任意名称、DSN、数据库地址、密码或配置文件路径。
- 新入口默认replay；dry强制不发布。不得转调旧CLI的默认incremental行为；所有执行模式显式传给核心服务。
- 控制层另提供publish_only：不要求日期、不连接Caché，直接调用PublishService；它不加入核心RunMode。对dry＋publish或publish_only＋抽取日期等矛盾请求直接拒绝。
- incremental仅允许已批准日期/水位语义的接口。首页的出院日水位不代表修改时间水位；第二批保持replay，不推进checkpoint。
- 任务按“接口×日期”展开抽取单元，保存远端batch_id。一个接口的日期单元完成后发布一次，保存publish_batch_id；ID必须同时带profile，不能跨库假定全局唯一。
- 非预期抽取失败后，暂停该接口发布和后续未执行单元；已提交的其他日期raw及已成功接口保留，不能宣称整个多接口任务原子回滚。
- 已知源限制按原合同分类；是否发布已有/部分数据必须明确标注，旧数据的发布不算本次源读取成功。
- 重试从失败单元或发布阶段继续，不重跑已成功接口；发布失败且raw已成功时，优先仅重试发布。
- API的Idempotency-Key：同键同参数返回已有任务，同键不同参数返回409。人工/定时的重复受理与现有数据幂等分开控制。

## 4. 最小数据模型与状态

新增控制库迁移放在`control_migrations/`，不追加到原ingest的001..005，也不放进应用Alembic。

| 表 | 核心内容 |
| --- | --- |
| `sync_control.job` | job_id、来源manual/schedule、profile、参数摘要、发起人、幂等键、状态、取消请求、时间、汇总计数 |
| `sync_control.job_unit` | 接口、日期、抽取/发布阶段、单元状态、source_batch_id/publish_batch_id、恢复位置 |
| `sync_control.job_attempt` | 尝试序号、worker/lease token、心跳、起止时间、受控错误码、退出状态 |
| `sync_control.schedule` | 计划配置、医院时区、日期策略、默认禁用、配置版本、next_fire_at |
| `sync_control.schedule_fire` | schedule_id＋计划触发时间唯一，配置版本作为快照保存；改版本不允许重发同一触发 |
| `sync_control.event` | 提交/取消/重试/计划启停/恢复核对事件，不保存异常原文或临床值 |

父任务状态：`queued → running → succeeded / completed_with_source_limitations / failed / cancelled`。
取消请求是独立标志，不直接把仍在运行的任务改成cancelled。进程异常或提交状态不明时置`recovery_required`，完成核对后再决定续跑。
恢复路径明确为`running → recovery_required → queued / failed / cancelled`，不能从状态不明直接跳到succeeded。

必须区分：请求已受理、源已取完、raw已提交、CDM已发布、发布审计已写完。API返回202不表示数据同步成功。
行数汇总区分抓取次数、实际新增/更新和库内唯一记录数；不能把多日重复读取的fetched相加当作唯一病例数。

## 5. 执行可靠性与定时策略

### 5.1 worker与恢复

- 通过数据库事务领取队列；领取有owner token，完成/心跳写入使用token校验，防止旧worker回写覆盖新状态。
- 初始源端总并发1，保留核心接口锁，并增加任务层的同profile重叠窗口保护；后续提并发须有医院容量依据。
- 心跳与长时间ODBC执行分开，执行连接不跨线程/进程共享。数据库连接、语句超时及任务预算分别配置并实测。
- 租约超时不等于旧ODBC查询终止。不能只凭心跳超时自动再发同一查询；先核对旧执行进程/连接、目标锁和已提交批次，状态不明保留recovery_required；不依赖额外取得HIS管理权限才能运行。
- 取消在安全边界生效：当前数据事务完成或回滚后，停止未执行单元。第一版不提供任意SQL强杀或强制中断数据库事务接口。
- 网络瞬时失败可有限退避重试，默认最多2次额外尝试；权限、schema/key漂移、目标碰撞、厂商确定性错误不自动重试。
- 核心已有CDM提交后审计回写失败的窗口；任务层据批次/字段及血缘核对后幂等重试，不承诺跨库exactly-once。

### 5.2 定时

- 第一版提供每日/每周计划及受限日期策略，不开放任意Python表达式或无限cron规则。
- 计划默认disabled；调度器本身启动不表示任何业务计划启用。
- 每个计划明确profile、接口集、日期策略、运行模式、发布开关、重试预算及错过触发策略。
- mr可配置已确认出院日的新窗口与历史重取；滚动60天不是全部历史修改的保证，不推广给其他接口。
- 日期语义未知的来源维持人工显式replay；按日期参数定时重取需单独批准策略，不能自动解释为修改时间增量。
- 停机错过的计划只按既定策略补一个受限任务，不无上限补发；日历切换、重复tick及程序重启都有唯一触发记录。

## 6. 人工CLI与HTTP API

第一版CLI新增独立命令组`medqc-sync`，保留原`medqc-ingest`：

```text
medqc-sync job submit --profile core13 --interface web.mr --start 2026-10-26 --end 2026-10-28 --mode replay --publish
medqc-sync job list
medqc-sync job show <job-id>
medqc-sync job retry <job-id>
medqc-sync job cancel <job-id>
medqc-sync worker
medqc-sync api
```

HTTP路由合同：

| 路由 | 功能 |
| --- | --- |
| GET /v1/interfaces | profile、可用/受限/禁用状态及允许模式 |
| POST /v1/jobs | 受理人工任务，返回202和job_id |
| GET /v1/jobs、GET /v1/jobs/{id} | 任务列表、阶段、进度、计数、受控错误 |
| POST /v1/jobs/{id}/retry、/cancel | 授权重试或安全取消 |
| GET/POST /v1/schedules | 查询/创建默认禁用计划 |
| PATCH /v1/schedules/{id} | 带版本条件修改计划 |
| POST /v1/schedules/{id}/enable、/disable | 明确启停并审计；部署时不自动调用 |
| GET /health/live、/health/ready | 进程/控制库就绪，不主动调用Caché探针 |

API初始只绑定127.0.0.1，通过文件注入服务凭据，提供只读/运行/计划管理权限区分。未来由质控后端鉴权后调用，浏览器不拿同步服务密钥；客户端不能任意冒充可信发起人。
API不加载Caché或CDM管理员凭据，不导入整个MedQC后端或.env。列表和日志只返回操作元数据，不能返回正文、患者键、DSN、文件秘密或驱动异常原文。

## 7. 开发任务与精确文件范围

以下路径均相对`apps/medqc-data-integration/`。每个任务提交一个可验证成果，不提交半成品客户包。

### T0：固定profile与现状基线

- 新增`src/medqc_ingest/control/profiles.py`、`tests/test_control_profiles.py`。
- 先写测试：原注册表不变、4来源拒绝、第二批待真实源回传时不误启用、未知日期语义拒绝incremental、拒绝客户任意连接参数。
- 实现两个profile的合同与只读配置引用适配，复用既有InterfaceSpec；记录每接口的source readiness与策略状态。
- 将现有第二批真实源验证结果作为后续启用输入；不用重做已经通过的字段映射、reader或归档接管。
- 验收：开发可继续，客户未通过的来源不会被调度器调用。

### T1：任务合同、持久队列与控制库

- 新增`control/models.py`、`control/admission.py`、`control/ports.py`、`control/postgres.py`。
- 新增`control_migrations/001_job_control.sql`、`tools/initialize_sync_control.py`。
- 测试`test_job_admission.py`、`test_job_repository.py`：参数限制、幂等键冲突、唯一触发、并发领取、token过期保护、数据库范围与最小权限。
- 受理入口先验证完整请求再写任务；禁止部分参数已经创建任务后才发现禁用接口。
- 在独立合成PG验证事务/唯一约束；不向客户已有ingest/业务库套用控制库DDL。
- 验收：可提交、持久化、查询任务；服务重启后任务仍存在，尚不连接Caché。

### T2：任务runner、常驻worker与恢复

- 新增`control/runner.py`、`control/worker.py`、`control/recovery.py`。
- 测试`test_job_runner.py`、`test_worker_recovery.py`：抽取→发布依赖、仅重试发布、已知源限制、分块回滚、取消、子进程退出、租约过期和提交状态不明。
- 先实现单任务/单源并发，直接调用现有ExtractService/PublishService；不经shell拼接CLI或重写UPSERT。
- 用job_unit关联既有批次，记录每次尝试；若核心调用在失败前没有返回batch_id，采用受控关联标识定位，不根据“最新一行”猜归属。
- 验收：人工任务从队列执行到CDM，失败可定位并从正确阶段恢复，不重复已成功单元。

### T3：持久化调度与人工入口

- 新增`control/scheduler.py`、`control/cli.py`、`control/api.py`、`control/auth.py`；在`pyproject.toml`增加独立入口及可选API依赖。
- 测试`test_sync_scheduler.py`：医院时区、重复tick、重启、错过触发、配置变更、禁用计划和补发上限。
- 测试`test_control_api.py`：202受理、查询、权限、409幂等冲突、非法SQL/DSN参数拒绝、取消与重试状态限制、脱敏响应。
- CLI/API共用admission与授权约束；HTTP请求只入队，不等待Caché长查询。
- 验收：人工与定时都走同一任务状态机，API不持有业务数据读取/写入职责。

### T4：部署、离线包与一次集中验收

- 新增`deploy/windows/sync-worker.disabled.xml`、`sync-api.disabled.xml`及`deploy/systemd/medqc-sync-worker.service`、`medqc-sync-api.service`。
- Windows配置用于开机启动/崩溃恢复常驻进程，业务日/周计划仍由控制库调度，避免两套定时重复触发。
- 新增`tools/accept_sync_control.py`、`tools/build_sync_control_package.py`与`docs/DSH_SYNC_CONTROL_ACCEPTANCE.txt`。
- 源/目标配置、进程账户、ODBC位数、凭据ACL及数据库权限在一份部署清单固定；常驻运行不再依赖人工密码弹窗。
- 客户缺少的API依赖一次性离线打包并校验，不在每轮验证临时联网安装。
- 完成开发机保护回归、真实PG集成和解压包验证后，只交付一个0.4候选包给DSH集中验收。

## 8. 集中验收清单与收口

固定验收环境只建立一次；不把这份计划当成现在就建库、启用任务的指令。

| 编号 | 必须通过的验收 |
| --- | --- |
| A1 | 人工指定接口和三日窗口，可提交、查看进度、执行、发布并查看行数；相同请求不重复入队 |
| A2 | 定时计划在测试时钟下按医院时区触发且仅一次；真实计划仍默认禁用 |
| A3 | 两次执行业务键不重复，源更新保留版本，发布第二轮零变化 |
| A4 | 源错误/目标错误/进程退出分别能审计、回滚或进入恢复核对；只重试失败单元 |
| A5 | worker重启后queued任务不丢失；running不会直接被伪装成功或盲目重复执行 |
| A6 | 人工取消不会留下半批数据，任务状态与真实执行阶段一致 |
| A7 | 4禁用来源、未知增量语义、未启用profile均不会绕过闸门；原13引擎及字段合同保护回归通过 |
| A8 | 配置/日志/API/离线包没有口令、正文或真实病例键；无鉴权调用被拒绝 |
| A9 | 控制库及目标数据备份恢复可用；既有验收基线和正式业务库未改 |
| A10 | 直接Python/安装包可启动；禁用部署配置可核验；未自动注册/启用任务或切换业务源 |

交付完成定义：代码和锁定依赖、独立控制库迁移、API合同、CLI操作说明、两个常驻进程部署配置、一个离线包、一份集中验收报告及运行手册齐全，A1–A10通过。

**开发完成、客户验收通过、正式启用分别记录。** 本轮不自动启用任何任务。客户验收发现非预期错误时，定位后只补受影响测试/步骤，已通过且基线未变的部分不重复搬库或重验。

## 9. 交付节奏

| 交付点 | 包含任务 | 可展示结果 |
| --- | --- | --- |
| M1 任务管理 | T0–T1 | 任务提交、查询、幂等与持久化；无Caché写入动作 |
| M2 常驻执行 | T2 | 人工任务实际执行、发布、失败定位与恢复 |
| M3 调度与API | T3 | 可人工/定时触发，HTTP异步受理，计划默认禁用 |
| M4 交付收口 | T4＋A1–A10 | 一个离线包、一轮客户验收、固定启用条件 |

按M1→M2→M3→M4顺序实施。第二批真实源结果核验与开发并行；厂商受限来源不拖住已通过来源，也不被虚报为成功。
不扩接口、不重做既有字段研究、不在第一版增加独立前端、分布式队列或全量重新建库。生产启用和业务数据源切换另行安排。
