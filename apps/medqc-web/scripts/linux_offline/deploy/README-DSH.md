# DSH：Ubuntu22 / Python310 / PG16 完整离线部署

本包为独立业务应用及依赖，不附患者数据、口令、JWT、激活码、私钥或模型。此前1026加密包仍单独使用。本次仅连接新建medqc_business，独立CDM接入尚未完成。不可将DATABASE_URL改为medqc_sync_cdm。

## 1. 核对交付文件及前置条件

将tar.gz及外部sha256文件传到服务器，以下示例假定在/data/medqc/offline-install。运行账号guohua可创建该目录；不使用根分区放材料。管理员确认时钟处理方案及80/8001空闲；不直接修改仍在运行的同步/模型服务的时间、配置或进程。

```bash
set -euo pipefail
cd /data/medqc/offline-install
sha256sum -c MedQC-Ubuntu22-Python310-PG16-offline.tar.gz.sha256
tar --no-same-owner -xzf MedQC-Ubuntu22-Python310-PG16-offline.tar.gz
export KIT=/data/medqc/offline-install/medqc-offline
(cd "$KIT" && sha256sum --check --quiet SHA256SUMS)
cat "$KIT/BUILD.json" "$KIT/VALIDATION.json"
ss -ltn | grep -E ':(80|8001)\b' || true
```

若80或8001已有监听，先报告，不停止其进程。确认服务器是Ubuntu22.04/x86_64，python3.10可用。不需要Docker来运行质控应用，不执行apt/pip联网，不复用同步/模型venv。

## 2. 管理员创建独立系统账号与业务目录

```bash
getent passwd medqc-business || sudo useradd --system --user-group \
  --home-dir /data/medqc/business --no-create-home --shell /usr/sbin/nologin medqc-business
sudo install -d -o medqc-business -g medqc-business -m 0750 /data/medqc/business
sudo -u medqc-business env MEDQC_INSTALL_ROOT=/data/medqc/business \
  MEDQC_PYTHON=/usr/bin/python3.10 bash "$KIT/deploy/install.sh"
```

install.sh会离线建立新venv、pip check、复制新版本并建立current/venv符号链接。兼容服务器ensurepip缺失，不接触系统Python包。不会创建数据库、启动服务或自动迁移；如出现失败保留日志，不能强行跳过依赖校验。

## 3. 由Docker管理员创建新业务库和专用账号

仅管理员进入已确认的medqc-postgres16，不涉及已停止的Dify PG15容器：

```bash
sudo docker exec -it medqc-postgres16 psql -U postgres -d postgres
```

在psql内执行（如对象已存在，先核对归属，不删除或重置）：

```sql
CREATE ROLE medqc_business_app LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION;
\password medqc_business_app
CREATE DATABASE medqc_business OWNER medqc_business_app ENCODING 'UTF8';
REVOKE CONNECT ON DATABASE medqc_business FROM PUBLIC;
GRANT CONNECT ON DATABASE medqc_business TO medqc_business_app;
\q
```

\password会现场提示输入，密码不进入命令行或聊天。不要修改三个medqc_sync_*库的角色、表、权限、迁移号或数据，也不调整PG容器配置/重启服务。

## 4. 配置并初始化业务库

```bash
sudo -u medqc-business /data/medqc/business/venv/bin/python \
  "$KIT/deploy/configure.py" --host-ip 192.168.140.177
sudo -u medqc-business /data/medqc/business/venv/bin/python \
  "$KIT/deploy/db-admin.py" migrate
sudo -u medqc-business /data/medqc/business/venv/bin/python \
  "$KIT/deploy/db-admin.py" create-admin --username poc_tester
sudo -u medqc-business /data/medqc/business/venv/bin/python \
  "$KIT/deploy/db-admin.py" check
```

configure.py交互接收新业务库密码并生成独立JWT，保存600权限配置；不打印凭据。migrate先执行PG16完整备份及目录校验。对全新空库，它显式初始化历史迁移依赖的sync_job_state、visit_index和既有任务owner，再实际执行Alembic迁移到062，最后初始化既有运行时样本元数据与11张Bundle表。任务owner包含历史三列execution_mode/draft_ids_json/rule_count及源库已核实默认值batch/[]/1。已到062的31列空表可定向补齐，job_kind按导出结构允许空；非空表需要补列或改可空性时拒绝自动处理。五个任务JSON列继续允许NULL表示尚无结果，不复制旧库更严的约束。前置和Bundle模板只有结构，没有患者行；其他同名结构不一致即停止，不覆盖。不会stamp或连接同步库。create-admin只新增显式账号，密码现场输入两次；已有同名账号会拒绝，不重置或提升现有用户。

默认ENV=production、正常启动模式，但MEDQC_STARTUP_BACKGROUND_ENABLED=false。它只读检查必要业务结构，跳过启动DDL、预热和历史恢复；不是依赖可选规则验证表的acceptance模式。手动业务入口保留，初次验收不要点击质控/同步。生产环境不加载内存演示账号，也不向缓存账号回退，原有默认账号保护仍保留。

## 5. 导入1026（材料包独立传输）

