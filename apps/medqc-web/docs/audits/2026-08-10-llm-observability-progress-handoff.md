# 模型性能观测看板进度与续接说明

日期：2026-08-10  
状态：按用户要求暂停，目标尚未完成，不可作为上线验收结论  
当前分支：`codex/lx0609-tech-debt-20260730`  
暂停时 HEAD：`4bfca8aa4`

## 1. 原始目标

完成模型性能观测看板的端到端开发：

- 持久化真实模型逻辑调用与每次 HTTP 尝试；
- 统计单病历调用次数、总调用次数、输入/输出/总 Token、响应时间、重试、并发；
- 提供管理员只读聚合 API；
- 在系统配置增加“模型性能”页签；
- 保证权限、隐私、失败关闭；
- 完成迁移、聚焦回归、两份真实病历对账和浏览器视觉验收。

## 2. 已提交成果

| 提交        | 内容                                                                                     | 当前结论 |
| ----------- | ---------------------------------------------------------------------------------------- | -------- |
| `cf40b0adc` | 冻结模型观测字段、隐私、统计与验收合同                                                   | 已提交   |
| `dbb9ea104` | 新增 `sys.llm_call_events` 迁移、核心记录器、四川质控主模型客户端及样本任务/执行器上下文 | 已提交   |
| `3c7e781b0` | 增加 overview、病历列表、单病历调用明细只读聚合 API                                      | 已提交   |
| `d404c7fd8` | 注册模型观测路由并补服务商筛选                                                           | 已提交   |
| `a61fff12e` | 修正重试数和 Asia/Shanghai 趋势分桶                                                      | 已提交   |
| `33829f8d6` | 补 LLM 配置探针、编码质控、预生产场景；关闭浏览器文件直连模型                            | 已提交   |
| `66495b987` | 补生产应用路由注册回归                                                                   | 已提交   |
| `4b7ba78d9` | 纳管首页抽取、ICD 推荐、诊疗画像、自定义规则、旧模型代理等独立模型出口                   | 已提交   |
| `4bfca8aa4` | 纳管智能上传字段映射模型调用                                                             | 已提交   |

已提交的主合同如下：

1. 一次逻辑调用可包含多次 HTTP attempt；`logical_call_id + attempt_no` 唯一。
2. 模型观测写入失败为 fail-open，不反向改变临床质控结果。
3. 事件不保存 Prompt、响应正文、API Key、endpoint、患者三坐标原文。
4. 病例身份只保存 HMAC 后的 `record_key_hash`；三坐标不完整时不生成病例哈希。
5. Token 未完整上报时使用 `usage_state=unknown`，不得按 0 统计。
6. 读取接口仅允许非演示的 `admin`、`sync_admin`、`super_admin`。
7. 超过 10 分钟仍为 running 的事件只读投影为 abandoned，不改写原始事件。

## 3. 已有验证证据

已完成且当时通过的聚焦验证：

- 核心事件、中央模型客户端、长度截断重试、任务父子 root 和执行器上下文：相关回归已在提交前通过。
- 只读 API：12 项聚合/权限/隐私测试；后续 provider、重试、时区和路由回归分别通过。
- 独立出口：`test_llm_observability.py + test_llm_observability_independent_egress.py` 共 18 项通过。
- 已提交版本的字段映射出口：5 项通过；暂停前的未提交重试 follow-up 单独运行 `test_field_mapper_observability.py` 为 6 项通过。
- 前端初版：服务、面板、系统配置权限等 23 项聚焦测试曾通过；后续口径 follow-up 已修改但尚未完整复跑。
- 已提交前端直连关闭回归：浏览器不会直接携带厂商 URL/API Key 调模型。

注意：暂停前最后一次组合回归曾出现 3 个测试失败，均为收紧代理元数据与 Agent 会话口径后留下的旧断言；断言已修改，但组合回归尚未重新跑完。因此当前工作区不能宣称全绿。

## 4. 当前未提交工作

以下为本任务相关、仍在工作区中的改动，不应丢弃，也不应与无关脏改动混提：

### 4.1 后端

- `backend/app/services/llm_observability.py`
  - 增加同步模型出口记录器，供 QC Agent 的同步 `httpx` 调用使用；
  - 对 scene/root/provider/model 等元数据做长度、格式和敏感前缀保护；
  - 增加不可信外部 ID 的 HMAC 派生方法；
  - 增加 OpenAI SDK 异常分类；
  - 支持调用方显式传递同一 `logical_call_id` 和递增 `attempt_no`。
- `backend/app/services/qc_agent/intent_router.py`
  - QC Agent 意图模型调用接入同步观测边界。
- `backend/app/routers/qc_agent.py`
  - 客户端 session 只保存安全派生 ID；
  - 不信任客户端提交的 institute/patient/visit，不生成病例哈希。
- `backend/app/services/field_mapper.py`
  - OpenAI SDK 内部重试关闭；
  - 由业务层显式最多 3 次重试，每次真实 attempt 单独记录且共享一个 logical call；
  - SDK 缺 total 时由 Python 使用 input + output 计算。
