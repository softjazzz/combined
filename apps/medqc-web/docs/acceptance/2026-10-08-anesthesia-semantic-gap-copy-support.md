# N12 麻醉访视抽取待确认客户解释支持

准备基线25406df7d2506f4870674ca73cddd10523bf966d。CT03固定源独审无新增阻断后，root只授权本支持提交：规则LX0609-04-04-02、reason semantic_extraction_unresolved；不包含N12抽取执行、Prompt、reason公共枚举接入或CT04。

精确生产范围：customer_renderer.\_RULE_DATA_GAP_REASON_MESSAGES加唯一tuple（标题“麻醉访视内容暂无法确认”、结论“现有访视正文的必填内容尚未形成可靠抽取结果，暂时无法判定填写是否完整。”、建议“请复核现有访视正文或重试质控；不要据此补写或改写记录。”）；\_FINALIZER_RULE_DATA_GAP_CUSTOMER_MESSAGES加同tuple使用上述结论；Finalizer.\_RULE_DATA_GAP_EXPLANATIONS加同tuple，reason_label=内容抽取待确认，missing_sources/missing_fields为空。既有structured_suggestion保护集合只加此tuple，避免通用补齐资料建议覆盖精确建议；不得全规则禁覆盖。

专属消息测试7项。包含真正Reducer→Renderer→Finalizer入口及公开Finalizer默认/已有空缺口保护；037其他reason和其他规则同reason仍用既有解释。当前本树decision_model/reducer尚未接入该reason，只在专属测试临时模块白名单替身允许data_gap，测试明确标示，不能当作完整正式执行合同通过；生产全局枚举归N12核心owner。本支持提交交给N12树与核心联合验证后由root集成。未改模型调用/状态/事实；无需PG、env、网络或真实模型。

在root唯一槽执行：未改生产红7为3失败/4通过（.tmp/n12-copy-support/red.log），失败均为目标消息缺失/缺源默认解释，无夹具异常。限定生产补丁后绿77全部通过（7新消息支持+70既有Finalizer，.tmp/n12-copy-support/green.log），未使用PG、env、网络或真实模型。提交只含两生产文件、新专属测试和本文，普通中文真实hooks；CT03原独审预期/测试、其他字典条目/逻辑均冻结。

逆向逐字保护确认仅三个消息字典tuple及一个建议保护tuple，其他条目/代码不变；decision_model、Reducer、native、CT03 mapping及正文gap专属测试逐字不变。1147前端源码/配置hash与本批已完成lint输入一致，继承lint证据（0错误、1214既有警告）；此前typecheck资源终止，全量前端unit未运行，不宣称通过。Ruff/差分校验与正常Husky编码门禁另记录。新reason的正式发送/抽取/错误分支和保存回读由N12核心树联合测试，不以本支持模块的临时reason白名单测试替代。
