# 首批 subagent 分工表

## 1. 文档目的

- 本文档用于定义第一轮并行推进时的 subagent 分工边界。
- 目标不是把任务切得越碎越好，而是保证：
  - 关键路径不断
  - 不同 agent 不撞同一领域模型
  - 不误改现有脚本
  - 输出结果能直接汇总进主线实施

## 2. 总体建议

第一轮建议同时开启 `4 个 subagent`，上限 `5 个`。

推荐首轮并行：

1. 病历主链路 agent
2. 统计与 Dashboard 口径 agent
3. 认证与账户 agent
4. 规则基线接入 agent

可选第 5 个：

5. 任务调度 agent

## 3. 共同行动约束

所有 subagent 都必须遵守：

- 基于 `workstation v4` 现有前后端增量开发。
- 允许新增页面、接口、聚合层、配置和数据模型。
- 默认不改现有项目前后端脚本。
- 如果需要改：
  - 启动脚本
  - 构建脚本
  - 发布脚本
  - 部署脚本
  - 联调脚本
  必须人工确认。
- 数据基座固定为：
  - `PG`
  - `Redis`
  - `Celery + Redis`
- 规则基线固定为库里现有的 `四川省 146 条质控规则`。
- 所有前端 subagent 默认使用 `frontend-skill`。
- 前端相关页面方案、组件实现、信息层级和视觉结构，优先按 `frontend-skill` 的工作方式推进。
- 如果前端 agent 认为需要偏离 `frontend-skill`，必须先说明原因再调整。

## 4. Agent 清单

### Agent-A 病历主链路

#### 目标

- 拉通 `门急诊 / 运行 / 终末` 病历质控主链路。
- 明确列表、详情台、筛选模板、自定义列的页面与接口边界。
- 前端部分默认使用 `frontend-skill`。

#### 负责范围

- 门急诊病历页
- 病历详情审核运营台
- 筛选模板
- 自定义列
- 门急诊查询接口
- 病历详情聚合接口

#### 输入

- [实施路线图-页面与接口优先级.md](D:/LLM/lx0222/health-qc-monorepo/apps/medqc-web/docs/gap/实施路线图-页面与接口优先级.md)
- [数据源与统计口径说明.md](D:/LLM/lx0222/health-qc-monorepo/apps/medqc-web/docs/gap/数据源与统计口径说明.md)

#### 输出

- 门急诊列表页实施方案
- 详情台接口草案
- 列表筛选与列配置的数据结构建议
- 涉及文件清单与风险点

#### 禁止触碰

- 认证模型
- 规则模型
- 调度器实现
- 现有项目脚本

#### 推荐写范围

- `src/views/dashboard/records/*`
- `src/components/*records*`
- `backend/app/routers/*records*`
- `backend/app/services/*detail*`

### Agent-B 统计与 Dashboard 口径

#### 目标

- 冻结 `all / outpatient_emergency / running / final` 四类场景口径。
- 拉通 Dashboard 与统计分析的一致聚合逻辑。
- 前端部分默认使用 `frontend-skill`。

#### 负责范围

- Dashboard 场景分类
- 待办统计口径
- 工作表现口径
- 统计分析一期接口
- 统计页面的数据映射

#### 输入

- [数据源与统计口径说明.md](D:/LLM/lx0222/health-qc-monorepo/apps/medqc-web/docs/gap/数据源与统计口径说明.md)
- [Epic启动包.md](D:/LLM/lx0222/health-qc-monorepo/apps/medqc-web/docs/gap/Epic启动包.md)

#### 输出

- Dashboard 聚合口径说明
- 统计一期接口清单
- `STAT-02A` 的实现建议
- 真实数据替换 Mock 的落地路径

#### 禁止触碰

- 登录页实现
- 规则后台领域模型
- 调度器基础设施
- 现有项目脚本

#### 推荐写范围

- `backend/app/routers/dashboard_api.py`
- `backend/app/routers/reports.py`
- `src/views/statistics/*`
- `src/api/statistics-api.ts`
- `src/api/dashboard.ts`

### Agent-C 认证与账户

#### 目标

- 完成 `users_db -> 持久化账户表` 迁移方案。
- 明确 `用户名/手机号 + 密码` 的统一登录入口。
- 如果涉及登录页前端实现，默认使用 `frontend-skill`。

#### 负责范围

- 账户表设计
- 登录请求模型
- `account` 登录标识
- 用户名/手机号唯一约束
- 旧 `email` 语义兼容迁移

#### 输入

- [认证改造方案.md](D:/LLM/lx0222/health-qc-monorepo/apps/medqc-web/docs/gap/认证改造方案.md)
- [开工边界说明.md](D:/LLM/lx0222/health-qc-monorepo/apps/medqc-web/docs/gap/开工边界说明.md)

