# 业务助手 M2 操作链核查与最小实施设计

日期：2026-10-02。本次只读源码审查，未提交、未调用真实模型、未读写共享数据库或重启服务。取消问答轮数上限不构成创建质控任务、提交反馈或发送消息的执行授权；产品必须由用户确认具体预览后执行。本文不把跳转现有页面当作完成操作闭环。

## 真实入口及合同

所有列出的请求响应均为源码合同，尚未证明本次独立只读测试服务已挂载、数据库已迁移或Worker可运行。

### 单病例复检与科室专项任务

权威入口是 `backend/app/routers/qc_sichuan.py:1912` 的 `POST /api/v1/qc/sichuan/workspace/batch-jobs`，DTO在同文件431行。单病例与批量沿用同一链，分别传一项/多项明确三坐标 `record_refs:[{institute_id,patient_id,visit_id}]`。传明确 `rule_set_key`、正式 `rule_ids`、`scope`（按现有规范化）、科室与日期条件；其余执行策略由正式默认值解析，不由模型覆盖。不要使用只含住院号的 record_ids。DTO还接受 sync_scope、doctor、date_field、start_date、end_date、keyword、run_mode以及诊断/模型策略字段，助手首版不暴露这些高风险自由参数。

创建响应为 success envelope 的 data：正式job字段（id/status/filters等）、rule_count、draft_ids、rule_set_key/name/version、execution_strategy、quality_profile、bucket_strategy、batch_output_mode、max_refine_candidates、run_mode、refine_summary、idempotency_reused。1918行起验证规则集和正式范围、拒绝待验收规则；2053行起按明确三坐标 collect_records，2080行起要求实际匹配集合等于请求集合。2268行附近调用 submit_detached_task 后台执行，不能把创建成功写作质控已完成。

任务回读：同文件2373行 `GET /workspace/batch-jobs/{job_id}`，优先按 created_by 读取，限定的共享样本任务另有只读投影；LX0609经Canonical回填后返回完整正式状态、摘要与结果。列表为2310行 `GET /workspace/batch-jobs`。取消为2820行 `POST .../{job_id}/cancel`，按本人任务操作；重试2837行 `POST .../{job_id}/retry`，正在排队/执行返回409，支持父子任务重新入队。聊天停止不得自动调用任务取消。

现有创建依赖 require_product_activation（定义 `backend/app/services/product_activation.py:282`）及规则/病例存在性检查；创建段未调用 business_agent 的 UID病例/科室授权。因此助手适配必须对每个病例再次调用既有 BusinessAccess/require_record，不能把已登录或产品激活等同于病例授权。确认时再次验证权限撤销及医生单病例/管理者限定范围。

幂等实际能力有限：2116行生成包含范围、规则、设置/运行时快照的payload，2158行hash为key；2163行只扫描本人 queued/running 各前100条复用。它不是原子占位，也不覆盖完成后重复提交、超时未知结果或并发创建。不能仅转发该接口就声称满足PRD重复确认不重复建任务。

旧 `backend/app/routers/tasks.py:556` 的 `/api/v1/tasks/{task_id}/re-analyze` 逐项调 QCService.evaluate、最多前50条，不是本LX0609明确定义的Canonical任务链；不得用于替代本次单病例复检。该文件409行 assign 分配抽样病历给质控员，不是整改责任科室分派。

### 异议反馈

现有可写合同是演示版：`qc_sichuan.py:2550` 的 `PUT /api/v1/qc/sichuan/workspace/result-feedback-demo/{rule_id}`。请求由 `backend/app/schemas/qc_sichuan.py:33` 定义：root_job_id、record_ref、feedback_type(correct/incorrect/note)、expected_status、error_category、comment≤500。incorrect要求期望状态、错误类别及说明；note只要说明且禁止状态/类别；correct禁止状态/类别。响应data为反馈id、任务/结果标识、original_status、反馈字段、result_digest、created_by/created_at/updated_at。GET同前缀支持按root_job_id+record_ref回读；/all为演示汇总。

`qc_sichuan.py:1760` 同时锁 UID admin-001 与邮箱 admin@medqc.com；`backend/app/services/qc_workspace/result_feedback_demo_store.py:103` 的数据库约束也限定该UID。Store保存前读取Canonical存在性和当前摘要，唯一键(root_job_id,record_ref,rule_id,created_by)更新现有反馈，不改Canonical判定；555行 save重新计算result_digest，输入不接受预览时的expected_digest，因此仍缺预览→确认间的结果变更校验。反馈表不可用返回503，不自动迁移。

