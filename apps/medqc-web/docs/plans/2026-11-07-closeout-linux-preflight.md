# Linux交付预检准备（2026-11-07，不含0916）

候选联合树起点为`e87c06799`，业务基线`6ad6817b1`，已等价纳入出院终点`8e31894cf`和工作区读取`0c92b275c`。本文只记录Linux工具准备；最终业务Commit由主协调收口后固定。本轮没有最终包、Build ID、包SHA256或现场验收结论。

## 已确认缺陷及最小补丁

`backend/app/services/case_material_snapshot.py:storage_root`依次使用`QC_CASE_MATERIAL_DIR`、`QC_DISPATCH_STATE_DIR`父目录下的`case-materials`，两者均缺失则使用具体release的`backend/data/case-materials`。原`stage_upgrade.py:stage`只确认业务配置文件存在，未检查有效材料路径；临时配置反例证明相对材料路径仍进入应用复制步骤，旧release默认目录也会随代码切换而变化。这是交付前阻断，不能靠修改路径后重新采集来修补旧任务。

补丁在`stage_upgrade.py:material_storage_preflight`中复用部署已有`python-dotenv`，按应用`load_dotenv(override=False)`的插值及进程环境优先级只读计算有效目录。在复制前拒绝相对路径、`releases`下任何版本、实际`current`/新旧应用目录及符号链接别名；不要求持久目录已首次创建。返回和回滚记录增加有效路径及其来源。不会创建、搬迁、删除材料、读取患者文件或更改配置；既有代理配置原字节保留。调用`check_compat`仍不读业务配置、不导入应用。

原Linux暂存夹具和`smoke_upgrade.py`的合成配置同步使用持久`state/dispatch`。只变测试夹具，没有运行依赖安装式冒烟。真实API/Worker/systemd环境及目录权限仍需现场核对；暂存进程环境不能替代实际服务环境。

## 复用入口与身份要求

- `linux_app_upgrade/check_compat.py`：逐文件SHA256、BUILD完整Commit/Build ID、Ubuntu22/x86_64/Python3.10、既有业务venv、精确依赖锁、pip check和第三方二进制导入；不安装依赖。
- `linux_app_upgrade/make_package.py`：必须显式提供发行方64位源包SHA256和40位应用Commit，源包内部逐文件清单及BUILD身份一致才可提取；本轮不调用生成器或制包workflow。工具Commit不能替代应用Commit，旧包及旧依赖验收不能证明新源码可交付。
- `linux_app_upgrade/stage_upgrade.py`：再次检查、材料路径预检、复制新release及记录；不切current、不改venv/配置、不启停服务、不自动迁移。异常半成品由人工核查，不自动清理。
- `linux_offline/deploy/db-admin.py`：仅另获批准时按实际版本显式备份/迁移；check同样会连接业务库，本轮没有执行任何action。不可将它描述成离线文件检查。

## 实际迁移依赖与回滚边界

源码静态核对：`20261102_000062 → 20261105_000063_bundle_refresh_storage → 20261106_000064_daily_qc_schedules`。063创建/校验Bundle刷新任务与失败审计存储，保留历史owner；064新增每日计划和逐日触发账本，`enabled`数据库默认false。迁移定义未修改，也未执行Alembic或连接任何数据库。

现场当前版本、既有表owner/结构/权限、063和064是否已执行均未知，因此不能承诺无需迁移。新功能须满足实际063/064合同；不stamp、不downgrade、不通过删表重建绕过问题。代码回滚保留新增表、材料对象、任务引用和历史结果，先确认旧代码兼容升级后结构，不恢复dump覆盖现有结果。

材料有效目录应稳定在release外，例如`/data/medqc/business/state/case-materials`。原配置的`QC_DISPATCH_STATE_DIR=/data/medqc/business/state/dispatch`已可推导该目录，无须覆盖现场env。若旧材料曾落在release内，先保留原件并单独批准迁移/兼容方案，不能静默改目录。保留代理、密钥、激活、角色及任务设置；升级器不启用模型、RabbitMQ、自动计划或未验收CDM，也不擅自关闭已有获准配置。现场发现已有任务/计划运行应停止交付并报告，不由工具自动接管。

## 必要验证与限制

- 已先运行复制前阻断反例：原实现失败，错误为`unsafe material path reached application copy`；补丁后拒绝相对材料路径，未发生应用复制或state目录创建。
- `python -B test_material_preflight.py -v`通过8项，1项真实目录符号链接用例因Windows缺权限跳过；实际执行外层禁用`socket.connect/create_connection/getaddrinfo`，没有网络、数据库或模型调用。覆盖显式路径优先级、dotenv插值/进程优先级、未创建持久目录、release默认/任意版本/相对路径拒绝、解析后current别名，以及暂存/模拟代码回切期间材料历史和代理配置不变。真实链接切换仍须Ubuntu定向验收。
- 因暂存实现和夹具均有变化，按主协调要求补跑原`test_upgrade.py`与新增路径文件这一小集合：23项共21通过、2跳过，socket拒绝；两个跳过均为当前Windows不能验证的真实链接用例。原生成器测试仅在临时目录构造微型合成归档，任务结束清理，不属于正式交付制包。未运行依赖安装式冒烟、完整构建或全量矩阵；原14项Ubuntu证据不能替代新路径行为验收。
- 公共工作流`.github/workflows/linux-offline-server.yml`原PR入口只运行`test_upgrade.py`，干净Python仅具标准库；新增只读路径解析使用应用已有`python-dotenv==1.0.0`。公共门禁适配由主协调处理，需纳入新增用例并保持网络隔离；本轮未安装任何依赖、未调用CI，不将新增用例记作Ubuntu已通过。现场始终使用`$ROOT/venv/bin/python -B`，缺少已锁定的dotenv依赖返回明确错误，不现场补装。

现场未验收清单：最终源包外部SHA256/内部清单/应用Commit一致性；源依赖锁与医院现有venv一致性及原生库；实际服务运行Commit/Build；业务库版本与063/064结构/权限；材料旧位置、跨版本同路径及API/Worker权限；代理现场配置和实际服务环境；活动任务/MQ/模型/计划状态；80/8001/systemd、激活、院内页面与历史1026/PDF结果只读可见；升级后旧代码回切兼容性。

未执行：最终制包/构建、安装依赖或服务、Docker、真实代理/模型/CDM/业务PG连接、任何迁移或账号操作、患者任务/质控重跑、推送/合并/部署/切换/重启。本文准备就绪不等于可发布或现场可启用。
