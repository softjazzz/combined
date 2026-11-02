# 首页V2与同步服务联合适配验收

**Goal:** 推送两个独立修复分支并创建Draft PR；在新联合工作树验证迁移汇合、PG隔离、最新结果及持久重试，不修改正式集成线。

**Architecture:** 固定业务基线d2a94df3b，保留5709c7f18与661135442的完整祖先。060、061历史不改，新增062唯一汇合头。测试只使用本轮新建、独占loopback端口、显式cluster_name的临时PG集群及合成数据；禁止读取.env或调用外部网络/模型。

**Tech Stack:** Alembic、SQLAlchemy、psycopg2、PG18独立集群、pytest、既有OfflineIsolation。

## 顺序与验收

1. 两修复分支分别推送，创建业务线目标Draft PR #25和#26，不合并。
2. 从远端业务线最新d2a94df3b新建codex/frontpage-sync-joint-adapt-20261101，仅在该树合入两候选。保留V7.1与目标C01保护，原工作树WIP不纳入。
3. 先固定多头反例；新增20261102_000062，父版本060和061，只汇合历史，不伪造字段、不stamp旧库。更新本联合分支的图测试，两个原候选不动。
4. 用一次性PG18执行真实增量迁移：从055合成历史结构运行双方056+、048、060/061/062；覆盖单schema与split，以及先首页/先同步两种起点。合成历史结构不能冒充从空库全历史升级。
5. 同一集群验证首页真实持久账号范围、PG病例锁/唯一latest、旧慢任务选轮、取消；控制库001→002、缺迁移拒绝、并发领取、持久退避/重建仓储和旧租约。失败保持产物并修复最小缺陷。
6. 严格离线复跑439首页与379同步保护及必要业务保护；前端未变沿用54定向并完成必需静态检查。
7. 记录实际PG版本、所有通过/跳过/未执行项及两个Draft PR CI状态；本地提交联合适配，不推送联合分支、不部署、不合并。

## 安全边界

不连接5432、既有库、HIS、客户机、Strata或真实模型。新集群只绑定127.0.0.1且使用独占高端口，测试连接必须核对集群标记和白名单数据库；只允许一次性内存SQLite及本轮集群。结束停止本轮PG，不停止其他服务、不递归删除目录。

## 实际交付

