# RR-PUB01 公开事实 sentinel 最小闭环

固定准备基线 `58e29ffe9edc559bee552c734dc66ebed9ebf32c`。DD-F01 固定独审 39 项通过，root 已集成；本项不再修改死亡诊断、危急值或 074 文件。依据 `F:/MedQC-worktrees/review-artifacts/rr-scope-pub-design.md` 的 RR-PUB01 段；RR-SCOPE01 不在本项范围。

公开入口 `validate_luxian_0609_published_customer_display_facts` 的联合返回合同包含 `NotImplemented`。未知规则字典进入通用执行器校验后返回该 sentinel，旧公开入口却对其调用 `.get`，原 `test_unknown_rule_is_not_claimed_by_basic_family` 的 `raw={}` 因此产生 AttributeError。下游已有 identity 判断及 Store 的字典白名单投影，不需要改变规则发布范围、状态、Renderer、执行器或保存层。

生产改动批准范围：Finalizer 通用 fallback 调用后、现有 None 拒绝门禁前，增加 `if validated is NotImplemented: return NotImplemented` 两行。保留所有已知规则的 ValueError、现有 None 回退、专属 preop/antimicrobial 状态检查及 DD scope gap 门禁。禁止透传 raw、吞异常或用宽泛类型兜底合并 sentinel 与缺失事实。

## 冻结专属预期

新专属测试 `test_luxian_0609_published_sentinel_closure.py` 的预期在生产修改前冻结，原 unknown 红用例保持不改：

- 未知规范化 ID，空字典或包含 verification_kind/private 字段的字典返回同一 NotImplemented，输入不改；None、非字典保持 None。
- Store 未知字典投影为空，不能暴露原始字段；未知 non_compliant 无可审计解释仍 ValueError；身份字段冲突仍拒绝。
- 已知时限 C、抗菌药原因 NC、死亡诊断 scope_conflict gap 的合法公开事实保持字典全等；时限/死亡诊断的非法字段、抗菌药非法 reason_documented 值、三类矛盾状态仍拒绝。
- pending_definition 的 not_executed/policy_definition_pending 空事实仍 None。
- 三类已知事实经合成 SQLite 正常保存、新 Engine 和新 Store 回读保持相等；未登记 LX0609 身份的正常保存仍拒绝。直接构造的合成历史未知 LX Envelope 经回读校验及客户投影不外传 raw，客户可省略空 facts 字段；内部 load_selected 只校验 Envelope，不就地清洗其 raw。这不等于真实历史 API 验收。

## 验证安排与边界

唯一测试槽由 root 调度，已完成红→两行修复→聚焦绿，结束即释放。沿用隔离 runner，禁止读取 .env、PG、网络和真实模型。前端无变更，按 root 批次授权复用已冻结源码/配置 hash 的门禁证据，资源限制如实记录。真实模型调用为 0；此验证不能称临床或真实模型验收。

提交仅三路径：Finalizer、新专属测试、本说明。中文提交必须等待 root 的独占 Git/Husky 槽，使用真实 hooks。本轮准备不改任何旧测试或 DD 文件。

## 最终证据

- 最终固定红：原 unknown 用例加 29 项专属测试共 30 项，10 失败/20 通过；10 个失败均为 `NotImplemented.get` 的 AttributeError。日志 `.tmp/rr-pub01/pytest-final-red.log`。最终夹具曾在撤去两行的原生产基线上重新红，再恢复两行，排除仅新增预期无法复现的问题。
- 聚焦绿：6 个文件共 321 项全部通过，耗时 2.63 秒。覆盖新专属、完整 basic_timeliness_customer_projection、canonical_result_finalizer、preop_unknown_delivery、antimicrobial_result_mapping、discharge_published_boundary；日志 `.tmp/rr-pub01/pytest-final-green.log`。专属 29 已包含其中，不重复累计。
- 新 Engine/新 Store 的 SQLite 合成回读包含时限 C、抗菌药 NC、DD scope_conflict gap，事实和状态保留。未知 LX 正常写入拒绝；额外历史读取探针是直接修改本地合成 SQLite Envelope，客户投影无 private_payload/synthetic-secret，不能解释为真实病例/真实历史 API 验收。
- 初次夹具假设纠正记录：抗菌药既有白名单允许过滤额外字段，因此改用非法必需字段值验证拒绝；SQLite 正常保存夹具补齐既有 result_status/is_compliant 合同。CUSTOM 非 LX 不在 LX 客户合同范围，初次失败是测试假设错误，改为已知规则正常回读和未知 LX 保存拒绝/直接合成历史读取；公开空事实字段可省略，断言为空而不要求输出空键。没有为这些夹具修改产品逻辑。初次日志 `pytest-red.log`、`pytest-green.log`、中间 `pytest-final-green.log` 已由最终记录覆盖；最终红/绿独立保留。
- Python 两限定文件 Ruff 与 git diff --check 通过。生产 diff 恰为两行，所有原测试不改；前端 1147 个已冻结输入 hash 逐项比对保持相同，既有 lint 0 error/1214 warning 证据复用。前端 type-check 因此前资源压力被正常停止，未确认完成；全量前端 unit 未运行，本轮不重启，均不冒称通过。
- .env/PG/网络/真实模型为 0。隔离 runner 禁 dotenv 加载并封锁 .env 读取、网络连接；测试 SQL 仅 SQLite。

root 已授予独占 Git/Husky 槽，正常中文提交使用真实 `.husky/pre-commit`（lint-staged + app encoding）；日志 `.tmp/rr-pub01/commit.log`。本项尚待固定提交独审。生产范围没有新增模型调用、重试、规则身份、目录发布变化或其它 Finalizer 分支修改。
