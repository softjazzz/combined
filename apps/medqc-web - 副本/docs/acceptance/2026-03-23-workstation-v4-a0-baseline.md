# Workstation V4 A0 基线冻结（2026-03-23）

## 1. 基线口径

- PRD 基线：`docs/PRD-泸县验收收尾.md`
- 交付主线：`4.1.2 病案问题概览`、`6.2.2 分组器本地化适配`
- 代码快照日期：2026-03-23
- 证据优先级：代码/接口 > 历史文档描述

## 2. PRD 条款矩阵（关键项）

| 条款                   | 代码证据                                                                                           | 当前状态                 | 缺口                                       |
| ---------------------- | -------------------------------------------------------------------------------------------------- | ------------------------ | ------------------------------------------ |
| 4.1.2 病案问题概览     | `backend/app/routers/notifications.py`、`src/views/workstation-v2/composables/useNotifications.ts` | 已有通知明细、已读流程   | 缺“当天集中点聚合视图与接口契约”           |
| 6.2.2 分组器本地化适配 | `src/views/drg/GrouperConfig.vue`、`src/api/drg.ts`、`backend/app/routers/drg.py`                  | 页面存在但原为 Mock 主导 | 需配置中心、版本发布回滚、一致率校验与审计 |

## 3. B/C 写入边界

- B 链（4.1.2）：
  - 可写：`backend/app/routers/notifications.py`、`src/views/workstation-v2/composables/useNotifications.ts`、`src/views/workstation-v2/WorkstationV4View.vue`
  - 禁写：`backend/app/routers/drg.py`、`src/views/drg/GrouperConfig.vue`、`src/api/drg.ts`
- C 链（6.2.2）：
  - 可写：`backend/app/routers/drg.py`、`backend/app/services/drg_config_store.py`、`src/api/drg.ts`、`src/views/drg/GrouperConfig.vue`
  - 禁写：V4 assist 面板相关文件

## 4. 回滚边界

- B 回滚边界：仅回滚通知聚合接口与 V4 消息页概览 UI，不影响通知明细接口。
- C 回滚边界：仅回滚 `drg config` 路由与配置中心页面，不影响 `drg/predict`、`drg/statistics` 等既有路径。
