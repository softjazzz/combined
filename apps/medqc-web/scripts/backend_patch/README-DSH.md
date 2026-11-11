# DSH：东华病历详情只读查看后端修复

补丁 backend-emr-6cd06ff77；基础后端 e1f65ffe73f121842dfa997c41d1c9c517bd804e。
仅替换 backend/app/routers/emr_render.py，复用原依赖，不迁移数据库、不改配置、不切current、不改前端。
现有 eb2fbb4ca 前端补丁保留。runtime-build 继续报告基础版本；补丁身份由 PATCH.json、目标文件哈希和安装receipt证明，不能把它宣称为整个后端切到6cd06ff77。

## 1. 收包与只读检查（不停止服务）

上传 tar.gz 及同名.sha256到 `/data/medqc/backend-fix-6cd06ff77`，然后复制执行：

```bash
set -euo pipefail
cd /data/medqc/backend-fix-6cd06ff77
sha256sum -c MedQC-backend-emr-fix-6cd06ff77.tar.gz.sha256
test ! -e medqc-backend-emr-fix
test ! -L medqc-backend-emr-fix
tar -xzf MedQC-backend-emr-fix-6cd06ff77.tar.gz
cd medqc-backend-emr-fix
sha256sum -c SHA256SUMS
sudo -H -u medqc-business /data/medqc/business/venv/bin/python -B manage.py check \
  --root /data/medqc/business \
  --expected-current /data/medqc/business/releases/medqc-web-customer-20261110-235900
sudo systemctl is-active medqc-business-api medqc-business-web
curl -fsS http://127.0.0.1:8001/api/v1/runtime-build
curl -fsS http://127.0.0.1/build-info.json
```

如果校验失败、发现已有补丁文件、current改变或服务身份与既有部署不符，停止并报告，不删除备份、不改校验条件。
安装前按既有管理途径确认没有活动任务；本补丁不提供绕过认证的查询脚本，也不读取.env。不要以“列表可以读”代替活动任务检查。

## 2. 安装（需取得本次服务器部署授权）

本次“制作修复包”不等于部署授权。获准后，仅停API；Web与同步服务保持原状态。下列块安装失败会尝试重新启动API，但不会擅自覆盖现场变更。

```bash
set -euo pipefail
KIT=/data/medqc/backend-fix-6cd06ff77/medqc-backend-emr-fix
EXPECTED=/data/medqc/business/releases/medqc-web-customer-20261110-235900
sudo -H -u medqc-business /data/medqc/business/venv/bin/python -B "$KIT/manage.py" check \
  --root /data/medqc/business --expected-current "$EXPECTED"
sudo systemctl stop medqc-business-api
if sudo systemctl is-active --quiet medqc-business-api; then
  echo 'API仍在运行，停止安装'; exit 1
fi
trap 'sudo systemctl start medqc-business-api' EXIT
sudo -H -u medqc-business /data/medqc/business/venv/bin/python -B "$KIT/manage.py" apply \
  --root /data/medqc/business --expected-current "$EXPECTED"
sudo systemctl start medqc-business-api
trap - EXIT
sudo systemctl is-active medqc-business-api medqc-business-web
curl --retry 10 --retry-delay 1 --retry-connrefused -fsS http://127.0.0.1:8001/api/v1/runtime-build
curl -fsS http://127.0.0.1/build-info.json
sudo -H -u medqc-business cat "$EXPECTED/backend/backend-emr-6cd06ff77.json"
sudo -H -u medqc-business sha256sum "$EXPECTED/backend/app/routers/emr_render.py"
```

最后的哈希必须等于PATCH.json的after_sha256。runtime-build仍为e1f65ffe7，前端build-info仍为eb2fbb4ca。API健康检查只证明启动，不证明文书阅读通过。

## 3. 实际查看联验（只读；不得点击质控、同步或模型测试）

在浏览器正常登录，刷新病历池，选同一份明确有文书的东华病例，点击“查看”。核对列表与详情的三坐标属于同一病例。

- Network中实际核对 `/api/v1/emr/{visit}/documents?view=summary`，不是只核对 `/api/medical-records/documents`。
- 入院优先请求及后续完整目录请求成功；有文书的病例目录不为空。
- 点击一份文书，核对 `/api/v1/emr/{visit}/render` 返回的content或render_blocks与所选文书一致，页面正文可见。
- 切换另一份文书及另一病例，不混入上一病例内容。
- 当前不存在的文书不可借别的正文显示；实际无文书的病例仍可为空，不能保证871份都有材料。
- 错误只记录状态码、脱敏detail、traceId、数量和耗时；不要在聊天粘贴正文、账号令牌或患者身份。
- 助手 `/api/v1/qc-agent/business/access` 503不在本包范围内，不修改其授权配置。
- 不启动质控以生成Bundle。当前查看即使没有Bundle也应可读，不能用新增任务掩盖问题。

保留1026的27/15/27与20个历史任务基线，不新增任务、不启用调度或RabbitMQ。仅在已获准的只读核对范围内检查，不为验收额外扩大数据库访问。

## 4. 回滚（本补丁安装后的恢复；需要有对应receipt及原文件备份）

若启动失败，或实际阅读新增阻断，按受控部署回滚授权执行。仍只停API，不回滚前端、不downgrade数据库。

```bash
set -euo pipefail
KIT=/data/medqc/backend-fix-6cd06ff77/medqc-backend-emr-fix
EXPECTED=/data/medqc/business/releases/medqc-web-customer-20261110-235900
sudo systemctl stop medqc-business-api
if sudo systemctl is-active --quiet medqc-business-api; then exit 1; fi
trap 'sudo systemctl start medqc-business-api' EXIT
sudo -H -u medqc-business /data/medqc/business/venv/bin/python -B "$KIT/manage.py" rollback \
  --root /data/medqc/business --expected-current "$EXPECTED"
sudo systemctl start medqc-business-api
trap - EXIT
sudo systemctl is-active medqc-business-api medqc-business-web
curl --retry 10 --retry-delay 1 --retry-connrefused -fsS http://127.0.0.1:8001/api/v1/runtime-build
```

原文件备份保留为 `emr_render.py.before-backend-emr-6cd06ff77`；安装与回滚receipt均保留。发现文件被其他人修改时工具拒绝回滚，不手工强覆盖。

## 验证边界

见VALIDATION.json及VALIDATION-REPORT.md。开发侧不接触服务器、业务库或模型；本包不包含密码、DSN、.env、患者材料。Ubuntu24.04/Python3.12隔离替换回滚并不等于服务器Ubuntu22.04/Python3.10完整应用启动验收，现场必须完成上面的启动和真实浏览器只读联验。
