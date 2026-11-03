# P5-B收缩交付：最小Context准入与06-01-04闭环

PR29后续复审确认的病程族局部结果保留、Gateway候选身份边界及新增隔离验证，见[评审修复记录](2026-11-03-pr29-review-fixes.md)。下文514项为原交付历史，不代替新Head的771项验证或远端CI。

本报告替代前版报告中“本地调用统一补4096”等较宽实现口径，不扩展为整个LX0609适配16K。

## 基线、范围与结论

- 开始HEAD：`ca201cae55f514585ba3a1238a719d7838f500d9`；工作区干净。
- 工作树：`C:\medqc-token-budget-p5b-20261102`；分支：`codex/lx0609-token-budget-p5b-20261102`。
- 本轮沿用现成独立工作树，仅增量修正准入能力、输出上限继承和必要观测。没有合并其他开发线，没有改动集成分支。
- 默认保持原行为：`LLM_LOCAL_TOKEN_BUDGET_ENABLED=false`、`LX0609_TOKEN_SPLIT_ENABLED=false`。没有启用或重启运行中服务。

| 问题 | 当前结论 |
|---|---|
| 哪些路径具备保护 | 正式LX0609统一客户端direct、Gateway最终组装/发送、Prime及补核/升级的实际发送边界具备准入；开启开关后生效。未知能力或形态明确拒绝 |
| 哪些能够安全拆分 | 原检查/培养独立事件及06-01-04事件×病程配对；保留完整正文、稳定引用和必要比较目录，复用原归并 |
| 哪些仍不能在16K执行 | 继承16384输出的非空请求；单事件/单文书/必要比较目录仍超限的请求；没有对应DSH计量合同、消息形态验证或计量组件的请求 |
| 是否已做真实16K验收 | 未做。本轮只有Mock计量、固定应答与内存SQLite；没有宣称医学质量等价 |

## 本轮最小修正

1. `llm_token_budget.py`的能力和计量器身份增加`verified_message_shapes`，逐一绑定纯文本角色序列，例如`user`、`user|user`、`system|user|user`。默认空集合，不自动从`verified=true`推导消息形态支持。配置与已安装计量器的声明必须一致。
2. 单User验证不能放行两User或system+user；工具、富媒体和未验证字段暂不支持。未知形态在计量及模型排队前返回`CAPABILITY_UNVERIFIED / message_shape_unverified`，不会先发送再依赖服务端钳制。
3. 删除检查公共包装器中未指定上限就补4096的逻辑；主抽取预探测也不再带4096。调用点显式512/600/1024/4096等参数继续保留；未指定的沿用客户端原配置。没有动态输出预算算法，没有根据734次历史请求P95调整参数。
4. 只有本地严格准入开启时，复用已有请求观测记录最终参数、实际输出Token与finish_reason；不新增观测表或平台。准入日志保留消息形态、计量输入、实际输出预留、模型/Profile及拒绝原因，通过已有logical_call_id/request_id关联。没有用实际输出量代替发送前输出预留。
5. 策略版本为`lx0609-token-batches-p5b-v2`，消息形态声明进入能力/计量器身份及既有冻结隔离。旧冻结不删除、不改写；同输入、同模型、同协议仍可热复用。

共享抽取本轮**恢复继承原输出配置**。默认16384仍是输出上限，无法连同非空输入和安全余量放入16K，因此明确拒绝，而不是悄悄改4096。固定应答中以既有客户端配置600走通链路，仅证明参数/合同搬运正确，不是生产600的推荐或医学验收。

## 正式链与结果边界

原证据快照 → 原检查族投影/共享抽取 → 06-01-04专项与定向补核 → 原配对校验/事件归并 → Native → Binding → Finalizer → Aggregator → Canonical。

