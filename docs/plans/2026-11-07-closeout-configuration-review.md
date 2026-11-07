# 业务配置收口专项复核

联合基线：`e87c06799`（业务 `6ad6817b1` 加已授权的出院终点、工作台只读元数据变更）。本专项仅审查模型配置、实际调用、HTTP出口、历史任务冻结和既有设置说明；没有连接业务PG/CDM、客户机、Strata、代理或模型，没有写业务库、启用调度、执行病例或部署。

## 实际调用链

后台 `LLMApiConfig.saveDraft` → `POST /llm/configs` 保存默认选型与 `custom_parameters.task_role_models` → `POST /qc/sichuan/reload-config` → `SichuanQCService.reload_config` → `LLMConfigLoader.reload_config_for_service` 构造并校验一审、二审候选客户端。后台角色只接受三个用途的 null 或 provider/model，地址和密钥由部署注入，不随角色选择提交给上游。

`SichuanQCLLMClient` 在构造时固定角色运行配置；`for_task_role` 使用同一父统计及Gateway出口，不在调用中重新读取选型。调用绑定如下，未分类的语义调用仍走判断分析，不能推断所有规则族都已拆成独立抽取：

| 配置 | 实际绑定 | 继承行为 |
| --- | --- | --- |
| 默认 | 原provider/model，以及正式二审的旧兼容选型入口 | 新保存百炼配置的 `qc_use_selected_model=true` 应保持后台默认模型；历史配置保留环境裁决兼容逻辑 |
| 事实抽取 | `native_exam_lab_execution._generate_exam_lab_fact_response`；会诊 opinion_load 首答与原有补核 | 回到根正式客户端，不产生额外调用 |
| 判断分析 | `execution.prepare_luxian_0609_execution`；检查检验、会诊公开执行入口 | 回到根正式客户端 |
| 专项核验 | `check_exam_result_record`、`check_exam_finding_analysis`、`check_exam_reason` | 保留原正式客户端及旧环境调用点兼容逻辑 |

客户端角色身份经过隐私包装及会诊应答冻结包装保留；`task_role_call` 在外层冻结读取前进入角色分区。新配置的运行身份包含默认/显式角色、有效推理参数、endpoint指纹、Gateway profile/地址指纹、本地计量合同与旧调用点配置。事实IO在原A0/A1分区下再按角色身份隔离，旧文件不删除。

新任务接纳调用 `capture_luxian_0609_task_runtime`；Worker领取后先克隆当前客户端，再 `assert_luxian_0609_task_runtime_match`，不匹配在医学执行前拒绝。已经运行并持有独立克隆的任务继续沿用其旧实例；排队/恢复任务不能保证换配置后仍执行。历史已保存结果不经此链重算。

## Gateway、HTTP与原合同

- 角色候选构造复用 `configured_gateway_profile`（按provider或model映射）及 `GatewayDispatchClient._connection_settings`，检查profile/provider、当前模式、URL、令牌长度和地址指纹；缺模型profile拒绝保存。实际发送前再次核对当前profile/地址身份；不在请求失败后换默认模型、Provider或Direct。
- Direct：`generate` → `_dispatch_payload` → `safe_post_json` → 共享HTTP资源按精确目标主机选择原池/代理池。无响应断连只复用同一路由做既有一次重试，输出预算与payload保持。
- Gateway：`generate` → `GatewayDispatchClient.complete` → 受控ASGI入口 → payload验证/预算复核 → `HttpxProviderSender.send`；独立Gateway进程自身按相同主机策略选择代理。API到Gateway的内部传输不套该上游主机代理。
- 代理精确主机规范化、配置错误范围保护、`trust_env=False`、CA验证及不跟随重定向保持。代理超时、断连、407及重定向均不转直连；错误不暴露代理底层信息。损坏配置拒绝受影响云端请求，明确本地目标保持原约束。
- P9本地请求保留完整Greedy、nested Thinking关闭、必要输出预算不缩小、已验证模型/计量/模板/消息形态要求，以及响应身份校验；不合格不发HTTP，不回退云端。百炼原Thinking/预算及原受控重试不因角色增加而更改。

## 本轮发现：保存后正式二审丢失角色与默认选型标记

已在联合基线复现：`LLMConfigLoader.reload_config_for_service` 已正确构造双方候选；`SichuanQCService.reload_config` 随后从 `self.client` 手工重组配置并再次覆盖 `adjudicator_client`，其custom_parameters只列旧推理/并发字段，遗漏 `task_role_models` 和 `qc_use_selected_model`。

合成默认 `synthetic-default`、三个用途 `synthetic-facts / synthetic-analysis / synthetic-check`，环境旧裁决 `legacy-default`。真实service重载后，一审仍保留三个用途，二审经 `for_task_role→generate` 的三次固定出口payload.model全部变成 `legacy-default`。这会使后台显示已保存角色，但正式分析入口仍回到旧裁决模型。既有角色测试只覆盖保存→loader→client，没有覆盖service再次覆盖候选的链。

新增 `apps/medqc-web/backend/tests/unit/test_business_closeout_configuration.py` 只覆盖这一已复现缺口。配置和应答均合成，捕获真实generate出口payload，断言三个选型、Thinking、输出上限、角色配置不外发和双方身份一致。修复由主协调拥有的运行代码统一处理：最小方向为保留loader已经原子校验构造的双方候选，避免service再次用不完整对象覆盖。