- Draft PR [#25](https://github.com/softjazzz/combined/pull/25)：5709c7f18，首页独立修复；[零模型质量门](https://github.com/softjazzz/combined/actions/runs/41390494807)、调度隔离、M2一次性基础设施均成功。
- Draft PR [#26](https://github.com/softjazzz/combined/pull/26)：661135442，同步独立修复；调度隔离和M2一次性基础设施成功，[零模型质量门](https://github.com/softjazzz/combined/actions/runs/41390495669)有3项失败，见下方阻断。
- 两PR均以未移动的远端业务线d2a94df3b为base，未合并。原独立工作树干净，未纳入账单/病理059 WIP。
- 联合工作树：`C:/medqc-frontpage-sync-joint-adapt-20261101`；分支`codex/frontpage-sync-joint-adapt-20261101`。仅本地合入双方，062父版本为060/061。050、048、双方056/057/058和060/061历史保持不变。
- V7.1 Layout、main.ts、tokens、Theme和mqIcons保留目标版本；导航及前端整体与首页候选5709c7f18一致，同步生产源码与661135442一致。联合新增仅迁移汇合、测试入口、图断言及本说明，不重写临床判断。

## 一次性PG实际验收

本机Docker未启动，未启动Docker或已有服务。复用已安装的`D:/Program Files/PostgreSQL/18/bin`，用initdb创建本轮全新集群，实际版本**18.3**，只监听127.0.0.1:62997，cluster_name=`medqc_sync_control_synthetic`；结束后pg_ctl fast停止成功。没有连接业务PG16或5432。

**26 passed**（12.62s）：

1. 单schema/split × 直接汇合/先060/先061共6种路径。使用明确声明的最小055历史结构夹具，执行真实048、两条056/057、058、060、061、062增量DDL；最终真实alembic_version仅062，既有合成行保留，双方表/字段/索引均核对，重复upgrade幂等。
2. 6种路径均在真实PG并发保存同病例首批结果，病例事务锁与部分唯一索引共同保证唯一latest，较新任务获选、旧结果仍保留；异院结果/任务拒绝，排队取消后不可领取。
3. 6种路径均使用真实PG SysUser SQL验证有效持久角色、机构和停用/坏JSON/无机构失败关闭；split中sys真实账号压住public同ID伪admin影子。
4. 6种路径移除合成签名列后，061在建索引前报ambiguous_050_history，事务回滚；不以同号stamp推断历史身份。
5. 控制库真实001→002，使用非登录owner及非超级运行角色；002前读取拒绝，升级后失败/退避同事务保存，重建仓储后两个并发领取者只有一个获得第2次尝试；旧token拒绝、绑定变更进入recovery_required。
6. 显式反例拒绝5432业务库与模型socket。测试入口未被启用时默认26项跳过，不会自动尝试PG。

另执行一次**两个独立Python进程**的崩溃恢复探针：第1进程在真实失败事务提交后os._exit(73)，没有进入监督进程观察/等待；第2进程从同库读取failed并领取attempt=2，完成验证后取消合成任务。两进程各自安装相同PG白名单与模型/HTTP隔离；不是内存重建冒充跨进程恢复，也不代表覆盖任意断电窗口。

### 重复执行（仅全新、空的一次性集群）

初始化与停止由外部显式执行；测试guard不开放任意子进程，也不使用.env。集群根目录须位于本工作树`.tmp`，数据目录名固定data，高端口必须空闲。不要指向任何已有PG数据目录。

```powershell
$pgBin='D:/Program Files/PostgreSQL/18/bin'
$pgRoot=Join-Path 'C:/medqc-frontpage-sync-joint-adapt-20261101/.tmp' ('pg-joint-'+[guid]::NewGuid().ToString('N'))
if (Get-NetTCPConnection -LocalPort 62997 -State Listen -ErrorAction SilentlyContinue) { throw 'Test port occupied' }
New-Item -ItemType Directory -Path $pgRoot | Out-Null
& "$pgBin/initdb.exe" -D "$pgRoot/data" -U postgres --auth-local=trust --auth-host=trust --encoding=UTF8 --no-locale
if ($LASTEXITCODE -ne 0) { throw 'initdb failed' }
& "$pgBin/pg_ctl.exe" start -D "$pgRoot/data" -l "$pgRoot/postgres.log" -o '-h 127.0.0.1 -p 62997 -c cluster_name=medqc_sync_control_synthetic' -w -t 30
if ($LASTEXITCODE -ne 0) { throw 'test PG start failed' }
try {
    Set-Location C:/medqc-frontpage-sync-joint-adapt-20261101/apps/medqc-web/backend
    py -3.10 -B scripts/run_frontpage_sync_pg_tests.py --data-directory "$pgRoot/data"
    if ($LASTEXITCODE -ne 0) { throw 'PG acceptance failed' }
    $probeDb='medqc_sync_control_acceptance_20991101'+[DateTime]::UtcNow.ToString('HHmmss')
    py -3.10 -B scripts/joint_pg_crash_probe.py fail-and-crash --database $probeDb --data-directory "$pgRoot/data"
    if ($LASTEXITCODE -ne 73) { throw 'expected controlled exit 73' }
    py -3.10 -B scripts/joint_pg_crash_probe.py verify-restart --database $probeDb --data-directory "$pgRoot/data"
    if ($LASTEXITCODE -ne 0) { throw 'restart verification failed' }
} finally {
    & "$pgBin/pg_ctl.exe" stop -D "$pgRoot/data" -m fast -w -t 30
}
```

## 联合隔离回归

- 首页runner：439 passed，3条既有弃用警告。
- 同步19文件：379 passed、1 deselected；保持子进程冷导入探针排除，不放宽OfflineIsolation。
- C01恢复、完整保存链、长文、检查核验与独立PACS：78 passed、1 skipped（须显式私有原报告的入口，本轮未读患者材料）。
- 首页页面/服务/轮询与导航：54 passed，传输层TCP/TLS/fetch阻断。
- 完整npm lint与type-check退出0；相关Ruff、UTF8无BOM/LF及diff检查通过。未重跑全站前端/全部后端；上述项目不能与CI数字相加作为独立病例数。

## 明确未收口：同步候选带入的010关联合同冲突

PR26零模型门11,946通过、3失败。联合本地独立复现相同两文件：5通过、3失败：

- `test_luxian_0609_010_missing_order_key.py::test_no_proven_defect_retains_missing_key_gap`
- `test_luxian_0609_010_order_key_native.py::test_unidentified_order_preserves_proven_defect_or_gap[True-False]`
- 同文件`[True-True]`。

来源`native_exam_lab_execution._order_exam_structure_outcome`在有检查/报告时提前返回None，未保留“其他相关医嘱缺身份”的旧缺口；真实Native固定应答链的两个反例从data_gap变为non_compliant，不只是测试文字不一致。相关函数AST与fd9e9a186来源完全一致，联合分支没有改它；在隔离进程仅换回业务基线d2a94df3b的该函数，同样8项全部通过。这是精确函数级反事实对照，不冒称整棵业务基线全量重跑。

本轮不擅自重定独立PACS与原010事件完整性的医学合同，不删断言、不屏蔽门禁。此项仍是**正式合并阻断**：需要保留独立PACS来源能力，同时明确并实现缺键/候选范围不完整的失败关闭边界，再覆盖这3个正式链反例。不能因为迁移/工程验收通过就认定可合并。

## 未执行及结论

未验证客户PG16、真实历史全链升级/历史伪050自动修复、所有断电阶段、HTTP实际接管/ODBC取数、Bundle现场读链、RabbitMQ重新部署或真实患者医学质量。没有新增患者材料、连接模型、运行病历质控、改正式分支或部署。

结论：推送/两Draft PR/独立联合适配/真实一次性PG工程验收完成；联合候选保持本地，两个PR继续Draft。#25检查已绿，#26因上述3项规则合同冲突暂不具备合并条件，不能宣称两条功能已经正式集成。
