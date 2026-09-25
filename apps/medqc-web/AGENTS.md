# AGENTS.md

## 常驻约束

- 默认范围为本仓库，前端重点 `apps/medqc-web`；用中文沟通、注释和提交，文本用 UTF-8 无 BOM、LF。跨会话任务先读 `docs/plans/PROJECT_ROLLING_TODO.md` 的当前焦点；V3.6 专题以 `docs/PRD-内涵质控V3.6总需求与差距矩阵.md` 和 `docs/plans/2026-09-22-v36-manual-capability-rolling-plan.md` 最新几节为准，不重读全部历史，也不凭聊天摘要推断已上线。
- 修改前核对真实调用链、问题证据和验收标准；以 1–2 个业务点做最小闭环，验收通过即提交并停止扩展。主协调 Agent 亲自审查关键 diff、模型输入、状态映射、调用量和真实病例证据；子代理结论须独立复核，多 Agent 只并发处理边界清晰的工作。
- 进度按“代码完成 / 非生产验证 / 业务库部署 / 真实病例与浏览器验收”分列报告；测试数量、`READY_FOR_REVIEW` 或粗略百分比不代替业务交付，未达验收不提升 PRD 覆盖状态。V3.6 长程任务不包含质控引擎整改或重写。
- 一个业务事实只保留一个权威所有者：执行器判定，Renderer 写文案，Finalizer 校验，Aggregator 装配，保存层/API/前端搬运。后续层不得重判状态、原因或事实；任务处理、缺陷整改、申诉复核、病历初审/复审各有独立 owner，不得互相代替。新抽象和公共改动先证明真实缺陷，普通新规则优先只改执行器及其测试。
- 兼容路径留在旧入口；新主链不依赖旧 payload。病例身份以 `institute_id/patient_id/visit_id` 三坐标为准，单一就诊号或旧表主键不得冒充身份合同，身份不明时失败关闭。比较同输入的状态、原因、事实、证据、LLM 调用/Token 和耗时。大文件继续扩张或结构拆分时，先说明职责边界并单独验证行为等价；普通 DTO/Prompt/trace 不重复加 digest。

## 质控与数据

- LX0609 先按规则范围查 `docs/0602/luxian_0609_formal_rule_catalog.csv`（001–049，含允许状态）、`docs/0602/泸县0609质控点-业务标准基线-v1.md`（001–075）及对应扩展证明，禁止跨范围套用。交付状态必须符合单规则合同，`uncertain`、`technical_error` 不得交付。
- “零回退”须固定保护集及其代码/产物基线；`needs_review` 不表示判据缺失。客户确认口径优先于国家/行业下限，再优先于我方实现；不能凭未复核状态声称标准待定，声称缺失须附文件:行号。
- 结构化字段、时间、存在性优先由 Python 判定。确需 LLM 时，只抽取最小语义事实，由 Python 校验和映射状态，明确失败语义、调用上限及真实病例验收。
- 业务库 `medqc` 只做只读核查；迁移只在获本批次明确授权的隔离库（当前 `medqc_v36_validation_20260924`）按序执行并回读，授权不跨批次、不跨库扩大。`qc` 与 `public` 两套同名表基线可能不同，迁移预检须按各 schema 实测基线精确匹配。本地联调用进程环境变量把 `DATABASE_URL`/`REMOTE_DB_URL` 指向隔离库，并在日志中核对库名。
- 含患者原文的排查文件放 `.tmp/0910-full-audit/`，以 `-private` 结尾且不提交；合成数据须可识别、可清理，验收后按授权清理。`docs/` 只保留长期结论。凭据仅从 `backend/.env` 读取，不写入脚本、日志或报告。

## 工具与交付

- 存在 `.codegraph/` 时，定位代码先用 CodeGraph；索引不代替真实 trace、测试或浏览器验证。`workstation-v4`/V5 页面采用浅色医疗中后台：总览/筛选/明细/结果分区，复用现有 token 与组件；未知值显示为未知，不伪造 0 或通过；纯展示不改后端合同。
- TypeScript 优先修 DTO、Store、props/emits 边界；不新增宽泛 `any`、`@ts-ignore` 或 `.vue.ts` 镜像文件。不得提交生成物、临时日志或关闭 CI 门禁。
- 小改动先跑聚焦测试；提交前默认运行 `npm run check:encoding`、`npm run lint`、`npm run type-check`、`npm run test:unit`，Python 改动另跑相关 pytest/Ruff。`npm run lint` 带 `--fix` 会改写无关文件，必要时改用只读 `npx eslint src --ext .vue,.js,.jsx,.cjs,.mjs,.ts,.tsx,.cts,.mts --quiet`。资源不足至少跑编码与 lint，并记录未运行项。
- 提交前检查 `git diff --cached --name-only`，只暂存本任务文件，使用中文提交信息。删除、强推、全局安装和数据库写入须明确授权；已授权交付的普通 `git push` 不必重复询问。浏览器验收需要登录时由用户本人输入口令。
