# Luxian0916 独立质控规则包实施计划

> 实施状态（2026-09-16）：首个独立闭环已完成编码、自动化回归和客户样本验证中的 30 份真实病历回放。结果合同、任务完成率和 0609 隔离门禁已通过；`LX0916-022`、`LX0916-032` 的真实客户来源覆盖率未通过发布门禁，因此该规则包继续默认关闭，只能在客户样本验证中显式选择。

**Goal:** 建立完全独立的 Luxian0916 质控规则包，首批包含 32 条非病案首页规则，支持按前端选择启用；不依赖 SC 规则运行时实现，不计算评分，并保证任何 Luxian0916 失败都不会改变或破坏现有 Luxian0609 质控脚本、任务和结果。

**Architecture:** Luxian0916 使用唯一业务命名 `LX0916-*`，拥有自己的规则目录、规则族执行器、状态合同和测试。四川省标准仅作为一次性的政策依据，不作为运行时父规则、别名规则或回退规则；Luxian0916 不调用 SC 规则实现，也不把结果映射回 SC。现有 Luxian0609 与 Luxian0916 分属两个隔离模块和两个独立任务，前端显式选择 Luxian0916 才会执行。

**Tech Stack:** Python 3.10、FastAPI 服务层、pytest、Vue 3 Composition API、TypeScript、Vitest。

---

## 0. 本次实施结论

- 已建立 `LX0916-001..032` 唯一目录、五个规则族、结果合同、独立编排、病历包读取、输入投影、受控语义事实提取和批量执行器。
- 公共规则集目录只保存固定的 32 条发布合同，不导入 0916 执行模块；0916 worker 仅在请求精确选择 `luxian_0916_qc_v1` 时延迟加载。因此 0916 目录或执行器损坏不会阻断 0609 规则集加载。
- 单份病历最多调用一次 LLM；Prompt 只允许输出事实枚举，Python 规则族形成最终状态。模型解析失败返回空事实和内部诊断，不产生 `uncertain` 或 `technical_error` 客户结果。
- 语义事实增加机器门禁：模型不能创建“文书缺失”事实；存在性、完整性和事件事实必须绑定本次受控输入中的文书 ID 与来源类型，截断文书不能产生完整性结论，来源或时间窗不足时返回 `data_quality_gap`。
- 单条规则技术失败不伪造客户结果，任务摘要记录 `diagnostic_rule_failure_count`，前端单独提示查看技术详情。
- 0916 与其他质控集共用系统设置中的全局模型 HTTP 槽位，不再维护质控集专属并发键。每份 0916 病历最多调用一次 LLM，因此病历并发直接受全局槽位限制；这一收敛不修改 0609/0619 的执行器与规则族调度。
- 0916 保存时跳过 0609 专属 canonical record envelope；任务明细和共享读取 API 原样保留 0916 状态、原因、证据和定位。
- 麻醉同意材料在通用病历包中可能位于 `consent_form`。0916 通过自己的输入投影补入该来源，没有扩大公共证据白名单，也不会改变 0609 Prompt。
- 出院医嘱没有独立源表，0916 从 `discharge_record` 与 `daily_course_record` 的可读内容提取；无法确认时保持 `data_quality_gap`。

### Prompt 规范依据和失败边界

Prompt 优先引用仓库内《医疗机构病历书写规范（2026年版）》：首次病程记录、病例特点、诊疗计划的依据位于合并稿 `1878–1886` 行；出院记录和出院医嘱检查要点位于原稿 `4194` 行；麻醉相关文书排序与定义位于合并稿 `1012–1014`、`2623–2657` 行。补充核对的官方来源为国家卫生健康委员会《病历书写基本规范》（2010）：<http://www.nhc.gov.cn/bgt/s10696/201002/8cd7d4d70f4b42da839d2428dcbf723c.shtml>。

对不清楚的质控点执行以下顺序：先查客户规则原文，再查仓库内病历书写规范，仍不足时只检索国家卫生健康委员会、政府或行业标准原文。法规和规范只用于定义事实字段；Prompt 不输出合规结论。无法确认、来源未覆盖、时间窗不明确或模型输出非法时，规则返回 `data_quality_gap` 或内部诊断，不猜测为缺失或不合规。

### 巨型文件门禁检查

