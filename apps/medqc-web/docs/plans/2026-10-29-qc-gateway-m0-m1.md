# QC Gateway M0/M1 本地交付说明

日期：2026-10-29

## 交付结论

本交付在 `cedb9c10a017c30b767e7ed449b8c9b90e356a54` 基线上建立 M0 离线
测试入口，并为 M1 的执行策略、客户端路由和单活动 Gateway 提供合成验收入口。
基线 Alembic head 为 `20261026_000055`。同名远端 integration ref 未能确认，ref
fetch 失败，因此这里只声明本地审查基线，不声明最新远端。

本轮适配范围只有 LX0609 的样本、运行、终末正式入口。0916、自定义规则及其他
LLM 调用者明确保留旧模式。M2 RabbitMQ/独立 Worker/Outbox 不在范围。

## 文件与职责

| 文件 | 职责 |
| --- | --- |
| `backend/scripts/run_qc_scheduler_tests.py` | 默认 offline 的显式 suite/node runner；拒绝隐式全仓和未实现的 isolated-infra |
| `backend/tests/scheduler_support/isolation.py` | 凭据、dotenv、DNS/socket、非 SQLite 和子进程进程内护栏 |
| `backend/tests/unit/test_qc_scheduler_isolation.py` | 护栏正反例；SQLite、MockTransport、ASGITransport、asyncio 可用性 |
| `docs/architecture/adr-qc-dispatch-boundaries.md` | 调用者、owner、M1/M2 边界和后续验收门槛 |

M1 生产与测试文件由同一工作树内的执行策略、客户端路由、Gateway 三个独立实现批次
提供，并已纳入下述统一离线验收。

## 离线 runner 合同

从 `apps/medqc-web/backend` 运行：

```powershell
python -B scripts/run_qc_scheduler_tests.py --profile offline --suite m0-isolation
python -B scripts/run_qc_scheduler_tests.py --profile offline --suite m1-admission
python -B scripts/run_qc_scheduler_tests.py --profile offline --suite compatibility
python -B scripts/run_qc_scheduler_tests.py --profile offline --suite compatibility-restart --allow-reviewed-restart-probe
python -B scripts/run_qc_scheduler_tests.py --profile offline tests/unit/test_name.py::test_name
```

显式 suite 清单：

- `m0-isolation`：runner 自身隔离正反例；
- `m1-admission`：Gateway admission、取消、API、dispatch routing、dispatch runtime
  identity 和 scheduler execution policy；
- `compatibility`：共享 HTTP、任务身份、失败规则补跑、取消、最新完整轮次、
  结果读取/导出、计时、Canonical finalizer 和隐私身份保护。
- `compatibility-restart`：单独运行既有跨 Python 进程重启持久化保护；未带
  `--allow-reviewed-restart-probe` 时在收集前明确拒绝，不以 skip 凑绿。

`--profile isolated-infra` 当前输出明确拒绝，不会尝试本机 PG、RabbitMQ 或 Provider
端口。位置参数也必须是显式 pytest node；无 suite 且无节点时拒绝运行。

护栏覆盖：

- 不读取本机 `.env`；清空 DSN、数据库、Gateway 与 Provider 凭据/端点配置；
- 禁止 DNS 解析、普通 connect/connect_ex、UDP sendto、listener、便捷连接函数；
- Windows asyncio 仅精确允许 stdlib `socket.socketpair` 自身建立唤醒管道；
- 默认 SQLAlchemy 只允许合成内存 SQLite；旧模块导入后 `engine` 与
  `SessionLocal` 绑定同一个无表内存库；
- 收集前仅把 import 时硬建 `data/demo_feedbacks.db` 的 legacy `demo_db` 依赖替换为
  合成内存 seam；不替换 QC workspace/Canonical/保存 owner，其他磁盘 SQLite 仍拒绝；
- 显式 pytest plugin 提供 `TestClient(create_app())` fixture，但不进入 context
  manager、不运行主 app lifespan；路由、授权与测试保存/选轮 owner 保持真实；
- 禁止通用 `subprocess`、`os.system`、spawn/exec/startfile 等子进程逃逸；仅按当前
  Python、脚本 hash、backend cwd、临时 `.sqlite` 路径和 mode 白名单允许既有重启
  probe。该例外必须显式传 flag；create/create-full 只能新建并登记不存在的临时文件，
  后续 mode 只能用本次 runner 登记路径，且子环境重新清理、子脚本外层重装同一
  离线隔离；
- 允许 HTTPX Mock/FakeTransport、ASGITransport 与 asyncio，不启动主 app lifespan。

这是一层 Python 测试进程护栏，不是 OS 沙箱；M2 独立进程故障演练必须使用另行
批准的一次性基础设施。

## 当前验证记录

### 统一隔离集

主协调者最终统一运行 compatibility suite，并显式追加 M0、M1 六个文件及原模型/
配置保护文件：

```powershell
$qcUnifiedExtraTests = @(
  "tests/unit/test_qc_scheduler_isolation.py"
  "tests/unit/test_llm_gateway_admission.py"
  "tests/unit/test_llm_gateway_cancellation.py"
  "tests/unit/test_llm_gateway_api.py"
  "tests/unit/test_qc_scheduler_execution_policy.py"
  "tests/unit/test_llm_dispatch_routing.py"
  "tests/unit/test_llm_dispatch_runtime_identity.py"
  "tests/unit/test_llm_config_loader.py"
  "tests/unit/test_luxian_0609_llm_role_routing.py"
  "tests/unit/test_qc_llm_client.py"
  "tests/unit/test_qc_llm_client_qwen_thinking.py"
  "tests/unit/test_qc_llm_client_thinking_budget.py"
  "tests/unit/test_llm_execution_concurrency.py"
)
python -B scripts/run_qc_scheduler_tests.py --profile offline --suite compatibility @qcUnifiedExtraTests
```