最小可复用范围是该演示账号的正式保存结果反馈；不能自动放开到任意医生角色。助手从已授权保存问题引用推导root_job_id/record_ref/rule_id，不允许模型提交任意坐标。用户明确确认完整反馈内容后调用并回读；医院多用户支持需正式账号/授权和表约束方案，不应静默篡改演示合同。

### 整改分派与催办

`src/api/rectification.ts:36` 起声明 POST /api/v1/rectifications、GET列表/my-tasks/detail、POST /{id}/assign、submit/review。对 backend/app 全部Python检索无 rectifications 路由或实现；前端声明不能证明业务能力可用。但另有 `backend/app/routers/remediation.py:46` 的 `/api/v1/remediation` 正式路由：创建、更新、提交、审核、关闭及统计均操作 qc_remediation_tasks。此前核查遗漏此不同命名入口，不能由 /rectifications 路由缺失推断所有整改后端不存在。该链创建DTO带 qc_result_id、record_id、assignee_id/name/department、deadline、defect_description、remediation_requirement，61行创建入口只见登录依赖、结果/病历存在性检查，未见业务助手逐病例/科室授权和原子动作幂等；需独立核实责任范围与通知送达后复用。不能把 tasks/assign 借名当整改分派。

`backend/app/routers/defects.py:198` 提供 `POST /api/v1/qc/defects/{defect_id}/urge`，请求 `DefectUrgeRequest`（`backend/app/schemas/defects.py:51`）：message默认“请尽快完成整改”、deadline可选字符串。响应data为defect_id、action=urge、new_status=urged、message。实际只update qc_defects的status、urged_at/by/message/deadline并插入 qc_defect_history；该函数没有通知发送调用，历史写失败仅warning。不能依据“催办成功”响应声称消息已送达。

同路由还可 cancel-urge、mark-remediated、approve/reject、batch。通用 require_permission 仅检查资源动作权限（`backend/app/core/permissions.py:237`），催办更新按defect_id，未见逐病例/科室访问验证、版本CAS或幂等key；列表虽接受department但非绑定用户范围。直接向助手注册这些写工具会扩大权限。当前保存问题ID与qc_defects ID之间也未在本调用链证明有可靠映射。

分派/催办必须补：权威缺陷映射、责任人/科室可分配目录、逐对象授权、期限合法性、状态机、唯一动作键、成功/失败明细、审计与真实通知投递结果。未具备时显示“不可办理及原因”，不能用助手自己的记录充当整改台账。现有表内容/通知基础设施本次未访问验证。

## “我改好了”与材料版本

任务创建已经保存规则/设置/运行时、病例场景和评价日期快照（qc_sichuan.py:2108、2230附近），但这些不是医生最新EMR文书已同步的凭据。现有 business_documents 读取当前源文书并进行摘录定位，不返回可证明与EMR最新提交对应的材料版本。`backend/app/routers/sync.py:1538` 的 GET /api/v1/sync/runs 是有独立读取权限的同步运行历史，不等于当前病例新文书已到达；不能仅用最近同步成功或结果完成时间判断。

应先接入权威病例材料同步状态/版本：来源记录更新时间、最后成功同步时间、文书集合版本或既有材料版本标识，以及用户所指修改对应的已同步证据。复检预览展示当前可用材料与旧结果时间；确认时材料变化则要求重新预览。无法判断新文书是否同步时只能明确“将检查当前已同步材料，未确认新修改已到达”，不能把复检成功解释为新记录已验证。不要为了预览在普通DTO中到处重复添加digest；优先使用现有源版本，确缺可用版本再在正式材料所有者补合同。

## 最小实现顺序与所有权