将原加密7z放入批准的数据目录。使用随包工具解压，提示时输入口令，不将口令写进命令行：

```bash
umask 077
"$KIT/tools/7zip/7z" x /data/medqc/approved-input/MedQC-1026-materials-results.7z \
  -o/data/medqc/approved-input/1026
```

由管理员把这个专用解压目录归属medqc-business并限制访问；不得对/data/medqc或其他服务目录递归改权限。以下DataPath以实际解压后manifest所在目录为准：

```bash
export DATA_PATH=/data/medqc/approved-input/1026/data-private
sudo -u medqc-business /data/medqc/business/venv/bin/python "$KIT/deploy/sample_set_transfer.py" \
  check --env-file /data/medqc/business/config/business.env --package "$DATA_PATH" --owner-username poc_tester
# Check通过且确认业务应用/Worker尚未启动，再Import；工具会另做备份。
sudo -u medqc-business /data/medqc/business/venv/bin/python "$KIT/deploy/sample_set_transfer.py" \
  import --env-file /data/medqc/business/config/business.env --package "$DATA_PATH" --owner-username poc_tester \
  --pg-bin /data/medqc/business/tools/pg16 --backup-dir /data/medqc/business/backups --maintenance-confirmed
sudo -u medqc-business /data/medqc/business/venv/bin/python "$KIT/deploy/sample_set_transfer.py" \
  verify --env-file /data/medqc/business/config/business.env --package "$DATA_PATH" --owner-username poc_tester
```

每条命令必须独立确认退出码0再继续。脚本包含v2大JSON优化及逐表进度，不用旧超时副本。应得到27份、39145行、20任务、15Envelope、1140历史条目、99表verified=true。保留历史10完整/11部分/6当前无结果，不补跑。

结构检查按列名匹配，物理列顺序不同可以通过；缺列、多列、类型、主键及普通可空性差异仍拒绝。仅qc.custom_qc_batch_jobs的summary_json/items_json/failed_records_json/child_job_ids_json/child_summary_json允许“旧包非空、目标可空”，同时逐行核对旧包要求的非空值；不能利用此兼容丢失旧结果。所有写入仍使用PG目标类型转换与完整行比较，不裁剪JSON、不跳过Check。遇非空旧任务表的结构问题，停止报告，不删表重建。

## 6. 安装并启动业务专属systemd单元

```bash
sudo bash "$KIT/deploy/install-services.sh"
sudo systemctl start medqc-business-api.service
curl --fail http://127.0.0.1:8001/api/v1/runtime-build
sudo systemctl start medqc-business-web.service
curl --fail http://127.0.0.1/api/v1/runtime-build
curl --fail http://127.0.0.1/workstation-v5/login >/dev/null
sudo systemctl status medqc-business-api.service medqc-business-web.service --no-pager
```

安装脚本只安装本项目两个单元，不修改既有单元，不自动启动或enable。前端由独立低权限账号绑定80（仅CAP_NET_BIND_SERVICE），后端仅回环8001。80如已被使用就拒绝，不抢占、不停止Dify/其他服务。先用院内浏览器访问http://192.168.140.177并核对防火墙实际允许范围，不关闭整个防火墙。

使用poc_tester登录，按发行方确认的授权范围在产品激活页导入有效激活码；本包不签发新授权、不改公钥、不关闭验证。当前协议无机器绑定字段，能否沿用现有trial仍由发行方确认；记录到期日。先保持模型配置不启用、RabbitMQ关闭、无定时/恢复任务。

确认前后端Commit和Build ID与BUILD.json一致；查看1026的材料、时间、去重及历史结果，其他同步和模型服务状态与部署前一致。全部通过后，管理员才按需要执行：

```bash
sudo systemctl enable medqc-business-api.service medqc-business-web.service
```

## 7. 回滚与日志

```bash
sudo systemctl stop medqc-business-web.service medqc-business-api.service
sudo systemctl disable medqc-business-web.service medqc-business-api.service
sudo journalctl -u medqc-business-api.service -u medqc-business-web.service --since today --no-pager
```

仅停止新业务服务，保留业务库、备份、日志、原始1026包。不要删库、downgrade或盲目恢复覆盖；需要恢复数据库时，由管理员核对备份和目标库，仅对medqc_business操作。不恢复Dify、不重启Docker或现有PG。下一版升级须保留旧current/venv目标后再切换，不能覆盖旧目录。

## 验证边界

本包在GitHub独立Ubuntu22/Python310环境构建，断网命名空间中安装和合成PG16迁移/启动检查；具体结果以VALIDATION.json及日志为准。没有连接医院服务器、同步CDM或模型，没有运行真实病历或模型质量验收。PG客户端随包独立携带，不升级医院PG16.13。

不附Node业务助手、ICD语义向量、模型或医院数据；可选业务助手、服务器中文PDF字体及实际80端口/systemd/防火墙/激活/院内页面仍由现场确认。独立CDM读取及普通医院病例发现暂未接入，本阶段不能靠改连接串启用。

PG16构建来源：https://www.postgresql.org/download/linux/ubuntu/ 。仅构建机在线使用官方签名源，医院安装阶段不访问该源。