`custom_qc_workspace_service.py` 已超过 Python 2000 行。本次仅在既有完整方法 `complete_batch_job` 增加一个默认值为 `True` 的关键字参数 `persist_record_envelopes`，并在原有 envelope 写入点增加一次条件判断。该改动没有新增业务职责、状态机或转发层；它是阻止 0916 结果进入 0609 专属 canonical envelope 的最小公共边界修改。默认分支逐字保持现有 0609 行为，因此不另行拆分巨型文件。

### 已知剩余风险

- `LX0916-022` 的 `consent_form` 路由已有合成 bundle 冻结测试，但本次 30 份客户样本中没有麻醉知情同意来源链，规则结果为 29 条 `data_quality_gap`、1 条 `not_applicable`，真实来源覆盖门禁未通过。
- `LX0916-032` 已证明 `discharge_record` 能进入受控 Prompt，但本次只有 3/30 条结果绑定到该来源，其余 27 条为 `data_quality_gap`。规范要求出院医嘱个性化包含随访计划及注意事项，不能仅凭“随访”等零散文字放宽为合规。
- 在真实覆盖率完成前，上述两条的未知来源必须保持 `data_quality_gap`，不得为了提高命中率推断文书缺失。
- 0609 实施前聚焦测试已有 3 个范围计数失败；完整共享读取测试另有 4 个旧 stub 失败。0916 不修改这些预期，也不得新增 0609 失败。

### 30 份客户样本验证记录（2026-09-16）

客户样本验证池中 30 份病历全部进入独立 `luxian_0916_qc_v1` 任务。验证过程分三次收敛，每次只修复实测暴露的问题：

1. 首次回放发现后台任务查询误用了需要用户身份的读取方法，真实 worker 因缺少 `created_by` 停留在排队状态；改为既有的内部处理查询 `get_batch_job_for_processing`，并增加会拒绝旧调用方式的路由回归测试。
2. 第二次回放发现 14/30 次语义抽取无效，其中 13 次达到 1600 token 输出上限；单次受控调用的完成上限调整为 4096，并要求 JSON 对象响应。再次回放后 30/30 解析有效，无长度终止。
3. 第二次结果仍暴露统一 650 字截断导致入院记录、首次病程记录的完整性事实被安全门禁移除；改为来源优先且按来源设置上限，在 20000 字总预算内优先保留入院记录、首次病程、日常病程、出院记录和知情同意相关材料。

最终回放耗时 155.76 秒，30/30 病历完成，共生成 960 条结果（每份 32 条）：`compliant` 393、`non_compliant` 28、`data_quality_gap` 368、`not_applicable` 171，`not_executed`、`uncertain`、`technical_error` 均为 0。30 次语义调用全部解析成功，规则技术失败为 0。

独立合同复核确认：结果只包含 `LX0916-001..032`，每份病历恰好 32 条且无重复、缺失；任务结果中没有 LX0609 结果；回放前一笔 0609 任务的状态与内容摘要在回放后保持不变。该结论只证明执行合同和隔离性，不等同于全部规则业务准确率已验收。含患者原文的选择清单、运行快照和审计报告仅保存在 gitignore 的 `.tmp/0910-full-audit/`，文件名带 `-private`，不进入提交。

## 1. 不可变业务边界

### 1.1 唯一命名

- 规则集键：`luxian_0916_qc_v1`
- 产品名称：`Luxian0916 质控点 v1`
- 规则编号：`LX0916-001` 至 `LX0916-032`
- Python 模块命名：`luxian_0916`
- 前端常量命名：`LUXIAN_0916_*`
- 任务、结果、导出和诊断包均使用 `Luxian0916` / `LX0916-*`

客户页面、API 交付合同、结果列表和导出中不得出现以下命名：

- `SC-*`
- “SC 扩展规则”
- “SC 来源规则”
- `LX0916-SC*`
- 同一规则同时拥有 0916 与 SC 两个业务编号

### 1.2 禁止嵌套

Luxian0916 不是 SC 规则的包装器、别名层或子规则集。运行时禁止：

```text
LX0916 -> SC 规则 -> SC 结果 -> LX0916 结果
```

禁止以下实现：

- 在 0916 规则目录中保存 `source_rule_id=SC-*` 并依赖它执行；
- 运行时把 `LX0916-*` 替换成 `SC-*`；
- 调用 `run_final_fast_screen()` 执行 SC 规则后再修改结果编号；
- 从 `sichuan_rules_146.json` 动态加载 0916 规则；
- 修复 0916 时要求同时修改 SC 规则提示词或 SC pack；
- SC 规则执行失败后作为 0916 的隐式回退；
- 为了减少开发量复制整套 SC 脚本后继续共享同一事实所有者。