#### 输出

- 账户表字段清单
- 认证接口改造方案
- 前端登录页交互建议
- 数据迁移方案

#### 禁止触碰

- 业务统计口径
- 门急诊列表与详情台
- 规则内容
- 现有项目脚本

#### 推荐写范围

- `backend/app/routers/auth.py`
- `backend/app/schemas/auth.py`
- `backend/app/database/models/qc.py`
- `src/views/auth/*`
- `src/stores/*auth*`

### Agent-D 规则基线接入

#### 目标

- 以四川省 146 条规则作为第一阶段规则基线。
- 明确这些规则如何映射到新的规则后台模型。

#### 负责范围

- `sichuan_rules_146.json` 结构梳理
- 规则到 `rule_item` 的映射
- 规则到 `qc_point` 的映射策略
- 规则分组、场景、文书绑定建议

#### 输入

- [规则后台数据模型草图.md](D:/LLM/lx0222/health-qc-monorepo/apps/medqc-web/docs/gap/规则后台数据模型草图.md)
- [sichuan_rules_146.json](D:/LLM/lx0222/health-qc-monorepo/apps/medqc-web/backend/app/data/sichuan_rules_146.json)

#### 输出

- 四川 146 条规则接入方案
- 初始化入库字段映射表
- 规则分组建议
- 与质控点关系建议

#### 禁止触碰

- 登录与认证
- Dashboard 统计口径
- 调度器实现
- 现有项目脚本

#### 推荐写范围

- `backend/app/data/sichuan_rules_146.json`
- `backend/app/routers/scoring_rules.py`
- 新规则后台模型文档或初始化脚本

### Agent-E 任务调度

#### 启用条件

- 只有在第 5 个 subagent 需要开启时再启用。

#### 目标

- 明确 `qc_tasks + qc_async_jobs + Redis + Celery` 的调度闭环。

#### 负责范围

- 定时任务执行器
- Celery Worker / Beat 接入
- `schedule_config` 结构
- 重试、死信、幂等、锁

#### 输入

- [任务调度技术方案.md](D:/LLM/lx0222/health-qc-monorepo/apps/medqc-web/docs/gap/任务调度技术方案.md)
- [实施路线图-页面与接口优先级.md](D:/LLM/lx0222/health-qc-monorepo/apps/medqc-web/docs/gap/实施路线图-页面与接口优先级.md)

#### 输出

- 调度实现草案
- 任务状态机建议
- Worker/Beat 部署清单
- 与 `qc_tasks` 的映射关系

#### 禁止触碰

- 规则内容建模
- 登录页与账户模型
- 门急诊业务页面
- 现有项目脚本

#### 推荐写范围

- `backend/app/routers/tasks.py`
- `backend/app/services/async_job_store.py`
- 新增 Celery 配置模块
- 新增 worker/beat 启动入口

## 5. 推荐并行顺序

### 第一批同时启动

- Agent-A
- Agent-B
- Agent-C
- Agent-D

### 第二批按需启动

- Agent-E

原因：

- 前 4 个分别占据不同领域，冲突最小。
- 调度器虽然重要，但不是所有人第一分钟都依赖它。
- 先把主链路、统计口径、认证、规则基线定住，再开调度器最稳。

## 6. 汇总节奏建议

### 第一次汇总

- 在 4 个首批 agent 都输出各自方案后进行。
- 汇总内容：
  - 冲突点
  - 共享枚举
  - 共享模型
  - 高风险依赖

### 第二次汇总

- 在 Agent-E 输出调度方案后进行。
- 汇总内容：
  - 任务链路是否需要新增表
  - 调度状态是否影响页面口径
  - 是否触发脚本变更审批

## 7. 不建议的拆法

- 不要两个 agent 同时研究规则后台模型。
- 不要两个 agent 同时改 Dashboard 统计口径。
- 不要在认证方案未冻结前让前端 agent 直接改登录实现。
- 不要把“页面设计”和“同一页面真实接口”拆给两个 agent 同时改。

## 8. 主控 Agent 的职责

主控 agent 不应把关键路径完全外包，应该保留：

- 范围控制
- 文档合并
- 依赖冲突处理
- 统一 Jira 拆分
- 最终实施顺序裁决

subagent 负责产出局部结果，主控 agent 负责整合。

对于前端相关 subagent，主控 agent 还应额外检查：

- 是否明确使用了 `frontend-skill`
- 是否沿用现有产品语言而不是生成演示态页面
- 是否避免引入与 `workstation v4` 不一致的多余前端基础设施

## 9. 一句话建议

第一轮最稳的并行方式是 `4 个核心 subagent + 1 个可选调度 subagent`：病历主链路、统计口径、认证、规则基线先并行，调度器按需插入，不要一开始就让多个 agent 撞在同一层模型和同一批脚本上。
