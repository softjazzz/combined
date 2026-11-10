# 同步管理入口升级：实现与复审交接

日期：2026-11-10。状态：Draft PR #52候选，未合并、未部署。

## 基线与边界

- 分支：`codex/sync-management-integration-20261110`。
- 独占工作树：`D:/MedQC-worktrees/sync-management-integration-20261110`。
- 开工已 fetch 核实 business integration 为 `ef7551a14`；本分支直接从该提交创建，不依赖 PR #50/#51 或质控抽取修复。
- 只读参考同步服务 `C:/medqc-sync-version-recovery` 的 `b901eba8d`，以及用户提供的《MedQC-同步管理页接入交接说明-20261110.txt》。同步服务源码没有改动。
- 不复制同步页面，不使用iframe，不修改CSP，不代理任意上游路径。复用 Vue 工作台页面、业务鉴权与固定控制API适配器。

## 已实现的行为

### 服务能力与人工提交

显式检查服务时，由业务后端调用 `/v1/session` 和 `/v1/interfaces`，仅向前端投影权限、时区、完整日期上限、单次天数上限、profile日期恢复与禁用草稿能力。浏览器不接触同步令牌。

后端不再以本地时钟或硬编码7天判断人工日期范围，提交时重新读取服务能力。服务声明当前profile支持日期恢复时携带 `plan_version=2`；未声明时沿用服务旧计划合同，不猜测新能力。

人工提交保留业务操作者加operation_id派生的稳定幂等键；网络超时不自动重试，显式重试保留原范围和操作标识。服务会再次准入，不以业务页面校验代替同步服务校验。

页面改为“数据同步管理”，保留人工任务入口开关，将按钮改为“保存任务入口设置”。去掉默认链路选择的交互，不增加临床读取来源切换。仍按原组件事件通知父页使用独立同步入口，原业务库材料/PDF和临床读取配置不改。

### 日期单元详情与重试

现有GET任务详情增加受控的日期单元、阶段、状态、尝试次数、错误和计数投影；增加API客户端方法与详情抽屉。零行计数保持0，未知状态不冒充完成。

重试继续调用服务已有 `/v1/jobs/{id}/retry`，由服务决定未完成单元恢复；业务端不复制日期级恢复或队列逻辑。仅显示详情和刷新不会重试任务。

### 禁用计划草稿

业务侧仅增加查询计划与 `PUT /independent/schedule-drafts/{id}`。所有上游路径由后端固定构造；不提供创建可执行计划、PATCH、enable或disable的透传接口。

允许保存每日/每周回看设置和批准来源，profile、replay/publish与时区由后端绑定。编辑已有计划先核对profile并拒绝已启用项，使用服务端version完成CAS。保存后须确认同一计划编号、同一profile、enabled=false、next_fire_at=null，否则保持结果未确认。

草稿超时保留原UUID、version和完整内容，不自动重试；409必须先GET核对服务器版本，再由用户显式载入，不能自动覆盖。已启用计划只读显示。草稿写入未确认时阻止父面板重新检查/重载配置而丢失待确认请求。

草稿设置仍由服务端执行正式合同校验，业务端只做请求形状约束。保存禁用草稿不需要先启用人工任务入口，也不会启用自动调度。

### 权限与审计

- 沿用持久账号管理员校验（admin/sync_admin/super_admin），不信任浏览器自报角色。
- 人工提交、取消及重试要求同步令牌run权限；草稿保存要求schedule权限与schedule_drafts能力。读权限不因业务管理员身份被提升。
- 读写均绑定部署profile；同步Bearer令牌仍由后端托管，业务JWT不被发往同步服务。
- 任务提交/操作、草稿保存的成功与失败审计显式传入实际业务操作者，关联operation_id或任务/计划编号。同步服务仍只识别其令牌Actor；两层身份不混为同一用户，也没有新增跨服务身份伪造协议。
- 保留受控HTTP状态和错误码/位置等白名单，409不再被ValueError捕获误转为503；不回传原始异常、错误正文、患者正文或访问凭据。

## 代码入口

