# 历史诊断变更明细展示兼容

## 基线与旧合同证据

- 独立分支：`codex/historical-diagnosis-trace-compat-20261113`。
- 基线：`e431176cc`，源码树与已合并的 `90edf8ca2` 一致；复用现有隔离工作树。
- 旧提交 `196c4cf64d8e634e6199471bd3f998749f91c878` 在独立诊断变更分支增加了 `extended_document/diagnosis_change_trace.py`、连续性事实校验、写入和明细展示，定义 `diagnosis-change-trace-v1`。当前集成树没有该扩展，严格字段集合检查因此将历史 `diagnosis_change_trace` 拒绝为409。
- 三种旧计数依据：`structured_transitions` 的次数必须等于明细条数；`declared_diagnoses`、`document_mentions` 的次数只能为null。文书份数不能替代诊断变更次数。
- 后续独立提交 `d307e4745` 又引入事件协议和新的规则执行逻辑。本次不合入该分支、不支持未知事件版本、不改变医学判定。

## 修复范围

仅为 `LX0609-12-02-01` 的 `diagnosis_change_documentation_check` 接入旧v1精确合同。纯校验模块从旧提交的读取校验提取，不包含材料读取、规则执行、生成或网络能力；补充非字符串field_path的显式拒绝。

校验外层精确字段、布尔状态、trace版本、计数依据/数量、日期、来源白名单、`src_`脱敏引用形状、有界摘录、字符位置及观察文书计数。合法明细深拷贝返回；未知字段、无效明细不通过“丢弃后重试”绕过校验。原有汇总合同不变。

不重算结果，不修改保存的状态、结论、建议或未知次数；不使用当前CDM补历史。Canonical身份、冻结病例范围、账号归属、状态一致性及客户DTO脱敏逻辑保持原样。不改变演示账号筛选、助手503或前端路由。

## 必要隔离验证

通过 `scripts/run_pr8_offline_tests.py` 执行，禁dotenv、禁网络、禁非SQLite数据库连接。仅合成数据，没有调用规则/模型。

- 修复前新增测试：3条合法旧合同读取失败，14项保护通过，复现额外trace字段被拒绝。
- 修复后 `test_historical_diagnosis_trace_compat.py` + `test_luxian_0609_continuity_result_mapping.py`：44通过。包括三种旧计数模式、旧汇总、未知版本/字段、畸形引用、摘录越界、计数冲突、身份冲突；合成SQLite真实保存再按Canonical读取，确认信封字节不变、密钥轮换不破坏历史引用、跨账号/任务/机构拒绝、损坏状态仍拒绝。
- `test_failed_task_detail_access.py`：3通过，未登录401、越权404、获准用户200。
- 改动Python文件Ruff F检查通过。既有Pydantic/Starlette弃用及schema字段警告保留。

本轮不连接本地或服务器业务库；SQLite仅临时合成库。没有修改历史任务/信封/快照、运行质控、调用模型、部署、重启本地服务、合并或推送。

## 未验证项

没有对真实历史任务进行读取重放或浏览器验收，不能将合成用例通过称为现场修复已生效。当前运行的后端没有自动重载；需后续明确安排本地加载候选后的只读验收。尚不兼容未核定的其他trace版本，未知合同仍返回受控拒绝。
