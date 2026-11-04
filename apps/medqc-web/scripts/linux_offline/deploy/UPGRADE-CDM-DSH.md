# DSH：998f7ac94业务基线的双数据源离线交付

此包的应用基线是`998f7ac94ff6d9bf3a5a52383c0f909a36ad6509`。打包提交以`BUILD.json.commit`为准，含交付说明、计量清单和隔离测试更新；没有修改该基线的`backend/app`、前端源码或迁移。前后端runtime必须与该打包Commit一致，不冒充旧包。

默认：原有源`legacy_pg`、CDM停用、RabbitMQ关闭（legacy）、无模型凭据、启动后台/任务恢复/监视关闭。安装器保留既有business.env，不会覆盖已保存的来源、模型、MQ模式，因此升级前必须检查旧环境，不能把“新包默认”当作“旧配置已强制关闭”。

本指南分两阶段：收到包后可先做只读预检；停止应用、安装、业务库备份/升级和保存来源设置均需用户另行批准后执行。不触碰同步服务、同步三库结构/数据、Strata、Ollama、Docker、Dify或现有端口映射。不创建CDM账号、不授予数据库权限。

## 1. 收包与只读预检（先执行，未批准不升级）

将包和同名sha256传至`/data/medqc/offline-998f7ac94`，不要覆盖旧offline-install。以下命令不会安装、迁移或启动应用：

```bash
set -euo pipefail
cd /data/medqc/offline-998f7ac94
sha256sum -c MedQC-Ubuntu22-Python310-PG16-offline.tar.gz.sha256
test ! -e medqc-offline
tar --no-same-owner -xzf MedQC-Ubuntu22-Python310-PG16-offline.tar.gz
export KIT=/data/medqc/offline-998f7ac94/medqc-offline
(cd "$KIT" && sha256sum --check --quiet SHA256SUMS)
cat "$KIT/BUILD.json" "$KIT/VALIDATION.json" "$KIT/DUAL-SOURCE-VALIDATION.json"
readlink -f /data/medqc/business/current
readlink -f /data/medqc/business/venv
sudo systemctl is-active medqc-business-api medqc-business-web medqc-sync-api medqc-sync-worker || true
ss -ltn | grep -E ':(80|8001|5432|18083)\b' || true
```

构建验证是Ubuntu22.04/Python3.10、仅回环网络、一次性PG16，两独立库及060的68表无数据schema快照；不等于医院真实接口或患者质量已验收。不要输出.env、JWT、数据库口令或患者内容。

CDM预检只使用同步管理员提供的**已存在专用只读账号**；不能复用超级用户/同步写入账号。请同步管理员确认库名`medqc_sync_cdm`、schema`cdm`、主机127.0.0.1、端口5432。若现场不同，先报告，不自行修改数据库。

在批准的账号下，现场交互编辑专用pgpass，格式`host:port:database:username:password`，特殊冒号和反斜线按libpq规范转义。密码不进命令行、聊天或普通日志。文件必须归medqc-business、0600，所有父目录可穿透。将它放在`/data/medqc/business/config/cdm.pgpass`；不要读取或复制同步服务的.env。准备凭据文件仅为部署文件，不向数据库写入。

```bash
read -r -p 'CDM只读账号名（不输入密码）: ' CDM_READER
sudo -H -u medqc-business env -C /data/medqc/offline-998f7ac94 \
  /data/medqc/business/venv/bin/python "$KIT/deploy/cdm-preflight.py" \
  --host 127.0.0.1 --port 5432 --database medqc_sync_cdm \
  --username "$CDM_READER" --passfile /data/medqc/business/config/cdm.pgpass
unset CDM_READER
```

该工具只查询系统目录、身份和权限，不读患者行、不DDL、不保存应用配置；检查PG16、只读事务、四个目录表三坐标、全部可见CDM表SELECT和无DML权限。失败则报告脱敏错误，不自行建表、改权限或迁移CDM。完整40接口的字段映射/临床内容仍需现场抽查；四表检查不代表全量合同通过。

