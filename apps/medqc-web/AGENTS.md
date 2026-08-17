# AGENTS Rules For Codex

## Scope

- Default scope is this monorepo.
- Frontend app focus: `apps/medqc-web`.

## 多 Agent 协作与架构责任

- 主协调 Agent 是项目大脑和最终责任人，不能只转发实现 Agent 的方案、进度或结论，也不能把需求分析、架构判断和验收判断整体外包。
- 主协调 Agent 在派发开发任务前，必须亲自核对业务目标、真实代码调用链、现有数据/测试证据和历史问题，明确根因、预期收益、最小改动范围、失败语义与验证方案。
- 实现 Agent 是执行者，只按主协调 Agent 已明确的方案、文件白名单和验收标准编码、测试与提交；不得自行扩大范围、改变架构方向或用局部单测替代业务效果证明。
- 测试/审查 Agent 负责独立证伪，重点检查真实业务结果、回归影响、性能数据和边界条件；测试通过不等于业务目标达成。
- 主协调 Agent 必须亲自审查关键 diff、模型输入、状态映射、调用次数、性能数据和真实病例回归结果，不能仅凭 `READY_FOR_REVIEW`、测试数量或 Agent 报告接受实现。
- 每次任务开始前，主协调 Agent 至少给出：问题证据、根因判断、实施方案、文件范围、验收指标和剩余风险；证据不足时先做只读调查，不得让实现 Agent 猜测开发。
- 优先采用 1-2 个业务点的小闭环：真实问题 -> 最小修改 -> 聚焦测试 -> 真实数据复核 -> 性能/准确性对比。没有准确率、耗时或客户体验收益证据的架构扩展不得继续投入。
- 多 Agent 并发只用于加速已明确且相互独立的执行或验证工作；并发不能替代主协调 Agent 的统一设计、取舍和最终验收责任。

## 防止过度工程化与技术债回流

- 先证明真实问题，再设计抽象。没有真实病例、冻结测试、调用链或性能证据的“未来可能需要”，不得作为新增平台、模块、配置或重构的理由。
- 默认采用最小闭环：一个规则或一个低耦合规则族 → 一个明确根因 → 最小修改 → 聚焦测试 → 真实输入复核 → 停止。不得把相邻问题、顺手优化或后续设想混入同一 Task。
- 每个业务事实只能有一个权威所有者和一条主资料链；禁止为同一事实新增第二个 Bundle、Resolver、状态机、分类层、资料快照或隐式回退来源。
- 规则执行器负责判定；Renderer 只组织客户文案；Finalizer 只校验和补缺；Aggregator 只装配和排序；Envelope、数据库、API 与前端只原样搬运。除明确合同外，后续层不得重新解释或改写业务状态、原因码和事实。
- 新增普通规则的目标是“规则执行器 + 对应测试”即可完成；如果必须同时修改任务入口、公共编排、聚合器、保存、API 和前端，必须先停止并给出重复所有者或缺失合同的证据，再单独评审公共边界改动。
- 不以“文件很长”“通用性更好”“未来复用”为由重写或平台化。巨型文件只能在行为冻结后受控拆分：保留公开入口、一次只拆一个规则族、只移动已有逻辑、每个阶段绿色可回滚；不得在拆分中改变口径、算法、状态或交互。
- 不新增通用基类、注册表、依赖注入层、全局 Store、配置开关或学习型/LLM 层，除非现有边界已无法表达明确合同，且已记录至少两个已发生的独立问题、替代方案和增量验收指标。
- 兼容逻辑必须隔离在旧入口：新任务主链不得新增对旧 payload、旧聚合或旧执行器的依赖。未证明真实客户链路仍使用的兼容路径，不得为了“清理行数”而提前重构。
- 测试数量不是完成度。验收优先比较相同输入下的状态、原因码、关键事实、证据定位、LLM 调用/Token 与耗时；行为未变的结构调整不得借机扩大回归范围或宣称业务能力提升。
- 当一个 Task 已达到批准的验收标准，必须提交、通知审核并暂停；下一步需要新的授权。禁止以“顺手做完”“避免以后再改”为理由连续扩展。

