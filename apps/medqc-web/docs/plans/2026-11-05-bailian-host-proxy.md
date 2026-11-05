# 百炼部署级主机代理（方案A）

## 基线和范围

基于业务集成71ad3c619567fcf4afb6af20ea8ee8c19c627501，独立分支codex/bailian-host-proxy-20261105。
只调整正式模型HTTP出口：Direct的safe_post_json与Gateway的HttpxProviderSender。
不改前端、模型选择、Prompt、Thinking、Greedy、输出预算、医学结果合同和数据库。
用户已确认方案A；没有应用DSH旧补丁，其报告和16项测试未独立核实。

## 配置

默认两项都为空，保持原路径。以下仅为配置示例，本轮没有应用：

```ini
LLM_HTTP_PROXY=http://192.168.118.99:18090
LLM_HTTP_PROXY_HOSTS=dashscope.aliyuncs.com
```

域名为逗号分隔的精确hostname，不接受通配符、URL或端口；规范化大小写、IDNA和末尾根点。
代理首期仅支持显式端口的http:// HTTP CONNECT地址，不支持内嵌用户名口令、SOCKS或HTTPS代理。
仅填一项或非法配置保留错误状态，受影响请求报固定错误码，不会当作未配置而直连。一个代理供匹配主机的所有模型使用。
保留正常CA验证和trust_env=False，不读取系统HTTP_PROXY/HTTPS_PROXY/ALL_PROXY/NO_PROXY。
不跟随重定向，不因代理失败换直连或另一Provider。
Direct保留原有一次无应答断连重试，始终在同一个客户端；超时和其他错误不增加传输重试。
Gateway继续沿用原受控重试、截止时间和取消机制，本次不增加重试。

## 生命周期与安全

Direct增加代理池，但仍共享一个线程池和并发计数；关闭时等待在途并关闭两池。
取消await不等于阻塞HTTP已终止，保持原有实际在途跟踪和槽位释放语义。
Gateway保留每次调用独立AsyncClient的释放策略，不新增跨事件循环池。
测试分别注入直连和代理transport；只注入直连transport时，匹配代理请求明确拒绝，防止HTTPX代理mount绕过隔离。
代理传输失败只给安全错误码，不回显底层异常和代理地址；不新增Prompt、原答或凭据日志。

## 生效和回滚（仅说明）

- Direct：配置放入业务API实际读取的部署环境文件，新进程首次创建HTTP资源时固定配置。
- Gateway：同名配置放入独立Gateway进程环境，创建应用时读取；只改业务API的.env不会配置远程Gateway。
- 应用到Gateway内部请求保持原路径。独立MQ Worker要求Gateway，出口配置在Gateway侧。
- 修改后等待在途结束，再重启相应HTTP发送进程；不宣称热更新或自动多进程同步。
- 回滚时清空两项并重启相应进程，恢复原路径。离线服务器可能无法直连百炼，这不是自动旁路。
- 不需重启前端、PG、同步服务或Strata，不改防火墙、DNS和路由。

## 范围和验收边界

safe_post_json现有调用者共享此出口。字段映射OpenAI SDK、Agent意图路由独立Client、ICD嵌入requests未纳入，不能宣称全系统HTTP统一代理。
CDM、PG和同步连接未修改；Strata及本地模型目标不在名单时保持原路径，P9身份与P5-B预算准入继续由原实现执行。
正式后端锁定httpx==0.25.2，proxies按该版本实现，本次不升级依赖。

## 验证

使用run_qc_scheduler_tests.py --profile offline，屏蔽dotenv、真实网络、真实模型、非SQLite数据库；只用合成材料与固定应答。
新增集合加入现有m1-admission CI入口，未关闭或放宽隔离。
开发机用户site存在较新HTTPX，会覆盖锁定版本；命令用python -s -B选择本机已安装的0.25.2，不修改全局依赖。
最终联合集合245通过、0失败、0跳过（此前66/225为重叠阶段验证，不累加）。现场CONNECT/TLS、长期稳定性和容量未新增验收，不声称医学质量或真实业务吞吐。


