# Workstation V4 数据同步控制台验收清单（P0）

> 目标：确认 `workstation-v4/system-config` 数据同步控制台满足上线要求（无 Mock、权限正确、链路可用、可回退）。

## 1. 验收范围

- 页面入口：`/workstation-v4/system-config?tab=dataSync`
- 后端主归口：`/api/v1/sync/*`
- 旧入口：`/dashboard/settings?tab=data_sync`（应跳转至 V4）

## 2. 环境准备

- 准备 2 个账号：

1. `admin`（可读可写可执行）
2. `qc_manager`（只读）

- 准备连通性状态：

1. Mongo 可连
2. PG 远端可连
3. PG 本地可连

## 3. 页面级验收

### 3.1 控制台加载

- 打开 V4 系统配置页，默认显示“数据同步配置”页签。
- 页面卡片（连通状态/上次同步/待处理/异常）有真实数据。
- 不出现演示静态字段或 Mock 文案。

### 3.2 连接配置区（ConnectionStudio）

- `Mongo 源`：

1. 可编辑 URI/库名/读偏好/超时
2. 点击“保存并测试”后有真实结果反馈

- `前端 PG`：

1. 可编辑主机/端口/库名/用户名/密码
2. 保存后返回连通性结果

- `本地库`：

1. 只读不可编辑
2. 可测试连通性

### 3.3 策略配置区（SyncPolicyPanel）

- 字段可正常加载并展示当前配置值。
- `admin` 可保存策略。
- `qc_manager` 只能查看，按钮禁用。

### 3.4 概览与动作（SyncOverviewBar）

- `测试全连接` 调用聚合测试并展示 3 源状态。
- `试运行` 调用预检并展示可执行性/阻断项/告警/预计影响。
- `执行同步` 仅在预检通过后可点击。
- 高风险提示可触发：

1. Tier3 夜间窗口外二次确认
2. 存在失败记录二次确认

### 3.5 结构与映射

- `SchemaExplorer` 显示真实 schema 与样本数据。
- `FieldMappingWorkbench` 显示真实只读映射列表（非演示数据）。

### 3.6 运行面板（SyncRunPanel）

- 实时日志可见、可清空。
- 执行中状态可见，完成后自动停止轮询。
- 运行历史可查看并按 `source/tier` 过滤。

## 4. 接口级验收（建议用 Postman/Apifox）

## 4.1 GET（admin + qc_manager）

- `GET /api/v1/sync/status` -> 200
- `GET /api/v1/sync/statistics` -> 200
- `GET /api/v1/sync/config/mongo` -> 200
- `GET /api/v1/sync/config/pg` -> 200（密码脱敏）
- `GET /api/v1/sync/mappings` -> 200
- `GET /api/v1/sync/runs` -> 200

## 4.2 写操作（仅 admin）

- `PUT /api/v1/sync/config/mongo` -> 200（字段校验生效）
- `PUT /api/v1/sync/config/pg` -> 200
- `POST /api/v1/sync/test-connection/*` -> 200
- `POST /api/v1/sync/test-connection/all` -> 200
- `POST /api/v1/sync/preflight` -> 200
- `POST /api/v1/sync/trigger` -> 200

## 4.3 权限矩阵

- `qc_manager` 调用任一写接口应返回 403。
- 未登录/无角色调用读接口应返回 401/403。
- 仅前端禁用不算通过，必须后端拒绝生效。

## 5. 并发与幂等

- 在同步执行中再次触发 `trigger`：

1. 返回明确拒绝信息（如“同步正在进行中”）
2. 不重复启动任务
3. 不写入误导性历史记录

## 6. 兼容与回归

- 旧入口 `/dashboard/settings?tab=data_sync` 自动跳转至 V4 页。
- `/api/system/db/config` 仍可用于历史兼容调用，不影响新入口。
- 不改动正式业务表结构，不影响既有同步引擎。

## 7. 通过标准（上线门槛）

- V4 页面核心卡片和按钮全部由真实接口驱动。
- admin 可完成完整链路：配置 -> 全连接测试 -> 预检 -> 执行 -> 查看日志/历史。
- qc_manager 全程只读，无法通过后端写配置或触发执行。
- 旧入口仅跳转，不再承载旧版业务逻辑。
- 验收过程无阻断级缺陷（P0）。
