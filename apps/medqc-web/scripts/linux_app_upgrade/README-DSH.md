# 业务线适配说明（2026-11-06）

本目录合入PR #37的精简升级工具，不合入其过期双源应用/测试DDL，不构建或部署任何新包。下面原09f627a0e/062记录仅保留历史复现，**不能用于当前业务线服务器升级**；当前版本须使用新发行说明的应用Commit、Build、数据库迁移要求与只读预检，不恢复双源切换。

生成器不再默认下载或提取旧09f627a0e。必须同时显式提供已验收完整包、发行方SHA256、该包BUILD.json的完整应用Commit；不一致拒绝。手动workflow同样要求source_run_id/source_sha256/application_commit，不能偷偷换最新Artifact。输出包PACKAGE.json的database_migrations_required为null（尚需逐版本确认），不是承诺无需迁移；工具本身不连接库、不迁移、不启停或部署。定时新功能需要064，既有063刷新必须保留。

依赖检查复用源包精确版本锁，不自动安装。未通过当前发布环境的计量/身份/依赖/迁移验收，不得将工具自测当作交付包验收。本次未调用手动制包workflow。

## 当前候选的材料与迁移预检（2026-11-07）

`check_compat.py`仍不读取业务配置或连接数据库。`stage_upgrade.py`在复制前只读解析`business.env`的材料路径，复用部署已有`python-dotenv`，不导入应用；其插值和进程环境优先级与应用`load_dotenv`一致。有效目录按`QC_CASE_MATERIAL_DIR`优先，否则取`QC_DISPATCH_STATE_DIR`父目录下的`case-materials`。二者都未配置时，应用回退到当前release的`backend/data/case-materials`，暂存器拒绝继续。相对路径、任何release或`current`及其符号链接别名中的路径均拒绝；尚未首次创建的持久目录允许通过。输出和回滚记录包含`material_storage_dir`及来源，不输出代理地址、凭据或其他配置。

兼容检查与暂存必须沿用已安装业务venv中的`/data/medqc/business/venv/bin/python -B`，不能替换为系统`python3`。当前业务依赖已固定`python-dotenv==1.0.0`；缺失时停止并返回`existing_business_venv_python_dotenv_required`，不现场安装依赖或忽略错误。`check_compat`另会先核对venv身份及源包精确依赖锁。

现场应另核对API、Worker及其服务环境实际使用同一目录。暂存命令的进程环境不等于systemd实际环境，此工具不读取systemd状态或证明服务权限。若旧材料已在release中，先停止交付并制定经批准的保留/迁移方案；不要直接新增路径变量让旧任务失去材料。暂存器不创建、搬迁或删除材料，也不覆盖`.env`、代理、模型、MQ或计划配置。代码回切必须保持同一持久目录并保留新旧材料、任务引用和历史结果，不以清空快照或数据库降级代替回滚。

当前源码迁移依赖为`20261102_000062 → 20261105_000063 → 20261106_000064`：063为Bundle刷新存储，064为每日计划与触发账本，计划默认关闭。现场真实Alembic版本与结构仍未知，必须逐版本确认；不得沿用下方历史062“无需迁移”口径。仅在另获批准的维护窗口使用现有`db-admin.py`备份并执行必要迁移，不自动迁移、不stamp、不downgrade、不重新导入1026。代码回退前先确认旧版能读取升级后结构，保留新增表和数据。

本轮仅准备预检，未制包、安装依赖、操作服务或访问数据库/模型。候选来源、定向检查及现场未验收项见归档（`git show archive/docs-pre-cleanup-202611:apps/medqc-web/docs/plans/2026-11-07-closeout-linux-preflight.md`）；下方历史操作示例不能直接用于当前版本。

```text
python -B apps/medqc-web/scripts/linux_app_upgrade/make_package.py --source <已验收完整tar.gz> --source-sha256 <发行方64位SHA256> --application-commit <该包40位应用Commit> --output <全新目录>
```

原PR #37历史包、Ubuntu11项隔离及依赖复用冒烟结果属于原固定应用，不能替代当前业务线应用验收。新版本仍需独立说明迁移、发布窗口及回退，不通过downgrade删历史表。

---

# Linux精简应用升级包：复用已有依赖

应用来自已验证的完整包，文件逐字节一致，未重新编译。业务基线998f7ac94，实际应用Commit **09f627a0e19380d5a605302cc0058482a7c2682f**，Build **medqc-web-customer-20261104-235302**。PACKAGE.json中的packaging_commit仅是升级工具版本，不是应用runtime Commit。

本包不带wheelhouse、Python、PG客户端或7zip，不运行pip install，不新建venv、不更新已有工具或systemd。适用已有完整安装的Ubuntu22.04/x86_64、Python3.10、062业务库服务器。没有安装依赖的新服务器应使用完整离线包。

## 1. 收包及兼容检查（不停止服务，不连接数据库）

将tar.gz和同名.sha256放在新目录`/data/medqc/app-upgrade-09f627a0e`，不要覆盖旧安装目录。

```bash
set -euo pipefail
cd /data/medqc/app-upgrade-09f627a0e
sha256sum -c MedQC-Ubuntu22-Python310-app-upgrade-09f627a0e.tar.gz.sha256
test ! -e medqc-app-upgrade
tar --no-same-owner -xzf MedQC-Ubuntu22-Python310-app-upgrade-09f627a0e.tar.gz
export KIT=/data/medqc/app-upgrade-09f627a0e/medqc-app-upgrade
(cd "$KIT" && sha256sum --check --quiet SHA256SUMS)
cat "$KIT/BUILD.json" "$KIT/PACKAGE.json"
sudo -H -u medqc-business env -C /data/medqc/app-upgrade-09f627a0e \
  /data/medqc/business/venv/bin/python -B "$KIT/check_compat.py" --root /data/medqc/business
```