复现（仓库根目录）：

```powershell
python -s -B apps/medqc-web/backend/scripts/run_qc_scheduler_tests.py --profile offline --suite m1-admission tests/unit/test_shared_http_client.py tests/unit/test_llm_config_loader.py tests/unit/test_strata_p9b.py tests/unit/test_gateway_context_budget.py tests/unit/test_context_token_budget.py tests/unit/test_context_budget_review_regressions.py tests/unit/test_qc_llm_client_thinking_budget.py
```

新增保护包括：两模型相同主机共用代理、主机伪装不命中、空配置默认关闭、配置错误拒绝、双路径无直连兜底、407及重定向拒绝、断连重试保持代理、正式客户端输出上限不变、并发共槽、取消与关闭、Gateway真实ASGI入口、实际HTTPX同步/异步代理池CA校验。
项目锁定HTTPX下执行。第一次用默认解释器因用户site覆盖到不支持proxies的新版本而失败，未据此修改产品依赖；改用-s后通过。
一次新增固定应答误用了仅Strata支持的结构化恢复条件，已改为百炼实际存在的断连恢复回归；没有为测试新增百炼恢复行为。
Ruff、git diff --check、前端type-check通过；ESLint --no-fix为0错误/3506个既有警告，前端文件无差异。
前端全量单测、完整质控、真实代理、真实模型及服务器验收未执行。本轮没有读取现场Key或复制DSH补丁，没有业务库写入和配置更改。

## 给DSH的边界说明（待未来授权交付后使用）

本次只有独立分支代码，未推送、打包、部署或启用。不能直接对旧服务器版本添加配置并认为功能已生效。
后续获得含此改动的应用包后，先确认Runtime版本和httpx==0.25.2；按实际Direct或Gateway发送端放置两项部署配置，名单只填dashscope.aliyuncs.com。
保持所有模型身份、预算、输出参数与TLS设置不变；使用持有人轮换后的Key，禁止复用此前暴露Key。
本机固定应答不替代现场正式链验收；不得自动点击测试连接、提交病历或调用收费模型。现场连通性已有独立证明，重复真实调用需要另行授权。


## P2复审修复：配置故障隔离

复审基线c64a9dbdc。已先用Direct共享资源初始化与Gateway.from_env→ASGI入口固化两组反例，覆盖漏填主机、漏填地址、非法地址及非法主机名单（共8个参数场景）；修复前在配置构造阶段失败。

新语义：严格parse仍可用于配置校验，运行时load保留错误码与可确定的目标范围，不阻止共享资源或Gateway创建。
- 主机名单完整有效：只拒绝匹配主机；其他未匹配目标按原路径执行。
- 主机名单缺失或损坏：不能确定哪些云端目标应受代理约束，拒绝公网和归属不明的域名；只放行明确本地的localhost、回环、链路本地、RFC1918或IPv6 ULA字面地址，不做DNS探测。
- 损坏名单中能明确识别的目标仍优先拒绝，包括被显式列出的本地地址，不能借本地放行绕过。
- Gateway在排队/发送前返回gateway_proxy_configuration_invalid，retryable=false；这不是Provider断连，不记录远端未知在途，不隔离共享资源。
- 通过实际Gateway生命周期和先本地→拒绝云端→再本地的序列验证Strata仍可用。缺失主机时普通内网域名不能自动证明本地，需修正名单后使用，未引入新的配置白名单。

没有改正常代理路由、TLS、医学合同或默认关闭语义；未连接代理、模型、业务库。修复后复跑上述同一联合命令：262通过、0失败、0跳过，22.11秒。相比原245项新增17项（两条正式路径的8个参数场景及9个范围判定场景）。Ruff与diff检查通过；类型及前端全量单测本轮未重复执行，前端无差异。