允许复用的仅限无业务口径的基础设施，例如：

- 病历文书读取与标准化；
- 结构化医嘱、检验、检查和手术事件查询；
- LLM 客户端；
- 通用任务队列、取消与日志设施；
- 通用状态 DTO，但 0916 必须自行完成状态合法性映射。

### 1.3 四川标准的角色

四川省质控标准只承担政策依据作用：

1. 实施前人工整理出 Luxian0916 规则原文；
2. 将规则改写为独立的 0916 触发条件、适用条件、排除条件和证据要求；
3. 规则发布后，运行时只读取 0916 自己的目录和脚本；
4. 后续修复直接修改 `luxian_0916`，不回到 SC 规则实现。

政策依据可以记录标准名称和条款文本，但不保留可执行的 SC 规则 ID 依赖。

### 1.4 最短结果路径

吸取既有质控点反复修改聚合器、状态映射和结果补丁的教训，Luxian0916 固定使用以下单向路径：

```text
0916 规则目录
  -> 规则族执行器
  -> Luxian0916RuleResult
  -> 任务保存 / API 原样返回
  -> 前端原样展示
```

业务结论只能在规则族执行器中形成一次。`Luxian0916RuleResult` 至少一次性包含：

- `rule_id`
- `status`
- `reason_code`
- `findings`
- `evidence`
- `suggestion`
- `document_anchors`
- `diagnostics`

后续层的职责严格限定为：

- orchestrator：调用、故障隔离、稳定排序、汇总计数；
- persistence：原样保存；
- API：原样投影；
- frontend：按字段展示和筛选。

禁止新增以下中间解释层：

- 二次业务 Aggregator；
- 重新判定状态的 Finalizer；
- 根据文案猜测状态的 Renderer；
- 保存前后分别执行的状态归一化器；
- API 层补理由、补证据或改状态；
- 前端把技术状态重新解释为合规或不合规；
- 为兼容旧结构而增加新的 0916 回退结果链。

如果客户文案需要格式化，只允许使用纯展示函数调整标题、标签和排版，输入和输出中的 `status`、`reason_code`、事实、证据和定位必须保持不变。

每条规则的修复入口必须可以从 `rule_id` 直接定位到所属规则族文件和对应测试，不允许先经过公共聚合器再反查业务来源。

## 2. Luxian0609 隔离底线

### 2.1 名称澄清

当前仓库中现有稳定客户规则包的真实键是：

```text
luxian_0609_qc_v1
```

本计划把用户所说“0619 那批已经打磨好的脚本”理解为这批现有 Luxian0609 规则。代码、测试和计划均使用真实名称 `0609`，不创建不存在的 `0619` 命名。

### 2.2 代码隔离

Luxian0916 不得修改或依赖下列 0609 权威边界：

- `LUXIAN_0609_QC_V1_RULE_IDS`
- `backend/app/services/luxian_0609/` 下的原生执行器
- 0609 phase scope、交付范围与冻结范围
- 0609 状态映射、聚合器、结果保存和结果投影
- 0609 并发配置、LLM 参数和超时配置
- 0609 前端规则选择、任务文案和结果展示合同

允许在公共规则集目录中**新增**一个 0916 条目，但不得改写 0609 条目、顺序语义、默认选择或专属元数据分支。

### 2.3 任务和结果隔离

- 0609 与 0916 必须创建不同任务 ID；
- 0916 不得作为 0609 的子任务；
- 0916 不得把任何结果写入 0609 任务或 0609 最新结果；
- 0916 失败只能把自己的任务标记为失败；
- 0916 取消、超时、模型异常、解析失败和部分规则失败不能改变 0609 状态；
- 前端关闭或不选择 0916 时，0609 的请求 payload 与当前版本完全一致；
- 删除或下架 0916 规则集后，0609 仍可独立启动、执行、查看和导出。

### 2.4 资源隔离

第一阶段 0916 仅在客户样本验证中手动执行，不与 0609 自动组合运行。0916 使用独立的并发配置键，不能修改现有 0609 配置。

如果两个任务共用同一 LLM 账号或全局 HTTP 连接池，无法承诺并发运行时耗时绝对零影响。第一阶段采取以下约束：

- 不自动同时发起 0609 与 0916；
- 0916 默认采用保守并发；
- 0916 不修改全局 `LLM_HTTP_MAX_CONCURRENCY`；
- 0916 性能验收不得以降低 0609 并发换取；
- 若未来要求严格的性能零影响，应另立任务使用独立队列或独立 provider 配额。

