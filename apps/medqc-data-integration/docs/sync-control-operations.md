# MedQC v0.4控制服务运行说明

## 1. 部署形态和范围

管理API、常驻worker是两个进程。API/CLI只操作控制库；worker执行子进程才加载数据面绑定，复用既有抽取/发布引擎。
调度计划在控制库持久化，默认禁用。Windows XML只负责常驻进程的开机启动/崩溃恢复；不为每个接口再建一套操作系统定时任务。
源码ZIP使用`tools/run_sync_control.py`启动，无需预先安装本项目wheel；第三方依赖仍需已具备或由完整离线依赖包安装到指定虚拟环境。

第一批13来源的合同保持原样。第二批13来源默认禁用，必须有真实客户Caché/PG16验收证据才允许profile启用；4个受限来源仍不开放。
不能把控制流程的fake/控制PG验证称为26接口真实源验收，也不能因API返回202就宣称同步成功。

## 2. 配置分离

发行包中的`examples/*.example.json`含占位符，不可直接运行。正式配置由现场部署清单确定，保存在受保护运行目录，不打包回传。

- API配置：控制库API角色、目录元数据、127.0.0.1端口、token文件引用；不放worker bindings或Caché密码。
- worker配置：控制库worker角色、目录元数据、心跳/轮询/租约、bindings文件引用。
- bindings：profile对应的Caché源配置文件引用、全新独立ingest/CDM目标及运行passfile。不得绑定`medqc`或原13现场写库。
- API token文件：仅本机生成的随机token与可信actor/permissions映射，read/run/schedule分别授权；不信任HTTP客户端任意actor header。
- 所有秘密通过已有/新建受保护文件读取，不传密码明文参数、不读取.env、不把secret放到日志。

最小角色：`medqc_owner`为NOLOGIN属主；`medqc_job_api`、`medqc_job_worker`为非超级用户控制库LOGIN角色；数据面继续使用受控的运行身份。
控制库初始化器不创建数据库或全局角色，不会自动授予业务库权限。缺少角色/凭据时应停在预检，由部署管理员按明确授权准备，不能临时使用超级用户运行常驻服务。

`prepare_sync_control_acceptance.py --output ABSNEW --admin-passfile EXIST --create-missing-roles`
负责新建一个验收控制库与缺失的两种运行角色，随后调用初始化器。已有角色需另传现有的
`--api-passfile/--worker-passfile`，工具不重设其口令。其`worker.json`中`bindings_file=null`，
`prepare.json`明确`worker_ready=false`、`source_bindings_configured=false`：只准备控制验收，尚不能执行真实源任务。
真实worker启动前须有独立批准的数据面配置与目标库绑定，不能将fake验收配置误当作全链路部署完成。

## 3. 启动和人工操作

以下为命令形状，`$python/$release/$workerConfig/$apiConfig/$tokenFile`须来自已核验部署清单：

```powershell
& $python (Join-Path $release 'tools\run_sync_control.py') --config $workerConfig worker
& $python (Join-Path $release 'tools\run_sync_control.py') --config $apiConfig api
& $python (Join-Path $release 'tools\run_sync_control.py') --config $apiConfig --token-file $tokenFile job submit --profile core13 --interface web.mr --start 2026-10-26 --end 2026-10-28 --mode replay --publish --idempotency-key operator-request-001
& $python (Join-Path $release 'tools\run_sync_control.py') --config $apiConfig --token-file $tokenFile job list
& $python (Join-Path $release 'tools\run_sync_control.py') --config $apiConfig --token-file $tokenFile job show <job-id>
& $python (Join-Path $release 'tools\run_sync_control.py') --config $apiConfig --token-file $tokenFile job retry <job-id>
& $python (Join-Path $release 'tools\run_sync_control.py') --config $apiConfig --token-file $tokenFile job cancel <job-id>
```

