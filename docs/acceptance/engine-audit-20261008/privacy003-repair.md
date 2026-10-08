# PRIV003 已知三入口拒发边界子项（待固定独审）

起点为 `4232ca617`，只修改普通会诊shadow、semantic20、028 golden三脚本及获批测试/专属报告。002公共privacy/worker/repository/assembly生产代码均未修改。两真实CLI目前不能直接外发：没有已存在生产调用方可传入同操作collect的合法原身份内存来源；后续必须经审查接入合法来源。这是拒发边界子项，不是整个PRIV003功能完成，不是规则验收通过。

## 实现与正常路径

ordinary/semantic内部入口仅接受私有 `_Luxian0609IdentityCollector` 对象，按完整CaseRef读取已读source provider；不接受字符串、raw dict、任意callable、合成标签或三ID降级。collector类型不是原身份真实性证明；真实来源仍须是已审repository.collect的操作局部对象，本轮未新增这样的生产脚本调用方。缺源/空或遮罩姓名/错病例/关闭源固定拒发。

每病例套已有source-required scope，将source与现有材料provider组合，每次调用重读；wrapper和actual attempt在observation/capture/transport前校验。不同病例wrapper独立，同病例保留外层provider，finally恢复scope，取消/异常/延迟child和第二attempt失效拒发。脚本借用外层collector，不提前关闭上游对象。原身份不进入case-map、source返回合同、bundle、ledger、JSON、trace、log或持久化。没有新增PG查询、refresh或环境读取。

ordinary缺源在既有source读/客户端配置构造前抛固定隐私异常，main固定文案和非零退出；有合法内存来源的内部入口保持native与stage capture链。semantic缺源输出固定 `privacy_boundary_error`、review_error/evaluation_unknown/agreement=None，拒发不计completed/attempt；当前独立main在读JSON/runtime client前固定非零退出。正常材料、候选不入prompt、20/40调用约束、JSON解析/业务规则预期保留。

028仅固定硬编码10项SCENARIOS。保留私有原始tuple基线，拒绝公共tuple替换、新建同label/合成label对象；Scenario仍frozen，CLI不新增材料文件、row_loader、scenarios或synthetic信任开关。每固定场景建立独立合成collector（固定合成姓名及三坐标，仅内存），source scope+材料provider+wrapper，finally close。正常模型分支保留；本轮只向内存transport发送合成临床文本，不运行真实配置client。原expected/reduce未改，测试中的业务DTO是明确替身，不是临床验收。

## 先红与绿证据

冻结3生产文件SHA记录见 `privacy003-minimal-design.md`。先红运行8项全部失败（0.39秒），无加载/支撑错误：ordinary缺源真实/伪synthetic两例各触及内存observation/capture/transport1次；semantic两generate分支各1且completed=1；028残留合成ID10场景各10；新建伪场景两例被接受；替换tuple触及各1。可信红之后才修改生产。

首轮绿46项34通过/12失败：retry控制误用残留原名导致首attempt合法拒发、AST main namespace缺asyncio、原async marker在禁自动插件strict设置下未注册。这些是支撑/测试设置失败，不计隐私红或业务绿。修正后保留全部原async装饰器，显式加载本地pytest_asyncio注册。

第二轮46项45通过/1失败：原semantic测试要求PHONE_13800138000_BEARER_SECRET原样进入prompt，与新增手机号保护冲突。按主协调明确裁定保留原PHONE fixture，并附固定非身份临床标记：材料到达contains检查新临床标记，所有实际prompt同时不得含原手机号或原PHONE完整令牌，产物原forbidden保留并追加新临床标记。20/40、candidate排除、原全部业务contract/状态断言未放宽。

最终专属47项全部通过（2.23秒）：包含原8反例、三个正常transport控制、六类不可信/失效源、semantic两分支残留/错病例/失效/字典拒发、固定10场景正常对照、延迟child、异常/取消、第二actual attempt失效、两个CLI配置/source前拒发、并发与同病例外层provider/lease、额外手机号处理正常控制，以及原semantic10函数当前源码AST的业务断言。原装饰器保留；测试经真实pytest收集并显式注册插件，原unit业务函数在wrapper内执行。

命令：`PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest -p pytest_asyncio.plugin --noconftest -q --tb=short --no-showlocals backend/tests/privacy_closure_20261008/test_script_boundaries.py`。AST仅加载当前函数/纯文本辅助与纯privacy模块，外部selector/session/row_loader/native结果/客户端/观测/诊断为内存替身，公开规则清单从本地权威JSON读取。没有完整app/script import，不签收已有导入副作用或真实应用E2E。

真实患者材料、`.env`、PG、真实模型、网络均0。此前171归档保护未重跑；本轮未启动Node/完整前端。静态Ruff只对两个既有sys.path引导脚本明确豁免E402，其他规则正常检查；最终上述Ruff检查及git diff --check均通过。提交与真实Husky尚待主协调串行窗口，不能提前认领通过。

## 未闭范围

两真实CLI来源接入/功能恢复，patient_information未在现有读中出现的专有身份，其他未逐文件复核脚本，真实应用集成与规则验收均开放。不能把缺源拒发或合成业务替身的passed当整个003完成，也没有授权真实患者外发。