功能结果、脚本和状态隔离是本期硬门禁；共享外部模型服务造成的理论资源竞争必须如实记录。

## 3. 规则目录

### 3.1 运行病历直接检查：14 条

目标文书形成后即可检查内容质量，不依赖终末状态：

| 0916 编号    | 规则名称                                   | 目标文书     |
| ------------ | ------------------------------------------ | ------------ |
| `LX0916-001` | 再次或多次入院记录未总结既往住院诊疗经过   | 入院记录     |
| `LX0916-002` | 无完全民事行为能力患者填写为病史陈述者     | 入院记录     |
| `LX0916-003` | 现病史记录不全或描述不清                   | 入院记录     |
| `LX0916-004` | 未记录与鉴别诊断有关的重要阳性和阴性症状   | 入院记录     |
| `LX0916-005` | 未详细记录入院前检查、治疗经过及效果       | 入院记录     |
| `LX0916-006` | 既往史记录不全                             | 入院记录     |
| `LX0916-007` | 个人史、婚育史、月经史或家族史记录缺失     | 入院记录     |
| `LX0916-008` | 儿童患者缺婴幼儿喂养史或生长发育史         | 入院记录     |
| `LX0916-009` | 体格检查遗漏重要体征或记录不准确           | 入院记录     |
| `LX0916-010` | 首次病程记录无病例特点                     | 首次病程记录 |
| `LX0916-011` | 首次病程记录病例特点未归纳或不全面         | 首次病程记录 |
| `LX0916-012` | 首次病程记录缺诊断依据、鉴别诊断或诊疗计划 | 首次病程记录 |
| `LX0916-013` | 首次病程记录诊断依据或鉴别诊断不充分       | 首次病程记录 |
| `LX0916-014` | 首次病程记录诊疗计划不全面或不具体         | 首次病程记录 |

这些规则只评价已经形成的目标文书内容。目标文书尚未到应写时点时返回“未到检查时点”；已超过法定或客户约定时限仍缺失时，应由独立的时效性规则处理，不能在内容规则中偷判缺失。

### 3.2 运行病历事件触发检查：16 条

只有先确认触发事件发生，才允许判断对应记录是否缺失或不完整：

| 0916 编号    | 规则名称                                             | 必需触发事件       |
| ------------ | ---------------------------------------------------- | ------------------ |
| `LX0916-015` | 重要病情变化未记录或记录不全                         | 明确的病情变化事件 |
| `LX0916-016` | 对病情变化无分析判断或具体处理意见                   | 明确的病情变化事件 |
| `LX0916-017` | 存在不合理检查或不合理用药                           | 检查或用药医嘱     |
| `LX0916-018` | 危急值报告及处理记录不完整                           | 危急值事件         |
| `LX0916-019` | 重要操作未记录或记录不规范                           | 重要操作事件       |
| `LX0916-020` | 修正或补充诊断未记录理由和依据                       | 诊断修正或补充事件 |
| `LX0916-021` | 手术同意书缺项或描述不清                             | 手术安排或手术事件 |
| `LX0916-022` | 麻醉同意书缺项或描述不清                             | 麻醉安排或麻醉事件 |
| `LX0916-023` | 无麻醉记录                                           | 已实施麻醉         |
| `LX0916-024` | 麻醉记录缺项或描述不清                               | 已形成麻醉记录     |
| `LX0916-025` | 手术记录缺项或描述不清                               | 已实施手术         |
| `LX0916-026` | 手术安全核查记录缺项或描述不清                       | 已实施手术         |
| `LX0916-027` | 急诊手术缺主治及以上医师指示记录                     | 急诊手术事件       |
| `LX0916-028` | 非计划再次手术相关记录未说明上次手术情况或原因       | 非计划再次手术事件 |
| `LX0916-029` | 特殊诊疗、特殊用药、试验、高耗材或自费项目同意书不清 | 对应特殊诊疗事件   |
| `LX0916-030` | 病危（重）通知书缺项或描述不清                       | 病危或病重状态事件 |

事件门控必须由 0916 自己定义并测试，不能调用 SC 规则的适用性判断。

### 3.3 出院前或终末检查：2 条

| 0916 编号    | 规则名称                       | 检查时点                       |
| ------------ | ------------------------------ | ------------------------------ |
| `LX0916-031` | 出院记录诊疗经过不全面或不详细 | 已形成出院记录或进入出院前质控 |
| `LX0916-032` | 出院医嘱缺失或不完整           | 已下达出院安排或进入出院前质控 |