这些是人工命令示例，不是交付时自动执行的动作。源执行必须有批准目标绑定；控制API不接受客户端提供连接参数、SQL或过程名任意替换。
replay不推进checkpoint；incremental只对批准语义的来源开放。publish_only只发布已存在raw，不访问Caché。dry不写数据面，但任务控制元数据可按任务管理要求登记。

## 4. 任务与恢复

任务状态queued/running不表示已完成。成功需源抽取、数据事务和必要的CDM发布都完成；已知源限制单列为completed_with_source_limitations。
取消运行任务仅发取消请求，当前事务结束/回滚后停止后续单元，不强杀ODBC事务。
raw已成功、发布失败时，重试应只重跑发布，保留此前成功单元及全部尝试记录。
租约过期或子进程状态不明进入recovery_required；不能据“心跳超时”直接重新执行同源任务。
人工恢复先核对旧进程/连接、目标事务/锁及批次；无法判定时保持隔离，不通过改表伪造succeeded。
历史源失败、故障注入失败和identity序列空洞均保留，不为了全绿删除审计。

已授权的恢复操作者完成上述核对后，可使用CLI解除隔离；此命令要求token绑定的`schedule`权限，且使用worker控制库角色配置。它不启动执行器、不读取bindings、不访问数据面，也不接受任意SQL。`retry`还会重新验证当前profile是否仍获准执行。

```powershell
& $python (Join-Path $release 'tools\run_sync_control.py') --config $workerConfig --token-file $tokenFile job reconcile <job-id> --decision retry --proof-file $proofFile
```

`$proofFile`必须为绝对路径、UTF-8 JSON文件，且恰好包含以下四个键：

```json
{
  "executor_stopped": true,
  "target_locks_clear": true,
  "batches_checked": true,
  "commit_state": "idempotent_retry"
}
```

前三项必须由操作者核对旧执行进程/连接、目标事务/锁和相关抽取发布批次后如实填为true；无法确认时不要执行reconcile。`commit_state`只允许`not_committed`（已确认未提交）、`committed_verified`（已确认提交结果）、`idempotent_retry`（已确认可安全幂等重试）。这是一份人工核对声明，审计记录为`operator-attested`，不表示服务自动验证了外部提交状态。`--decision cancel`或`fail`会保留历史尝试并终止该恢复任务；`retry`仅将未完成单元重新排队，保留已成功单元，实际执行仍由worker按队列领取。

## 5. 集中验收与证据层次

`accept_sync_control.py --mode fake`验证真实控制状态机和实际JobRunner/Scheduler，但执行器使用纯虚构数据，不访问Caché或PG。
加`--http-test`通过实际FastAPI应用的进程内HTTP验证401/403、202异步受理、可信actor和响应脱敏，不监听网络端口。
`--mode postgres --config ... --allow-control-writes`只允许新空验收控制库，复用同组虚构执行场景；不会触碰ingest/CDM。
若加`--http-test`，还必须传同一控制库的`--api-config`，HTTP受理/查询使用实际API角色仓储，执行使用worker角色仓储；不能借worker权限假装API角色授权已验证。

上述控制验证的PASS不是完整部署PASS。真实source/target链路、运行进程重启、HTTP真实监听、备份恢复必须由专门证据另行报告。
`acceptance.json`会明确记录fake_executor、cache_accessed、ingest_or_cdm_accessed、live_pipeline_verified和backup_restore_verified，不得删掉false字段后宣称上线。

每个部署候选包只安排一次固定客户环境验收。已经通过且基线未变化的阶段不重复建库/克隆；失败时保留现场，定位后只修复相关项目。

## 6. 操作系统模板

Windows的`sync-worker.disabled.xml`和`sync-api.disabled.xml`中两个Enabled均为false，路径/账户仍需替换。发行工具不会注册任务。
Linux systemd文件仅是迁移模板；不能据静态验证声称Linux服务已安装或运行。交付工具不执行systemctl、schtasks、服务/防火墙修改。
最终启用时应明确服务账户及凭据ACL可读性、单进程守护和本机API监听；开发验收不自动授权启用。