首次运行：

```text
python -s -B apps/medqc-web/backend/scripts/run_pr8_offline_tests.py tests/unit/test_business_closeout_configuration.py
1 failed, 3 warnings in 4.49s
实际model：legacy-default（三次）；预期：synthetic-facts / synthetic-analysis / synthetic-check
```

主协调最小修复删除service中的重复重建，保留loader已原子校验的双方候选。本专项重跑新增用例及已有 `test_strata_client_binding.py`：4 passed，3 warnings，5.29s。除三个角色实际payload、默认模型不回流、预算与Thinking外，已有绑定用例验证通用执行器切换新客户端、隔离任务继续使用旧客户端；未扩大到全套。

随后在同一新增用例补充二审根默认模型必须为 `synthetic-default` 的明确断言，仅复跑该文件：1 passed，3 warnings，4.20s（与上面重叠，不累加）。自有测试与本报告UTF-8无BOM、仅LF，diff格式检查通过。

```text
python -s -B apps/medqc-web/backend/scripts/run_pr8_offline_tests.py tests/unit/test_business_closeout_configuration.py tests/unit/test_strata_client_binding.py
```

## 既有提示与最小修正文案

现有角色说明准确限定了检查检验、会诊及三个检查专项；“角色调用失败不会自动切换服务”与原失败关闭一致。默认配置页明确“连接测试会实际请求默认模型；保存只校验配置”，没有宣称保存会做真实连通性或角色医学质量验收。

一处原说明过强：`LLMTaskRoleSettings.vue:64` 原“配置在新任务开始时固定，已有任务不受影响”没有区别在途与尚未领取/恢复任务。Worker严格拒绝与当前运行身份不一致的旧快照。主协调已仅修改现有提示为：“新配置仅用于新建任务，进行中的任务保留已固定配置；排队或恢复任务如配置不匹配，需重新创建。角色调用失败不会自动切换服务。”没有新增设置页面或观测平台，没有更改样式或交互。本专项代理只拥有测试及报告，UI运行文件由主协调修改。

代理属于部署配置：Direct在发送进程首次创建HTTP资源时固定，Gateway创建应用时固定，API保存/reload不热切换其主机代理。现有代理专题文档已明确两侧配置、生效进程及重启边界，本轮没有执行配置应用或重启。

## 复用证据、覆盖与限制

本轮没有重跑已有全量集合。执行源码一致性检查：

- `6ac54edb9→e87c06799` 的角色owner、客户端、隐私包装、快照、service及 `test_llm_task_roles.py` 零差异。复用 `apps/medqc-web/docs/plans/2026-11-06-roles-daily-business-adaptation.md` 的定向77项历史联合证据中角色相关结论；该数字还含每日计划/迁移/启动项，不当作本专项测试数量。
- `469e2a506→e87c06799` 的Direct/Gateway代理、预算/P9源码及代理/P9测试零差异。复用 `apps/medqc-web/docs/plans/2026-11-05-bailian-host-proxy.md` 的262项定向历史联合证据及其最终修复边界；不当作联合Head本轮CI。
- `test_llm_task_roles.py` 已覆盖全继承、实际三角色payload、克隆、变更拒绝旧任务、角色/A0/A1冻结隔离、取消与并发、隐私与会诊应答、缺profile和本地禁止转云，以及真实Gateway固定出口→Native/Binding/Finalizer/Canonical内存保存的两个检查结果。
- `test_llm_http_proxy.py` 已覆盖两个模型同主机、精确名单、Direct/Gateway失败无兜底、重定向/407、payload/预算保持、取消、共享容量、配置错误隔离与同步/异步真实HTTPX池的CA选项。
- `test_strata_p9b.py` 已覆盖Direct/Gateway最终HTTP、Thinking/Greedy、输出预算、部署及响应身份、有限结构化恢复、失败不冻结和身份分区。另保留原Thinking预算文件证据。

未覆盖/不作承诺：真实Gateway注册表和模型身份是否与部署一致、真实CONNECT/TLS和长期容量、真实Tokenizer、实际模型医学质量、现场在途/恢复任务操作、多进程配置同步及真实历史病例重算。本轮只用固定应答和内存SQLite，全部实际测试由 `run_pr8_offline_tests.py` 禁dotenv、网络与非SQLite连接。

最初尝试直接在PR8入口执行两个既有角色用例，因该入口故意不加载上层conftest而缺 `client` fixture，两项setup error，未执行产品断言。使用已有无lifespan `tests.scheduler_support.pytest_plugin` 后仅补验这两项，2 passed，26 warnings，18.25s；分别证明角色变更拒绝旧运行快照、原客户端实例/继承计划保持旧配置，没有放松隔离。这两项不是本次修复新增测试。

```text
python -s -B apps/medqc-web/backend/scripts/run_pr8_offline_tests.py -p tests.scheduler_support.pytest_plugin tests/unit/test_llm_task_roles.py::test_changed_role_rejects_old_task_snapshot tests/unit/test_llm_task_roles.py::test_all_inherited_uses_existing_client_and_old_plan_stays_frozen
```
