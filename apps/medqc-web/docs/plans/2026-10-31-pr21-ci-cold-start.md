# PR21请求观测、实验冻结与冷启动CI收口

**Goal:** 将实际请求观测与A0/A1隔离套件纳入现有调度门，修复冷启动检查与offline的冲突，保留网络、dotenv、数据库及通用进程隔离。

**Architecture:** 现有offline suite增加固定冷启动及其保护；原架构检查保留49条固定应答和不导入SichuanQCService断言。唯一测试helper验证固定源码SHA256、隔离Python启动及最小环境，并在任何业务导入前重新安装OfflineIsolation。通用subprocess.run/Popen和原重启probe白名单不变。CI现有门增加新suite，PR过滤补入固定评审Base，不删除或跳过旧门禁。

基线f6b5687f8；分支codex/strata-case-cache-20261030，业务集成线不变。

1. 已复现RED：原冷启动测试在父进程subprocess.run处被OfflineIsolationError阻断，未执行其架构断言。
2. 实现无参数、源码验签的固定helper；子进程用-I/-S/-B/-X utf8，不继承PYTHONPATH、代理、模型/数据库凭据。仅显式带入已加载隔离依赖的可信site-packages目录，不执行.pth；工作目录固定backend、shell=false、30秒超时只终止自有子进程。
3. 子进程先安装同等隔离，再真实验证socket、DNS、PG连接、dotenv与子进程均被阻止，最后执行原49条合成固定应答冷启动。没有真实模型或业务数据库访问。
4. 增加源码变化/参数注入/最小环境/超时回收与通用进程仍禁止的反例，CI步骤与触发条件保护。suite包含请求观测、A0/A1和冷启动；未开启缓存、改变Prompt或医学状态。
5. 本地聚焦与必要扩大offline验证，静态/编码检查；提交推送同一PR并核对远端CI，不合并或部署。

这是受控测试探针，不是服务启动、完整病历质控或任意脚本执行能力。探针源码改动必须复核后同步更新固定digest，CI会拒绝不匹配源码。


## 本地验收

- 原节点RED已复现：`--profile offline tests/unit/test_luxian_0609_preproduction_runner.py::test_preproduction_runner_cold_process_does_not_load_sichuan_service`，在父进程通用subprocess拦截处失败。
- 原节点及固定探针保护首次GREEN：5通过。增加CI触发保护及更严格-S启动后，原节点/反例/既有网络与DB隔离共26通过。
- 新CI专题suite：`python -B scripts/run_qc_scheduler_tests.py --profile offline --suite llm-request-audit`，**213 passed，1 warning，9.72秒**。
- 最终必要扩大：同suite追加`test_luxian_0609_preproduction_runner.py`、`test_qc_scheduler_isolation.py`、`test_qc_infra_isolation.py`、`test_luxian_0609_preproduction_api.py`，**289 passed，33 warnings，17.99秒**。与上述结果有重叠（原冷启动node也可能同时由整文件选中），不相加，不宣称289个不同业务场景。
- 5个Python文件Ruff通过；只读ESLint 0错误/3401项既有warning，无前端变动，未重跑全量前端类型及单测。暂存后核对UTF-8无BOM/LF及编码。
- 固定探针源码SHA256：`4d81e240ee4f2ea71ddd0c20befef637d9264e5be8a4162c8d786ad74d91885c`。source快照通过校验后才序列化执行，避免再次读取文件；任意参数/修改源码拒绝，超时只kill该helper持有的进程。
- 子进程在业务导入前实际断言socket/DNS/PG连接/dotenv/普通进程均被OfflineIsolationError阻断，保留原49条固定应答与不加载SichuanQCService的前后断言；不启动后端服务，不调用模型。
- CI既有M0/M1、兼容和M2 synthetic步骤保持，新增专题步骤无skip或continue-on-error；PR过滤补入codex/strata-review-base-20261031，push codex/**仍触发。并非放开测试真实网络或业务DB。

## 仍保留的限制

只证明测试环境的冷导入边界与合成固定应答，不证明客户机服务启动、Provider连通、Thinking实际生效、真实医学准确率或性能。新helper仅测试支持，不成为业务API或任意脚本执行器。业务执行器/Prompt/数据库/迁移均无变化；未运行真实病历/27例质控、连接Strata、调用真实模型或部署。工作树集成HEAD仍为cedb9c10a，原6项未跟踪材料未变。远端新Head的CI结果在PR中更新，不能沿用旧Head绿灯。
