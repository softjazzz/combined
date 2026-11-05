# fa314c6c2 精简Linux升级与百炼代理

应用固定为 fa314c6c251fc5dd02eda96a7d30d70642cc1eb0。工具提交另记PACKAGE.json，不伪装业务版本。本包适用Ubuntu22.04 x86_64、Python3.10和已验收的062业务库，复用原venv、PG16工具；不带依赖，不执行迁移或导入1026。

**本次交付的部署配置默认启用代理**：`http://192.168.118.99:18090`，精确目标 `dashscope.aliyuncs.com`。源码空配置仍关闭，解包和暂存不修改现场；必须显式执行apply_proxy步骤才会在既有安装生效。只改两个代理键，不选择模型、不设置Key、不授权推理。代理失败不直连兜底。

## 给DSH的可复制指令

请在已批准的维护窗口执行。先确认没有运行中质控、Worker或自动任务，发现存在则停止并报告，不直接打断或恢复历史任务。不得修改同步三库、同步/模型服务、PG容器、DNS、路由或防火墙。

将tar.gz及同名.sha256放入新的`/data/medqc/app-upgrade-fa314c6c2/`，保证medqc-business可读取，保留旧release。

### 1. 校验和兼容检查（不停止服务）

```bash
set -euo pipefail
ROOT=/data/medqc/business
DELIVERY=/data/medqc/app-upgrade-fa314c6c2
cd "$DELIVERY"
sha256sum -c MedQC-Ubuntu22-Python310-app-upgrade-fa314c6c2.tar.gz.sha256
test ! -e medqc-app-upgrade
tar --no-same-owner -xzf MedQC-Ubuntu22-Python310-app-upgrade-fa314c6c2.tar.gz
KIT="$DELIVERY/medqc-app-upgrade"
(cd "$KIT" && sha256sum -c --quiet SHA256SUMS)
cat "$KIT/BUILD.json" "$KIT/PACKAGE.json"
sudo -H -u medqc-business env -C "$DELIVERY" "$ROOT/venv/bin/python" -B "$KIT/check_compat.py" --root "$ROOT"
```

检查已有150项依赖版本、pip check和第三方原生模块，不读取business.env、不连接库或模型。失败则停止，不自行安装或改锁。DSH另按现有权限只读确认Alembic062、历史导入三列和1026正常。本次没有新迁移，不执行migrate/stamp/导入或质控。

### 2. 停业务前后端并暂存

```bash
OLD_APP=$(readlink -f "$ROOT/current")
OLD_VENV=$(readlink -f "$ROOT/venv")
sudo systemctl stop medqc-business-web medqc-business-api
sudo -H -u medqc-business env -C "$DELIVERY" "$ROOT/venv/bin/python" -B "$KIT/stage_upgrade.py" --root "$ROOT" --expected-current "$OLD_APP"
```

核对输出receipt中的previous_current、staged_current和unchanged_venv。暂存不切current、不改配置；目标重复或依赖不符拒绝覆盖，保留异常现场。

### 3. 显式应用启用代理的部署配置

```bash
sudo -H -u medqc-business env -C "$DELIVERY" "$ROOT/venv/bin/python" -B "$KIT/apply_proxy.py" --env-file "$ROOT/config/business.env" --backup-dir "$ROOT/backups"
```

记录返回的backup完整路径，不打印配置正文。脚本先做0600备份，再原子更新LLM_HTTP_PROXY和LLM_HTTP_PROXY_HOSTS；重复键等异常停止。保留原账号、Key、激活、CDM、RabbitMQ、快照及自动任务配置，不自动启用任何任务。不得复用此前暴露的Key。

当前流程面向既有Direct部署。**若现场是Gateway模式，先报告实际Gateway配置文件和进程**：相同两项必须配置到真正发送Provider HTTP的Gateway环境并重启；只改业务business.env不能宣称Gateway代理已生效。本包不擅自定位或修改其他进程配置。

### 4. 切换与零模型验收