### 巨型文件预防与拆分收益门禁

- 行数只作为架构预警，不作为机械拆分目标。Vue 单文件组件达到 1200 行、Python 文件达到 2000 行时，后续新增功能不得默认继续写入；主协调 Agent 必须先说明新增职责为何不能进入现有独立模块或一个新的深模块，并把判断写入任务方案。
- 单次计划向同一文件新增 200 行以上生产代码时，实施前必须检查是否形成了可独立测试、具有完整职责的业务域或展示块。能够独立成立的职责应直接放入独立模块，避免先堆入巨型文件再返工拆出。
- 禁止为了降低父文件行数创建转发壳、逐函数碎片或“一百行一个组件”。新模块必须隐藏一个完整且有意义的职责，拥有最小稳定接口；删除该模块会迫使这项完整职责回到调用方，而不是只少一层转发。
- 受控拆分原则上应一次迁出至少 250 行连续生产职责。低于 250 行的拆分，只有在能够消除重复实现、重复所有者、高频冲突点或明确的安全风险时才可批准；否则应停止并选择收益更高的边界。该阈值是投入产出门禁，不得通过增加样板代码凑数。
- 不得把“父文件减少行数”单独作为拆分收益。每个拆分任务在实施前后都必须报告：父文件行数变化、新模块行数、生产代码净增减、被迁出的完整职责、公开接口变化、行为等价证据、测试耗时和仍留在父文件中的职责。
- 拆分提交不得同时修改业务逻辑。若差分或测试发现原实现缺陷，应先保持拆分前行为完成结构提交，再另立最小 TDD 任务修复；安全漏洞导致无法保留旧行为时，必须停止拆分并升级为独立修复任务。
- 代码审查发现文件已越过上述预警线、且本次仍继续加入新的独立职责时，应阻止合入，除非任务方案记录了不可拆分证据和后续治理责任人。禁止以“这次只加一点”为由持续累积。

## Development Rules

- Use UTF-8 without BOM for all text files.
- Keep line endings as LF.
- Do not introduce new `.vue.ts` mirror files.
- Do not bypass type errors by broad `any` changes in shared types.
- Prefer fixing type boundaries (`api dto`, `store state`, `component props/emits`) over local casts.

## CodeGraph 调用链定位工具

- 本仓库已安装并初始化 CodeGraph，本地索引目录为 `.codegraph/`，该目录只用于本机分析，不得提交。
- 项目代码量大、历史技术债多；遇到“入口不生效、页面回退、调用链不清、前后端结果投影不一致、LX0609 新旧链路混杂”等问题时，应优先用 CodeGraph 做只读调用链定位，再决定修改点。
- PowerShell 中优先使用绝对路径调用：
  - `$CodeGraph = 'C:\Users\Coldplay\AppData\Roaming\npm\codegraph.cmd'`
  - `& $CodeGraph status .`
  - `& $CodeGraph query CustomerSampleValidation`
  - `& $CodeGraph explore CustomerSampleValidationView`
  - `& $CodeGraph node src/views/workstation-v4/CustomerSampleValidationView.vue`
- 常用场景：
  - 查前端结果查看入口：`SemanticRulesBatchResultDrawer`、`CustomerSampleValidationView`、`QCRecordCompareWorkbench`。
  - 查 LX0609 后端链路：`prepare_luxian_0609_execution`、`execute_luxian_0609_native_*`、`aggregate_luxian_0609_orchestrated_results`、`build_documents_from_domain_bundles`。
  - 查影响范围：`& $CodeGraph impact luxian_0609_result_aggregator`，或使用 `callers` / `callees` 查看调用关系。
- 修改代码后，如需要继续依赖索引判断影响范围，应执行 `& $CodeGraph sync .` 同步索引；索引异常时才执行 `& $CodeGraph index .` 重建。
- CodeGraph 只用于快速定位源码结构和调用关系，不能替代真实病例 trace、pytest/vitest、浏览器验证、性能数据和业务验收判断。

## Frontend UI/UX Rules

