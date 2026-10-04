# 业务助手授权读取与原文定位实施计划

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 先走通一份明确授权的医生病例和一个机构内科室的管理问数，再完成具体问题到原文的定位和真实验收。

**Architecture:** DSH 继续管理模型循环与历史；MedQC 服务端管理授权并复用现有保存结果、正式统计与文书读取。试点授权绑定认证后的账号 ID，不从可自行修改的科室、姓名或前端输入推断权限；旧全院保存结果/EMR 入口不向医生开放。

**Tech Stack:** FastAPI、Pydantic、现有 Canonical/EMR 服务、Vue/Ant Design Vue、DSH 原生运行时。

---

基线为 `9916241a7`，在 `codex/medqc-business-agent` 独立工作树继续。用户指定使用现有管理员账号读取并自行查找病例；该账号实际角色为 admin/qc_manager，不能替代真实医生角色验收。不启动主应用 Worker、不写客户数据库，不扩 SQLBot、写操作或更换模型。

### Task 1：服务端范围与两条授权读取链

**Files:** 新增 `backend/app/services/qc_agent/business_access.py`；修改 `backend/app/routers/business_agent.py`、`backend/app/services/qc_agent/business_tools.py`；测试 `backend/tests/unit/test_business_agent_access.py` 及现有 `test_business_agent.py`。

1. 以 `MEDQC_AGENT_ACCESS_FILE` 指向本地不提交的服务端授权 JSON，按不可自行修改的账号 ID 记录医生病例三坐标及管理者机构/科室；配置缺失、范围缺失或不符均拒绝。每次读取重新校验，撤销授权后不能恢复旧会话或打开旧来源。
2. 添加仅返回当前账号范围的 `/business/access`。创建、恢复、聊天、工具和引用都使用同一授权所有者；停止仍可取消本人执行。
3. 新增经过范围校验的单病例保存结果及科室统计读取入口。正式结果调用原读取服务，统计调用原分析服务，并在加载 Canonical 结果和计算正式指标前限制病例身份；不重判或重新聚合已返回统计。
4. 将业务工具回调切到上述入口，保留原 Bearer。医生只访问授权三坐标；管理病例引用也必须属于当前机构/科室。
5. 测试无授权、本人/他人病例、同名科室跨机构、改前端科室、改个人资料科室、旧引用与授权撤销；核对未授权读取在查询正式结果前被拒绝。原全院 API 的医生拒绝用例继续通过。

### Task 2：问题到对应文书的原文定位

**Files:** 新增 `backend/app/services/qc_agent/business_documents.py`；修改业务 router、`src/api/businessAgent.ts`、`src/views/workstation-v4/components/BusinessAgentDrawer.vue`；新增服务和组件聚焦测试。

1. 从已校验版本的具体保存问题取证据坐标；由服务端按同一病例授权读取当前文书，复用既有安全 source_ref 投影和 source_document_aliases。
2. 仅以来源引用精确对应文书。没有匹配、匹配多份、当前原文已变化、摘录不存在或重复出现时明确返回定位状态；不按文书标题、列表顺序或相似段落猜测。
3. 原文点击不发模型请求。展示保存摘录与当前文书的区别；唯一匹配摘录用位置范围高亮，重复或未命中时只打开已确认的文书，不伪造定位。
4. 测试来源错配、跨病例引用、任务版本变化、源读取失败及迟到文书响应隔离；用管理员实际保存结果验证读取，另记录真实医生权限验收缺口。

### Task 3：小范围真实 WeKnora

等待明确服务配置与授权知识库，保持官方搜索/读取、关闭 ask。仅用少量规范核对标题命中、正文、引用打开、截断补读、失败与越界拒绝；记录实际版本和资源，配置缺失不得填写兼容或成功。

### Task 4：真实病例和全量结果

1. 使用获授权病例核对连续追问、第二条绑定、患者 A→B→A、刷新、停止与来源定位，区分管理员联调和真实医生/科室账号验收。
2. 不将未经明确授权的病例用作外部框架演示。原始材料仅存 `.tmp/0910-full-audit/*-private/`。
3. 在 `TZ=Asia/Shanghai` 执行 `npm run test:unit` 全量，保留首次失败与后续复跑；可降低 worker 并发排查资源影响，不增加超时或改断言强迫通过。
4. 提交前运行编码、Lint、类型、相关 pytest/Ruff 和聚焦测试，只提交本任务文件，中文提交；更新接续卡与验证记录，明确未完成项。

授权文件管理方式为最小试点入口，不宣称已有完整医院人员/科室主数据集成。正式授权主数据接入与客户部署另行验收。
