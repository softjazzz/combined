# 统一升级包：演示反馈改用业务PG（未执行现场操作）

本包包含160155b15统一功能，并新增演示反馈PG存储。正式医生申诉、整改、沟通及反馈表不改。
保留 `/api/v1/demo/feedbacks` 及列表、统计、导出、删除接口；不创建第二套临床数据源。

## 变更与回滚边界

- 业务库 medqc_business：显式迁移064→`20261112_000065`，只新增 `qc.demo_feedbacks`、`qc.demo_feedback_imports` 和索引。
- 不涉及同步/CDM库的迁移编号。没有自动启动迁移，不允许stamp/downgrade。
- 原release和 `backend/data/demo_feedbacks.db`（及存在的WAL/SHM）原样保留。停API/Web后逐字备份到state，再对副本做SQLite一致性快照。
- 迁移和首次导入属于同一个PG事务：失败整体回滚。重复导入跳过已有台账，不覆盖后来修改、不恢复后来删除的反馈；冲突整批拒绝。
- 迁移前先生成“旧现场程序+4个PG兼容文件”的独立回滚release。回滚仍读PG，升级期间新增反馈保留。原SQLite不接收新写入。
- **065成功后严禁直接把current切回原始旧release**，它只读SQLite且要求064。只能使用本包兼容回滚入口。
- 兼容回滚前后端版本接口保留旧现场标识；额外兼容覆盖由root私有receipt和完整文件清单证明，不声称旧release字节不变。
- 配置、现有venv、快照、旧冻结及历史结果均保留；后台启动、恢复、监视器和日调度继续关闭。

## 1. 收包及自动检查（不需要SHA侧车或人工核对）

把tar.gz上传到全新目录。下面仅设置本次收包路径；如与现场不同，替换第一行。

```bash
set -euo pipefail
INBOX=/data/medqc/feedback-pg-upgrade
ROOT=/data/medqc/business
OLD="$ROOT/releases/medqc-web-customer-20261110-235900"
cd "$INBOX"
mapfile -t archives < <(find . -maxdepth 1 -type f -name 'MedQC-Linux-app-upgrade-*.tar.gz')
test "${#archives[@]}" -eq 1
test ! -e medqc-app-upgrade
test ! -L medqc-app-upgrade
tar --no-same-owner -xzf "${archives[0]}"
KIT="$INBOX/medqc-app-upgrade"
sudo chown -R root:root "$KIT"
sudo chmod -R a+rX,go-w "$KIT"
sudo -H -u medqc-business "$ROOT/venv/bin/python" -B "$KIT/check_compat.py" --root "$ROOT"
```

工具自动验证包内完整性、版本、依赖，不安装依赖。任何失败停止。不要调用旧版release_guard去删除反馈SQLite；本包专用入口只接受这一个已知库及其WAL/SHM，其他未知文件仍拒绝。

## 2. 切换前预检（另需允许业务库只读检查）

```bash
sudo "$ROOT/venv/bin/python" -B "$KIT/feedback_upgrade.py" preflight \
  --root "$ROOT" --expected-old "$OLD" --allow-readonly-db
```

此步骤不迁移、不导入、不暂存、不切换、不停服。自动核对现场补丁字节、同一配置来源、实际运行环境、关闭开关、持久目录、064及必要业务结构。
输出ok=true后才具备申请维护条件；不代表现场已升级。

## 3. 维护实施（只有明确授权停服、迁移和导入后执行）

确认没有活动质控任务；保留现有业务库备份，备份凭据不放命令行或报告。确认可用维护身份、磁盘空间和本包回滚工具。

```bash
sudo "$ROOT/venv/bin/python" -B "$KIT/feedback_upgrade.py" apply \
  --root "$ROOT" --expected-old "$OLD" --allow-readonly-db \
  --execute --allow-feedback-migration
```

顺序：再次预检→暂存新release及兼容回滚release→写私有维护receipt→停Web/API→备份原SQLite及WAL/SHM→只在副本上生成一致快照→065和导入单事务→065只读结构复验→切换→启动→HTTP版本验证。
只迁移演示反馈；不调用模型、质控、Bundle、CDM或同步。快照及备份目录含反馈内容，保持0700，不打包回传。

## 4. 失败处理及兼容回滚

任何异常均停止，不强行重跑apply、不删除receipt或重建目标目录。工具可能故意保持服务停止。

- 若迁移事务明确回滚且只读证实仍为064、current仍是原release，可由运维按原配置重启旧服务。连接中断造成提交结果未知时，必须先只读核对revision，不能猜测。
- 若已是065，即使尚未切换或新版启动失败，也使用下面的兼容回滚。绝不恢复旧业务库dump覆盖新结果。

```bash
sudo "$ROOT/venv/bin/python" -B "$KIT/feedback_upgrade.py" rollback \
  --root "$ROOT" --expected-old "$OLD" --allow-readonly-db --execute
```

该入口核对root私有receipt、配置和unit不变、完整回滚文件、065结构后，停服并切至兼容旧程序。PG表及所有新增反馈继续保留，不降库、不删除列、不回写SQLite。
若需要重新升级，先提交本次状态和失败码形成恢复计划，不擅自删除暂存目录重新执行。

## 5. 联验与报告

1. runtime-build和build-info应与包内BUILD一致；兼容回滚时应为旧现场标识并具有对应私有receipt。
2. 只读核对演示反馈旧记录数量/字段；如另外授权提交合成反馈，确认新增、统计、导出，再通过兼容回滚确认同一ID仍可见。不把真实患者正文放日志。
3. 正式医生反馈流程保持原样；1026、结果信封、历史材料及冻结不重算。
4. 报告迁移revision、导入inserted/skipped/total、原库保留、当前路径、服务状态和未验收项。不要输出密码、DSN、配置正文或反馈正文。

开发侧验证见VALIDATION.md和evidence附件。隔离PG版本及Linux版本与现场差异须保留，不以固定替身冒充现场完整启动验收。