这两条不进入普通运行病历持续扫描，避免患者尚未出院时被误判。

## 4. 状态合同

Luxian0916 每条规则必须在目录中显式声明允许状态。建议统一基础状态：

```text
compliant
non_compliant
not_applicable
data_quality_gap
not_executed
```

其中：

- `not_executed`：触发事件或检查时点尚未到，固定使用 `reason_code=evaluation_window_not_mature`；
- `not_applicable`：患者不属于该规则适用场景；
- `data_quality_gap`：应判断但必要数据源不可用；
- `uncertain` 与 `technical_error` 只能保留在内部诊断，不得进入客户交付结果。

规则执行器负责状态判定；Renderer、API 和前端只能搬运，不得重新解释状态。

## 5. 失败语义

- 单条 0916 规则失败：标记该条内部技术失败，其他 0916 规则按既定合同完成；不得写入客户结论。
- 0916 任务整体失败：只更新 0916 任务状态，不生成或覆盖 0609 结果。
- 0916 目录加载失败：前端隐藏或禁用 0916，不回退到 0609、SC 或其他规则集。
- 0916 LLM 解析失败：按 0916 自己的诊断合同记录，不调用 SC 脚本重试。
- 0916 事件门控数据缺失：返回 `data_quality_gap`，不得误判问题，也不得调用 0609 兜底。
- 0916 尚未完成开发或验收：默认不启用，0609 继续按现状运行。
- 0916 回滚：只注销 0916 入口和规则集，不需要回滚 0609 文件或数据。

## 6. 模块边界

### 6.1 新增模块

建议创建一个具有完整职责的深模块：

```text
backend/app/services/luxian_0916/
  __init__.py
  contracts.py
  rule_catalog.py
  admission_rules.py
  first_course_rules.py
  course_event_rules.py
  surgery_consent_rules.py
  discharge_rules.py
  orchestrator.py
  bundle_reader.py
  input_context.py
  semantic_extractor.py
  batch_worker.py
```

职责：

- `rule_catalog.py`：32 条规则的唯一目录、名称、适用场景、允许状态和所需证据；
- `contracts.py`：唯一的 `Luxian0916RuleResult` 与文书定位合同；
- `admission_rules.py`：`LX0916-001..009`；
- `first_course_rules.py`：`LX0916-010..014`；
- `course_event_rules.py`：`LX0916-015..020`；
- `surgery_consent_rules.py`：`LX0916-021..030`；
- `discharge_rules.py`：`LX0916-031..032`；
- `orchestrator.py`：只负责调用规则族、收集结果和隔离失败，不重新解释规则结论。
- `bundle_reader.py`：只读取通用 running/final 病历包，不经过四川质控服务或 0609。
- `input_context.py`：把通用病历包投影为 0916 唯一事实上下文，并补入 0916 专用 `consent_form` 来源。
- `semantic_extractor.py`：单次受控 LLM 事实提取；限定输入、输出枚举、Token 和失败语义。
- `batch_worker.py`：独立任务执行、并发、进度、失败隔离和原样保存。
- `Luxian0916RuleResult`：由规则执行器直接生成的唯一结果合同；任务、API 和前端不得创建第二个业务结果模型。

删除任一规则族模块都会迫使其完整业务职责回到 orchestrator，因此不是转发壳拆分。

### 6.2 禁止导入关系

```text
luxian_0916 -> luxian_0609    禁止
luxian_0609 -> luxian_0916    禁止
luxian_0916 -> SC rule pack   禁止
SC rule pack -> luxian_0916   禁止
```

可以共同依赖无业务口径的底层文书、事件、LLM 和任务基础设施。

### 6.3 计划修改文件

