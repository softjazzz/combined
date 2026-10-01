# 业务助手精简输入 Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 同病例同五个问题保持正式事实与引用，降低重复模型输入，使两轮保存问题查询在原模型/60秒内完成。

**Architecture:** MedQC 仍搬运正式保存事实、拥有授权和坐标；DSH `output.render` 仅投影模型需要的内容，`presentationMeta` 保留完整卡片与分页范围，由原生 JSONL 回读。不新增对话历史、质控结果副本或压缩框架。概览分页/按状态过滤，具体证据不截断；当前授权和任务版本检查保留。

**Tech Stack:** Python/FastAPI/Pydantic、Vue/TypeScript、DSH 0.1.5-rc.2、既有 qwen3.8-flash。

---

### Task 1：原生输入体积基线

文件：`backend/tests/manual/analyze_business_agent_trace.py`；私有产物不提交。

读取上一轮五轮的实际 JSONL，按工具量化模型文本与展示 metadata，按模型请求量化此前轮次/工具文本重放。字节不冒充 Token，实测供应商用量仍作为最终对照。

已核对 DSH 锁定版本 `ToolOutputDefinition`：`render(args,value)` 与 `presentationMeta(args,value)` 均从验证后的 canonical value 纯投影，metadata 原生持久化，模型文本独立。

### Task 2：分页概览与精简原生投影

文件：`backend/app/services/qc_agent/business_tools.py`、`agent-runtime/business-output.mjs`、`agent-runtime/runtime.mjs`。

先增加失败回归，再实现：

- 保存结果支持状态列表、页码、每页最多10条、`index/saved_text` 明确模型读取目的。全量状态计数只数原状态，不重判；展示范围明确说明全部/过滤类别、页号、匹配总数、已返回与剩余，空页不谎称没有其他类别。
- 后续页需要从已查看任务携带 `expected_job_id`，同病例保存版本变更409，未查看版本404。卡片与索引使用同一数组顺序/稳定result_id。
- 模型概览默认仅索引；用户需要保存结论/建议可选择 `saved_text`，仍限制每页大小，完整卡片保留原结论建议。解释才读取单问题证据；仅搬运保存文字不额外查规则。
- 单问题的结论、建议、reason与完整证据只给模型一份；完整引用与文书入口不变，不裁掉否定条件。规则仅提供当前标题、口径、发布状态和版本范围说明；统计沿用正式值，排除重复展示文案及病例内部字段。
- 原 native history 不压缩：先比较精简后实测的重放量，再决定是否需要锁定版本已有上下文机制。

回归命令：`python -m pytest --confcutdir=tests/unit tests/unit/test_business_agent*.py -q`；`node --test`。

### Task 3：可核对的页面范围

文件：`src/api/businessAgent.ts`、`src/views/workstation-v4/components/BusinessAgentDrawer.vue`、相关单元测试。

在模型答案和完整卡片旁显示本轮读取页的状态范围、已返回/匹配总数与剩余。原文弹窗和切患者隔离保留。第二条必须指向同页UI顺序，跨页访问仍可经业务工具完成。

回归覆盖模型投影/完整卡片分离、第二条绑定、跨页完整性、任务409、授权撤销403、患者切换和停止/恢复。

### Task 4：同五轮一次真实重放、证据核对及交付

文件：`backend/tests/manual/verify_business_agent_compact.py`、新验证记录、接续卡、滚动焦点。

沿用之前已授权两份病例和原模型；原五个问题/会话次序不改，每轮保存状态、耗时、模型/工具调用、供应商Token与原生trace。真实模型本轮最多10轮，首轮固定五轮，有异常仅必要定向复测。逐项回查完整卡片、正式状态/结论/建议与证据坐标；不得只凭completed称答案准确。

运行编码、Lint、类型、前端全量统一上海时区、相关Python/Ruff及原生测试。只暂存本任务文件，本地中文提交，不推送、合并、写共享PG、启Worker或停止主3000/8001。

实际医生/科室管理者及真实WeKnora缺口继续保留，本轮不重复索要配置。
