# 后台云端与Strata选择：设计及交付

日期：2026-10-30。基线 `02f7992be`，独立工作树 `C:/medqc-strata-case-cache-20261030`，
分支 `codex/strata-case-cache-20261030`。

用户确认：后台选择百炼／Strata及模型；地址和密钥仍由部署配置提供。
本轮不连接现场、不写业务库、不调用真实模型、不重跑质控、不改业务集成分支。

## 设计选择与完成范围

沿用现有模型配置页面、`/api/v1/llm` API和配置owner，不单独建一套本地模型管理。
新增独立 `strata` Provider，保留百炼、Ollama及其他已有服务；不把Ollama改名冒充Strata。
地址、密钥、真实Gateway资源与profile仍由部署人员配置；后台不提供其编辑或泄露接口。
相较允许任意地址写入后台的方案，此方式复用既有部署和安全边界；需要新增服务地址时仍须部署人员处理。

实际链路：现有后台选择 → 既有配置保存 → 配置loader → 一/二审客户端 → 按服务商及模型选择Gateway profile → 独立资源 → 原规则解析和保存链。
临床执行器、Prompt、判断合同及保存schema没有变更。

- Provider/模型目录接入Strata，部署模型名原样展示；修正通用fallback将模型名强制小写的问题。
- API明确拒绝未知、未启用Provider，不能静默改为默认云端服务。
- 后台Strata保存与连接测试要求完整的Gateway配置；保留旧直接客户端路径的兼容能力，但后台不启用绕过统一准入的Strata直连。
- 一审使用后台所选模型；Strata二审默认同模型，可用 `STRATA_ADJUDICATOR_MODEL` 显式部署覆盖，不沿用云端 `LLM_ADJUDICATOR_MODEL` 的默认名字。
- 当启用Strata时，若已配置的已知role覆盖仍指向另一Provider，则拒绝配置，需部署人员清理；不静默向云端发送本地模式的专项请求。
- 按模型区分profile时，二审或显式role换模型会重新解析正确的profile，不携带原模型profile。
- Web真实客户端先完整构造/校验一审、二审再替换，不在失败时留下半更新客户端。既有正式任务独立runtime及运行身份校验继续使用。
- MQ Worker每批读取配置；配置相同复用服务，配置改变创建新服务，旧批次持有的实例不被修改。配置读取失败不使用过期配置放行。已冻结身份的排队旧任务仍按既有合同校验，不能静默换服务。
- 模型列表异步加载使用版本守卫，旧响应不能覆盖新服务商；未加载完或没有模型时不能保存。

## 部署配置合同

新增客户端 `LLM_GATEWAY_PROFILES`，支持Provider→单profile，或Provider→模型→profile。
空字典兼容旧 `LLM_GATEWAY_PROFILE`。模型映射优先且精确匹配，缺少模型不猜测其他profile。
名称须属于对应Provider的受控前缀；模型名区分大小写。

示意（仅文档，没有修改运行env）：

```dotenv
LLM_VISIBLE_PROVIDERS=alibaba,strata,ollama
LLM_DEFAULT_PROVIDER=alibaba
LLM_DISPATCH_MODE=gateway
LLM_GATEWAY_URL=http://127.0.0.1:8765
LLM_GATEWAY_TOKEN=<部署人员提供的至少32字符密钥>
LLM_GATEWAY_PROFILES={"alibaba":{"qwen3.8-flash":"alibaba_main"},"strata":{"Local/ActualModel":"strata_main"},"ollama":"ollama_main"}
STRATA_API_ENDPOINT=http://strata.internal:8080/v1
STRATA_MODEL=Local/ActualModel
STRATA_API_KEY=
STRATA_ADJUDICATOR_MODEL=
STRATA_CASE_CACHE_MODE=off
```

`Local/ActualModel`须换成Strata实际API模型名，不能按模型文件名猜测。
Gateway进程另需真实的 `LLM_GATEWAY_PROFILES_JSON`（完整profile注册表，含Provider/模型/端点/资源），
不是上面客户端的路由映射。两侧profile和模型必须一致。
多模型须逐一登记各自真实profile；不能只改后台模型名而让它仍指向固定其他模型的profile。
模型映射中的名称自动进入后台目录；可选自定义名称仍须由真实服务和对应Gateway配置支持。