- `backend/app/routers/proxy.py`
  - 旧代理不再把客户端自填 provider/model 原样写入事件，改为受控枚举。
- `backend/app/routers/llm_observability_read.py`
- `backend/app/services/llm_observability_read.py`
  - 单病历调用明细继承总览的日期、场景、服务商、模型筛选。

### 4.2 前端

- `src/services/llmObservability.ts`
- `src/types/llmObservability.ts`
- `src/views/workstation-v4/components/system-config/LlmPerformanceObservabilityPanel.vue`
- `src/views/workstation-v4/DataSyncConfigPage.vue`
- 对应服务、面板、系统配置测试。

当前前端 follow-up 已实现或正在实现：

- 严格只接受 `{ success: true, data }`；
- 真实业务场景枚举；
- 单病历抽屉继承当前筛选；
- 存在未知用量时显示“已上报 Token”，不冒充完整总量；
- 明细显示 `usage_state`；
- 快速筛选采用最后一次请求生效；
- `?tab=llmObservability` 可直接打开页签；
- 演示账号隐藏，正式管理员角色显示。

这些未提交改动必须先做 diff 审查和完整聚焦回归，不能直接提交。

## 5. 当前数据库状态

暂停时只读检查结果：

```text
alembic current: 20260802_000025
alembic heads:   20260810_000028
```

因此本地数据库尚未创建 `sys.llm_call_events`，当前后端即使运行也只能因写入 fail-open 而继续业务，无法形成真实看板数据。

未执行：

- `alembic upgrade head`；
- 数据库表/索引实库验收；
- 新后端基于迁移后的重启；
- 真实病例事件写入与 API 对账。

数据库升级属于写操作，恢复任务后仍需按项目规则获得用户明确授权。

## 6. 尚未闭合的问题

### P1：必须完成后才能验收

1. 仍有两个生产可达模型出口未纳管：
   - `backend/app/routers/demo.py` 的演示规则生成；
   - `backend/app/services/icd_semantic_retrieval_service.py` 的 Embedding 请求。
2. 当前未提交的 QC Agent、字段映射重试、元数据保护、明细筛选和前端口径改动尚未完成组合回归与提交。
3. 本地数据库未升级到 028，真实事件表不存在。
4. 未复跑两份真实病历并对账：
   - institute：`LX0609_0728_DERIVED_V1`
   - patient/visit：`LX0609_DERIVED_208790_V1`
   - patient/visit：`LX0609_DERIVED_359787_V1`
5. 未证明父任务与规则族 child task 均聚合到同一 root，两个病例按不同 record hash 去重。
6. 未完成登录态浏览器视觉验收、筛选交互、病历明细抽屉和权限 403 验收。

### P2：应在最终审核前处理或明确接受

1. 同步和异步 Recorder 目前存在事件字段装配重复，后续有漂移风险；先以冻结测试锁定，再决定是否仅抽取一个私有构造函数。
2. 外部 SQLBot 运行在独立进程，本看板无法覆盖；前端需明确“不含独立 SQLBot”。
3. 观测写入为 fail-open，数据库不可用时会低计；页面必须展示数据可用性/更新时间，不能显示伪 0。

## 7. 与本任务无关的工作区改动

下列现有脏改动不是模型观测任务，续接时必须保留且不得混入提交：

- `docs/0508/single_visit_qc_pack_performance_breakdown.*`
- `src/views/workstation-v4/semantic-rules/**`
- `tests/unit/views/workstation-v4/semantic-rules/**`
- 既有未跟踪计划、手册资产、外部医学文档和 `tmp-npm-single-record-panel/`。

## 8. 建议续接顺序

1. 先审查当前未提交 task diff，只暂存模型观测白名单文件。
2. 补纳管 demo 规则生成与 ICD Embedding，并增加“一次真实 HTTP = 一次 attempt”的测试。
3. 运行后端组合回归：

```powershell
cd backend
python -m pytest `
  tests/unit/test_llm_observability.py `
  tests/unit/test_llm_observability_independent_egress.py `
  tests/unit/test_llm_observability_qc_agent.py `
  tests/unit/test_llm_observability_read_api.py `
  tests/unit/test_field_mapper_observability.py `
  tests/unit/test_qc_agent_intent_router.py -q
python -m ruff check <本任务后端文件>
```

4. 运行前端聚焦测试、`npm run lint`、`npm run type-check`、`npm run check:encoding`。
5. 分后端出口、读取 API、前端看板三个小提交提交，避免与无关脏改动混合。
6. 获得数据库写授权后执行 `alembic upgrade head`，核对表、索引和约束。
7. 重启后端，复跑 208790、359787 两病例；按 parent root、record hash、executor、attempt、Token 与原任务统计逐项对账。
8. 使用正式管理员和演示账号分别做浏览器验收；保存截图和脱敏验收报告。
9. 最后做逐项完成度审计，确认无未覆盖生产出口后再宣称完成。

## 9. 暂停边界

本次仅新增这份进度说明文档。暂停后不继续：

- 修改业务代码；
- 暂存或提交未完成代码；
- 执行数据库迁移；
- 重启服务；
- 发起真实模型调用或病例质控。
