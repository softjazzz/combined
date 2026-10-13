# SCOPE6-01 独立限定复核

结论：固定提交 `b5d0991a22c79aea3821a7819042a66a974c033f` 的入口修复通过独立静态复核。未发现本次修改引入的新产品阻断；可以进入根串行集成。此结论属于 0609 原选择范围入口合同层，不是部署通过或完整临床验收。本审阅没有启动测试、应用服务、Worker、PG、模型或网络，没有读取 `.env` 或真实病例。

## 固定范围与来源

父提交 `f4d32a679ddb6614afbe6bda4fb6e16fc4121dc3`。提交仅有三路径、192 行新增：生产路由新增 13 行、新增 143 行集成测试、新增 36 行设计记录。此前候选 `c289d82ef876404ab3286501c31e96646b6807de` 到最终提交仅设计记录 1 行替换，追加真实 Husky 记录；生产和测试字节相同。读取和导出均使用 `git show` 固定提交，没有以工作树后续编辑作为源码证据。审阅结束时 owner 树 `git status --short` 为空，固定差分 `git diff --check` 无输出。

`source-hashes.json` 保存 12 个固定 Git blob、SHA256、相对父提交字节一致性；`fixed.diff` 保存完整三路径差分。Worker、规则集解析、phase scope、rule master、既有 release_scope 测试、共享真实链路夹具均与父提交字节相同。完整提交 diff 没有 catalog、注册、默认策略、隐私或其他生产文件变更。

`expectations.json` 冻结六项独立合同。冻结发生于任何独立执行之前，但审阅时已知 owner 的反例及运行结果，因此不宣称盲测或先于开发的红绿冻结。本轮没有独立运行结果文件，也没有将静态六合同计为六次执行通过。

## 控制流与修复判断

固定 `router.fixed.py:1025` 先规范化原 `selected_rule_ids`。`rule_ids` 来自已解析的规则集；固定 `rule-sets.fixed.py:306` 的 LX0609 规则集以实际 catalog 与 phase 目录交集、扣除客户排除项建立，未使用全 master 作为白名单。

新增校验位于 `router.fixed.py:1198–1215`，对完整原选择逐项判断规则集成员；不合法项立即 HTTP 422。暂停选择分离从 1216 开始，默认 acceptance-only 投影和随后 execution resolver 均保持原实现。这个位置同时保护后面的 grouped 和 leaf 路径，无需给 Worker 添加兼容吞错。

拒绝发生在模型配置读取 1289、grouped parent 保存 1648、child 保存 1727、leaf 保存 1805 和派发 1767/1822 之前。已注册暂停项仍属于原 resolved 范围，所以与 active 混合选择继续保留 customer scoped/paused 身份；只有暂停项沿用原 422。未显式选择时新增列表为空，原默认冻结分支继续执行。非 0609 分支没有新增校验。0916 是用户排除范围，没有开展其功能验收。

## 测试真实性与覆盖边界

新增测试实际使用 FastAPI `TestClient` 调用生产 POST `/api/v1/qc/sample-pools/{pool_id}/run`。失败断言以 SQLAlchemy 真正 COUNT 任务表比较前后增量，并记录 dispatch 次数；正常路径实际从 `CustomQCWorkspaceService.get_batch_job_for_processing` 回读 SQLite filters。没有 monkeypatch 规则集解析、execution resolver、phase/inventory、路由函数或任务创建/回读来制造 expected output。

复用夹具将 workspace/sample-pool engine 与 SessionLocal 指向合成 SQLite，创建真实 ORM 表、病历、样本池；真实 `collect_records` 和保存逻辑保留。夹具替换外部认证/激活、settings、医院资料读取、模型配置并禁止模型调用；SQLite 下另将 `_sync_batch_job_parent_columns` 置空并用 single schema。这些是明确的数据库迁移及外部边界替身，不能用测试证明 PG 迁移、真实授权或实际模型配置正确。新增测试截获后台 dispatch，只验证入口交接，不执行完整 Worker。直接调用真实 Worker inventory validator 提供消费者合同对照，不等于执行 Worker 端点。

新增六项涵盖：未注册 pending+active；已注册 paused+active；仅已注册 paused；默认选择；客户排除项+active；普通未知项+active。拒绝测试同时检查 `(HTTP, 新增任务数, dispatch 数) == (422, 0, 0)`。关键未注册反例 ID 是固定 `LX0609-06-03-01`，没有通过注册该规则来消除失败。

`_registered_paused` 动态取生产 delivery/inventory/paused 交集的第一项，能验证存在真实可交付暂停项及投影，但未固定完整暂停身份集合。默认 expected 集合也来自生产 delivery helper，存在共同来源，不能单独发现该 helper 的完整名单错误。旧 release_scope 15 项提供独立的固定五条 PILOTS 集合、三条指定默认 active 成员、grouped delivered/executed 的 75/65 数量，以及具体显式选择和重试不得扩张的冻结断言；其完整默认集合仍由同一 helper 派生。因此旧测试增强了发布冻结证据，不构成独立完整规则名单验收。本修复没有修改旧测试以适应变化。

## 已有运行证据与门禁

以下来自固定 owner 设计记录，不是本审阅重跑：修正夹具后的真实原生产 6 项为 1 failed / 5 passed，唯一产品失败是 pending+active 的 `(200,1,1)`；最小修复后新增 6 + 原 release_scope 15 为 21 passed，18.91 秒。早期 socketpair 守卫导致的 6 setup errors，以及 scoped 顺序误假设导致的额外失败，均保留为支撑问题，不计产品失败。其临时离线 runner 不在提交内，本审阅只读该 runner，未执行或独立认证其 guard。

固定设计记录报告标准真实 Husky 执行成功：lint-staged 无匹配任务，check:encoding 检查本次两个 staged 文本文件通过。提交的根 package lint-staged 没有 `.py` 匹配，本轮不据此声称 Python 格式/静态 lint 通过。backend 没有发现本项目 Ruff/pyproject/setup.cfg 门禁配置，不凭新测试风格臆造已要求的 Ruff 命令。

仓库 AGENTS.md 要求完整 encoding、lint、type-check、test:unit；过重时最低仍是 encoding + lint。owner 明示未运行前端全量 lint/type-check/unit，因此 lint 是最低提交要求的未完成门禁，Husky 成功不能替代它。根可按最终集成范围安排并记录这些门禁，未运行项不能写成通过。本审阅不擅自启动额外资源任务。

最终集成候选 SHA 仍需根串行重跑 0609 入口范围聚焦回归，并保留目录冻结、已有显式 acceptance/retry/grouped 控制；本修复固定 SHA 的 owner 21 不能替代集成后结果。完整正式客户链、真实授权/配置、PG 迁移与部署验收均未由本报告完成。PRIV004/005/002 和 RR-PUB01 的既有独审按各自固定 SHA/方法继承，未扩充为本项运行证据。

## 产物

- `review.json`：结论、发现、门禁和来源索引。
- `expectations.json`：六个冻结合同，注明冻结时序和未执行。
- `source-hashes.json`、`fixed.diff`：固定源码身份和精确修改范围。
- `*.fixed.py`、`design.fixed.md`、`agents.fixed.md`、`package.fixed.json`、`precommit.fixed.sh`：固定 blob 导出，供复查真实方法边界。
