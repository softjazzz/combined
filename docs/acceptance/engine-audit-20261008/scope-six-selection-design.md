# SCOPE-06 原始选择范围校验修复

基线 `f4d32a679`，分支 `codex/qc-fix-scope-six-20261008`。SCOPE6-01 已在真实样本入口复现并完成最小修复：包含未注册 LX0609-06-03-01 的显式选择现在返回 422，不创建任务、不派发 worker。新增 6 项及原 release_scope 完整 15 项共 21 项全绿（18.91s）。尚待独立审阅和根串行集成。

## 冻结合同与缺陷

正式 POST `/api/v1/qc/sample-pools/{pool_id}/run` 对未注册规则请求必须在入口明确拒绝。已注册暂停规则与 active 混合选择继续创建任务并保留暂停交付范围；仅选已注册暂停规则继续原 422；未显式选择继续既有默认冻结范围。客户明确排除项不能借全部 master 白名单进入任务。本项是 0609T5 范围修复，不扩展隐私，不启用或注册 LX0609-06-03-01。

原 `qc_sample_pools.py:1029` 保存规范化原选择，1198 起先分离阶段暂停项，1237 只验证剩余 active。原选择仍经 1449/1462 进入 paused/scoped 任务过滤器。worker 1389 校验 execution、gate-only、paused 并集，真实独立包 inventory 不接受未注册 pending 项。实际合成正式 POST `[LX0609-06-03-01, LX0609-01-01-01]` 产生 `(HTTP 200, 1 个新任务, 1 次 dispatch)`，同时真实 worker inventory 校验拒绝该组合；确认不是静态猜测。

## 精确修改范围

唯一生产修改 `apps/medqc-web/backend/app/routers/qc_sample_pools.py:1198`，新增 13 行。在暂停剥离前对原 normalized selected 校验成员，allowed 取本次已解析的 `rule_ids`（原 1153）。`sample_validation_rule_sets.py:306–336` 已将实际 catalog、phase 目录、客户排除范围交集投影为该目录，不使用全 master。拒绝沿用当前错误文案“所选质控点不属于当前规则集”。后续执行 resolver、默认投影、paused-only 分支全部保留。

新增正式测试 `apps/medqc-web/backend/tests/integration/test_luxian_0609_sample_scope_membership.py`，新增本说明；没有其他生产/测试变更。worker、catalog、phase、规则注册、发布范围、隐私公共模块均未改。原 privacy 分支及 4ba69f47b 保留，从 clean 工作树新建本分支，没有 reset/stash/丢弃改动。

## 正式合成验证

复用已有 release_scope 合成 SQLite 夹具与真实 FastAPI TestClient。路由、resolver、phase、inventory、创建任务和 SQLite 持久化均为生产实现；外部认证、医院资料、模型配置依赖为明确合成替身。新测试只捕获后台 callable/job_id，不运行 worker；模型调用由既有 no_llm 守卫禁止。测试完整保留有效选择集合，并按既有 normalize 的排序比较。

6 项新测试覆盖：未注册 pending+active 在入口拒绝；已注册暂停 LX0609-03-01-01+active 正常交付；仅已注册暂停保持原 422；默认冻结范围保持；客户排除项+active 拒绝；普通未知 ID+active 拒绝。拒绝测试同时断言 `(状态码, 新增任务数, dispatch 数) == (422, 0, 0)`。旧 release_scope 15 项完整执行，含分组父子任务、显式验收项、重试冻结范围和现有 Node/tsx DTO 摘要门禁；未改任何旧测试断言。

| 阶段 | 实际结果 | 判读 |
| --- | --- | --- |
| 第一次原生产运行 | collected 6，6 setup errors，8.67s | Windows asyncio 内部 socketpair 被临时网络 guard 误拦；未到 POST，不算产品红 |
| 第二次原生产运行 | 2 failed / 4 passed，7.07s | pending+active 真实 `(200,1,1)`；另一个失败为新测试误假定 scoped 保留输入顺序，不算产品缺陷 |
| 修正支撑后的原生产红 | 1 failed / 5 passed，5.39s | 唯一产品失败仍为 `(200,1,1)`，其余控制全绿 |
| 最小修复后绿 | collected 21，21 passed，18.91s | 新 6 + 旧 15 完整通过；pending+active 现在 `(422,0,0)` |

## 离线与执行边界

临时 guard/runner 仅留本树 `apps/medqc-web/backend/.tmp/scope_six_offline_guard.py`、`run_scope_six_offline.py`，不提交，不新增测试框架。应用导入前替换 dotenv 函数，阻断 `.env` 文件读取、PostgreSQL 和网络连接，仅允许合成 SQLite。socket connect 仅在调用栈精确包含标准库 `socket.py/socketpair` 时允许 Windows 内部 self-pipe，其余一律拒绝，没有普通 localhost 豁免。

第二次运行的用户 LLM 配置查询尝试被 guard 阻断（0 真实连接）；随后显式固定 LLMConfigLoader 的合成配置依赖，最终红/绿均无该查询。没有安装依赖，没有读取真实病历，没有真实模型/PG/网络/.env 访问。Node 使用既有只读依赖运行原 DTO 小门禁，没有前端全量运行。

最终命令在 backend 下执行：`PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONUTF8=1 python .tmp/run_scope_six_offline.py tests/integration/test_luxian_0609_sample_scope_membership.py tests/integration/test_luxian_0609_release_scope.py`；runner 内部 `pytest --noconftest ... -q`，防止公共 conftest 在 guard 前导入应用。21 为本次实际 collected 数。3 个既有 deprecation/schema warnings，无环境或支撑失败。仅证明合成业务入口合同，不声明真实患者规则验收。标准真实 Husky 已执行通过：lint-staged 无匹配任务，app check:encoding 扫描本次 2 个 staged 文本文件并通过。未绕过 hook、未改 common config。未运行前端全量 lint/type-check/unit，范围为后端路由最小改动及合成门禁；独立审阅由根调度。
