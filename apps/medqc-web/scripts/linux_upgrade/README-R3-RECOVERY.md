# r3：稳定服务配置校验与失败暂存归档

应用仍为d36b44a00 / 20261112-034500，不重建应用。r2失败发生于迁移前，不能据此声称升级完成。

## 工具修复

ExecStart只剔除已识别的运行状态尾段（start_time、stop_time、pid、code、status），保留path、完整argv、ignore_errors；未知结构拒绝。停服前后仍比较User/Group/UMask、WorkingDirectory、Environment、钩子、EnvironmentFiles、DropInPaths、FragmentPath及配置哈希。不得仅跳过停服后的检查。

## 本次残留处理

不删除，不现场编辑旧receipt。新入口archive-failed默认只检查，--execute才归档。
同时核对原current、原服务active、064且两张反馈表不存在、旧补丁字节、配置和稳定unit相符、新版完整文件、兼容回滚完整文件、同一.env链接、尚无反馈备份目录。

归档四项到state/failed-feedback-<build>/：
1. 暂存新版release；
2. 兼容回滚release；
3. feedback-upgrade维护receipt；
4. stage_upgrade写出的app-upgrade暂存receipt（上一轮摘要未列，但正式stage会创建）。

归档不改原release、SQLite、配置、PG、current或服务。任何未知差异都停止。移动中断时保留PLAN.json和已移动对象，不自动续跑、不删除；需按计划只读核对实际位置再处理。

## DSH命令（新目录收包后执行）

不带SHA侧车；沿用主README第1节，但将INBOX改为/data/medqc/feedback-pg-upgrade-r3。
不要覆盖旧r2 kit。

```bash
set -euo pipefail
ROOT=/data/medqc/business
KIT=/data/medqc/feedback-pg-upgrade-r3/medqc-app-upgrade
OLD="$ROOT/releases/medqc-web-customer-20261110-235900"
sudo -H -u medqc-business "$ROOT/venv/bin/python" -B "$KIT/check_compat.py" --root "$ROOT"
sudo "$ROOT/venv/bin/python" -B "$KIT/feedback_upgrade.py" preflight \
  --root "$ROOT" --expected-old "$OLD" --allow-readonly-db
sudo "$ROOT/venv/bin/python" -B "$KIT/feedback_upgrade.py" archive-failed \
  --root "$ROOT" --expected-old "$OLD" --allow-readonly-db
```

先报告预检及archive_ready=true。原维护授权不等于可无视新失败；如有任何不符，不执行下一段。
在确认维护窗口、无活动任务、备份有效并获准归档保留及重试后：

```bash
sudo "$ROOT/venv/bin/python" -B "$KIT/feedback_upgrade.py" archive-failed \
  --root "$ROOT" --expected-old "$OLD" --allow-readonly-db --execute
sudo "$ROOT/venv/bin/python" -B "$KIT/feedback_upgrade.py" apply \
  --root "$ROOT" --expected-old "$OLD" --allow-readonly-db \
  --execute --allow-feedback-migration
```

归档后新的apply会生成新的暂存和receipt，原失败证据在归档内保留。不复用未经核对的旧暂存，不伪造迁移状态。
失败恢复仍按主README：明确064且current原版可恢复原服务；065只能用兼容回滚，不降库、不覆盖新增反馈。

禁止修改同步/CDM、启调度、调用模型、运行质控或重跑27份。现场前端、PG16及真实数据验收仍须报告实测，不以隔离替身结果代替。
