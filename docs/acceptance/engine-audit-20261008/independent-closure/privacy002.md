# PRIV002 固定提交独立复审

结论：PRIV002在本次限定的0609已读身份来源、病例scope与最终发送消费边界内，独立冻结的49项探针全部通过，未发现可确认新增缺陷。可以据此关闭本次定义的修复接缝问题；不能据此关闭未读取/不在声明来源字段内的所有身份或宣称完整工作端点、客户链、部署通过。

审阅固定提交 `4232ca617e9b3b746b9ba17b65558a2ec3c0ba63`，父提交 `6b8fa3e583d22979c305f4959db8ee8953c80e68`，只审0609。10文件差分已核对，生产源码全部来自固定 `git show` 导出。完成静态复核、执行前独立期望冻结与标准库方法消费验证；生产/共享测试未编辑。

## 固定链路与源码结论

`record_repository.collect_records` 在原始查询 `.all()` 后、序列化前调用可选 collector。frontpage直接ORM/tuple或SQLAlchemy Row、显式visit锚点、完整CaseRef锚点及 `today_inpatient` 转接均已传递回调。三个锚点来源（登记、入院、出院）都消费原有已加载行。`CustomQCWorkspaceService.collect_records` 仅在非空回调时转发此私有参数。差分未新增数据库查询、原身份字段或普通返回字段。

`privacy_identity_context._Luxian0609IdentityCollector` 只读取 `vars(source)` 已加载字段，不用 getattr 触发懒加载。明确读取姓名、病案/住院/证件/医保标识、联系人与地址/工作单位字段；不遍历任意嵌套name，不收集医师、药品或正文。内存按完整CaseRef三坐标分组；缺坐标、未知来源、异常scalar、无法归属来源和没有非星号原姓名均固定失败关闭。单病例provider每次检查collector活性、全局/病例invalid标记及原姓名条件。collector/holder使用固定repr，pickle主动拒绝；close清空各值集合并使既有provider失效。

worker仅在0609任务内创建collector，将其capture回调传入已有collect入口，水合后仅补已有 `patient_name/mr_no/inpat_no`。每条病例的真实 `_evaluate_single_record` 方法先按完整CaseRef取provider，进入私有source scope，再进入原观测与诊断边界。collector保存在本次job局部变量，不进批结果/客户DTO/bundle缓存；递归重试前和job finally都close，重新进入worker时重新收集。

`privacy_request_scope._case_scope` 让原正式decorator与准生产decorator共同继承有效同病例source scope。具有已收集来源要求的scope下，错病例/缺坐标内部调用被标记无效，禁止降级为仅三坐标provider。execution改为把三坐标传入绑定，并使用绑定函数返回的合并provider包装LLM；已收集原身份与当前证据身份同时保护wrapper及最终attempt。scope退出仍继承004的租约失效与恢复保证。

现有record序列化合同本来含patient_name/mr_no/inpat_no，现有bundle本来可能包含正文。这里核查的是collector没有新增原值字段或把值集合写入合同/缓存；不能把“合同未新增字段”解释为整个系统所有原字段或原正文从未持久化。根任务明确授权复用已读整ORM，本修复没有新增PG读取。

## 独立冻结与执行结果

`expectations.json` 在执行前冻结5个collect分支、12个来源字段、实际缓存hit/miss、11类失效来源/错病例及正常脱敏文本等期望。`probe.py` 已执行以下消费边界：

- 原repository方法体，所有collect分支及today转接；比较有/无collector的query调用数量和返回合同。
- 原 `load_or_assemble_scene_bundle` 与 `load_running_final_bundle` 函数体的不同hit/miss控制流，底层load/assemble/upsert为内存替身；已有bundle和正文不因collector改变。
- 完整worker病例wrapper → 完整正式 `evaluate_running_final_bundle_input` 方法及真实decorator → 完整prepare函数至provider构建/绑定/包装后的首个规则loader → 真实wrapper和完整client `generate/final attempt` 方法体。
- 原身份无标签透传拒发、姓名标签脱敏且保留130mg/1.5小时、缺失/失效source、完整CaseRef隔离、同visit不同患者/机构、并发worker病例、repr/JSON/pickle拒绝、close及错误/取消后的scope恢复。
- job最终清理用实际finally语句摘录验证；没有执行完整job授权/队列/保存流程。004/005既有独审证据继承，不重新执行其全量探针。

所有配置、adapter、计划、源查询、缓存I/O、临床规则聚合与观测均为显式替身。虽然使用完整方法体而不是只摘新增行，AST和替身仍不等于完整工作端点。日志/观测接收端的生产实现、实际ORM SQL投影与懒加载、持久化表、正式worker全job、最终集成SHA工程测试及客户链仍缺独立本轮执行门禁。

根任务于集成聚焦回归186项通过后授予唯一轻量槽；本审计只执行一次 `python -B F:/MedQC-worktrees/review-artifacts/privacy002-closure/probe.py`，进程约0.635秒，返回49 passed / 0 failed，结果逐项见 `results.json`，完成后立即释放槽。186项为根任务提供的集成证据，本代理未重跑且不冒充本探针结果。

冻结期望SHA256为 `6d9633bbaee0f08ad7a3e3ec207fb92d95d75a014cffc3f9dbec9148a5b49f4f`；探针主逻辑记录约0.132秒。执行后未修改期望或探针实现。

49项包括5个collect分支合同/读次数对照、24个字段×缓存分支拒发、2个正常正文脱敏保留医学量值、11个失效来源/病例归属拒发、完整CaseRef隔离、并发正式消费、collector/holder序列化限制、close失效、RuntimeError/CancelledError的病例scope恢复与实际job finally清理摘录、客户端替身日志不输出收集值。拒发均发生于observation/capture/transport替身事件之前；正常请求仍经过三个事件，姓名已去除且130mg/1.5小时保留。缓存miss的upsert替身收到原bundle合同，未写入collector集合或新增字段；已有合成正文不是“从未缓存”的证据。

## owner证据与差距

root提供67项开发合成绿及旧worker-wrapper四项对照红，本报告作为开发证据记录，不冒充独立结果。静态检查owner `test_collected_identity.py` 的hit/miss由同一loader替身仅记录不同mode标签，并未执行实际缓存分支；其repository helper不包含today_inpatient方法，execution只执行三条绑定语句。本独立探针已补这三处消费边界，仍使用无数据库替身。

PRIV004/005既有独审报告保留原固定SHA结论和历史钩子事实。PRIV002修复候选已得到本轮限定边界独立通过，不能扩张为全部privacy问题关闭。未访问PG、`.env`、真实病例、模型/网络、服务或浏览器，未外发、编辑生产/共享测试或提交。可确认findings/defects为空；未执行工程与客户门禁作为验证限制保留。

产物：`expectations.json`、`probe.py`、`results.json`、固定 `*.fixed.py` 源码。