保持同一个Shell中的ROOT/KIT/OLD_APP/OLD_VENV。从receipt读取NEW_APP，从第3步读取PROXY_BACKUP，替换下方两个占位路径：

```bash
NEW_APP=/data/medqc/business/releases/实际build_id
PROXY_BACKUP=/data/medqc/business/backups/实际business.env.before-proxy文件名
case "$NEW_APP" in "$ROOT"/releases/*) ;; *) exit 1;; esac
test "$(readlink -f "$ROOT/current")" = "$OLD_APP"
test "$(readlink -f "$ROOT/venv")" = "$OLD_VENV"
sudo -H -u medqc-business env -C "$DELIVERY" "$ROOT/venv/bin/python" -B "$KIT/probe_proxy.py" --backend "$NEW_APP/backend" --env-file "$ROOT/config/business.env"
sudo -u medqc-business ln -sfn "$NEW_APP" "$ROOT/current"
sudo systemctl start medqc-business-api medqc-business-web
curl --fail http://127.0.0.1:8001/api/v1/runtime-build
curl --fail http://127.0.0.1/api/v1/runtime-build
curl --fail http://127.0.0.1/workstation-v5/login >/dev/null
test "$(readlink -f "$ROOT/venv")" = "$OLD_VENV"
```

Runtime的Commit必须为完整fa314c6c2，Build与BUILD.json相同；80/8001保持原端口。probe要求ok=true、bailian_route=proxy、network_calls=0、model_calls=0，仅证明实际配置与路由，不证明实网连通。

保留现有QC_CASE_MATERIAL_DIR及其内容，不清空历史快照；PDF副本不新增快照。若快照目录此前未配置，先报告，另行确认持久目录；不要让升级临时目录冒充历史存储。

经过授权登录后，只读查看1026与历史结果，不点击模型测试、质控、同步或保存配置，不开启CDM/MQ/模型和自动任务。不要恢复历史任务。

### 5. 实网验收边界

DSH已有CONNECT/TLS及虚构请求证明，本次无需重复真实调用。回报包校验、依赖、probe、runtime、页面及其他服务状态即可。本次不发送付费请求或患者材料。

后续另获授权时，才可用持有人轮换后的安全Key和虚构材料，在固定调用点做一次真实请求、禁止隐藏重试，记录路由、HTTP状态、Token和耗时；请求前明确模型与预算。不能自动执行或记作本次已验收。

### 6. 失败回滚：恢复配置并回切应用

OLD_APP/OLD_VENV必须来自receipt，PROXY_BACKUP必须是本次脚本输出。不要猜测路径，不删除release。

```bash
sudo systemctl stop medqc-business-web medqc-business-api
case "$OLD_APP" in "$ROOT"/releases/*) ;; *) exit 1;; esac
case "$PROXY_BACKUP" in "$ROOT"/backups/business.env.before-proxy-*) ;; *) exit 1;; esac
test "$(readlink -f "$ROOT/venv")" = "$OLD_VENV"
sudo -u medqc-business test -d "$OLD_APP"
sudo -u medqc-business test -f "$PROXY_BACKUP"
sudo -u medqc-business cp -- "$PROXY_BACKUP" "$ROOT/config/business.env"
sudo -u medqc-business chmod 600 "$ROOT/config/business.env"
sudo -u medqc-business ln -sfn "$OLD_APP" "$ROOT/current"
sudo systemctl start medqc-business-api medqc-business-web
curl --fail http://127.0.0.1/api/v1/runtime-build
```

不downgrade、不删材料/快照、不恢复dump覆盖结果，不修改venv。若升级后另改过配置或运行过任务，先核对兼容性，不用旧备份覆盖新增配置。

## 验收限制

字段映射OpenAI SDK、意图路由独立HTTPX和ICD嵌入requests旁路未覆盖。名单缺失或损坏时保守拒绝云端和普通域名，明确不受影响的本地字面地址可用。

本包无真实Key、患者材料或新依赖。真实代理容量、医学质量、院内权限、发布窗口和完整病历吞吐未验收。Ubuntu断网验证和现场正式链验收需分别记录。
