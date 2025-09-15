# 智慧医保质控引擎（Yibao QC Engine）开发说明

本文档为质控引擎的开发执行指南，融合现有仓库实现、我的方案与 Gemini 的建议，供实现者（如 Claude）按步骤落地。目标是提供一套前后端一致、可扩展、可观测的规则执行引擎，并与当前 yibao 项目无缝集成。

## 1. 目标与范围

- 统一规则 DSL 与执行：规则以 JSON/表结构存储，执行引擎在后端运行（本地 Python），可选云端（Supabase Edge Functions）增强。
- 可扩展：可插拔操作符（==、!=、>、>=、<、<=、in、not_in、contains、not_contains、regex、between、exists）、自定义预处理函数（如计算年龄）。
- 可视化闭环：复用已完成的规则 UI（apps/yibao-web/src/views/*）进行创建/编辑/测试，后端引擎提供沙箱与实时评估。
- 可观测：记录命中、耗时、错误、缓存命中率；提供统计接口；支持版本化与回溯。
- 双运行模式：
  - 优先 DB 表（Supabase/Postgres）；不可用时回退 JSON（apps/yibao-web/backend/medical_rules.json）。
  - 前端优先调用 Edge Functions；失败回退后端 API（参见 src/services/supabaseSdk.ts）。

不在本阶段覆盖：复杂跨会话/跨就诊的全量回放审计（可在后续批处理任务中实现）。

## 2. 现有代码与关键路径

- 前端（Vue 3 + TS + Vite）：`apps/yibao-web/src`
  - 规则 UI 与沙箱：`views/RulesList.vue`、`RulesEditor.vue`、`RuleImport.vue`、`Sandbox.vue`
  - Supabase SDK 与评估回退策略：`src/services/supabaseSdk.ts`
  - API 客户端（认证/拦截器/刷新）：`src/services/apiService.ts`
- 后端（FastAPI）：`apps/yibao-web/backend`
  - 入口与认证：`main.py`、`auth_utils.py`
  - 规则 API（CRUD/导入/导出/沙箱/统计）：`rules_api.py`
  - JSON 规则库（1173 条）：`medical_rules.json`
- 配置与代理：`vite.config.ts`（/api 代理到 8002；/rest、/fn 代理 Supabase）

## 3. 统一规则 DSL（与现有数据对齐）

为兼容仓库中不同字段风格，加载层进行“宽进严出”的字段统一，执行层使用统一模型。

- 基本字段：`code`、`name`、`rule_type`、`severity`、`enabled`、`created_at`、`updated_at`、`created_by`
- 条件表达式（兼容两种写法）：
  - 叶子：`{ fact: 'patient.age', op|operator: '>=', value: 18 }`
  - 组合：`{ all: [ ... ] }` 或 `{ any: [ ... ] }`
- 动作：`{ action_type: 'intercept'|'warn'|'notify'|'log', message_template: '患者{patient.age}岁...' }`
- 触发事件：`triggers: [ 'prescription_create' | 'prescription_update' | 'order_create' | 'order_update' | 'payment_calculate' | 'settlement' ]`
- 严重级别：`info | warn | block`

样例：
```json
{
  "code": "DRUG_AGE_001",
  "name": "药品年龄限制",
  "rule_type": "drug_age",
  "severity": "block",
  "enabled": true,
  "conditions": {
    "all": [
      { "fact": "patient.age", "operator": "<", "value": 18 },
      { "fact": "drug.category", "operator": "==", "value": "adult_only" }
    ]
  },
  "actions": [
    { "action_type": "intercept", "message_template": "患者年龄 {patient.age} 岁，不能使用 {drug.name}" }
  ],
  "triggers": ["prescription_create", "prescription_update"]
}
```

注意：仓库中的规则既有平铺 `conditions: []`（叶子列表），也有树形 `all|any` 结构。加载时需统一为树形：叶子列表视为 `all`。

## 4. 模块划分（后端 Python）

新增目录 `apps/yibao-web/backend/engine/`，模块如下：

- `dsl.py`
  - Pydantic 模型：Rule、Condition（叶/组合）、Action、Trigger
  - 字段规范化：`op|operator` 归一；叶子列表 → `all`；空值/类型转换校验
- `operators.py`
  - 操作符注册表：`== != > >= < <= in not_in contains not_contains regex between exists`
  - 可扩展注册 API：`register(name, func)`；所有比较需空值/类型安全
- `templating.py`
  - 消息模板渲染：沿用 `rules_api.py` 的 `{path}` 替换，缺失字段保持占位
- `evaluator.py`
  - 编译与执行：将条件树编译为可执行谓词（函数闭包），短路求值（all/any）
  - 决策合成：block > warn > pass
  - 输出结构：`{ decision, hits: [{code,name,severity,messages[]}], execution_time_ms }`
- `repository.py`
  - 规则来源：优先 DB 四表（`yibao_rules`、`yibao_rule_conditions`、`yibao_rule_actions`、`yibao_rule_triggers`），回退 JSON（medical_rules.json）
  - 索引：按 `triggers`、`drug.code`/`service.code` 等建立内存索引
  - 缓存：按 `rule.id + updated_at|version` 缓存编译结果，规则变更失效
- `audit.py`
  - 存储命中：写入 `yibao_violations`（不可用 DB 时降级为日志）
- `metrics.py`
  - 指标：总请求、平均/分位耗时、命中数、缓存命中率、错误率

## 5. API 设计与集成

新增 API（FastAPI 下）：

- `POST /api/engine/evaluate`
  - 入参：`{ event_type: string, context: object, rule_ids?: number[] }`
  - 出参：`{ decision: 'pass'|'warn'|'block', hits: [...], execution_time_ms: number }`
- `POST /api/engine/batch-evaluate`
  - 入参：`{ event_type: string, contexts: object[], rule_ids?: number[] }`
  - 出参：每条 context 一个结果；提供分页/切片处理
- `POST /api/engine/reload`（管理员）
  - 触发仓库刷新与缓存失效

改造现有沙箱端点以复用引擎（保持对前端兼容）：
- `/api/rules/sandbox/test` → 内部调用 `engine.evaluate`
- `/api/rules/sandbox/batch-test` → 内部循环调用或共享编译结果

认证与 CORS：沿用 `main.py` 与 `auth_utils.py`；修复已完成。

## 6. 数据库与表结构（Supabase / PostgreSQL）

沿用现有四表，并新增两表：

- `yibao_violations`（命中记录）
  - 字段示例：`id serial PK, rule_id int, rule_code text, visit_id text, severity text, message text, context_json jsonb, decision text, execution_time_ms int, created_at timestamptz default now()`
- `yibao_rule_versions`（规则快照）
  - 字段示例：`id serial PK, rule_id int, version int, rule_json jsonb, created_by text, created_at timestamptz default now()`

样例 SQL：
```sql
create table if not exists yibao_violations (
  id bigserial primary key,
  rule_id int,
  rule_code text,
  visit_id text,
  severity text check (severity in ('info','warn','block')),
  message text,
  context_json jsonb,
  decision text check (decision in ('pass','warn','block')),
  execution_time_ms int,
  created_at timestamptz default now()
);

create table if not exists yibao_rule_versions (
  id bigserial primary key,
  rule_id int not null,
  version int not null,
  rule_json jsonb not null,
  created_by text,
  created_at timestamptz default now()
);
```

## 7. 执行流程（单次评估）

1) 入口接收 `{ event_type, context, rule_ids? }`
2) 加载规则：按 `enabled && triggers` 过滤，可选按 `rule_ids` 收敛
3) 预过滤：如存在 `drug_info.drug_codes`、`service.code` 索引，用 context 快速筛选
4) 编译执行：条件树 → 谓词，短路求值；异常安全（类型/空值）
5) 决策归约：block > warn > pass；渲染消息模板（缺失字段保留占位）
6) 审计写库：`yibao_violations`
7) 返回结果与耗时

## 8. 性能策略

- 预编译与缓存：以 `rule.id + updated_at|version` 作为 key；编译产物包含字段访问路径预解析
- 索引：按事件与关键字段（`drug.code`、`service.code`、`diagnosis.code`）维护内存索引
- 并行/切片：在 `batch-evaluate` 中对 contexts 做分片评估（受限于 GIL，优先复用编译缓存与 IO 并发）
- 1173 条规则：先预过滤再评估；单请求目标 TTFB 毫秒级到几十毫秒

## 9. 错误处理与边界

- 空值与类型：所有比较运算均需空值短路与安全转换（数字比较以 `float()` 尝试，失败视为不匹配）
- 未知操作符：返回 False 并记录警告；支持扩展注册
- 模板渲染：缺失字段保留占位 `{path}`，不抛异常
- 安全：敏感字段（如身份证号）在审计存储中脱敏/过滤（可配置）

## 10. 测试计划

- 单元测试（engine 层）：
  - 操作符：每个操作符边界值、类型错误、空值
  - 表达式：all/any 嵌套、组合深度、短路行为
  - 模板：多层嵌套路径、缺失字段
  - 决策合成：多条规则混合 severities
- 集成测试（API 层）：
  - `/api/engine/evaluate`：最小上下文、复杂上下文、rule_ids 过滤
  - 沙箱端点：与现有前端联调用例
- 基准测试：
  - 1173 条规则子集与全量，记录 P50/P95

## 11. 实施计划（里程碑）

- M1 引擎核心（后端 Python）
  - engine 目录与核心模块（dsl/operators/templating/evaluator/repository）
  - 统一 DSL 解析与操作符注册；单元测试
- M2 API 与集成
  - 新增 `/api/engine/evaluate` 与 `/api/engine/batch-evaluate`；
  - 改造 `/api/rules/sandbox/*` 调用引擎；
  - 命中写入 `yibao_violations`（无 DB 时降级日志）
- M3 性能与观测
  - 预编译缓存、索引、指标采集与日志；
  - `/api/engine/reload` 热重载；
  - 边界与鲁棒性加固
- M4（可选）Edge Functions
  - 使用 `@health-qc/rule-engine` 的 TS 实现部署到 Supabase Functions；
  - 前端/后端复用相同 DSL；
  - Python 引擎作为离线/回退路径

## 12. 集成步骤（改动清单）

- 新增目录与模块：`apps/yibao-web/backend/engine/*`
- 新增 API 路由：在 `main.py` 注册 `/api/engine/*`
- 沙箱端点接入引擎：修改 `rules_api.py` 的 sandbox 路径调用 `engine.evaluate`
- 注入 Supabase：沿用目前 `main.py -> rules_api.set_supabase(supabase)` 的方式；engine 仓库层按需获取
- 数据表：如启用 DB 审计，按第 6 节建表；否则日志降级

## 13. 本地开发与验证

- 环境：Node.js 18+、Python 3.8+、Supabase（可选）
- 安装：
  - 前端：`apps/yibao-web` → `npm install`
  - 后端：`apps/yibao-web/backend` → `python3 -m venv venv && source venv/bin/activate && pip install -r requirements.txt`
- 运行：
  - 后端：`python main.py`（默认 8002）
  - 前端：`npm run dev`（代理 /api 至 8002）
- 验证：
  - `POST /api/engine/evaluate` 使用示例上下文
  - 前端沙箱页：执行规则测试；观察命中与消息渲染

## 14. 安全与合规

- 认证：沿用 JWT（`auth_utils.py`），后端端点统一 `HTTPBearer`
- CORS：在 `main.py` 已配置允许 3008/3009… 源
- 数据最小化：审计存储避免落敏感字段，必要时脱敏（可配置白名单/黑名单）

## 15. 参考与附录

- 现有文件：
  - 后端：`apps/yibao-web/backend/main.py`、`auth_utils.py`、`rules_api.py`、`medical_rules.json`
  - 前端：`apps/yibao-web/src/services/supabaseSdk.ts`、`src/services/apiService.ts`、`src/views/*`
- 相关文档：
  - `docs/database-schema.md`、`docs/rule-design.md`、`docs/qc-engine-optimization-plan.md`

---

实施者（Claude）在开始 M1 前请先对接：
- 确认 DSL 与 `medical_rules.json` 的字段差异与兼容策略；
- 确认是否启用 DB 审计（决定是否创建 `yibao_violations` 表）；
- 确认 `/api/engine/*` 返回结构是否需要附带更多调试信息（如条件命中轨迹）。

完成 M1 后，请提交：
- engine 核心模块与单元测试；
- `/api/engine/evaluate` 与示例 cURL；
- 基础性能报告（单条/批量，含 P50/P95）。