最终结果：`338 passed, 72 warnings in 26.50s`，无失败。

该集合实际覆盖生产前缀配置清理、dotenv/DNS/socket/DSN/磁盘 SQLite/默认子进程
拒绝、内存 SQLite 与 Fake/ASGITransport、Gateway admission/API/取消/quarantine、
dispatch/runtime identity、族并发策略、旧 direct 客户端/思考参数、CAS/取消/补跑、
Canonical 最新完整轮次、结果读取与导出。

### 显式受控重启集

跨进程持久化保护必须单独显式授权：

```powershell
python -B scripts/run_qc_scheduler_tests.py --profile offline --suite compatibility-restart --allow-reviewed-restart-probe
```

最终结果：`18 passed, 24 warnings in 170.88s`，无失败。运行使用当前严格 guard、
Python isolated mode、固定 probe hash 和本次测试登记的新临时 SQLite 路径。

统一隔离集与受控重启集的测试文件不重叠，但因后者采用单独显式授权模式，结果分别
报告；不得把早期 `18`、`42`、`162` 等重叠/中间运行数字再次累加为最终结果。

### 静态检查

- 34 个变更 Python 文件通过 UTF-8 无 BOM、LF 和 Python 3.10 AST 检查；
- Ruff 除 `app/services/sichuan_qc_service.py` 的 7 个既有问题外全部通过，这 7 项与
  基线逐项一致，本轮没有新增 Ruff 问题；
- `git diff --check` 通过。

## 配置与能力声明

- Gateway 默认关闭，默认 `direct`；M1 完成不等于启用流量或部署服务。
- 未知/未注册 role 配置继续按旧兼容合同忽略，不改变主模型；已知显式 role 若缺少
  API key 或配置格式错误则失败关闭，不静默沿用主模型或回退云端。
- 保持现有默认 `qwen3.8-flash`；部署 `.env` 的 thinking=true 不改为全局 false，
  只保留既有调用点的显式覆盖。
- Strata 容量 2 仅作为配置和 FakeTransport 并发上限验证，不表示已接入或实测。
- 初期 Gateway 网络重试为 0；已发送后超时/断连/取消状态未知时须保留 resource
  quarantine 与 unknown-inflight sentinel，不能立即回收并满额放行。当前只允许人工
  核实服务端工作结束后恢复，不声称按截止时间自动清除或自动恢复容量。
- 本轮不声称交互/批量混合优先级公平调度或多机 HA 完成。
- Gateway sentinel 只覆盖同一主机、同一显式 `state_dir` 的单活动实例，不提供跨主机
  协调、自动故障恢复或 HA。
- 仓库当前依赖记录：FastAPI 0.104.1、Uvicorn 0.24.0、Pydantic 2.5.0、
  pydantic-settings 2.1.0、HTTPX 0.25.2、aiohttp 3.9.1、OpenAI 1.76.0；
  本轮未安装或升级。最终离线运行环境实际为 HTTPX 0.28.1、Pydantic 2.13.4；没有
  在仓库锁定的 HTTPX 0.25.2/Pydantic 2.5.0 独立环境再次复跑，因此锁定版本兼容性
  仍是合并/发布前限制，不能由本轮结果外推。
- Celery 5.3.4 已存在不代表 RabbitMQ 客户端选型。AMQP 库/版本、Erlang/
  RabbitMQ 配对、队列类型与 Broker 故障演练全部属于 M2。

## 保留合同与未适配调用者

M1 必须保留现有领取 CAS、attempt/fencing、30 秒租约心跳、取消保护、失败规则补跑、
Canonical 发布与最新完整轮次优先。规则执行器仍是临床判定唯一 owner；Gateway 不得
制造或重判临床状态。

Provider/model/思考、dispatch、规则范围和材料身份在任务创建时固定；病历/族执行
策略在任务领取、建立隔离 runtime 时按当时有效配置冻结，不属于模型 runtime
identity。创建到领取之间的紧急降容不能把排队任务误判成模型身份变化。

`http_max_concurrency` 虽被捕获为策略参数，旧 direct 流量仍使用可热重配的进程级
global gate；本轮不承诺每任务 HTTP 硬上限冻结，也没有新增 task-local HTTP
semaphore。Gateway 新流量由单活动 resource owner 管理，不与旧 gate 双重准入。

0916、自定义规则、前页抽取、编码、字段映射、Agent 和演示入口仍走旧模式。旧模式
的共享 HTTP 限流不得因 LX0609 Gateway seam 被取消。

## 明确未做与授权边界

未安装 RabbitMQ/AMQP 依赖，未建 Outbox/迁移/独立 Worker，未运行 Broker 故障矩阵，
未连接业务库或本机测试端口，未调用真实模型或 Strata，未读取新增患者材料。
未修改业务 `.env`，未执行 Alembic 迁移，也未部署 Gateway、MQ、HA 或 Strata。

当前用户只授权本地开发；未授权 push、merge、部署、打包、重启、业务库写入、
`.env` 修改、真实 Provider/Strata 验证或 RabbitMQ 安装。

## 后续验收边界

1. 在仓库锁定的 HTTPX 0.25.2/Pydantic 2.5.0 独立环境复跑相同集合；
2. 合并前重新核对实际 integration HEAD、迁移 heads、未合并修复与工作树 diff；
3. 部署前另行验证服务身份、同机 `state_dir` 权限、人工 sentinel 恢复流程与真实
   Provider 合同；
4. M2 另行授权后再锁 AMQP/RabbitMQ 版本并做一次性 PG/Broker 故障演练；
5. 真实 Strata 容量、取消与性能只能在另行授权后验收。