1. 独立纯预览模块（可立即实施，无DB写）：建议 `backend/app/services/qc_agent/business_actions.py`。输入仅为已解析身份/范围、既有授权病例、正式规则目录、保存结果与材料状态的类型化快照；输出 operation、allowed/blocked_reasons、明确病例和规则清单、excluded/paused规则、旧job/version、材料截至信息、预览警示。只校验/投影，不调用模型、不建任务、不决定医学状态。医生只能单病例，管理者必须显式病例集合；缺范围、未知/待验收规则、无权限必须拒绝。数量上限由产品合同配置，不为演示任意扩大。
2. 服务端预览+确认合同：建议 POST /business-agent/sessions/{sid}/actions/preview 返回 preview_id、expires_at、上述只读预览；模型只能提出预览。确认由用户按钮调用 POST .../actions/{preview_id}/confirm，body只含明确确认标记/确认nonce，不重新接受任意病例与规则。绑定UID、会话、操作和确定的范围；确认再次授权和校验目录/材料/保存版本，有变化409重新预览。文字“是”不能绕过具体预览确认。
3. 幂等必须落在正式业务创建边界：新增持久化action_id→job_id的原子声明/唯一约束，或扩展正式任务创建支持调用方幂等key；不能仅在聊天内存加锁。重复确认、网络断开后恢复、任务已完成再重试都返回同一job；结果未知先按key查任务再决定，不能盲目POST。需要持久化迁移及正式任务服务配合，纯预览不宣称已解决。
4. 操作卡持久绑定真实job/feedback ID，刷新后从服务端回读状态；执行进度、部分失败、重试/取消和前后结果对比均来自正式任务。比较同病例、同规则、旧新保存任务，展示材料/规则范围变化，不重判结果。预览、执行、进度和回读都要在助手内形成闭环，链接仅辅助。
5. 第一写闭环优先单病例/明确规则复检，然后复用同一确认契约扩管理专项。反馈演示账号可独立接入；整改分派可继续核查 remediation 既有链的授权与幂等缺口，真实催办仍需验证通知投递，不能用跳转或状态修改代替送达。

草稿和趋势仍属M2但不依赖写接口：草稿只能基于已读取事实，未证实事实留空/待补充，复制不关闭缺陷；本人趋势需要本人主数据授权、共同规则范围和明确分母，科室趋势复用正式统计，不由模型聚合。此处只核查操作链，不把它们自动判为已完成。

## 验收及外部条件

本地受控测试先覆盖预览无写、混合授权拒绝、暂停规则剔除显式说明、材料未知/变更、过期确认、重复/并发确认、提交超时后回查、权限撤销、刷新恢复、旧新任务隔离、反馈不改Canonical及通知部分失败。纯预览可以用合成类型快照完成独立测试；写闭环须在明确授权的隔离数据库/任务环境验证，不对共享PG随意发起测试。

待确认外部条件：正式任务运行服务及模型配置是否可在隔离写环境使用；材料同步版本是否可提供；反馈表已迁移与账号合同；remediation既有链授权与幂等、责任目录及通知投递基础设施；生产医生与科室管理者授权。无限问答预算不能解决这些依赖。只读服务中的GET成功或源代码有POST，都不证明执行、持久化和恢复已验收。

## 本轮已实施的纯模块

已新增 business_actions.py 与 test_business_actions.py。预览绑定账号、会话、到期时间、当前上下文、明确三坐标、正式规则及可信材料版本；确认必须提供 confirmed=true 与相同确认摘要，并重验授权、范围、目录和材料版本。未知/暂停/仅待验收规则、跨机构、重复病例、医生批量、缺care_phase、材料未知或未证实同步均拒绝。输出 FormalTaskRequest 只含当前正式规则集、明确规则/病例及running/final范围，不把统计完成日期混入任务入院/出院筛选。没有HTTP执行器、任务创建、持久幂等或成功任务卡，整合方仍需补齐这些真实链路。医生现有上下文通常未给care_phase，不能猜，应由服务端读取当前病例状态后预览。模块的授权集合和同步证明只接受服务端可信来源，不能直接绑定客户端JSON。

## 提醒/台账读取审查接续

新只读投影按当前账号、关联结果三坐标及当前医生病例/管理科室成员验证，通知正文与整改要求信任既有业务关联数据所有者；没有额外证明自由文本绝不提及其他病例，本次也没有发现真实错绑或泄露证据。不得据合成任意文本输入宣称发生真实越权。独立审查发现源列表第100页有下一条时返回has_more=true但第101页被422拒绝，现已修为has_more=false、scan_limit_reached=true、state=partial并明确仍有未扫描项；常规空页/排除页也明确不能称当前范围已查完。23项合成读取/授权/分页测试及Ruff通过，真实数据库与模型调用均为0。纯M2预览模块仍未接入执行器，不是办理闭环。
