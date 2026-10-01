# MedQC 业务助手 DSH 运行时

这是独立工作树中的只读接入验证。DSH 执行模型/工具循环并保存 JSONL 历史；MedQC 负责账号归属、明确访问范围、正式结果和统计。实际管理员的有限病例/科室已只读验证；实际医生/科室管理者身份、真实规范库及答案质量仍未验收，不能据此部署客户环境。

## 固定依赖与运行

- Node.js >=22.19；本次使用 24.19.0。系统 Node 20 仅用于安装，不能用于运行。
- DSH 0.1.5-rc.2，Cordis 4.0.2，官方 `@wxg-prc-cpg/dsh-weknora` 0.1.0。锁文件固定依赖；overrides 保持同一 DSH 候选版本，避免 npm 自动混入后续候选版本。
- 在本目录执行 `npm ci --ignore-scripts`、`node --test`、`node server.mjs`。
- 服务只监听 `127.0.0.1:8013`，内部请求必须带 `X-MedQC-Runtime-Key`。不注册 shell、任意文件读取或业务写工具。

配置仅从本工作树 `../backend/.env` 读取：`LLM_MODEL`、`LLM_DEFAULT_PROVIDER`、`LLM_API_ENDPOINT`、`LLM_API_KEY`；阿里云优先沿用 `DASHSCOPE_BASE_URL/API_KEY`，DeepSeek 优先沿用 `DEEPSEEK_BASE_URL/API_KEY`。不另选模型。`MEDQC_AGENT_RUNTIME_KEY` 是本地桥接随机密钥；Python 服务使用相同值，配合 `MEDQC_AGENT_RUNTIME_URL=http://127.0.0.1:8013`、`MEDQC_AGENT_BACKEND_URL=http://127.0.0.1:8003`。

真实 WeKnora 接入还需 `WEKNORA_BASE_URL`、`WEKNORA_API_KEY`、显式允许的 `WEKNORA_KNOWLEDGE_BASE_IDS`（逗号分隔）；平台级密钥按部署要求提供 `WEKNORA_TENANT_ID`。只注册官方搜索和原文读取工具，关闭委托问答。未提供服务时不注册知识工具，不能输出伪造原文引用。配置了地址但未提供知识库范围时拒绝启动。

执行历史在应用 `.tmp/0910-full-audit/business-agent-dsh-private/`，不提交。业务元数据仅保存账号、上下文和引用坐标；不复制模型历史或结果正文。参考 [验证记录](../docs/plans/2026-09-30-business-agent-m1-validation.md) 区分模拟与真实验证。

模型文本通过 `business-output.mjs` 纯投影，完整卡片和分页范围保留在原生 `presentationMeta`。保存概览默认 `index`、每页最多10条；正式结论建议用 `saved_text`，状态数组为空表示全部类别，后续页必须携带已见 `expected_job_id`。不截断单问题证据或重判状态；旧会话的大输出不会自动重写。同五轮性能/质量边界见[精简输入验证](../docs/plans/2026-10-01-business-agent-compact-input-validation.md)。

## 本机合成业务联调

使用 `backend/tests/manual/business_agent_validation_app.py` 的独立 FastAPI 应用，不使用主应用启动钩子，不创建表、启动 Worker 或读取客户数据库。它的固定合成身份只对该测试应用生效。

1. 在 `backend` 运行 `python -m uvicorn tests.manual.business_agent_validation_app:app --host 127.0.0.1 --port 8003 --no-access-log`（必要时将本目录设为 `PYTHONPATH`）。
2. 启动本目录的 Node 运行时。
3. 在应用目录设置 `VITE_BACKEND_TARGET=http://127.0.0.1:8003`，运行 `npm exec vite -- --config vite.config.mjs --port 3003 --strictPort`。
4. 打开 `/tests/manual/business-agent-preview.html`。这是组件联调页，不代表主应用登录或真实医院权限验收。
5. 真实模型的五轮验证脚本为 `backend/tests/manual/verify_business_agent.py --run-real-model`；必须显式传参数，会产生实际模型调用。原始结果只写隔离目录。

标准单测：运行时 `node --test`；Python 在 `backend` 执行 `python -m pytest --confcutdir=tests/unit tests/unit/test_business_agent.py -q`，避免加载主应用公共 conftest；前端执行 `npm run test:unit -- tests/unit/views/workstation-v4/useBusinessAgent.spec.ts tests/unit/views/workstation-v4/QCAgentChatDrawer.spec.ts tests/unit/views/workstation-v4/WorkstationV4HomeEntry.spec.ts`。

## 明确范围与真实只读联调

主业务接口需要 `MEDQC_AGENT_ACCESS_FILE` 指向服务端私有授权文件，按账号 UID 配置 `doctor_cases`、`manager_scopes`；缺失/无效503，无授权403，即使管理员也不能绕过新链路范围。字段示例和验收结果见[授权与原文验证](../docs/plans/2026-09-30-business-agent-scoped-read-validation.md)。不把可编辑个人资料或前端筛选当作授权。

在 `backend` 使用 `tests.manual.business_agent_readonly_app:app` 启动8003：显式设置 `MEDQC_AGENT_SOURCE_ENV` 为用户授权的既有 `backend/.env` 路径，以及上述私有授权路径。只选择读取 DATABASE_URL、DB_SCHEMA_MODE、DB_SEARCH_PATH、JWT_SECRET、JWT_ALGORITHM；PostgreSQL连接强制只读。实际登录委托既有8001，新验证服务不注册账号或修改角色，也不加载主应用/启动Worker。合成应用和真实只读应用不能同时占用8003。

真实病例坐标、截图及模型输出必须留在 `.tmp/0910-full-audit/` 的私有目录，不放入本仓库页面或 Git。当前已有私有浏览器验证页，不在文档复制其病例配置。统一时区全量检查：设置 `TZ=Asia/Shanghai` 后执行 `npm run test:unit -- --maxWorkers=1 --minWorkers=1`。

离线体积分析脚本：`backend/tests/manual/analyze_business_agent_trace.py --results <私有五轮结果> --trace-root <原生JSONL目录> --output <私有报告>`，统计文本字节，不代表Token。真实同五轮脚本为 `backend/tests/manual/verify_business_agent_compact.py --run-real-model`，沿用私有原始病例/问题和真实令牌，每轮前扣减10轮私有预算账本；本次10轮已经用尽，不能通过删除账本或重复脚本绕过预算。实际角色及WeKnora缺口未解决。
