# V3.6 Workspace 病历审核待办合同审计

## 结论

原 PRD 没有要求运行、终末 workspace 的待审核/待复审结果必须先分配给特定审核人。现有代码已经形成两条不同合同：

- 任务病历审核待办是个人队列，必须来自当前用户受领的任务病历；
- 运行/终末 workspace 病历审核是当前用户在其数据可见范围内、凭 `QC_RESULTS.REVIEW` 可操作的共享队列。

因此，缺少 workspace 审核受领人不是实现待办计数和下钻的前置阻断。共享队列不得伪装为“已分配给我”或返回虚构的 `assignee_id`；若以后需要抢单、指派或工作负载分配，应作为独立业务合同实现。

## 原文依据

- 总 PRD 的角色目标写明质控员“处理分配给自己的质控任务，查看病历和缺陷详情，完成审核和复审”，约束的是任务处理范围，没有规定每个 workspace 结果必须另行分配审核人：`docs/PRD-内涵质控V3.6总需求与差距矩阵.md:48`。
- “我的待办：待审核、待复审病历”的验收口径是点击病历数进入列表并保留筛选上下文，没有审核受领要求：`docs/PRD-内涵质控V3.6总需求与差距矩阵.md:109`。
- 手册差距基线要求待审核、待复审计数按三场景下钻，也没有定义审核分配状态机：`docs/plans/2026-09-22-v36-manual-capability-rolling-plan.md:45`。

## 现有权威边界

### 个人任务队列

`GET /api/v1/record-reviews/todo` 把当前用户 ID 传给 `list_my_record_review_todos`，服务只枚举本人受领的任务病历。这条链应继续保持个人队列语义，不与 workspace 共享池互相冒充：

- `backend/app/routers/record_reviews.py:167-188`
- `backend/app/services/record_review_service.py:922-1059`

### Workspace 共享审核池

运行/终末病例审核入口要求 `QC_RESULTS.REVIEW`，当前权限映射授予 `admin` 和 `qc_manager`，但没有审核受领关系：

- `backend/app/routers/record_reviews.py:83-88`
- `backend/app/routers/record_reviews.py:191-227`
- `backend/app/core/permissions.py:68-75`
- `backend/app/core/permissions.py:115-121`

审核事实仍由 `QCRecordReview` 权威链维护，绑定三坐标和当前 `job_id + envelope_id`。列表批量状态与单病例审核共用相同锚点和状态推导，已经能区分 `pending_review`、`pending_recheck`、`approved`、`doubtful`：

- `backend/app/services/record_review_service.py:717-801`
- `backend/app/services/record_review_service.py:844-885`
- `backend/app/services/medical_records/query_service.py:506-570`
- `backend/app/services/medical_records/query_service.py:689-714`

因此，workspace 待办可以定义为“当前登录用户有权处理的共享工作池”，而不是“已受领给当前用户的结果”。

## 实现仍需闭合的缺口

1. **三场景边界**：运行、终末分别按现有 workspace 列表的相同数据范围和 `review_state` 谓词计数；门急诊审核尚未开放时必须显示不可用，不能并入计数。
2. **对象范围**：`QC_RESULTS.REVIEW` 只是资源权限。计数、下钻和提交必须复用同一个病例对象可见范围，不能因用户属于审核角色池就越过机构或科室范围。
3. **个人与共享去重**：任务个人队列和 workspace 共享池可能指向同一三坐标及结果对象。产品若合并展示，必须按完整三坐标与 `job_id + envelope_id` 去重；在合同未确定前保持两个入口分列，不直接相加。
4. **同一快照**：首页计数与下钻列表必须共用相同场景、审核状态和数据范围谓词。失败时显示不可用，不保留旧数或伪造零。
5. **文案准确**：可以放在“我的待办”区域，含义是当前用户可处理；不得展示“分配给我”“我的受领病例”等个人归属文案。

## 不在本批范围

- 不新增审核抢单、指派、转派或专人工作量状态机；
- 不把角色权限池冒充病例对象授权；
- 不把任务受领人自动写成 workspace 审核人；
- 不因本审计提升 PRD 覆盖状态。
