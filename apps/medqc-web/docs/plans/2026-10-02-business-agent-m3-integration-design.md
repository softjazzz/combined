# 业务助手 M3 辅助整合与 M2 复用调查

日期：2026-10-02。范围：当前独立工作树源码核查；未运行模型、Embedding、浏览器或写数据库。路由/组件存在不代表已接入助手，也不代表实际医院权限验证通过。

## 1. 结论与最低成本顺序

优先在现有病历详情父组件内增加受控面板切换，而非拼接未被目标页消费的 URL query。助手病例三坐标必须与当前详情严格相等才能切换；首页助手没有完整病历对象，暂不能沿用详情页全局选中患者。管理汇总日期是质控完成时间，不能直接转成通知日期、出院日期或 DRG 结算日期。

1. 只读编码字典查询：复用真实 GET 查询与独立抽屉，明确只是编码检索，不自动应用编码。不依赖患者材料，但展示当前患者时须固定三坐标并清理切换中的候选。先确认真实模式，避免默认 Mock。
2. 同病例画像面板：复用已有组件前先修请求代次/取消和病例标识传递；仅打开面板不自动运行模型。保留助手会话、当前卡片与返回位置。
3. 已有报告展示/导出：先确定报告类型与生成来源。首页报告草稿不是科室质量分析报告；不能把二者混成一个“分析报告”。可先导出已确认的同一汇总，但必须保留原统计期间、机构/科室、数据时间与口径，不刷新统计。
4. 通知收件箱只读接入与主动订阅分开；订阅和 EMR 外部接入暂缺执行合同。

本次仅交付调查设计，未新增无人调用的适配模块，未修改正在验收的 Drawer/API。实现入口需与主协调确认宿主事件及所有者，避免与当前浏览器验收冲突。

## 2. 真实调用链与上下文边界

| 能力        | 已核实入口/接口                                                                                                                                                                                                | 当前上下文事实                                                                                                                                                   | 最小实施与限制                                                                                                                   |
| ----------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------- |
| 画像        | `WorkstationV4View.vue::openAiProfilePanel` 先 ensureFullDocumentsLoaded，再打开 `WorkstationV4AssistView.vue` 的画像 Modal；`AIProfileDashboard.vue::analyzeProfile` POST `/api/v1/frontpage/profile/analyze` | 当前请求发 medical_text、首页诊断与手术，不带机构/患者/住院三坐标。medicalText watch 清结果，但 fetch 回来没有代次验证/AbortController；切患者后旧响应仍可能写入 | 先修 A→B 迟到响应隔离；完整材料读取失败不能标成分析已完成；接入时固定 scopeKey，结果需同时匹配三坐标及材料版本                   |
| 编码/DRG    | `WorkstationV4AssistView.vue` 的 qc 插槽 coding 分页与 ICD 抽屉；`src/api/drg.ts::searchICDCodes` GET `/api/v1/coding/search`；suggestCoding、validateCoding、predictDRGGrouping 等既有方法                    | 字典请求只含 keyword/category/limit；应用编码通过 `apply-icd-code` 事件，具有修改语义。drg.ts 第44行默认 Mock，只有 VITE_USE_DRG_MOCK 显式 false 才使用真实接口  | 先只开放真实字典只读查询；不把模拟候选或入组预测当正式业务结果；应用编码需另走正式确认流程                                       |
| 首页报告    | `src/api/frontpage.ts::generateReportDraft` POST `/api/v1/frontpage/generate-report-draft`，支持 nhc_frontpage/insurance_settlement/combined；`useFrontpageDraft.ts` 管理材料/visit 的生成路径                 | 是病例首页/结算草稿语义；存在只发 visit_id 或 medical_text 的路径，不能推断具备助手三坐标授权                                                                    | 先复用已加载同病例报告显示；生成属于新执行，必须显示材料范围、请求状态与参考草稿性质                                             |
| DRG分析报告 | `src/api/drg.ts::getAnalysisData`、`exportAnalysisData`，后者 `/api/v1/drg/analysis/export/{format}`                                                                                                           | 同样受默认 Mock 分支影响；不是业务助手的质控完成日期统计                                                                                                         | 明确类型后单独映射过滤条件；不得继承错误日期语义或冒充当前汇总                                                                   |
| 通知        | `useNotifications.ts` GET `/api/v1/notifications`（page_size=30）及 `/overview`（本地当天date）；标已读 PUT `/{id}/read`、`/read-all`；后端 `routers/notifications.py` 有PG持久化                              | 现有概览固定当天，列表不是助手当前机构/科室/期间的查询；前端筛选不等于服务器授权。现有已读是写操作                                                               | 可单独只读收件箱入口，明确“账号通知”；不能叫“当前科室期间订阅结果”。不在本次创建订阅、触发通知或标已读                           |
| EMR         | `RecordDetailWorkspace.vue` 通过 AsyncEMRViewer 显示已同步文书；后端 `routers/emr_render.py` `/api/v1/emr` 为 bundle 渲染，角色依赖含admin/qc_manager/sync_admin/super_admin                                   | 当前是站内查看，不是第三方 EMR 浮窗/SSO/回写；助手当前文书定位已有专用只读API                                                                                    | 不造外部链接。须有医院目标系统、受信身份、机构患者住院映射、origin allowlist、上下文消息协议、注销/切患者事件及只读/回写权限合同 |