## 2. 升级（需批准维护窗口后执行）

服务器已有062和1026，**不重复建库、创建poc_tester、导入1026或签发激活**。保持现有账号、激活文件、JWT、业务URL、材料schema和历史结果。先确认没有活动质控、同步触发或业务Worker；有任务时停止升级并报告，不能强杀模型/同步服务。

以下命令只停止两个业务单元。不要重启整台服务器、Docker或PG：

```bash
set -euo pipefail
export KIT=/data/medqc/offline-998f7ac94/medqc-offline
ROOT=/data/medqc/business
STAMP=$(date -u +%Y%m%dT%H%M%SZ)
sudo -u medqc-business mkdir -m 0700 "$ROOT/backups/upgrade-$STAMP"
STATE="$ROOT/backups/upgrade-$STAMP"
readlink -f "$ROOT/current" | sudo -u medqc-business tee "$STATE/previous-current.txt" >/dev/null
readlink -f "$ROOT/venv" | sudo -u medqc-business tee "$STATE/previous-venv.txt" >/dev/null
sudo systemctl stop medqc-business-web medqc-business-api
sudo -u medqc-business cp -a "$ROOT/config/business.env" "$STATE/business.env"
sudo -u medqc-business cp -a "$ROOT/tools" "$STATE/tools"
sudo -u medqc-business cp -a "$ROOT/state/dispatch" "$STATE/dispatch" 2>/dev/null || true
sudo -H -u medqc-business env -C /data/medqc/offline-998f7ac94 \
  MEDQC_INSTALL_ROOT="$ROOT" MEDQC_PYTHON=/usr/bin/python3.10 bash "$KIT/deploy/install.sh"
sudo -u medqc-business "$ROOT/venv/bin/python" "$KIT/deploy/db-admin.py" migrate
sudo -u medqc-business "$ROOT/venv/bin/python" "$KIT/deploy/db-admin.py" check
printf 'Rollback record: %s\n' "$STATE"
```

`migrate`自动pg_dump并校验备份，再执行正式062链及结构检查；本版没有新增Alembic迁移，不stamp、不重建已有任务表。出现非空表结构冲突就停止报告。备份只写`/data/medqc/business/backups`。

启动前核对business.env保留原DATABASE_URL/JWT/激活路径，同时如下开关关闭；模型Key和已保存的模型设置不得擅自删除/改写，如旧配置启用模型或MQ，先报告并取得关闭授权：

```ini
MEDQC_STARTUP_MODE=normal
MEDQC_STARTUP_BACKGROUND_ENABLED=false
MEDQC_RESUME_QC_TASKS=false
QC_TASK_DISPATCH_MODE=legacy
QC_SC_RULE_SOURCE_MONITOR_ENABLED=false
CDM_DATABASE_URL=
CDM_PGPASSFILE=
```

还需确认`state/dispatch`实际持久模式仍为legacy（环境变量不能覆盖持久RabbitMQ开关）；本轮不启动Worker/Outbox Publisher、不开启定时任务、不执行连接测试模型。若此前存在CDM来源配置，确认仍停用且默认legacy，不通过直接SQL修改配置。

已有systemd单元保持原样，不再运行首次安装器install-services.sh、不自动enable。确认80/8001已由刚停止的业务释放，启动并检查：

```bash
sudo systemctl start medqc-business-api
curl --fail http://127.0.0.1:8001/api/v1/runtime-build
sudo systemctl start medqc-business-web
curl --fail http://127.0.0.1/api/v1/runtime-build
curl --fail http://127.0.0.1/workstation-v5/login >/dev/null
sudo systemctl is-active medqc-business-api medqc-business-web
```

Commit/Build ID必须匹配BUILD.json及浏览器`build-info.json`。只读查询Alembic为062，保留1026的27份和原材料/历史结果数量；不使用重新质控验证升级。

## 3. 双数据源页面验收