- Create: `backend/app/services/luxian_0916/__init__.py`
- Create: `backend/app/services/luxian_0916/contracts.py`
- Create: `backend/app/services/luxian_0916/rule_catalog.py`
- Create: `backend/app/services/luxian_0916/admission_rules.py`
- Create: `backend/app/services/luxian_0916/first_course_rules.py`
- Create: `backend/app/services/luxian_0916/course_event_rules.py`
- Create: `backend/app/services/luxian_0916/surgery_consent_rules.py`
- Create: `backend/app/services/luxian_0916/discharge_rules.py`
- Create: `backend/app/services/luxian_0916/orchestrator.py`
- Create: `backend/app/services/luxian_0916/bundle_reader.py`
- Create: `backend/app/services/luxian_0916/input_context.py`
- Create: `backend/app/services/luxian_0916/semantic_extractor.py`
- Create: `backend/app/services/luxian_0916/batch_worker.py`
- Modify: `backend/app/core/settings.py`
- Modify: `backend/app/routers/qc_sample_pools.py`
- Modify: `backend/app/routers/qc_sichuan.py`
- Modify: `backend/app/services/custom_qc_workspace_service.py`
- Modify: `backend/app/services/qc_rule_sets.py`
- Modify: `backend/app/services/sample_validation_rule_sets.py`
- Create: `backend/tests/unit/luxian_0916/`
- Modify: `backend/tests/unit/test_qc_rule_sets.py`
- Modify: `backend/tests/unit/test_qc_sample_pools_router.py`
- Modify: `src/views/workstation-v4/customer-sample-validation/customerSampleValidationConfig.ts`
- Modify: `src/views/workstation-v4/customer-sample-validation/useCustomerSampleValidationController.ts`
- Modify: `src/views/workstation-v4/customer-sample-validation/batchJobPresentation.ts`
- Modify: `src/views/workstation-v4/customer-sample-validation/CustomerSampleQcTaskStatusBar.vue`
- Modify: `tests/unit/views/workstation-v4/CustomerSampleValidationView.spec.ts`

### 6.4 明确不修改

- `backend/app/services/luxian_0609/` 全部文件
- 0609 规则目录、phase scope、状态策略、聚合器和结果投影
- SC 规则 JSON、launch tier、fast-screen pack 和 SC 提示词
- `src/styles/index.prebuilt.css`
- 数据库结构
- 构建输出、运行时日志和临时诊断产物

## 7. 开发阶段

每一阶段遵循“小闭环：规则原文 → 独立实现 → 聚焦测试 → 真实病历复核 → 停止”。不得一次性复制 32 条 SC 脚本后再批量修复。

### Task 1：冻结 0609 保护基线

**Files:**

- Read only: 0609 规则目录、执行器、聚合与测试
- Create, do not commit: `.tmp/0910-full-audit/luxian-0916-0609-protection-baseline-private.md`

**Steps:**

1. 记录实施开始时的 Git commit。
2. 记录 `LUXIAN_0609_QC_V1_RULE_IDS` 完整集合和数量。
3. 记录 0609 客户交付范围、执行范围和冻结范围。
4. 选择现有已验收保护病例，记录 0609 状态、原因码和关键证据。
5. 运行现有 0609 聚焦测试并保存结果。
6. 后续每个 0916 阶段完成后重复相同对照。

保护基线必须对应实施开始时点；不得使用早于现有 0609 修复的历史产物。

### Task 2：建立独立 0916 规则目录

**Files:**

- Create: `backend/app/services/luxian_0916/rule_catalog.py`
- Test: `backend/tests/unit/luxian_0916/test_rule_catalog.py`

**Steps:**

1. 先写失败测试，断言规则编号严格为 `LX0916-001..032`。
2. 断言目录中不存在任何 `SC-*` ID 或运行时来源字段。
3. 断言规则名称、场景、触发类型、允许状态和所需证据齐全。
4. 断言 14 条直接运行、16 条事件触发、2 条出院前置。
5. 实现最小目录并运行测试。
6. 确认目录不导入 0609 或 SC 模块。

### Task 3：实现入院记录规则族 `LX0916-001..009`

**Files:**

- Create: `backend/app/services/luxian_0916/admission_rules.py`
- Test: `backend/tests/unit/luxian_0916/test_admission_rules.py`

**Steps:**

1. 为每条规则写阳性、阴性、边界和数据不足测试。
2. 明确儿童、女性、无完全民事行为能力、再次入院等适用条件。
3. 优先用结构化字段和确定性判断。
4. 需要语义理解时只提供当前入院记录的最小必要上下文。
5. 输出只能使用该规则允许状态。
6. 用真实病例复核证据定位和误报。
7. 重跑 0609 保护基线。

### Task 4：实现首次病程规则族 `LX0916-010..014`

**Files:**

- Create: `backend/app/services/luxian_0916/first_course_rules.py`
- Test: `backend/tests/unit/luxian_0916/test_first_course_rules.py`

**Steps:**

1. 为病例特点、诊断依据、鉴别诊断和诊疗计划分别定义判定边界。
2. 避免把文书存在性与内容质量混为一条规则。
3. 对语义判断限定输出枚举和失败语义。
4. 完成真实病例复核。
5. 重跑 0609 保护基线。

### Task 5：实现病程事件规则族 `LX0916-015..020`

