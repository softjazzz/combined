# 分角色模型配置实施与验收

**Goal:** 默认模型、事实抽取、判断分析、专项核验可以分别选型；全部继承时保持旧模型和调用合同。

**Architecture:** 复用 user_llm_configs.custom_parameters 保存角色选择，不增加迁移。运行客户端在创建时固定已校验的角色运行配置；显式调用点选择客户端，保持原 Prompt、解析、医学判定和持久化。角色路由身份参与任务快照及外层事实冻结分区。

**Tech Stack:** FastAPI、Python、Vue 3、Ant Design Vue、pytest、Vitest。

基线：e17ac959a61ec9586e6d72708f290483def76525。独立分支 codex/llm-task-roles-20261102；不改集成分支、不连业务数据库或模型服务。

## 实施顺序

1. 新增严格角色配置 owner：只接受三个角色的 null（继承）或 provider_code/model_code；复用部署配置和 Gateway 校验，不接受端点、密钥、隐式兜底或任意运行参数。
2. 客户端固定角色配置，克隆运行时保留；热重载不改变在途实例。默认正式语义调用绑定判断分析；检查检验主抽取和会诊意见抽取绑定事实抽取；检查结果/阳性分析/检查理由专项绑定专项核验。
3. 角色身份加入任务运行快照；所有现有事实冻结的最终 IO 路径在原 A0/A1 分区之下再按角色运行身份隔离，避免外层命中旧事实跳过新模型。
4. 后台复用原默认模型选型，新加三个继承/自选用途行；本地ID保持大小写，地址密钥仍由部署提供。保存前验证整个角色计划，配置失败不部分保存。
5. 固定应答验证实际请求、隐私包装、角色继承、热重载隔离、冻结分区、错误/取消及原规则专项回归；前端验证保存回显、只读、异步选择、模型目录和类型。严格离线运行，不加载 .env。

## 验收边界

不把事实抽取等同于无医学风险，不增加预抽取层或规则数量；尚未显式分类的调用保持默认/判断分析路径。06-01-04实验级联与生产专项角色不能叠加混用，需显式拒绝冲突。全角色继承为回滚方法；旧配置不自动启用35B。不以固定应答通过宣称模型医学质量等价。

## 已完成的真实调用绑定

| 配置 | 实际入口 | 未单独选型时 |
| --- | --- | --- |
| 默认模型 | 原有 provider/model 配置 | 保留原有默认及历史裁决兼容逻辑 |
| 事实抽取 | native_exam_lab_execution._generate_exam_lab_fact_response；会诊 opinion_load 阶段首答及补核 | 继承原正式客户端 |
| 判断分析 | prepare_luxian_0609_execution；检查检验/会诊公开执行入口 | 继承原正式客户端 |
| 专项核验 | check_exam_result_record、check_exam_finding_analysis、check_exam_reason | 继承原正式客户端，保留原环境调用点覆盖 |

尚未单独分类的语义调用继续经过判断分析路径，不能宣称全部抽取模块已经独立拆分。本轮以检查检验、会诊两个业务点完成最小闭环，不重构其他执行器。Python时限、触发、适用及结果合同均不改；Prompt文本没有变化。

配置保存在既有 custom_parameters.task_role_models；三个值均为 null 表示继承，自选值只接受 provider_code/model_code。地址和密钥不入此对象，沿用部署配置。保存前静态校验全部角色，未启用Provider、缺部署配置、缺模型Gateway profile、未知字段等拒绝保存；保存不调用模型。默认为本地服务时拒绝云端角色，避免意外外发；不存在失败自动转云端逻辑。

客户端创建时固定完整角色运行配置，独立任务克隆保留该快照，子客户端使用同一个Gateway出口及统计父节点。角色改变会使旧任务运行身份校验失败；在途实例继续保留其原配置。角色用现有 model_role 观测标识，不把角色配置发给上游模型。

## 冻结与回滚

