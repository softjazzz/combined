# LX0609 全引擎复审四项定向修复

开发基线：`8b55db9e875924b88e1948fa1cb10e4d928a706f`。工作树：`D:/MedQC-worktrees/frozen-exam-association-fix-20261107`，分支：`codex/frozen-exam-association-fix-20261107`。本次在原 PR47 独立分支增量开发，不代表 PR47 已合并或本轮修改已经推送。

## 修改与边界

| 问题 | 最小修复 | 保护范围 |
| --- | --- | --- |
| 旧 `LLM_ROLE_MODELS` 重新读取全局裁决配置，可能使本地任务转云端 | 客户端创建时从实际有效参数捕获旧路由；任务克隆复制运行配置；真实选择器不再读后台当前选型；本地到云端明确拒绝 | 保留分角色配置优先级、脱敏、Gateway 身份检查，不增加模型调用和自动兜底 |
| 术前小结／讨论异常混为临床资料缺口 | `04-01-04/05` 的超时、传输、解析、错误引文／响应身份转为逐规则技术失败；输出 length 不接纳；预算拒绝由受影响规则承接 | 保留同族成功及不适用结果；有效模型事实为 unknown、真实材料不可用／截断仍保持原资料合同；4096输出要求不变；取消继续向上传播 |
| 输血前日期被补成午夜、带时区时间直接去掉时区 | 申请评估和逐次前评估关联统一复用已有精确时间解析器 | 日期不能证明先后；带时区先转换医院 +08:00；显式午夜保留；不改变输血医学条件和事件匹配规则 |
| 默认云端模型没有事实冻结分区 | 复用任务安全模型身份和现有用途冻结分区；正式执行器边界建立作用域 | 模型、有效参数、端点摘要、路由及配置变化分区；检查、抗菌药、会诊意见／应答隔离；不删除、覆盖或迁移旧冻结，不修改历史结果 |

新增旧路由身份只含模型、推理参数和地址摘要，不含 API Key 或原始地址。配置已被客户端接纳后，后台选型改变不改变该客户端及任务克隆；新的配置由新客户端／新任务使用。Gateway 出口身份漂移时明确失败，不恢复直连。

术前异常沿既有 `RuleDecision → Binding → Finalizer → Worker失败分类` 进入技术失败范围。可交付的同族结果照常进入 Canonical。没有新增自动重试：格式失败仍受原有补跑合同限制，预算错误不无限重发。

新执行不再读取未隔离的旧模型冻结；旧文件原样保留。历史结果读取、旧冻结内容、C18终点保护与检查身份v6未修改。没有更改0916、医学适用条件、Finalizer、保存层、前端、数据库或默认开关。

## 实际隔离验证

均在 backend 执行，使用 Python3.10、既有 `scripts/run_pr8_offline_tests.py`，阻断网络和非SQLite连接，禁读dotenv，不加载应用lifespan。仅合成材料、固定应答、临时冻结目录和内存SQLite。API夹具使用既有 `tests.scheduler_support.pytest_plugin`。

```powershell
python -B scripts/run_pr8_offline_tests.py -p tests.scheduler_support.pytest_plugin tests/unit/test_engine_review_priority_fixes.py tests/unit/test_llm_task_roles.py tests/unit/test_luxian_0609_native_preop_content_execution.py
# 111 passed

python -B scripts/run_pr8_offline_tests.py tests/unit/test_transfusion_association.py tests/unit/test_luxian_0609_task_runtime_identity.py tests/unit/test_llm_experiment_freeze.py tests/unit/test_luxian_0609_llm_role_routing.py
# 114 passed

python -B scripts/run_pr8_offline_tests.py tests/unit/test_luxian_0609_native_transfusion_execution.py -k '044 or pretransfusion'
# 25 passed，98 deselected

python -B scripts/run_pr8_offline_tests.py tests/unit/test_context_token_budget.py -k 'executor or family_failure'
# 5 passed，17 deselected
```

最终相关集合共255项通过，0失败、0跳过；115项其他用例按范围未选，不是通过。首轮新增保护在修复前为12失败／2通过；中间7条术前既有断言仍期待将技术异常保存为资料不足，已按本次新合同调整，未放宽有效引文、成功同族或材料不足的正面断言。一次离线入口未载入API夹具的收集错误已通过指定既有插件纠正。

新增保护实际验证：实际客户端旧路由与克隆、真实脱敏选择器；默认云端模型及参数变更隔离；旧冻结不变；四种申请时间与三种前评估关联时间；术前超时／网络／坏JSON／length；预算逐规则承接和取消；正式术前执行器→Binding→Finalizer→内存Canonical保存读取，及失败项不可交付分类；会诊意见／应答在同模型复用、跨模型不复用。

静态检查：`git diff --check`通过。改动Python文件的Ruff F检查除 `sichuan_qc_service.py` 的7条基线告警外通过；已对基线文件独立执行Ruff，确认同样2条F401、4条F541、1条F841，本轮仅在该文件新增任务克隆字段，未清理无关旧代码。

## 待Claude独立复审／剩余限制

- 本次为工程修复，不是全引擎或真实模型医学质量验收。未重跑全量质量门、PG16矩阵、27份病例、真实接口及现场部署。
- C18历史任务实际运行版本、C27探索项原文归属、短报告重复检查假歧义及不完整事件回退主抽取等原有限制未被本次解决。
- 未扩展模态同义词或新的临床身份锚点，也未修复全引擎报告中的其他问题。
- 新模型分区首次需要重新取得该模型事实；固定应答只验证隔离和恢复合同，不证明不同模型质量等价。
- 无数据库迁移或新配置开关。回滚本次代码即可撤回本轮行为，文件未迁移；回滚会恢复旧缺陷，不能因此认定旧行为安全。
- 本轮不合并、不推送、不部署、不修改业务库、不连接模型服务，不触及0916。
