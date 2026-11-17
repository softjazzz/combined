# 两例四类材料无模型联验操作单

**状态：方案准备，未执行。真实 clinical 的机构、类型、生命周期批准及发布条件未闭合，不能据本操作单启用生产。**

本地业务提交见同目录交付说明及 `git log -1`。同步源固定为 `cb437e611e802c5117f212c1e9743d2748ec4127`，合同 `clinical-primary-four-v1` / `clinical-primary-real-fields-v2`。`3123e0468` 只作已有证据，不引入冻结试跑工具到业务运行时。

## 1. 准入前提与责任

同步负责人提供 P01/P02 两例已经冻结的 canonical/native 机构、患者、就诊批准映射、四类类型及文书号关联批准、生命周期原值的批准依据、**实际发布后的** policy_hash/selection_id/逐类选中数量及来源覆盖状态。院方确认人签署机构、类型、生命周期语义，不能用空值、0/1或“有正文”代替批准。真实清单仍 HELD 时停止，不能为联验填伪批准或移除门控。

运维审核同目录 `READONLY-PERMISSIONS-PROPOSAL.sql` 的14个精确对象及列，仅使用批准的独立 CDM 只读账号及既有受保护 passfile。草案不执行GRANT，不使用同步管理账号，不授予 primary_attempt。原有业务来源配置读取继续使用现有权限；`ordinary_snapshot()` 会只读业务配置登记 `qc.sync_config_registry`，因此现场授权必须包括这一步配置读取。临床正文仍只读 `medqc_sync_cdm`，不会连接 clinical/homology/源 Caché/ingest。

业务负责人固定本次业务提交和批准政策文件。政策使用 `QC_PRIMARY_FOUR_POLICY_FILE` 格式：顶层 `policies` 数组，每项含同步提供的原始 `policy`、与其完全匹配的 `policy_hash`、对应既有 CDM 的 `source_binding`；只允许这两例。文件绝对路径、非符号链接、Linux无组/其他写位，建议0600。不要创建新推定规则或自行重算批准内容替代同步正式输入。

维护负责人另行批准一次执行窗口。联验不重启服务、不写生产任务或结果、不启自动采集/调度，也不启网页上的真实质控。新功能只在联验子进程临时开启，既有配置文件不修改。

## 2. 准备私有计划（不含凭据，不外传病例键）

运维在 release 外新建受保护目录（0700），保存一个0600的计划文件。下例中的占位值必须替换为同步负责人提供的**实际批准输入**；不是可以直接执行的批准单。文书类必须恰好四种，两个别名必须是 P01/P02；逐类数量可以为0，但每例至少有一份选中材料，且必须与实际发布清单一致。

```json
{
  "source_commit": "cb437e611e802c5117f212c1e9743d2748ec4127",
  "contract": "clinical-primary-four-v1",
  "metadata_revision": "clinical-primary-real-fields-v2",
  "document_types": ["daily_course_record", "presurg_summary", "surgery_record", "postsurg_firstcourse_record"],
  "authorization": "PENDING",
  "approval_reference": "待填实际批准单号",
  "approved_policy_file": "/protected/approved-primary-policies.json",
  "expected_source_binding": "待填现有独立CDM绑定",
  "cases": [
    {"alias":"P01","institute_id":"待批准","patient_id":"待批准","visit_id":"待批准",
     "expected_policy_hash":"待发布","expected_selection_id":"待发布",
     "expected_selected_counts":{"daily_course_record":0,"presurg_summary":0,"surgery_record":0,"postsurg_firstcourse_record":0}},
    {"alias":"P02","institute_id":"待批准","patient_id":"待批准","visit_id":"待批准",
     "expected_policy_hash":"待发布","expected_selection_id":"待发布",
     "expected_selected_counts":{"daily_course_record":0,"presurg_summary":0,"surgery_record":0,"postsurg_firstcourse_record":0}}
  ]
}
```