## 3. 为什么不能仅增加链接

`WorkstationAssistPanel.vue` 接收 patientInfo 并提供 profile/qc/drg/message 插槽；它不负责加载或授权病例。真实业务由 `WorkstationV4View.vue` 及子组件持有。该页目前 route.query 只见 stage 消费，没有助手三坐标/面板 query 的接收链。直接生成带 patient_id 的 URL 不会完成患者切换。

`RecordDetailWorkspace.vue` 已向 BusinessAgentDrawer 传 institute_id、patient_id、visit_id、document_id；反向打开同患者分析面板尚无事件链。最低成本是在该宿主补严格类型的只读事件，由同一父详情比对三坐标再选 assistTab，而非让 Drawer 改父全局患者。首页助手需独立受授权病例加载合同，不可调用旧全院病历池绕过范围。

## 4. M2 可复用与不能直接复用的部分

- 既有 `src/api/qc.ts::batchEvaluateQC` 是执行入口候选；必须追到当前正式任务主链并核对输入材料、规则范围、幂等及最终结果读取，不能只因名字含 batch 就接入。助手当前只读上下文不能直接升级成执行授权。
- `src/api/qc-result-feedback-demo.ts` 明确指向 `/api/v1/qc/sichuan/workspace/result-feedback-demo`。不能作为正式异议台账/审核/反馈闭环；待确定持久化实体、权限和处理状态合同。
- 编码应用、DRG建议接受/拒绝、通知标已读属于写语义；可复用交互样式，不能默认为助手已获业务写权限或已办理成功。
- 正式提醒/整改台账需服务端持久化、状态读回、负责人权限、重复提交保护与审计；订阅还需调度、投递目标、失败重试及停用语义。当前源码证据不足以声称这些合同完整。

## 5. 接入验收

1. A→B→A、相同住院号不同机构、缺三坐标：不可打开错病例面板，不接受迟到响应。
2. 打开画像/编码面板不自动产生模型或写调用；用户明确分析才执行，失败有真实状态。
3. 返回助手保留会话与原卡片；不自动重问、不刷新原统计。
4. 管理范围不传入病例面板；通知日期/DRG日期未定义映射时明确拒绝继承。
5. Mock 关闭后用真实只读接口/权限验收；缺服务或材料显示原因，不用静态数据补齐。
6. 外部 EMR 和主动订阅必须在目标系统/调度投递合同具备后验收；当前记录为未接入。

## 6. 本轮已修复（未接入助手入口）

画像组件已增加请求代次及 AbortController：材料/首页对象变化或卸载使旧请求失效；旧响应/旧错误/旧 finally 和延迟 expand 不再污染新材料。删除 success=false 时固定患者/85风险分的模拟回退，保留明确失败提示。专属组件测试先红2项，再绿2项，覆盖 A迟到/B仍加载及失败不造画像。首次测试曾因图标整包加载内存不足中断，改测试图标桩并单worker后正常。模型请求字段合同未改变。组件仍没有三坐标prop，材料文本及首页对象完全相同的跨患者切换不能由本组件自行识别，宿主整合仍需scopeKey；此次修复不等于M3已整合。

补充：真实宿主 WorkstationV4View 已有 selectedRecord→WorkstationV4AssistView 传递，现由 AssistView 将 instituteId/patientId/visitId JSON 元组作为 scopeKey 传到画像。缺任一坐标不渲染分析组件，显示原因；不把 record.id 猜成住院号。同材料跨患者也触发代次失效。新增 scope 切换用例，画像3项+Drawer14项共17通过。助手能力说明已对应只读提醒/整改查询更新；反馈办理/写入仍不可用。该scope修复使既有画像宿主更安全，但未增加助手反向打开入口。