检查不读business.env、不导入app、不连接数据库或模型，只检查本包哈希、平台、现有venv、锁定的150项依赖版本、pip check和第三方二进制模块导入。要求与已验证依赖组合**版本一致**；这不是对任意满足宽松requirements版本的兼容性保证。差异列表只报告包名和版本，不自动安装、删包或放宽检查。失败就停止，交开发侧核对；不能改锁文件让检查通过。宿主Python具体补丁版本和已有原生库也由本检查确认，CI与医院环境不是同一台机器。

前置业务结构仍应由DSH按现有权限**只读**确认：Alembic为062，之前1026导入所需三列已补齐、现有1026正常。本次不运行migrate、stamp、导入或修表。若现场结构与此前验收不符，停止报告。仅凭依赖检查通过不表示数据库结构已通过。

如果当前runtime已经是上述Commit和Build，且应用文件一致，则无需重复升级；保留此包备用，不重复暂存同名release。

## 2. 暂存新版本（维护窗口获批后）

确认没有活动质控或业务Worker。保留原账号、密码、JWT、激活、1026材料/历史结果、CDM/MQ和定时设置；不重新建库、建账号、导入1026。不改同步三库或同步/模型服务。

```bash
set -euo pipefail
ROOT=/data/medqc/business
KIT=/data/medqc/app-upgrade-09f627a0e/medqc-app-upgrade
OLD_APP=$(readlink -f "$ROOT/current")
OLD_VENV=$(readlink -f "$ROOT/venv")
sudo systemctl stop medqc-business-web medqc-business-api
sudo -H -u medqc-business env -C /data/medqc/app-upgrade-09f627a0e \
  "$ROOT/venv/bin/python" -B "$KIT/stage_upgrade.py" --root "$ROOT" --expected-current "$OLD_APP"
```

脚本再次做兼容和校验检查，将应用复制到新release，创建指向原business.env的链接，写受限回滚记录。**不切换current、不改venv/业务配置、不启停服务、不读写数据库**。目标目录或回滚记录已存在、current变化、依赖不符均拒绝覆盖；保留异常现场，不自动删除半成品。

记录文件为`/data/medqc/business/state/app-upgrade-medqc-web-customer-20261104-235302.json`。核对previous_current、staged_current、unchanged_venv与刚才记录一致。目标程序仍默认原有源，CDM停用；但现有保存配置不会被覆盖，若旧配置已启用MQ/CDM/模型/后台，先报告，不擅自强制关闭或启用。

## 3. 切换与页面验收（需获批）

```bash
NEW_APP=/data/medqc/business/releases/medqc-web-customer-20261104-235302
sudo -u medqc-business test -f "$NEW_APP/backend/app/data/runtime_build.json"
test "$(readlink -f "$ROOT/current")" = "$OLD_APP"
test "$(readlink -f "$ROOT/venv")" = "$OLD_VENV"
sudo -u medqc-business ln -sfn "$NEW_APP" "$ROOT/current"
sudo systemctl start medqc-business-api medqc-business-web
curl --fail http://127.0.0.1:8001/api/v1/runtime-build
curl --fail http://127.0.0.1/api/v1/runtime-build
curl --fail http://127.0.0.1/workstation-v5/login >/dev/null
test "$(readlink -f "$ROOT/venv")" = "$OLD_VENV"
```

runtime Commit必须是09f627a0e，Build同上；前端继续80，API继续回环8001，不安装/改写服务单元、不enable服务。不在升级脚本中自动发送登录请求；获准登录后可只读查看原1026、文书和历史结果，以及系统设置中的双数据源入口。不得点击质控、同步、模型测试或保存配置，不开启自动任务；真实CDM启用/默认源切换仍需另行授权。

随包`deploy/cdm-preflight.py`与完整已验证包相同。如需CDM只读预检，使用已获准的专用只读账号和medqc-business所有、0600的pgpass，只查询目录/权限，不读患者行，不新建角色/授权。不得把DATABASE_URL改成CDM，不复制同步服务凭据。

## 4. 回滚（只回切应用）

从上面的回滚记录读取OLD_APP和OLD_VENV，**不要猜测“上一个版本”**；人工确认旧路径在business/releases、venvs内且存在。没有修改依赖或配置，不需要重装依赖、恢复venv或覆盖business.env。

```bash
sudo systemctl stop medqc-business-web medqc-business-api
case "$OLD_APP" in /data/medqc/business/releases/*) ;; *) exit 1;; esac
case "$OLD_VENV" in /data/medqc/business/venvs/*) ;; *) exit 1;; esac
test "$(readlink -f /data/medqc/business/venv)" = "$OLD_VENV"
sudo -u medqc-business test -d "$OLD_APP"
sudo -u medqc-business ln -sfn "$OLD_APP" /data/medqc/business/current
sudo systemctl start medqc-business-api medqc-business-web
curl --fail http://127.0.0.1/api/v1/runtime-build
```

不删新release、材料或数据库，不downgrade、不重新导入1026、不恢复dump覆盖现有结果。如果升级后另改过CDM/MQ配置或运行过新任务，应先核对旧版兼容性，不盲目回切。

## 验收边界

应用本体沿用完整包Ubuntu22/Python3.10/PG16.15断网、062迁移、双库68表结构和结果隔离验证。精简包另外验证不带依赖/工具、应用哈希不变、复用现有venv的依赖检查、仅暂存、人工切换及回切，不连接业务库、不调用模型、不执行质控。医院真实依赖/结构/权限、systemd和浏览器验收仍由DSH另行完成。只报告版本、哈希、依赖差异及服务/页面结果，不附JWT、口令、连接串或患者正文。