计划校验默认不导入应用、不连接数据库。无参数只显示 argparse 帮助；不能把默认校验通过当成现场读取成功。不要打印计划、policy、环境文件或完整异常。无需传SHA侧车或手工核对；保留现有交付工具自动检查。

## 3. 可复制的命令模板（本轮未执行）

以下使用已经审核的业务代码目录和服务器现有 venv；先按现场批准值替换三个路径。只能由有权限的运维执行，不安装依赖，不启动API/lifespan/worker。

```bash
set -euo pipefail
APP=/path/to/reviewed-business-code
PY=/data/medqc/business/venv/bin/python
PLAN=/protected/two-case-primary-trial.json

# 准备态：不连接。先运行此步；非0即停止。
"$PY" -B "$APP/apps/medqc-web/backend/scripts/verify_primary_material_trial.py" --plan "$PLAN"
```

收到独立执行授权且计划中 `authorization` 已按批准设为 `APPROVED` 后，另开一个执行段。只运行一次；OUT必须为release外**尚不存在**的私有新目录。使用现有受保护部署方式提供来源设置与passfile，不通过参数传密钥、不 `cat .env`、不 `set -x`。

```bash
set -euo pipefail
APP=/path/to/reviewed-business-code
PY=/data/medqc/business/venv/bin/python
PLAN=/protected/two-case-primary-trial.json
OUT=/data/medqc/primary-trials/APPROVED-UNIQUE-TRIAL-ID
umask 077
test ! -e "$OUT"
"$PY" -B "$APP/apps/medqc-web/backend/scripts/verify_primary_material_trial.py" \
  --plan "$PLAN" --execute --output "$OUT"
```

脚本复用统一Provider所用的reader接缝与同一只读RR事务：固定选择清单及正文 → Bundle取行/规则输入替身 → 目录投影 → 私有全文材料副本 → 冻结读回及版本核对。它直接检查reader输入，不建立EvidenceReadSession、不执行医学判定。Bundle显式读取上限20000；规则输入若触及自身截断标记即停止，不宣称全量。它不运行规则、不创建真实质控任务；`material-trial-*`只是私有目录索引，不是任务表ID。

输出仅两例别名、选择ID、材料指纹、四类计数及零模型/规则/生产写入声明；完整正文只留OUT下0600材料对象。不要外传OUT/计划/政策正文。

## 4. 核对与停止条件

逐例确认 policy_hash、selection_id、选中版本与预期数量相同；目录同时保留替代版及待核信息，Provider仅含selected_version。手术正文为同版本 `surgery_process`，不补填 `record_content`。点击页面的正式验收另行授权，不用合成DOM测试冒充现场浏览器通过；只读页面时须核对相同版本和来源，不点击刷新Bundle、提交或质控按钮。

同一事务看到旧或新发布均可，但不得出现新manifest/旧正文混搭。捕获后即按私有副本读回，不再读current正文。旧生产任务/材料/快照及1026/PDF完全不动。

任一项非0、来源绑定/三键/政策不符、HELD、候选对象未部署、权限/连接异常、发布回执过期、计数或引用版本不符、截断、材料保存或完整性失败，**立即停止**。保留已经形成的OUT与日志，不补跑、不自动回退源库、不重试、不删材料、不改批准单。只有明确的同步选择结果允许Caché回退，技术读取失败不能假装成功零行。

## 5. 收尾与边界

记录业务commit、同步合同、两例别名、开始结束时间、退出码、报告中的计数/版本及未验项，诊断只输出受控类别。子进程退出即结束临时功能开关；不改服务配置或默认关闭状态。无需生产回滚：本操作不切换release、不迁移、不写任务/结果；失败产物只读保留，后续处置另行授权。

本轮仅完成合成材料链与方案准备。真实clinical准入、发布、现场浏览器和上述两例读取均未执行；医院/同步方负责剩余语义和发布条件，不要求先解决全院历史差异。
