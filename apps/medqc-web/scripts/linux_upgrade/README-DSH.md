# DSH：c3c657076-r2，加固交付（全部现场命令未执行）

应用保持c3c6570763975d731f2c3a85047ab986b87fa148，Build 20261111-234500；不重新构建前端、不改应用功能。r2替换交付工具与runbook。旧08378ddb包作废，不执行旧版裸ln/mv切换命令。
预期现场：e1f65ffe7后端＋6cd06ff77即时装配补丁，697ab73ca前端，current=/data/medqc/business/releases/medqc-web-customer-20261110-235900。未知现场修改停止，不自行改清单或删除备份。

## 1. 收包／离线检查（不连接数据库）

上传tar.gz和同名.sha256到全新目录/data/medqc/app-upgrade-c3c657076-r2。

```bash
set -euo pipefail
cd /data/medqc/app-upgrade-c3c657076-r2
sha256sum -c MedQC-Linux-app-upgrade-c3c657076-r2.tar.gz.sha256
test ! -e medqc-app-upgrade
test ! -L medqc-app-upgrade
tar --no-same-owner -xzf MedQC-Linux-app-upgrade-c3c657076-r2.tar.gz
KIT=/data/medqc/app-upgrade-c3c657076-r2/medqc-app-upgrade
sudo chown -R root:root "$KIT"
sudo chmod -R a+rX,go-w "$KIT"
(cd "$KIT" && sha256sum --check --quiet SHA256SUMS)
sudo -H -u medqc-business /data/medqc/business/venv/bin/python -B "$KIT/check_compat.py" --root /data/medqc/business
sudo -H -u medqc-business /data/medqc/business/venv/bin/python -B "$KIT/release_guard.py" \
  --root /data/medqc/business --expected-current /data/medqc/business/releases/medqc-web-customer-20261110-235900
```

包内VALIDATION.md、LINUX-VALIDATION.json及evidence/日志均列入SHA256SUMS。45/92项是原应用源码定向验证沿用，不冒充r2重新执行。仅保留应用和受控升级工具，已移除db-admin/sample_set_transfer及deploy迁移工具。

## 2. 切换前只读硬闸门（须另获只读连接授权）

本次开发没有连接业务库。以下命令由DSH获准后执行；必须显式--allow-readonly-db。无此参数不连接、不停止服务、不切换。

```bash
set -euo pipefail
KIT=/data/medqc/app-upgrade-c3c657076-r2/medqc-app-upgrade
sudo /data/medqc/business/venv/bin/python -B "$KIT/safe_switch.py" preflight \
  --root /data/medqc/business \
  --expected-old /data/medqc/business/releases/medqc-web-customer-20261110-235900 \
  --allow-readonly-db
```

工具只输出脱敏结论，不打印/proc环境、密码、DSN、business.env或JWT。

强制核对：
- API/Web账号、组、UMask、工作目录及启动入口；拒绝未知EnvironmentFile和启动前后hook。API必须是既有单worker uvicorn命令。systemd声明环境必须已应用于实际进程。
- 从实际API进程初始环境读取覆盖值，按python-dotenv实际优先级解析配置，不用操作员shell猜配置。拒绝无法由unit与配置重建的应用环境覆盖/插值，避免回滚时丢失来源。
- MEDQC_STARTUP_BACKGROUND_ENABLED必须显式为0/false/no；MEDQC_RESUME_QC_TASKS与QC_SC_RULE_SOURCE_MONITOR_ENABLED亦须显式关闭。缺失不按安全处理。QC_DAILY_SCHEDULER_ENABLED缺失仅按代码既有false默认；显式true拒绝。启动模式normal，ENV=production，调度模式legacy。
- 旧backend/.env必须为指向同一config/business.env的符号链接，配置为非符号链接普通文件且无组/其他用户权限。普通副本即使内容相同也停止；不擅自换配置来源。新release沿用完全同一目标。
- 实际生效的材料、端点及显式冻结目录必须为release之外的绝对路径。没有外部路径依据即停止。
- 业务库必须medqc_business；连接会话default_transaction_read_only=on，显式SET TRANSACTION READ ONLY，10秒语句/3秒锁/5秒连接超时。SQL守卫拒绝非SELECT/SHOW/SET TRANSACTION READ ONLY；最后rollback关闭连接。不执行DDL、迁移、正文读取或业务写入。
- 要求public.alembic_version恰为[20261106_000064]，并核对qc必要表、刷新表完整结构、真实账号表owner及认证必需列。版本表在public、业务表在qc是不同概念。错误/缺失/歧义均停止，不能补表或stamp。结构合同直接从本包源码读取，未导入app.main、app.database.connection或启动服务。