- `workstation-v4` 页面必须优先遵循 `apps/medqc-web/docs/gap/WorkstationV4-医疗浅色-DESIGN.md`。
- 医疗工作台 UI 默认采用浅色医疗中后台风格：浅背景、白色卡片、弱边框、轻阴影、清晰信息层级；不要使用深色大背景、营销化头图或高饱和装饰。
- 页面结构优先按“总览/筛选/明细/结果”分层，复杂功能必须拆成可扫描的区块，不要把创建、编辑、执行、结果全部平铺在同一大表单里。
- 组件交互遵循 Vue Pro / Ant Design Vue 的中后台模式：清晰工具栏、主次按钮分明、筛选项聚合、弹窗/抽屉承载复杂创建或编辑流程。
- 质控结果、病历文书、批量任务等高密度页面应优先保证可读性：问题卡片/分组摘要优先于窄表格；避免窄列导致中文逐字换行。
- 新增或重构前端页面时，优先复用现有 `workstation-v4` CSS token、布局容器和组件风格，不另起一套视觉语言。
- 不为纯展示效果修改后端接口契约；如必须改接口，先明确兼容字段和回退策略。

## Prohibited Actions

- Do not commit generated build output (`dist/`, coverage artifacts, temp logs).
- Do not disable CI gates in workflow files to force green.
- Do not add `@ts-ignore`; use `@ts-expect-error` with a short reason when unavoidable.

## Required Checks Before Commit

Run in `apps/medqc-web`:

1. `npm run check:encoding`
2. `npm run lint`
3. `npm run type-check`
4. `npm run test:unit`

If full checks are too heavy locally, run at least:

1. `npm run check:encoding`
2. `npm run lint`

## TypeScript Migration Strategy

- Keep `tsconfig.json` as compatibility config for mixed JS/TS.
- Use `tsconfig.strict.json` for strict migration work (`npm run type-check:strict`).
- Migrate module-by-module:
  1. Define/adjust shared types first.
  2. Fix API layer typing.
  3. Fix store typing.
  4. Fix component props/emits and view integration.
- For new modules, require strict typing from day one.

## Encoding Guardrails

- Enforce `.editorconfig` + `.gitattributes`.
- Keep `npm run check:encoding` in local and CI quality gates.
- If mojibake appears, fix source file encoding first, then content.

## 基本偏好

- 使用中文进行沟通和代码注释。
- commit message 使用中文。
- 使用 UTF-8。

## 终端命令安全策略

- 自动执行：文件读取、目录浏览、git status/log/diff、python/node 脚本执行、npm/pip install、dev server 启动、测试运行。
- 需要确认：文件删除(del/rm/rmdir)、git push/force、全局包安装(npm -g)、数据库写操作。

## 开发习惯

- 默认将边界明确的实现、只读排查、测试和真实数据复核优先委派给子代理；主协调 Agent 负责先行定位根因、定义最小方案与验收标准，并亲自审查关键 diff、真实结果和最终结论。只有涉及同一文件的顺序性修改、跨任务架构取舍或无法安全拆分的短小修复，才由主协调 Agent 直接实现。
- 开发或测试任务中，如果可以将读取、验证、浏览器检查、接口回归等工作拆给子代理并发执行，应优先并发调用子代理，以节约开发和验收时间；涉及同一文件写入或需要严格顺序的修改除外。
- 验证按风险分层：小范围修改先运行对应的聚焦单测、接口或浏览器检查；完整 `npm run type-check` 只在一个功能闭环完成、准备提交或改动共享类型/API 边界时运行。不得每次微小补丁后都重复完整类型检查，避免以低价值等待替代有效验证。
- 质控规则优先用 Python 处理结构化字段、确定性时间计算、精确存在性和可验证正则；若缺少可靠结构化字段，或判定依赖语义理解、跨文书角色/关联关系，且一个小闭环内无法稳定达到验收标准，应立即切换为“裁剪后的最小必要上下文 + 单次受控 LLM 事实提取 + Python 严格校验与状态映射”，不得无限堆叠关键词、正则和状态机。切换前必须明确 LLM 输入边界、输出枚举、失败语义、调用/token 上限及真实病例验收集。
- 每完成一个功能修改或 bug 修复后，主动使用 /commit workflow 提交代码。
