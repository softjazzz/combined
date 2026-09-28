# V3.6 缺陷排名场景 Implementation Plan

> 按 executing-plans 分步实现；主协调集成提交，子代理不自行提交共享工作树。

**Goal:** 收口固定80项中的07，让本周/上周人工质控缺陷排名支持可信场景筛选。

**Architecture:** 创建人工缺陷的事务已经锁定权威任务，直接冻结该任务的场景；排名只聚合事实，不重判。历史场景缺失只参与all，不批量猜测回填。不采用每次联查可变化任务的方案，也不从出院日期推断。

**Tech Stack:** SQLAlchemy、Alembic、FastAPI、Vue、Vitest、pytest。

## 固定边界

- 接续`101e83e11`，只补07，不改质控引擎、不顺带宣称04待办整项完成。
- QCDefect.scene为可空字段，允许running/final/outpatient_emergency；任务outpatient明确映射为outpatient_emergency，未知值拒绝新建，不影响历史只读。
- 创建时从锁内task读取scene，拒绝客户端指定来源；scene与缺陷及历史在同一事务保存，失败回滚。
- 人工缺陷唯一源仍是task_assigned_qc、已核实身份和人工创建事件；自动缺陷不冒充个人工作量。总数、通过数、驳回数沿用既有定义。
- 具体场景仅按冻结scene精确过滤；历史NULL只进all。同一窗口、同一人员、相同竞争排名规则，空数组表示真零，读取失败仍503。
- 迁移68只编写与合成测试，不执行真实数据库写入。qc/public分别精确预检；历史不自动回填。

## 五线所有权

1. 存储：`backend/app/database/models/qc.py`、`task_manual_defect_service.py`、迁移68、该创建服务原有测试及新迁移测试。先加冻结/未知/回滚反例，再实现。
2. 统计：`performance_ranking_service.py`、`manual_defect_review_service.py`的共用谓词（仅必要时）、原有排名与dashboard API后端测试。共用谓词默认all保持旧调用行为，不擅自扩展待办接口。
3. 前端：`src/api/__tests__/dashboard-performance.spec.ts`、`PerformanceBoard.test.ts`及必要API/组件边界。覆盖具体场景两种排名均有值、空数组与错误；不伪造零，不新增说明性UI。
4. 独立测试：新`backend/tests/unit/test_defect_ranking_scene_contract.py`，只新增自己的测试文件；覆盖跨场景、历史NULL、自动缺陷排除、同人跨场景与窗口边界。
5. 只读复核：核对原PRD07、事务scene owner、迁移双schema和排名查询；提出具体阻断，不重复全面审计其他模块。

## 集成与验收

1. 聚焦pytest与Ruff；Node测试由主协调集中，代理不得并发抢占。
2. 主协调检查关键diff，复验创建服务、排名、API与迁移；对已有调用保持兼容。
3. 类型、只读ESLint、编码和聚焦Vitest；全量检查按资源可用性执行并如实记录未完成项。
4. 按代码、非生产数据库、业务库部署、真实病例/浏览器四层记录；整项满足原07合同后才将Goal从1/10提升至2/10。
5. 仅暂存本批文件，中文提交，不推送。08角色口径待用户确认，不用07的实现替代该决定。
