# PR8 独立评审修复与目标线适配边界

## 范围与归因

本轮在 `codex/v36-v5-reports-draft-20261023` 修复独立评审的两项 P1 机构授权缺口及一项 P2 导出竞态；机构缺口和导出问题均继承自快照，不能记为本批最初接入时新引入。固定 base `codex/v36-report-review-base-20261023` 保持 `8c56466e9`，修复起点为 `f761e08b0`。只更新 Draft head，不合并、不部署、不打包、不执行实际库迁移或质控、不调用模型。80 项账本不因此提升。

功能修复提交：`e47f98a21`（机构授权）与 `cf9366e1f`（导出竞态）。原 PR 的 V5 四报表接入、待办修复和首批 V7.1 对齐范围仍见 `2026-10-23-v36-v5-reports-draft-pr.md`；本轮没有修改 Layout、导航配置、Token 或公共组件样式。

## 已修复

- 共用的 `report_institute_scope` 沿用 `_person` 与 `user_scope_owner` 读取可信持久账号，拒绝停用、缺失或角色配置损坏的账号；只有持久 `admin` 可全局读取，`qc_manager` 必须有可信机构。HTTP 声明的机构或角色不能扩大该范围。
- 人工待审计数、分页列表、病例读取及单条审核均加入同一机构谓词；越权病例读取拒绝，其他机构单条审核按不存在处理。CAS、禁止自审及历史同事务不变。新旧待办共用 helper 传入认证 ID，无权限仍为 null，来源不可用及读取失败仍保留原失败语义，不回退旧全院统计或归零。
- 病历质量及首页质量的共同 context owner 验证账号后再读取范围。病历池、已同步未生成首页的登记补充来源和现代首页结果在 SQL 中加入机构过滤；装配时再按机构校验输入，防止注入的来源扩大范围。统计、分页、下钻及 CSV 均消费同一受限 context。复用该 context 的既有指标入口只透传认证 ID，没有新增指标计算或恢复暂停范围。
- 两个报表的导出固定参数、列和文件名，并核对请求序号、身份/机构/角色/科室及筛选指纹。筛选、场景、身份变化、刷新或卸载废弃旧响应；旧请求不下载、不报旧错误、不清除新请求的 loading。当前失败可见，成功和失败都释放当前 loading。身份切换也清空旧汇总和下钻，阻止其延迟响应回写。

## 测试证据

- 后端最终聚焦 18 文件：286 passed、5 skipped、4 条既有依赖告警。新增机构合同含真实 SQLite 账号、缺陷与病历池查询、现代首页排名 SQL 谓词、同患者/就诊号跨院、HTTP 伪造 admin/机构、缺机构/停用/角色损坏、全局管理员、统计/下钻/CSV 同范围及未知值保持。不是仅 mock router 回执。
- 前端最终聚焦 15 文件：195 passed。新增 16 项延迟 Promise 用例先得到 14 failed / 2 passed，修复后全部通过，含场景/筛选/用户/机构/角色/卸载、旧拒绝与新 loading、当前错误及固定文件名。
- 原 PostgreSQL opt-in 测试同步为持久合成账号，并在其原有授权清理流程中清理这些账号；本轮没有运行其数据库路径，5 项明确 skip，不称 PG 并发验证。
- `run_pr8_offline_tests.py` 禁用 dotenv 文件来源、拦截网络并拒绝非 SQLite 连接，仅给旧 persistence 导入提供空内存会话工厂。Windows asyncio 的标准库 socketpair 唤醒管道是唯一网络 guard 例外，不开放应用本地服务访问。
- 首次普通 pytest 只清空 DSN，尚未完整禁用 dotenv，且在旧 persistence 导入处失败；该次不是完整凭据隔离运行，不能声称全程未加载 dotenv。没有建立实际库连接或调用模型。初版离线 guard 又误挡 Windows 内部 socketpair，导致 HTTP/asyncio 夹具失败；修正夹具后复跑通过，没有删除测试或放宽业务断言。
- 首次类型检查发现新增测试的 mock instance 推导为 void；改为在带明确 this 类型的点击 spy 中记录文件名，后续完整类型结果及静态检查见本轮 PR 更新记录。
- 最终完整 `npm run type-check`、全 src 及修改测试的只读 ESLint、23 个 Python 文件 Ruff、分批暂存编码/敏感信息及 diff 检查通过。敏感门禁指出既有异常脱敏测试的假 DSN 形态，把它换成明确 example 占位值后该文件 53 项再次通过，断言未删。未重跑全仓 pytest/Vitest，不用聚焦通过代替真实患者或目标线验收。

最终后端命令（在 backend 目录；所有参数均明确列出，不运行全仓）：

```powershell
py -3.10 scripts/run_pr8_offline_tests.py tests/unit/test_v5_report_institute_scope.py tests/unit/test_record_quality_report_service.py tests/unit/test_frontpage_quality_report_service.py tests/unit/test_manual_defect_review_service.py tests/unit/test_manual_defect_reviews_api.py tests/unit/test_manual_review_todo_scene_contract.py tests/unit/test_dashboard_review_todos_api.py tests/unit/test_dashboard_todo_truth.py tests/unit/test_dashboard_todo_stats_failure.py tests/unit/test_quality_reports_api.py tests/unit/test_frontpage_quality_reports_api.py tests/unit/test_modern_case_qc_result_service.py tests/unit/test_luxian_0609_result_analysis_service.py tests/unit/test_medical_record_indicator_service.py tests/unit/test_medical_record_indicators_api.py tests/unit/test_core_system_report_service.py tests/unit/test_core_system_report_api.py tests/unit/test_manual_defect_review_pg_integration.py
```