- 发送前使用最终payload的全部消息、实际输出参数及Profile安全余量核算；缓存Token不扣Context。
- Gateway收到严格准入要求时，不能因自身默认开关关闭而绕过；旧Gateway会拒绝新控制字段。首答、补核及升级沿同一个发送边界检查，不增加外部模型兜底。
- 可拆时复用现有事件和配对选择，不按最近文书关联，不裁剪长文、不用摘要取代证据。必要比较目录不能丢；对照事件不成为新待核任务。
- 已成功配对保留，局部否定不能形成完整缺失；早期失败/晚期成功不得制造确定超时。无法计量、超限及不能拆分均属于技术未完成，不回退成临床资料不足/合规/不适用。
- 失败范围、已成功范围及不完整标记沿既有合同保留；不完整结果不冻结为完整成功。技术原因沿Engine/Binding/Finalizer保留，不进入自动补跑的无限循环。
- 既有有限预算继续使用：最多16次请求、8层拆分、8次恢复、240秒；专项仍受原8次调用上限约束。取消停止后续派发。没有扩大规则包或引入平行执行器。

## 其余调用点的16K不兼容/未验收清单

以下为源码级清单，不是734次历史请求的逐条还原。除确定的默认16384算术不兼容外，没有真实本地Token值的项目标为条件风险或未验收，不能声称每次都超限。

| 位置/调用点 | 保留的输出上限 | 原因与当前处理 | 后续建议 |
|---|---|---|---|
| `native_exam_lab_execution._generate_exam_lab_fact_response` | 继承客户端，默认16384 | 默认输出预留本身已占满16K；事件二分不能解决输出预留问题。严格准入拒绝，不自动降上限 | 核实每批正式输出需求后另行确定配置，或选更大Context |
| 同文件`generate_ct_response`（06-01-01） | 继承客户端 | 同上；不在本轮06-01-04闭环范围 | 单独审核其输入/输出预算，不批量套4096 |
| `exam_result_record_check._check_result_batch` | 原4096，最终仍受既有客户端配置约束 | 配对可拆；单文书、单报告或比较目录仍超限则技术未完成 | 更大Context，或另行证明安全分片 |
| `exam_finding_relevance.classify_exam_finding_relevance` | 原1024 | 输入过大仍可能超限；原语义/分组不变 | 沿真实计量确定是否需专项分批 |
| `exam_reason_check._check_reason_batch`、`exam_finding_analysis._check_batch` | 原4096 | 沿原窗口/批次及统一准入；本轮不保证所有检查规则的Token拆分 | 单独核对原有投影完整性和可拆边界 |
| `native_consultation_episode_execution._execute_consultation_episode_rules`的意见/措施核对 | 多处继承客户端 | 默认16384不兼容；候选间语义依赖未在本轮重构 | 按真实阶段核实，保留技术失败，不变成临床资料不足 |
| `native_course_quality_execution.execute_luxian_0609_native_course_quality_rules` | 多处继承客户端 | 同上；未完成任意长病程分片 | 分调用点收口，不统一减输出 |
| `native_transfusion_execution`的抽取/补核 | 多处继承客户端 | 默认输出或多事件输入可能不兼容 | 保留原医学关联，单独验证分批 |
| `extended_document.discharge_course_content` | 原8192 | 留给输入的空间更小；没有真实本地计量，不声称可在16K执行 | 先验证必要原文范围和输出需求 |
| `extended_document.antimicrobial_action_extraction`、`discharge_diagnosis_equivalence`等 | 原2048 | 保留；输入仍需实际计量，不属于本轮全面改造 | 不因P95批量改参 |
| `extended_document.antimicrobial_order_reason`、`diagnosis_change_extraction`等 | 原4096 | 同上；原有字符/候选投影完整性未因此获得质量认证 | 专项材料与质量验收 |
| `native_treatment_order_consistency`、手术门控联合文本抽取 | 原512 | 保留，不因为短输出就免除最终输入计量 | 若触发超限仍明确未完成 |
| Strata Prime后续多消息请求 | 原参数 | 只有相同角色序列、模型、Tokenizer及模板均经验证才可准入；检查拆批与远程Prime组合仍因共享恢复预算未闭环而拒绝 | DSH交付对应形态合同后再另验收，不猜测API |

