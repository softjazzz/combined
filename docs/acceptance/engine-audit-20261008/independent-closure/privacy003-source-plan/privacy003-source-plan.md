# PRIV003：真实 CLI 身份来源最小接线设计

固定提交 `aa7a98c7e43bc23439db485fa56cd90ea6da4bd1`，目录 `F:/MedQC-worktrees/qc-integration-20261008`。继承 511 的已审发送边界及后续集成，本轮仅追踪两个仍 failclosed 的 CLI 来源；不重审已关闭边界，不运行测试，不改生产，不读取 `.env`/患者/PG，不联网或调模型。固定源码完整 SHA256 见 `privacy003-source-plan.json`。

**结论：完整可信原始身份入口确实存在于既有 worker collect 操作，但两个独立 CLI 当前都没有它，也没有现成生产调用方把该内存对象借给两个脚本。现有代码不能通过简单参数接线恢复真实 CLI；保持拒发。** CLI 不可用是身份来源功能前置未闭，不表示本轮又发现发送泄漏。不要为了过门禁创建没有调用方的新 API。

## 精确来源与当前断点

以下 app/ 与 scripts/ 代码索引以 `F:/MedQC-worktrees/qc-integration-20261008/apps/medqc-web/backend/` 为根；文件锁清单则以仓库根为根：

1. `app/services/sichuan_workspace_batch_worker.py:1386` 对正式 0609 操作创建 `_Luxian0609IdentityCollector`；`:1508` 调用 `workspace.collect_records`，`:1518` 传入 `identity_collector.capture`。
2. `app/services/custom_qc_workspace_service.py:2882` 的 `CustomQCWorkspaceService.collect_records` 将该可选回调原样传给 `RecordRepository.collect_records`（`:2897`）。
3. `app/services/qc_workspace/record_repository.py:810` 打开既有 session；`:844` 在既有 mr ORM `.all()` 后、序列化前，向 `_capture_private_orm_identities` 交付已加载实体。`:20` 回调只消费这些实体，不补查；`:207–209` 和 `:342–344` 同样消费既有 registration/admission/discharge anchor ORM。
4. `app/services/luxian_0609/privacy_identity_context.py:106` 的 capture 只读 `vars(source)`，避免 lazy load；source allowlist 为 mr、inpat_registration、admission_record、discharge_record。已有 `_ORM_IDENTITY_FIELDS` 覆盖 name、mr_no、inpat_no、id_card_no、insurance_no、contact_number、contact_name、contact_address、contact_telephone、nativeplace、currentaddress、work_unit。provider_for_case（`:124`）按完整三元 CaseRef，必须仍活跃且有未 masked 的原始姓名。已加载字段实际缺失时不能编造值或认为覆盖完整；必须继续拒绝缺有效原名的病例。
5. worker `:1541` 捕获既有 hydrate 返回的姓名/mr_no/inpat_no，作为补充，不能取代完整 ORM 身份；`:3277` 在单病例 scope 使用该 collector 的 live provider。`:4018` 自动重试前 close，`:4042` finally close。

两个 CLI 的断点：

| 路径 | 现有合法输入 | 原始身份是否足够 |
|---|---|---|
| ordinary main（shadow `:307`）→ `_run`（`:240`）→ source selector（ordinary_validation `:179`） | 现有参数化 SELECT 投影 running_record_bundle 的三ID、consultation 文档ID/时间/正文、daily/senior EXISTS | 不够。SQL `:208–216` 没有投影 name/mr_no/inpat_no/idcard/联系方式；没有持有已加载完整 ORM，正文不能当身份猜测来源。`_run` 无 collector 时先拒绝。 |
| semantic main（`:704`） | 目前仅解析参数并固定 return 1；即使 programmatic builder 收到 case-map/candidate/review queue，它们也不等于可信身份来源 | 不够。JSON坐标或外部声称的姓名都不能替代内存 collector。 |
| semantic builder（`:471`）→ native source reader（`:1565`） | daily/senior/consultation 的固定批准临床字段；source reader 以三ID SQL filter，返回批准投影 | 不够。相关 whitelist 含正文/文档/作者/时间，未返回完整患者身份，而且 builder 在合法 source provider 预检前不会调用 row_loader。先放宽预检来加载正文不是接线。 |

`ConsultationRecord` 确实继承 `PatientBasicMixin`（cdm.py `:565`），后者在 `:43–46` 声明 inpat_no/mr_no/name；这只证明表模型字段存在。当前 selector/native SELECT 没读取它们，不能将“数据库可能有”写成“此操作已经取得”。这三字段也不是全部已知身份。扩大 SQL 投影或增加 collect 调用都是新的数据采集设计，本轮不推荐为工具恢复引入。

## 自然 caller 核实

在固定 backend app/scripts 中追踪 `build_semantic20_review`、两个脚本模块名、`_private_identity_collector=`。semantic 的调用者只有自身定义/CLI（当前固定拒绝）与测试；ordinary-shadow 的 `_run` 只有自身 main 与测试。本轮未找到既有 app/worker 生产 caller 导入并调用它们。worker 已持有合法 collector，但其实际调用是正式 native 执行链，不是这两个审计脚本；它不会自然产生 semantic 的 case-map/candidate/review queue，也不会执行 ordinary selector 的验证台账。