- `backend/app/services/sync_control_client.py`：会话能力、日期/计划参数、固定HTTP运输和受控详情/草稿投影。
- `backend/app/routers/data_pipelines.py`：管理员与令牌能力交集、profile绑定、禁用草稿路由与操作者审计。
- `src/api/dataPipelines.ts`：类型及详情/草稿接口。
- `DataPipelineSettingsPanel.vue`：现有管理入口扩展。
- `SyncJobDetailDrawer.vue`：任务日期单元详情。
- `SyncScheduleDraftPanel.vue`：禁用草稿、超时与版本冲突交互。

## 实际验证

后端通过项目禁网入口，HTTP只用固定应答/MockTransport；业务账号和配置验证使用内存SQLite，不连接既有库：

```powershell
# cwd: apps/medqc-web/backend
python -X utf8 scripts/run_pr8_offline_tests.py tests/unit/test_data_pipelines.py -q --tb=short
```

结果：51项通过，0失败。包含既有35项，以及服务日期/plan_version=2、畸形能力、权限交集、日期单元脱敏、草稿CAS与审计、拒绝已启用/其他profile、409不吞掉不重试、无启用路由及畸形保存状态保护。

前端只运行 `tests/unit/views/workstation-v4/DataPipelineSettingsPanel.spec.ts`：15项通过。实际挂载页面及两个子组件，覆盖打开不提交、日期上限与只读权限、原人工幂等操作、单元详情、禁用草稿、超时原请求重试、409后显式载入、已启用只读和待确认请求不被重载丢失。无HTTP请求。

相关四个源码文件的独立vue-tsc项目通过；修改文件ESLint、后端Ruff F、UTF-8无BOM/LF与diff检查通过。共享依赖根缺少vue-eslint-parser链接，ESLint临时配置只将同版本已有解析器改为绝对导入，规则与仓库配置一致；未安装或修改其他工作树依赖。测试Vite缓存位于本工作树临时目录。

未运行全量质量门、完整前端测试或构建、PG矩阵、真实浏览器或医院HTTP验收。未修改CI配置；本轮不以固定应答证明实际同步吞吐或质控材料就绪。

## 部署前待验收

1. 只读核对现场同步服务实际版本和 `/v1/session`、部署profile、令牌权限与日期恢复能力，不假定本机参考提交等于现场。
2. 核对业务管理员和审计日志留存、固定API地址、令牌托管及必要网络可达性。令牌不进聊天或浏览器。
3. 确认人工任务入口仍由管理员明确启用，草稿保持禁用。页面没有计划启用能力，不能由此认定现场所有既有计划均被关闭。
4. 另行授权后再安排现场任务冒烟。本轮没有向真实API提交任务、重试任务或保存草稿。
5. 同步任务成功不是临床全接口一致发布/取材就绪证明；不据此自动创建质控任务。

本轮不修改同步数据库、临床数据库或业务库，不迁移数据库，不修改现场配置，不调用模型、不重跑27份，也不涉及0916。


## PR #52 独立复审补修（基于8ea205feb）

本次只修固定提交复审确认的两项功能P2、抽屉布局和两个新组件的外置样式，不扩展同步服务或权限合同。

- 发布单元按正式服务合同保留result.selected/written顶层整数，包含0；不与抽取counts混为一个字段。前端对应展示待发布行数和实际写入行数，缺失/非法值显示未返回，不伪造0。
- 草稿响应必须明确包含next_fire_at。字段缺失返回受控502，不补成null；显式null仍沿用正常禁用保存路径。前端502时保留原UUID/version/内容。
- 草稿创建、编辑和409冲突确认移入Ant Design抽屉；写入或结果未确认期间关闭按钮、遮罩和Esc关闭均禁用，close事件也有状态保护。版本载入仍需用户明确操作。
- SyncJobDetailDrawer和SyncScheduleDraftPanel的私有样式移到各自styles/*.css，以style scoped src引入；不改变全局主题或其他页面。

必要验证：后端test_data_pipelines.py 55项通过，前端DataPipelineSettingsPanel.spec.ts 18项通过；原独立复审3条API探针原样复跑为3项通过（与主保护语义重叠，不累计为额外覆盖）。定向vue-tsc、修改范围ESLint、Ruff F、编码及diff检查通过。前端验证使用抽屉替身验证属性/事件，没有真实浏览器截图验收。

未在本地重复全量质量门或PG矩阵。8ea205feb此前四项CI通过为旧Head证据，本次新Head须单独核对CI，不能据旧记录称新修复已全绿。未修改CI配置，未连接任何真实业务库、同步服务或模型，未重跑27份。