**Files:**

- Create: `backend/app/services/luxian_0916/course_event_rules.py`
- Test: `backend/tests/unit/luxian_0916/test_course_event_rules.py`

**Steps:**

1. 先实现病情变化、危急值、重要操作和诊断变更事件门控。
2. 没有触发事件时返回 `not_applicable`。
3. 事件已发生但检查时点未到时返回 `not_executed / evaluation_window_not_mature`。
4. 应检查但数据源不可用时返回 `data_quality_gap`。
5. 只有证据充分时返回 `non_compliant`。
6. 完成真实病例复核和 0609 基线回归。

### Task 6：实现手术与知情同意规则族 `LX0916-021..030`

**Files:**

- Create: `backend/app/services/luxian_0916/surgery_consent_rules.py`
- Test: `backend/tests/unit/luxian_0916/test_surgery_consent_rules.py`

**Steps:**

1. 先建立手术、麻醉、急诊手术、再次手术、特殊诊疗和病危重事件门控。
2. 不得因为找不到同意书就直接判问题，必须先证明适用事件存在。
3. 不得复用 SC 手术 pack 或提示词。
4. 为每种事件准备阳性、阴性、边界和数据缺口测试。
5. 完成真实病例复核和 0609 基线回归。

### Task 7：实现出院前规则族 `LX0916-031..032`

**Files:**

- Create: `backend/app/services/luxian_0916/discharge_rules.py`
- Test: `backend/tests/unit/luxian_0916/test_discharge_rules.py`

**Steps:**

1. 只有出院安排或出院记录形成后才进入检查。
2. 普通在院阶段返回 `not_executed / evaluation_window_not_mature`，不得误报。
3. 出院记录缺少诊疗经过或出院医嘱时输出明确证据。
4. 完成真实病例复核和 0609 基线回归。

### Task 8：建立 0916 独立编排与故障隔离

**Files:**

- Create: `backend/app/services/luxian_0916/orchestrator.py`
- Test: `backend/tests/unit/luxian_0916/test_orchestrator.py`

**Steps:**

1. 先写合同测试，断言规则执行器直接返回完整 `Luxian0916RuleResult`。
2. 编排器只调用 0916 规则族并原样收集结果。
3. 断言编排前后的 `status`、`reason_code`、事实、证据和定位逐字段相等。
4. 单条失败不覆盖其他规则结果。
5. 整包失败不调用 0609 或 SC 回退。
6. 注入 0916 异常，断言 0609 resolver、任务和结果不变。
7. 增加导入边界测试，禁止 0916 与 0609/SC 互相依赖。
8. 记录 0916 独立调用、Token、耗时和失败数量。

### Task 9：接入规则集目录和客户样本验证

**Files:**

- Modify: `backend/app/services/qc_rule_sets.py`
- Modify: `backend/app/services/sample_validation_rule_sets.py`
- Modify: `backend/tests/unit/test_qc_rule_sets.py`
- Modify: `backend/tests/unit/test_qc_sample_pools_router.py`

**Steps:**

1. 注册 `luxian_0916_qc_v1`，但默认不自动执行。
2. resolver 按精确键路由到 0916 orchestrator。
3. 未知键继续报错，不回退。
4. 0916 失败仅更新自身任务。
5. 任务保存和 API 返回的 0916 结果与执行器结果逐字段一致。
6. 0609 目录 DTO 与修改前逐字段一致。
7. 路由级注入 0916 失败，验证 0609 任务可继续执行。

如果接入必须改写 0609 公共编排或结果聚合，立即停止并重新评审，不得硬接。

### Task 10：前端显式开关与命名

**Files:**

- Modify: `src/views/workstation-v4/customer-sample-validation/customerSampleValidationConfig.ts`
- Modify: `src/views/workstation-v4/customer-sample-validation/useCustomerSampleValidationController.ts`
- Modify: `tests/unit/views/workstation-v4/CustomerSampleValidationView.spec.ts`

**Steps:**

1. 主规则集显示 `Luxian0916 质控点 v1`。
2. 页面只显示 `LX0916-*`，不显示 SC 编号。
3. 用户未选择 0916 时不提交任何 0916 参数。
4. 0916 不作为默认规则集。
5. 0916 目录不可用时禁用该选项，不影响 0609 卡片和按钮。
6. 0916 任务失败时只显示该任务失败，不改变 0609 最近任务状态。
7. 前端只展示后端状态和证据，不增加 0916 状态推断或兜底映射。
8. 前端 0609 快照测试必须保持通过。