Gateway继续使用既有 `LLM_GATEWAY_RESOURCES_JSON`：百炼绑定独立云资源（现有默认40槽），
Strata绑定独立本地资源（本阶段2槽），不得把两个profile绑到同一40槽本地资源。
客户端页面的HTTP上限不代表服务端推理容量。Gateway真实profile、资源、地址及密钥变更需要部署并重启对应进程；后台仅切换已部署的选择。
前缀缓存默认关闭，亲和调度未实施；本地服务失败明确返回错误，不自动发往云端。

## 验证与限制

后端通过既有 `scripts/run_qc_scheduler_tests.py --profile offline`：禁止dotenv、真实网络/数据库、普通子进程。
新增用例覆盖目录、角色权限、保存/读取、热重载、模型大小写、多模型profile、局部配置失败、MQ入口/服务刷新及本地失败不回退。
实际API保存到合成内存配置，再经真实loader/client、进程内Gateway ASGI和Provider MockTransport核对百炼→Strata→百炼出口；每次请求的模型和profile一致。
连接测试使用固定应答，不保存配置。旧连接失败保护用例补充合成密钥，使其确实进入被测应答异常分支，避免隔离环境无key时提前返回400。

前端使用实际SFC及API替身，覆盖选择、保存后重载、权限和迟到响应；Node预加载守卫禁HTTP/TCP/DNS真实出口，fetch由测试替身处理。
复用另一工作树已有node_modules，测试缓存定向写本工作树 `.tmp`；没有修改对方受跟踪源码。
没有浏览器或现场联通验收，没有安装新依赖、执行迁移或改运行服务。

## 最终验收记录

- 后端一次统一扩大集合：**343 passed、194 warnings、45.23秒**；没有将各轮及子集合数字相加。
  使用 `--profile offline --suite strata-prefix`，追加以下 `tests/unit/` 文件：
  `test_strata_admin_configuration.py`、`test_llm_config_loader.py`、`test_llm_config_permissions.py`、
  `test_llm_dispatch_runtime_identity.py`、`test_qc_dispatch_entrypoints.py`、`test_qc_batch_consumer.py`、
  `test_qc_worker_recovery.py`、`test_llm_gateway_api.py`、`test_llm_gateway_admission.py`、
  `test_llm_gateway_cancellation.py`、`test_qc_llm_client.py`、`test_qc_llm_client_qwen_thinking.py`、
  `test_qc_llm_client_thinking_budget.py`、`test_shared_http_client.py`。
- 前端3文件 **11 passed**：`LLMApiConfigStrata.spec.ts`、`llm-config-service.spec.ts`、`systemConfigAccess.spec.ts`。
  本轮Node网络守卫和缓存覆盖配置位于本工作树 `.tmp`，未提交为新CI入口；现有测试使用的API、fetch替身随仓库保留。
- `npm run type-check` 通过；全量 `npm run lint -- --no-fix` 0错误、3401警告，未清理无关既有警告；
  修改SFC的聚焦ESLint无警告，新测试内4个组件替身触发多组件同文件警告，无错误。
- 相关Python Ruff、`git diff --check`、UTF-8无BOM/LF及Python3.10 AST检查通过。
  `npm run check:encoding`通过（16个文本文件；env示例由额外UTF-8/LF检查覆盖）。
- 旧思考预算重载用例改为检查新生效的 `service.client`，并新增旧实例保持256不变的断言；
  512、1024及清空预算的行为继续验证，符合本次不改写在途实例的合同。

本轮无新迁移；现有配置表的Provider/模型均为字符串列，不需要为新增Strata选项修改schema。
未运行前端全部单元测试、远端CI、真实PG持久化、现场连接或完整病历质控；不能据固定应答声称现场联通、缓存收益或医学准确率已验收。
没有改部署env、启动/重启服务、写业务库、移动业务集成分支、推送、提PR或合并。
