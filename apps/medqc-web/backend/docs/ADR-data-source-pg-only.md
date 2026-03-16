# ADR: 数据源策略 — PG 单栈读写

**状态:** 已通过  
**日期:** 2026-03-16  
**决策者:** 开发团队 + Codex 审查

## 背景

MedQC 系统在 Repository 层设计了 `DATA_SOURCE` 环境变量，
支持 `sqlite`（本地开发）和 `mongo_api`（生产 MongoDB 直读）两种数据源。

实际情况：
- `MongoApiRepository` 全部方法为 `NotImplementedError`，从未投产
- 已实现的生产数据获取链路是：**Mongo → ETL 同步 → PG**
  （`mongo_sync.py` + `sync.py` 路由）
- 业务路由（tasks/defects/appeals 等）全部读写 PG

## 决策

**统一业务读写入口为 PostgreSQL，不做运行时直连 Mongo API 切换。**

| 环境 | 数据注入方式 | 业务读写 |
|------|-------------|---------|
| Demo | mock seed 脚本写入 PG | PG |
| Prod | Mongo ETL 同步入 PG | PG |

## 具体规则

1. `DATA_SOURCE` 默认值改为 `pg`
2. `DATA_SOURCE=mongo_api` → **启动即失败**（`RuntimeError`）
3. `DATA_SOURCE=<其他非法值>` → **启动即失败**（`ValueError`）
4. `sqlite` 保留为 `pg` 的兼容别名
5. `MongoApiRepository` 类保留但标记 `[DEPRECATED]`

## 影响

- 环境变量 `DATA_SOURCE` 语义变更：从"可切换"变为"PG 唯一"
- 非法配置暴露时机从运行期提前到启动/初始化阶段
- HTTP API 路由与请求响应不受影响

## 迁移指引

如需从 Mongo 获取数据：
1. 配置 Mongo 连接（`/api/v1/sync/config/mongo`）
2. 触发同步（`/api/v1/sync/trigger`）
3. 业务代码自动读取 PG 中同步后的数据