最终前端命令（在应用目录）：

```powershell
npx vitest run src/views/qc/reports/__tests__ src/components/icons/__tests__/MqIcon.spec.ts tests/unit/components/layout/WorkstationLayout.spec.ts tests/unit/router/workstation-report-routes.spec.ts tests/unit/router/route-access-guard.spec.ts src/api/__tests__/dashboard-review-todos.spec.ts --maxWorkers=1 --minWorkers=1
```

## 合成浏览器验证

独立 Vite 3031、独立测试标签页，通过拦截 API 返回合成登录/报表；不使用用户 3011 的账号口令，不以此证明真实认证或数据库授权。两个报表均验证当前 CSV 下载正例；分别暂停一份有效导出请求，修改科室后返回该 CSV，确认没有下载事件且按钮可再次使用。两者下钻均显示一份合成病历；390px 动画稳定后页面 scrollWidth=390，抽屉边界为 0 至约390.4px（子像素取整），无页面横向溢出。保留桌面/窄屏截图到忽略的 `.tmp/0910-full-audit/pr8-*-private.png`。

旧 Dashboard 直接报表链接也能挂载、显示合成汇总；1280px 下 scrollWidth=1265，不作全站视觉回归结论。未配置的整改/版本来源明确返回不可用，不以合成空结果掩盖。早期拦截夹具的响应包和事件游标/共享状态不匹配已纠正，导出证据只采用最终确实暂停、成功响应且有下载正例对照的运行。测试标签页和3031进程已关闭，视口模拟已恢复，原3011标签页及8011服务未操作。没有真实患者验收或业务库部署证据。

## V7.1 目标线只读核对

复核对象为远端 `codex/business-agent-integration=8c005ee08`，本轮未修改其引用或任何业务工作树。与修复起点分别有857/337个独有提交，不能只挑最初五提交就称可运行。

`git merge-tree --write-tree --name-only --no-messages github/codex/business-agent-integration f761e08b0` 返回1，确认 Layout、MqIcon、MqIconTile、mqIcons、mq-components 及多处后端/路由存在显式冲突。该命令只计算临时 Git tree 对象，不更新 index、工作区、分支或数据库；不把冲突称作“自动静默覆盖”。

文件处理清单：

| 类别                                          | 后续隔离适配分支的处理                                                                                                                                                                                    |
| --------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| WorkstationLayout.vue / workstationNav.ts     | 保留目标线；定向增加报表菜单与匹配规则，不移植 gap 外壳。保留 GlobalAssistantHost、WorkstationConfirmDialog、WORKSTATION_CONFIRMATION provide、DRG 页内切换、导航选中与面包屑、手术分级目录及规则验收入口 |
| main.ts / tokens-v2.css / workstationTheme.ts | 被比较两端相同，不重复移植                                                                                                                                                                                |
| MqIcon.vue / MqIconTile.vue                   | 保留目标线，格式差异不作为覆盖理由                                                                                                                                                                        |
| mqIcons.ts                                    | 保留目标线并集；gap 文件缺少目标已有 failed / pending，不能整文件替换                                                                                                                                     |
| mq-components.css                             | 只定向讨论 minmax(0,1fr)、min-width 的收缩修复；不整文件替换，也不夹带全局字距改动                                                                                                                        |
| 报表 Vue / API / 路由 / 测试                  | 在后端前置依赖接通后定向移植，并在目标 Layout 中重新验收权限、主题、抽屉、导出和多视口                                                                                                                    |

最小依赖清单：目标线静态路径核对缺少 record_quality_report_service、frontpage_quality_report_service、record_review_service、manual_defect_review_service、scoring_standard_service、scoring_service、rule_set_version_service、modern_case_qc_result_service 和 user_scope_owner；新增 report_institute_scope 同样不存在。需连同相应 router 注册、DTO/API、持久账号机构字段、审核/历史模型、规则版本与评分模型，以及 Canonical 已保存结果读取合同一起梳理。文件存在也不表示方法签名、来源、结果轮次或 schema 已兼容。禁止整条 gap 历史覆盖目标业务 owner。

## 迁移建议与未验证项

快照 migration head 是 `20261003_000084`；被比较业务线为 `20261020_000050`，共同祖先为 `20260915_000044`，之后分叉。本轮没有迁移增量。直接并存文件会形成双 head；单加 merge revision 也不能自动解决列/约束/数据 owner 冲突。后续应在独立适配分支先列两侧 DDL、schema 与数据前置条件，对冲突写明确兼容迁移，在完全合成空库验证两种升级路径，再以双方 head 的 down_revision 元组衔接。不得删除目标迁移、stamp 或用业务库试升级。本轮不生成未经验证的合并迁移。

“每次读取最新结果”的合同已复核：每个请求内 context 将汇总/下钻/导出限定于同一组结果，但不同 HTTP 请求会重建 context；普通明细没有返回全部轮次锚点。因此不承诺跨请求固定汇总时那一轮，也没有已发生跨院或跨轮串账的证明。本轮不引入任意旧轮回查。若业务需要固定快照，须另行定义服务端结果 ID/来源/三坐标与权限绑定的快照合同，不能用客户端轮次参数绕过最新结果校验。

本轮只修本 Draft，没有实施目标线适配、迁移衔接或目标运行时回归。导航/助手/确认框保留项是只读静态核对，不是已运行的目标线浏览器测试。未推送的本地业务线内容不可由本次远端比较证明；不能承诺“完全无覆盖风险”。建议继续保持 Draft，另建隔离适配分支处理依赖与上述明确冲突，不能直接改本 PR base 为业务线后合并。