原始无角色配置保持旧冻结行为。保存角色配置后，所有现有事实存储在原 A0/A1 分区之下增加 task-roles/<运行身份指纹>；身份包括默认及显式角色的模型、有效推理参数、地址指纹、Gateway profile/地址指纹和兼容环境调用点选择。修改选型自然失效旧分区，旧文件保留。即使外层 main/opinion 已有冻结，也不会绕开新模型。Windows使用长路径支持，避免新分区使原64位事实文件名超限。

会诊角色选择保留同一轮应答账本、使用量和“全轮可交付后提交”门槛；不能切换角色后绕开隐私包装或原始应答冻结。超时/错误沿用原调用点合同；角色路由自身不增加补核和升级。

回滚：将三个用途恢复“继承默认模型”后保存并正常重载；医学代码无替换，旧配置仍可用。首次保存用途配置会产生独立冻结分区，不会删除旧事实；不能承诺回滚后一定零模型调用。06-01-04旧实验级联开启时，生产角色自选拒绝配置，不静默覆盖实验策略。

## 验证结果（2026-11-02）

全部后端通过 scripts/run_qc_scheduler_tests.py 的 OfflineIsolation 执行：移除业务环境、阻断网络/业务数据库/子进程，注入内存SQLite。模型出口是固定函数或 httpx.MockTransport＋ASGITransport；冻结只写合成临时目录。前端使用 scripts/frontpage-v2-no-network.cjs 阻断TCP/TLS/fetch；新工作树没有复制 .env。

- 扩大后端：362通过、2跳过。命令为 `python -B scripts/run_qc_scheduler_tests.py --profile offline --suite dual-model-exam tests/unit/test_llm_task_roles.py tests/unit/test_luxian_0609_llm_role_routing.py tests/unit/test_strata_admin_configuration.py tests/unit/test_llm_config_permissions.py tests/unit/test_llm_config_loader.py`。
- 最终角色与冻结复核：62通过。命令为 `python -B scripts/run_qc_scheduler_tests.py --profile offline tests/unit/test_llm_task_roles.py tests/unit/test_luxian_0609_second_stage_freeze_completion.py tests/unit/test_llm_experiment_freeze.py`。与扩大集重叠，不相加。
- 两条固定正式链分别形成合规/不合规：实际Gateway请求用synthetic-35b抽取、synthetic-flash专项核验，经过Native、Binding、Finalizer和Canonical内存保存读取；状态/原因/事实/证据一致，重复命中冻结零请求。
- 前端45通过：LLMApiConfigStrata、DataSyncConfigPage、workstation-report-adaptation。新增角色回显、继承保存、目录失败、迟到响应保护；复用既有管理权限保护。命令为 `node --require ./scripts/frontpage-v2-no-network.cjs node_modules/vitest/vitest.mjs run tests/unit/components/LLMApiConfigStrata.spec.ts tests/unit/views/workstation-v4/DataSyncConfigPage.spec.ts tests/unit/router/workstation-report-adaptation.spec.ts --maxWorkers=1 --minWorkers=1`。
- 完整 vue-tsc --noEmit 通过。全量 src ESLint只读990文件、0错误；3401项已有警告未批量修改。三个改动生产前端文件定向ESLint零错误零警告。
- 改动Python Ruff与基线比较，仍为7项继承问题、无新增；新增模块与测试Ruff通过。工作流YAML解析通过；CI已增加严格隔离角色测试，未删除或放宽任何原门禁。
- 首次并行运行有一项无关路由加载超时，完整三文件聚焦复核45项通过，没有放宽超时或网络隔离。

两处跳过是要求显式提供私有原始报告的入口，本轮没有载入。未运行全部前后端单测、真实Provider连通性、真实模型医学质量验收或运行中页面验收。不据固定应答宣布小模型质量等价。未读写业务库、改集成分支、调用模型、重跑病历、部署或推送。