本轮没有为会诊、病程或扩展文书新增完整拆批。既有薄异常保护仅防止预算拒绝被旧catch转成临床结论；不代表这些族已完成16K适配。原有投影或字符限制仍需各自验证，最终Token准入不能代替材料完整性验收。

## 配置与真实验收依赖

继续使用现有Gateway部署Profile中的`context_budget`，不增加前端页面或另一配置中心。除模型/版本、Tokenizer/版本、聊天模板/版本、Context、安全余量、Thinking及计量器身份外，新增：

```json
{
  "verified": false,
  "verified_message_shapes": []
}
```

这是附加到原能力对象的未验收示意，不是完整可用Profile。DSH确认单User后才能声明`["user"]`；不得据此声明`user|user`或`system|user|user`。计量器注册身份也须包含相同角色序列，不能只改配置字段绕过验证。不存在组件时为COUNT_UNAVAILABLE，没有任何字符长度估算兜底。

本轮没有取得或验证新的DSH分词组件、聊天模板/特殊Token、不同消息形态、Thinking/输出语义及计量误差。真实回放需另行授权，且不等同于医学质量等价。已有短且可写的冻结目录仍是前置条件；Windows普通长路径限制需通过已有冻结目录配置规避，本轮未重建缓存布局。

回滚：关闭新拆批仅恢复旧检查分批，严格准入可保留；停用未验收本地Profile或明确选择已有Provider。关闭准入后继续向16K服务发送超长请求不是安全回滚。

## 隔离验证

先写失败用例确认两处差异：未验证双消息被放行、未指定上限被补4096；修复后定向通过。

- 单User/多消息/不同角色序列、富媒体/工具未验证形态，以及计量器身份不一致，均有明确拒绝用例。
- 512、600、1024、4096和未指定上限均保留；继承16384的超限请求零发送。
- 真实统一客户端配置600 + Mock计量/固定HTTP应答走共享抽取与专项，并经正式保存读取、热冻结验证；两次最终发送均为600。
- 真实统一客户端首答成功、补核最终Prompt计量超限，补核零HTTP；已成功事件1/3保留，事件2准确未完成。
- 复用原保护集验证局部否定、早期失败/晚期成功、取消、次数上限、不完整不冻结，以及Native至Canonical的状态/事件/证据/时间关系。
- 本地严格模式复用请求观测，测试确认实际输出Token及finish_reason可见，完整Prompt和应答文本未进入日志。

命令均在`apps/medqc-web/backend`：

```powershell
python scripts/run_qc_scheduler_tests.py --profile offline --suite context-budget-p5b tests/unit/test_llm_gateway_api.py tests/unit/test_llm_dispatch_routing.py tests/unit/test_qc_llm_client_thinking_budget.py tests/unit/test_llm_request_observation.py
```

测试入口主动阻断网络、dotenv、外部进程和业务数据库，只允许内存SQLite及独立临时冻结。没有用假Key代替网络隔离。

最终命令结果见交付记录追加。未重跑全量前端测试、全后端测试或上一轮2487项扩大并集。上一轮两项扩大回归问题仍保留在历史报告，不因本轮必要保护集通过而宣称全量CI绿。

未合并、推送、部署或重启；未连接模型服务/客户机；未连接或写业务PG；未重跑病历或批次质控。没有新增患者数据读取、历史Token查询或真实模型调用。


## 最终交付记录

- 上述定向隔离命令：**514通过、0失败、0跳过**，1项既有Pydantic弃用警告。包含正式结果保存读取及百炼兼容保护；不代表514份病例或真实模型质量验收。
- 修改Python文件Ruff、`git diff --check`通过；只读ESLint（--quiet、无--fix）通过。暂存编码检查在提交前执行。没有前端修改，未重复全量前端测试或类型检查。
- 本轮源码变动限于3个已有模块：消息形态能力/准入、检查包装器输出继承、复用现有请求观测。其余为3个保护测试文件和本报告/历史报告链接。
- DSH真实计量组件、具体模型及聊天模板、消息形态、输出/Thinking语义和真实原文回放仍未验收；开关保持关闭。已有日志、算法能力、Mock计量和临床正确性分别陈述，没有相互替代。