## 8. 发布门禁

### 8.1 0916 自身门禁

- 32 条规则全部具有独立 `LX0916-*` 身份。
- 运行时代码不包含 SC 规则 ID 映射。
- 运行时代码不导入 SC pack 或 0609 模块。
- 每条规则至少有阳性、阴性、边界和数据不足测试。
- 事件型规则具备显式触发门控。
- 从规则执行器到任务保存、API、前端的状态、原因码、事实和证据逐字段一致。
- 不存在二次业务聚合器、状态 Finalizer 或前端业务状态推断。
- 任一 `LX0916-*` 可直接定位到唯一规则族文件和对应测试。
- 客户交付结果无 `uncertain`、`technical_error`。
- 至少一组真实病历回归完成，并记录准确性和耗时。

### 8.2 0609 零回归门禁

以 Task 1 记录的实施开始 commit 和保护病例产物为对照：

- `LUXIAN_0609_QC_V1_RULE_IDS` 集合、顺序和数量不变；
- 0609 客户交付范围、执行范围和冻结范围不变；
- 0609 已验收病例的状态、原因码和关键证据不变；
- 0609 单元测试和真实病例回归通过；
- 0916 成功、失败、超时、取消四种情况下，0609 任务状态和结果均不变；
- 前端不选择 0916 时，0609 请求 payload 与原版本一致；
- 删除 0916 注册后，0609 仍可独立运行。

任一项不满足，0916 不得发布。不得为了让 0916 上线而修改 0609 预期结果或降低 0609 测试标准。

### 8.3 工程质量门禁

运行：

```powershell
py -3.10 -m pytest backend/tests/unit/luxian_0916 -q
py -3.10 -m pytest backend/tests/unit/test_qc_rule_sets.py backend/tests/unit/test_qc_sample_pools_router.py -q
npx vitest run tests/unit/views/workstation-v4/CustomerSampleValidationView.spec.ts
npm run check:encoding
npm run lint
npm run type-check
npm run test:unit
```

提交前检查：

```powershell
git status --short
git diff --cached --name-only
git diff --check
```

只使用路径限定提交，不提交当前工作区中的预编译 CSS、构建信息、临时产物或其他任务文件。

### 8.4 最终自动化验收记录（2026-09-16）

- `py -3.10 -m pytest backend/tests/unit/luxian_0916 -q`：198 passed。
- 三个客户样本验证前端聚焦测试文件：87 passed。
- `npm run test:unit`：121 个测试文件、997 个测试通过。
- `npm run type-check`、`npm run lint`、`npm run check:encoding`：通过。
- 0916 共享任务读取合同聚焦用例：通过；完整共享读取文件仍有 4 个实施前已存在的 0609 stub 失败，本次未扩大失败集合。
- 0609 聚焦测试仍保留实施前记录的 3 个范围计数失败；0916 未修改 `backend/app/services/luxian_0609/`，也未改写这些旧预期。
- 独立复核曾复现“模型输出 `presence=missing` 可形成无来源不合规”的缺陷；修复后，缺失事实不能由模型注入，相关集成测试确认其安全降级为 `data_quality_gap`。
- 已完成 30 份真实客户病历回放，任务完成率、状态合同、耗时和 0609 隔离性已留证；`LX0916-022`、`LX0916-032` 的来源覆盖门禁未通过，不能宣称完成全部业务准确性验收，继续通过显式选择和默认关闭控制风险。

## 9. 交付顺序

1. 先冻结 0609 基线。
2. 建立 0916 独立目录和状态合同。
3. 按五个规则族逐个完成小闭环。
4. 所有规则族完成后再接任务入口。
5. 先在客户样本验证中手动启用。
6. 完成真实病历和 0609 零回归验收后，才允许显示给客户。
7. 病历池自动运行、运行病历定时扫描和出院前拦截分别另立任务，不在本期顺手接入。

## 10. 剩余风险

1. 32 条规则需要独立打磨，工作量高于复用 SC，但后续修复路径更短、业务所有权更清楚。
2. 内容质量规则可能需要 LLM，必须逐条控制输入范围、输出枚举和失败语义。
3. 事件门控依赖医院数据覆盖率；缺数据必须返回 `data_quality_gap`，不能伪装为不适用或合规。
4. 共用外部 LLM provider 时仍可能存在资源竞争；功能隔离不等于物理资源隔离。
5. Luxian0916 尚未完全验收前保持默认关闭，不能以半成品替换 0609。