成功仅证明该时刻闸门通过，不授权部署。保存报告不得包含凭据。已有后台任务/活动任务需按原维护流程确认；本工具不停止任务或改调度配置。若开关不符合要求，报告并等待独立配置变更决定，本包不会代改。

## 3. 暂存与切换（另外获得维护授权后）

先完成第1、2节并确认没有活动任务、具有现有备份。保留1026、历史结果、冻结、快照、旧release及补丁receipt。下面配置/state备份不替代业务库备份，不含pg_dump/迁移命令。

```bash
set -euo pipefail
ROOT=/data/medqc/business
KIT=/data/medqc/app-upgrade-c3c657076-r2/medqc-app-upgrade
OLD=/data/medqc/business/releases/medqc-web-customer-20261110-235900
BACKUP="$ROOT/backups/upgrade-c3c657076-r2-$(date -u +%Y%m%dT%H%M%SZ)"
sudo install -d -o medqc-business -g medqc-business -m 0700 "$BACKUP"
sudo -H -u medqc-business sh -c 'umask 077; tar -C "$1" -czf "$2/config-state.tar.gz" config state' sh "$ROOT" "$BACKUP"
sudo -H -u medqc-business "$ROOT/venv/bin/python" -B "$KIT/stage_upgrade.py" --root "$ROOT" --expected-current "$OLD"
# 应返回activated:false；已有目标目录/receipt则停止，不覆盖、不删除。
sudo "$ROOT/venv/bin/python" -B "$KIT/safe_switch.py" apply --root "$ROOT" --expected-old "$OLD" --execute --allow-readonly-db
```

apply会重新执行全部闸门（不是复用过期PASS），验证暂存文件全集、配置来源与依赖，再保存root:root/0600的脱敏切换证明、停止服务、重查unit/config是否变化、切换并启动。随后自动核对前后端HTTP身份均为c3c657076/234500。证明不含环境明文/密码，只含路径、身份和完整配置/unit摘要；没有旧证明则禁止猜测式回滚。

如果在停服务后发现配置变动，保持停止，不启动未知配置。若新启动失败或身份不符，不创建任务来验证，使用第4节；不自动迁移、恢复旧数据库或改配置修饰错误。

## 4. 回滚（只在本工具已执行切换流程且另获授权时）

```bash
set -euo pipefail
KIT=/data/medqc/app-upgrade-c3c657076-r2/medqc-app-upgrade
sudo /data/medqc/business/venv/bin/python -B "$KIT/safe_switch.py" rollback \
  --root /data/medqc/business \
  --expected-old /data/medqc/business/releases/medqc-web-customer-20261110-235900 \
  --execute --allow-readonly-db
```

即使新API无法启动也能执行：不依赖存活的新PID，而是校验root私有证明、当前unit和同一配置，然后用已证明可重建的环境重新只读检查064。恢复原目录前后均核对原文件哈希；恢复后核对后端e1、前端697。若停服务后尚未切链接也可恢复已验证旧服务。无有效证明、配置/unit变化、未知current或旧文件变动就停止，不强制恢复。

原目录保留所有旧补丁；业务064、历史结果、旧冻结、快照不回退或删除。新key/settings.json保留在外部目录。旧应用不识别新端点管理文件，回滚后使用原部署配置，恢复质控前需另行确认；不自动调用模型。

## 5. 上线只读联验与限制

获准后浏览器核对当前文书、终末抽屉、病历池时间、数据管理、超级管理员端点抽屉与普通账号拒绝。不开模型测试、不保存真实端点、不创建质控/同步/Bundle任务。

本轮本机隔离环境为Ubuntu24.04/Python3.12。目标Ubuntu22.04/Python3.10全应用启动没有执行，linux_final_package_smoke继续标not_executed，不伪造PASS；check_compat在现场强制精确环境检查，不能跳过。没有新增迁移；064不符就阻断。