因此同进程桥接在类型和生命周期上可行，**在现有真实调用链中未被使用、没有已确认自然 caller**。跨 CLI 进程不能借入 worker 的闭包/collector；把它写 JSON、pickle、bundle、文件、缓存或从 argv 接收原始身份均不符合本次约束。

## 最小设计：已有能力，不增建空接口

只有当真实业务调用方明确需要“在本次已授权 collect 操作中执行这项验证”时，才在那个已存在调用方接线：

```text
已有操作 owner 创建 collector
  → 原本就要执行的 collect_records(..., record_refs=完整精确CaseRef,
                                    _private_identity_collector=collector.capture)
  → 对验证需要的每个CaseRef调用 live provider 并预检
  → 借给已存在的 ordinary _run(...,_private_identity_collector=collector)
     或 semantic build_semantic20_review(...,_private_identity_collector=collector)
  → 仅返回原有安全台账/结果
  → owner finally close（含异常、取消、重试）
```

这只是参数流设计，未增加函数、未建议修改 worker 的正式执行语义。两个脚本已有借入参数与最终发送 gate，无需重做。调用方必须本来就要运行上述 collect 查询；为 CLI 临时补一次 `collect_records` 不属于“无新增查询的桥接”。选择范围必须用完整 CaseRef，不得退化为同 visit_id 或 patient_id；没有匹配 holder/原始姓名则拒发；材料provider继续合并，并保持最终 attempt 重新检查。

生命周期 owner 是 collect 操作，不是脚本：脚本借用对象，不关 borrowed collector；owner在脚本及其所有合法子任务结束后 finally close；每个 case scope 退出使延迟子任务失效；重试新操作重新从那次合法读取 capture，不复用已关闭旧 provider。原始值不进入可序列化 bundle、结果、日志、进度或全局缓存，不读正文推测姓名，不用生产硬编码字段值充当来源。

## 独占写入范围与当前阻断

**当前推荐生产待改文件集合为空。** 已有参数接口足够表达桥接；缺真实 caller 时继续改脚本不能创造合法来源，也不应新增永不调用的 `_run_from_collected_context` 或数据读取框架。现有 CLI 拒发保持。

如后续 owner 明确一个自然 caller，先取得该 caller 文件独占锁，才新增“调用已存在脚本函数时传 collector”的窄改动；锁名/路径必须以该真实 caller 为准，本轮不能预先杜撰。由于 worker当前不是这两项验证的自然 caller，不建议取得 worker 锁来强插验证业务。

只有 caller 确实需要调整脚本协议时，条件性文件锁范围是以下两个现有文件，逐一交接；不触碰当前 scope6 占用的 PRIV002 公共模块：

- `apps/medqc-web/backend/scripts/run_luxian_0609_consultation_ordinary_shadow_validation.py`
- `apps/medqc-web/backend/scripts/review_luxian_0609_semantic20.py`

条件性测试文件可独占新增 `apps/medqc-web/backend/tests/privacy_closure_20261008/test_cli_identity_source_wiring.py`，不扩写共享 test_script_boundaries/offline_support；仅在来源方案和真实 caller确认、root分配测试槽之后实施。

具体开放前置 `PRIV003_REAL_CLI_IDENTITY_SOURCE`：独立 CLI 进程没有完整原始身份，也没有可信内存 collector 的生产创建/借用 caller。若要求它独立自启动恢复，就需要明确批准新身份采集操作、最窄数据范围及来源owner，不能宣称只改两脚本就已闭环。本轮不为工具恢复推荐该扩展，维持拒发；这不是发送泄漏缺陷。

## 未来测试输入（只定义，未执行）

1. 正常接线：用合成的已加载 ORM doubles，在既有 collect 返回钩子处提供完整三ID及原始 name、mr_no、inpat_no、idcard、phone/contact/address；各值由测试工厂生成，每个CaseRef互异。只采显式字段，不扫描正文或嵌套name。确认真实 caller确实把同对象传入两脚本；读取计数等于原本 collect 操作，额外身份查询为0；原始值不出现在安全返回结果和内存capture/transport，临床标记保留。
2. 同 patient/visit 不同 institute：两个合成实体具不同原始姓名/证件；必须精确匹配，不能串例。请求CaseRef不在collection时，client/config/attempt不得放行。
3. 坐标-only、masked name、缺字段、外部JSON姓名、dict/callable、正文里姓名：不能代替有效收集。不得为此调用补查；固定拒发结果无原始值。
4. 源未加载：用 double whose getattr raises 验证capture只读vars，不触发ORM lazy load；已存在但未加载字段不补查、不编造。
5. 活跃性：预检/创建wrapper后关闭collector，再 generate与模拟retry均拒发；异常/取消/finally清空；case scope退出的延迟任务拒发；一操作的collector不跨操作复用。
6. 原始PHONE反例：保留 `PHONE_13800138000_BEARER_SECRET`，测试回调先证明原始fixture含标记与数字、collector源电话确实为原值，发送结果去除；`130mg`、`1.5h`、`头孢呋辛`保持。不先脱敏fixture来遮盖反例。
7. CLI 来源缺失：actual CLI保持拒发；AST helper只能验证已摘录函数。真实 import/config若将来需测试，应另立禁读配置的测试环境/启动接缝，本轮不导入应用、不读.env。CLI不可用不作为send leakage红测。

所有本轮证据来自源码读取和符号检索。没有运行任何测试/探针、真实CLI、数据库、网络或模型；没有生产改动、提交、新worktree或解除gate。
