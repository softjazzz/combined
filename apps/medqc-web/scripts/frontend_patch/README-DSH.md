# DSH前端修复包 eb2fbb4ca

只适用于后端e1f65ffe73f121842dfa997c41d1c9c517bd804e、原前端medqc-web-customer-20261110-235900。
新前端eb2fbb4cac118888472657297bdbf2d8169a85f3 / medqc-web-customer-20261110-213000。

包含AI草稿来源保护、数据管理身份适配、真实统计提示及缺失字体引用修复。不包含助手授权503修复，不新增东华整表结构浏览能力。

前后端Commit不同是本次补丁的真实状态，页面版本组件可能提示版本不一致，不阻断业务。不要篡改后端版本字段消除提示。前端看/build-info.json；后端看/api/v1/runtime-build。

本包不含后端、依赖、密码或患者材料，不改数据库064、CDM配置、旧冻结或历史结果，不自动部署。安装修改现有release内frontend/dist；旧整套release清单不再描述当前前端，差量由PATCH.json和receipt记录，旧dist完整保留。

## 1. 收包和只读检查

将tar.gz及同名.sha256上传至/data/medqc/frontend-fix-eb2fbb4ca。本节只检查，不切换。

```bash
set -euo pipefail
cd /data/medqc/frontend-fix-eb2fbb4ca
sha256sum -c MedQC-frontend-fix-eb2fbb4ca.tar.gz.sha256
test ! -e medqc-frontend-fix
tar --no-same-owner -xzf MedQC-frontend-fix-eb2fbb4ca.tar.gz
(cd medqc-frontend-fix && sha256sum --check --quiet SHA256SUMS)
ROOT=/data/medqc/business
KIT=/data/medqc/frontend-fix-eb2fbb4ca/medqc-frontend-fix
EXPECTED=/data/medqc/business/releases/medqc-web-customer-20261110-235900
sudo -H -u medqc-business "$ROOT/venv/bin/python" -B "$KIT/manage.py" check --root "$ROOT" --expected-current "$EXPECTED"
sudo systemctl show medqc-business-web -p User -p WorkingDirectory -p ExecStart
```

预期ok:true。人工核对Web实际服务目录为EXPECTED/frontend/dist。身份不匹配、已有补丁/备份或校验失败立即停止，不删除目录或修改版本绕过。工具只用Python标准库，不读env、不连数据库。

## 2. 安装：另获部署授权后执行

只停Web，API保持运行。不更换current、venv，不改任何配置。

```bash
set -euo pipefail
ROOT=/data/medqc/business
KIT=/data/medqc/frontend-fix-eb2fbb4ca/medqc-frontend-fix
EXPECTED=/data/medqc/business/releases/medqc-web-customer-20261110-235900
sudo systemctl stop medqc-business-web
if sudo systemctl is-active --quiet medqc-business-web; then exit 1; fi
sudo -H -u medqc-business "$ROOT/venv/bin/python" -B "$KIT/manage.py" apply --root "$ROOT" --expected-current "$EXPECTED"
sudo systemctl start medqc-business-web
sudo systemctl is-active medqc-business-web
curl --fail --silent --show-error http://127.0.0.1/build-info.json
curl --fail --silent --show-error http://127.0.0.1/api/v1/runtime-build
curl --fail --silent --show-error http://127.0.0.1/workstation-v5/login >/dev/null
```

apply预期ok:true；前端身份为eb2fbb4ca/20261110-213000，后端仍e1f65ffe7。旧文件备份：EXPECTED/frontend/dist-before-frontend-eb2fbb4ca；receipt：EXPECTED/frontend/frontend-eb2fbb4ca.json。

apply失败或进程中断保持Web停止，记录目录及错误，不清理receipt、不重复apply。若apply成功而新Web启动失败，可用第3节回滚。

浏览器强制刷新或无痕窗口核对：东华病例不再请求AI草稿；数据管理无undefined路径、SQLite或40+/12+估算值；实际首页/文书可读。整表浏览明确提示未开放。助手access503仍需独立诊断，不宣称本包修复。

不点击质控、同步、补跑、模型测试，不改变调度/MQ/自启。真实正文若仍空，记录对应接口错误；不能把草稿422消失等同全部功能通过。

## 3. 回滚：仅本次apply成功后

```bash
set -euo pipefail
ROOT=/data/medqc/business
KIT=/data/medqc/frontend-fix-eb2fbb4ca/medqc-frontend-fix
EXPECTED=/data/medqc/business/releases/medqc-web-customer-20261110-235900
sudo systemctl stop medqc-business-web
if sudo systemctl is-active --quiet medqc-business-web; then exit 1; fi
sudo -H -u medqc-business "$ROOT/venv/bin/python" -B "$KIT/manage.py" rollback --root "$ROOT" --expected-current "$EXPECTED"
sudo systemctl start medqc-business-web
sudo systemctl is-active medqc-business-web
curl --fail --silent --show-error http://127.0.0.1/build-info.json
```

回滚核对当前文件及旧备份未变，恢复原前端e1f65ffe7/20261110-235900。补丁文件保留为dist-rolled-back-frontend-eb2fbb4ca。不恢复数据库、不覆盖任何结果。回滚后不直接重复apply；重装需开发核实新交付方案。

## 验证边界

前端Windows Node24.15构建；替换、静态服务和回滚使用本机WSL Ubuntu24.04/Python3.12，结果见外置报告。服务器Ubuntu22.04/Python3.10，本轮没有验证该精确组合。静态HTTP启动不等于真实浏览器完整交互验收。

未部署、未启动业务后端、未连接既有业务库、未调用模型、未重跑27份。