## 7. 备份与交付保护

控制库、ingest和CDM分别备份，角色/权限的恢复前置单独记录。逻辑备份可读不等于已实做恢复，需恢复并核对表/序列指纹。
只回传reports内非PHI统计JSON、manifest和CHECKSUMS。源配置、token、passfile、bindings、private日志、dump、raw和正文留在客户机。
依赖包只从固定离线wheelhouse安装；仅存在wheel文件不代表依赖闭包和目标Windows ABI已验证。发行manifest诚实保留该验证状态。

源码包与离线依赖附件分别生成，避免每次代码修复重传全部wheel。`requirements-sync-control.lock`
锁定CPython3.10/Windows x64运行及进程内HTTP验收依赖；`requirements-sync-control-dev.lock`为可选测试/build工具。
安装使用新venv及`pip install --no-index --require-hashes --find-links ... -r ...`，随后`pip check`。
`build_sync_control_package.py --dependencies-only --wheelhouse ABS --dependency-report ABS --output ABSNEW.zip`
要求验证报告的wheel与锁文件哈希逐项吻合，才将附件标记为离线闭包已验证。源码包单独仍不声称包含已验证依赖。
报告只证明开发机相同Python/平台的新venv离线安装、测试及wheel安装路径；客户ODBC驱动和真实源连接仍需现场证据。


## 0.4 可靠性补丁：002前置与旧任务

本补丁不启用服务、不改接管范围，也不修改已部署的001脚本。控制库须先备份，停API、Worker及计划器，确认旧进程全部退出后，使用受限迁移账号执行：

```powershell
python tools/initialize_sync_control.py --database medqc_sync_control --passfile C:/secure/control-migration.pgpass --user postgres --port 5432 --owner medqc_owner --upgrade-reliability
# passfile和迁移账号须替换为现场既有值；不能在未备份、服务未停止时执行。
```

`--upgrade-reliability`只在已有六张控制表的独立控制库上执行002，失败回滚；不创建库/角色、不接触临床业务库。新空库初始化自动执行001+002。源码离线包及wheel均包含002。旧代码不能在新版控制库旁继续写：typed列为持久owner、record_json为同事务镜像，混用旧Worker会破坏一致性。升级应在维护窗口完成，回滚代码前须另审控制库兼容方案，不能只启动旧Worker。

未安装002时，连接前置检查使ready、列表、提交和领取统一返回503/migration_required；不能先收任务后才报缺列。

每个作业首次执行前冻结配置数据面的非敏感SHA256身份，包含source namespace、ingest/CDM位置及接口合同；不包含密码、秘密文件位置、患者键或尝试UUID。仅凭据轮换不改变身份。重试/恢复发现身份变化进入recovery_required，成功单元保留且不在新库继续发布。配置已变更时应恢复原绑定后再核对；不能伪造新身份强行解锁。001历史作业若已有成功单元而无身份，安全保留为recovery_required，由操作人核对旧来源并新建明确范围的任务；不猜测历史同源。

连接类可重试失败的next_retry_at和冻结预算与finish_job在同一事务写入，故child已提交失败但Supervisor尚未观察退出时崩溃，也不会丢失重试。新Supervisor原子领取到期意图；默认30秒、120秒、最多额外两次。取消、手工重试、成功都会清除到期意图；未知提交/旧租约到期保持recovery_required，不扫描重发ODBC。服务重启不会跳过退避。

## 精确时间投影

源仅日期写入datetime/timestamptz时，以publish_contract/datetime_precision_missing显式中止发布；raw仍保留，任务和错误可追溯，不静默丢行，不补零点、不从签名或提交时间猜记录时间。date目标仍可接收纯日期；显式00:00:00为有效精确时刻。确认源返回真正时间后再按原重试合同继续。