第一步在CDM停用状态：用已有持久管理员登录（登录会更新最后登录时间，需该项授权），进入系统设置→数据与配置→数据同步中的“病历读取数据源”。确认原有来源默认启用、CDM停用、默认原有来源；不要点击“同步”“质控”“模型测试”。确认1026仍为27份，材料时间/new/去重和既有结果能查看。

只读预检通过后，**保存配置和启用CDM会写业务配置，须用户明确授权**。在授权后：

1. 部署配置仅添加`CDM_PGPASSFILE=/data/medqc/business/config/cdm.pgpass`，保持`CDM_DATABASE_URL`为空；重启业务API使凭据变量生效，不重启同步/模型。
2. 页面填写预检确认的主机、端口、库名和只读账号；先点击“只读检查”，此动作不保存、不读正文；通过后勾选启用CDM并保存，默认源暂保持原有。
3. 运行/终末病历池切换来源，核对分页/筛选/数量及已获授权的三坐标样例；查看文书、时间、首页和诊断；只展示必要内容，不将原文贴报告。没有首页的病例亦应按目录可见。
4. 两页签分别保持两个来源，确认不互相改变；切源后旧勾选、详情、进度清空。源库不可达应明确报错，不回退原有源或空白通过；不要人为停同步/PG制造故障。
5. 1026及其历史结果仍来自业务材料副本；旧结果不随默认源重解释。不启动新质控、不导入患者、不生成文书。
6. 只在另获授权后将默认源改为CDM并验证新开列表；这会写业务配置。不同源同键的历史结果不应混用，无法由现有样本验证的部分写“未覆盖”。

已发布CDM是快照，今日HIS实时核验、旧统计、跨病例分析及未适配生成/写入口可能明确拒绝；不是现场补表或放宽权限的理由。每日任务选源不在本版验收范围。

## 4. 回滚

仅应用回滚，不downgrade、不删库、不重新导入1026。先停止业务两个单元，确认无新CDM任务；使用第2节记录的STATE，核对旧路径都在`/data/medqc/business/releases`和`venvs`内。恢复旧current/venv符号链接及原business.env；保留新版本和日志，不删新库/新数据。如果升级前后未改数据库，不盲目恢复dump覆盖已有结果。结构/数据回滚须单独批准并核对备份目标。

```bash
# STATE由维护记录明确填写，禁止猜测或自动选“最新”。
sudo systemctl stop medqc-business-web medqc-business-api
OLD_APP=$(sudo cat "$STATE/previous-current.txt")
OLD_VENV=$(sudo cat "$STATE/previous-venv.txt")
case "$OLD_APP" in /data/medqc/business/releases/*) ;; *) exit 1;; esac
case "$OLD_VENV" in /data/medqc/business/venvs/*) ;; *) exit 1;; esac
sudo -u medqc-business test -d "$OLD_APP"
sudo -u medqc-business test -x "$OLD_VENV/bin/python"
sudo -u medqc-business ln -sfn "$OLD_APP" /data/medqc/business/current
sudo -u medqc-business ln -sfn "$OLD_VENV" /data/medqc/business/venv
sudo -u medqc-business cp -a "$STATE/business.env" /data/medqc/business/config/business.env
sudo systemctl start medqc-business-api medqc-business-web
curl --fail http://127.0.0.1/api/v1/runtime-build
```

如升级中更改了持久来源配置/MQ模式或创建过新任务，停止自动回滚，先人工核对旧程序兼容，不直接恢复旧配置覆盖。pg16工具副本保留在STATE，必要时独立核对后恢复；不修改系统PG。

## 5. 现场报告

只报告包SHA256、BUILD、062、服务状态、来源名称、只读权限、表/病例/历史结果计数及错误码、耗时。注明授权执行了哪些阶段；未启用项写未验收。不要附口令、API Key、JWT、完整连接串、患者原文或模型原答。开发侧不连接现场，服务器CDM真实联调、浏览器展示、激活及防火墙均待DSH另行验收。
