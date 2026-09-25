# 原始 LX0609：解压包跨进程恢复技术演练

## 固定版本与隔离范围

- 源码提交：`71f347e3a27ee5052417746388bca4c2200e2186`。从该提交新建干净的临时检出，不复制集成工作树中未跟踪的业务数据。
- 用 `scripts/package-customer-release.ps1`、PowerShell 7、`-SkipBundledActivation` 在本机临时目录构建；发布源码门禁通过。生成构建号 `medqc-web-customer-20260925-082620`，ZIP 解压后的 `frontend/dist/build-info.json` 与 `backend/app/data/runtime_build.json` 均记录同一构建号及上述 SHA。
- 未预激活包仅用于本机技术演练，不是客户交付物；未使用客户数据库、患者资料或模型服务。

## 从 ZIP 解压目录执行

测试读取现有 `backend/tests/unit/test_luxian_0609_task_restart_persistence.py` 的固定合成探针，在多个独立 Python 进程中以**解压包的 `backend` 为 `PYTHONPATH` 和工作目录**执行；每个进程回报实际加载的 `custom_qc_workspace_service.py` 路径，并断言位于解压目录内。

1. 第一进程通过正式 `CustomQCWorkspaceService.create_batch_job` 保存一条冻结的原始 `LX0609-01-01-01` 排队任务；第二进程执行启动扫描与正式 Worker，任务完成。任务行与 Canonical Envelope 均读回一条 `data_gap`，Token 为零，启动扫描只重投一次。
2. 另一条任务由第二进程领取至 `running` 后退出、不再续约；第三进程按超过续约期限的检查时点执行正式 `fail_stale_luxian_0609_running_jobs`。任务受控落为 `failed`，业务结果条数为零，`luxian_0609_usage_observation_complete=false`。这里通过前移检查截止时间模拟超时，没有等待真实三分钟，也没有真实模型在途中断。

包内源码模块路径断言、任务状态与 Canonical 断言均通过。此前隔离 PostgreSQL 18 的双进程唯一领取及旧代次零写入是另一组证据，不能将本次 SQLite 解压包演练写成客户 PostgreSQL 部署验收。

## 发现与剩余验收

- 相同发布脚本在本机 Windows PowerShell 5.1（`powershell -File`）于第 95 行报 `UnexpectedToken`，未开始打包；`pwsh -File` 成功。当前部署指南中的 `-SkipBuild` 示例也与脚本的显式拒绝相矛盾。发布流程须另行修正并在客户所用 PowerShell 版本验证，不能靠这次 PowerShell 7 成功掩盖。
- 尚未验证客户机真实启动脚本、客户 PostgreSQL 配置/迁移、生产认证、真实病例/模型执行、运行中模型调用中断费用或独立临床保护集。阶段 B/D 仅增加本机解压包的技术证据，整体 goal 仍 active。

## 2026-09-25 发布脚本兼容性补验

同一集成分支后续发现第 95 行解析失败来自 Windows PowerShell 5.1 将无 BOM UTF-8 中文注释按本机 ANSI 读取，导致注释与下一行 `if` 合并。脚本改为 ASCII 源码，默认授权名称仍由 Unicode 码位还原为原来的“MedQC 客户试用授权”；部署指南移除已被脚本拒绝的 `-SkipBuild` 命令，明确正式包会重新构建前端。

- `powershell.exe` 5.1 的 `Parser.ParseFile`：零解析错误；默认授权名称码位与原文一致。
- `powershell.exe -File scripts/package-customer-release.ps1 -SkipBuild -SkipBundledActivation`：进入预期的 `-SkipBuild is not supported` 门禁，不再于解析阶段失败。此命令在打包前退出，未生成产物。
- `test_customer_release_db_preflight_contract.py` 修正过期的成功夹具：现在提供匹配的 `build-info.json`，并新增旧构建号拒绝反例；整份 16/16 通过，Ruff 与编码检查通过。前端 lint、type-check 通过；全量单测并行运行时 1065/1067 通过，两个路由用例超 15 秒，结束后单独复跑分别 1/1、4/4 通过，不能把并行全量运行写成绿色。

这只关闭 PowerShell 5.1 解析和文档命令不一致的问题；尚未以 5.1 完整构建/解压，也未在客户机执行启动脚本或客户 PostgreSQL 恢复，不能扩写为阶段 B/D 部署验收。
