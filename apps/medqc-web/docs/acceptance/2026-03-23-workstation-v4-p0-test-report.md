# Workstation V4 P0 验收实测报告（阶段稿）

## 1. 验收信息

- 验收日期：2026-03-23
- 验收环境：本地开发环境（Windows + PowerShell）
- 验收分支 / Commit：`demo-backend-support` / `615b7cd0`
- 验收人：Codex（阶段执行）
- 说明：本报告为阶段收口稿，`npm run build` 与部分业务指标需统一回归窗口补测。

## 2. 范围确认

- P0 主线：
  - `4.1.2 病案问题概览`
  - `6.2.2 分组器本地化完整交付`
- 不修改“已完成/基本完成”措辞，仅补执行证据与验收口径。

## 3. 基础校验

### 3.1 TypeScript 校验

- 命令：`npx vue-tsc --noEmit --pretty false`
- 结果：通过
- 结论：通过

### 3.2 生产构建

- 命令：`npm run build`
- 结果：未在本轮完成留档（用户要求后续统一执行，避免长时阻塞）
- 结论：待补测

## 4. 4.1.2 病案问题概览专项

### 4.1 功能链路

- 已实现能力：
  - 当天问题聚合接口：`GET /api/v1/notifications/overview`
  - 概览视图与明细视图切换
  - 概览筛选（科室/类型/严重度）
  - 概览点击定位处理与已读联动
- 代码证据：
  - `backend/app/routers/notifications.py`
  - `src/views/workstation-v2/composables/useNotifications.ts`
  - `src/views/workstation-v2/WorkstationV4View.vue`
  - `src/views/workstation-v2/types.ts`

### 4.2 自动化验证

- 单测：`tests/unit/test_notifications_overview_router.py`
- 结果：通过
- 结论：接口契约通过

### 4.3 指标验收

- 当日问题聚合时效（P95 <= 60s）：待补测（需压测/采样脚本）
- 概览点击跳转成功率（>=99%）：待补测（需前端链路采样）
- 未读状态准确率（>=99%）：待补测（需业务样本回放）

## 5. 6.2.2 分组器本地化专项

### 5.1 功能链路

- 已实现能力：
  - 配置读取/保存/发布/版本列表/版本详情/回滚
  - 审计字段：`version_id/operator/operated_at/change_summary`
  - 一致率校验接口与差异明细
  - 前端 `GrouperConfig` 改为真实 API 驱动，并保留开发 Mock 开关
- 代码证据：
  - `backend/app/routers/drg.py`
  - `backend/app/services/drg_config_store.py`
  - `src/api/drg.ts`
  - `src/views/drg/GrouperConfig.vue`

### 5.2 自动化验证

- 单测：`tests/unit/test_drg_config_router.py`
- 结果：通过
- 结论：接口契约通过

### 5.3 指标验收

- 配置保存/发布/回滚全通过：接口单测通过，需补业务联调截图/日志
- 版本审计字段齐全可查：接口单测通过，需补查询留档
- 对照一致率 >=95%：口径已固化，需补真实样本实测值

## 6. 样本与口径固化（C3）

- 文档：`docs/acceptance/drg-consistency-sample-spec.md`
- 结论：
  - 样本来源、字段格式、匹配键已固化
  - 统计公式已固化：`一致率 = 匹配成功样本数 / 有效对照样本数`

## 7. 失败样本与复现步骤

- 当前状态：无阻断性失败样本归档（阶段执行）
- 待补项：
  - 统一回归窗口内记录失败样本ID、复现步骤、日志/截图路径

## 8. 当前结论

- 开发完成度：A0/B1/B2/C1/C2/C3 已完成
- 验收完成度：D1 部分完成（模板、证据、单测完成；业务指标与 build 留档待补）
- 最终判定：阶段通过（待统一回归补齐后出最终“通过/不通过”结论）

## 9. 待执行清单（统一回归窗口）

执行脚本：`scripts/run-workstation-v4-p0-acceptance.mjs`  
可选参数：`--skip-build`（跳过 build）  
可选环境变量：`PYTHON_BIN`（指定 pytest 解释器路径）

1. 执行并留档 `npm run build`
2. 执行 4.1.2 三项业务指标采样并填报
3. 执行 6.2.2 真实样本一致率测算并填报
4. 归档失败样本（如有）与复现步骤
