# 单一东华CDM来源：候选验收记录

## 范围与基线

BASE_SHA：`60afbc49fbc92cad3b5234a2c7031d6261fcdf1e`。工作树：`D:/MedQC-worktrees/business-single-donghua-cdm-20261106`，分支：`codex/business-single-donghua-cdm-20261106`。实际候选Commit以PACKAGE.json及FRONTEND-BUILD.json为准。

普通临床只有东华独立CDM一个来源；账号、配置、任务、结果、Bundle和刷新审计仍写业务库。没有增加第二套任务/结果表。原工作树的064、source_bound_storage及未提交改动未带入。063文件及迁移链与BASE逐字一致，本补丁无新迁移。

## 实现与保护

- `clinical_source_policy.py`：默认`MEDQC_CLINICAL_SOURCE_MODE=fixed_donghua_cdm`；无配置、停用、凭据无效及源读取失败均拒绝，不回退旧库。`legacy_compat`仅为旧部署回退及旧测试合同提供显式部署兼容，不是前端普通切源功能。
- `clinical_sources.py`和`clinical_connection.py`：普通GET、无ContextVar后台任务和普通样本池任务固定东华；来源在创建时持久化，恢复时按保存绑定读。历史缺来源仍解释为原来源，不自动改绑；旧普通任务不自动恢复、不改状态。
- `custom_qc_workspace_service.py`：创建任务前将实参三坐标纳入冻结，不能凭sample_pool_id切回原源。
- PDF例外先核对真实登记，伪造前缀拒绝；自建材料通过真实业务登记确认，保留063的同源写读。PDF不新增快照，不使用真实1026包作夹具。
- 历史结果按Canonical/既有任务保存合同返回；完整、部分、无结果不美化或重算。缺历史原文快照返回409，不拿当前CDM同号材料代替。授权及病例成员校验保留，包含登记自建病例历史入口的拒绝回归。
- 前端普通病历池显示东华CDM，忽略旧URL来源；系统设置只配置该来源，不提供Homo切换。材料/历史页保持登记或任务身份，不强标东华。原PG同步API及直接服务入口拒绝执行，页面也不初始化旧同步或自动读取旧科室。
- `medical-records/stats`返回东华临床数量；未适配的旧QC问题统计明确为null/不可用，不从旧业务临床结果借值。现有CDM跨病例结果分析入口继续禁用；单病例历史结果可读。未改医学判定合同。
- 独立同步控制API、任务协议、同步服务运行代码均未修改。定时质控、自动同步、模型及RabbitMQ不由本补丁启用。

## 实际验证

1. 本机网络隔离offline runner：187通过、0失败、0跳过。覆盖来源约束、无上下文冻结、授权、登记材料、历史完整/部分/空结果、快照、063 helper及原兼容合同。
2. 前端7文件定向集合：64通过、0失败、0跳过。包含实际设置面板、病历池composable、结果列表、独立同步控制面板与系统设置旧同步不初始化。
3. `npm run type-check`：退出0；`npm run lint -- --no-fix`：0 error（既有样式warnings）；编码检查通过。前端构建成功，既有字体路径与大chunk告警保留。
4. 首轮完整前端集合：1982通过、27失败（2009项）；本次取消双源切换及旧PG向导后的相关合同已改写并在64项集合通过。其余4项路由超时按2个worker独立复跑通过；另有1项保护快照断言仍失败：`QCRecordCompareWorkbench.vue`期望历史blob `1fa95425...`，当前与BASE均为`307b51e9...`，本补丁未修改该文件。没有通过放宽保护或删除断言掩盖该失败；不宣称完整前端全绿。
5. 真实PG16与最终候选自检见同目录附录；只认本轮日志，不把以前53项或本机PG18样例计入本轮。

命令（工作目录apps/medqc-web/backend）：

```powershell
python -B scripts/run_qc_scheduler_tests.py --profile offline tests/unit/test_single_donghua_source.py tests/unit/test_clinical_sources.py tests/unit/test_data_pipelines.py tests/unit/test_case_material_snapshot.py tests/unit/test_bundle_refresh_storage.py tests/unit/test_validation_material_selection.py tests/unit/test_validation_material_display.py
```

前端以`NODE_OPTIONS=--require <独立工作树>/apps/medqc-web/scripts/frontpage-v2-no-network.cjs`阻断外网，执行上述7文件Vitest集合。完整集合也使用同一护栏，未放宽网络以处理超时。

## 未验证与现场边界

- 不连接本机medqc、两个既有PG18验收库、医院服务器、真实Caché、代理或模型；这些连接及真实模型调用为0。没有导入或读取真实1026包。
- PG16为CI独立网络命名空间、owned一次性集群、纯合成两个物理库。声明062基线夹具→正式063；不是空库全历史迁移验收。CDM依赖表来自正式ORM；空mr_diagnosis兼容视图仅属合成夹具，不证明现场具备该对象。
- 完成合成任务持久化、冻结恢复、Bundle与Canonical保存读取；不执行完整规则引擎，不代表真实模型医学质量或病历吞吐。
- 单一数据库快照不等于全接口发布完成；现场结构、只读角色及受控发布窗口仍需DSH验收。候选deployable=false，不得直接替换正式release。

## PG16最终证据

CI运行[42183829625](https://github.com/softjazzz/combined/actions/runs/42183829625)，测试提交`3208e9f04c6c39e0b0863832a404044cfa64985c`：隔离边界187通过；PostgreSQL **16.15**、端口62997、owned集群，**13通过、0失败、0跳过**（33.56秒）。其中6项为正式063归属与生命周期回归，7项覆盖普通API→Bundle→冻结任务后台重建→Canonical保存读取、缺表/缺列/权限失败及登记PDF/自建材料保护（single/split业务布局）。

实际业务临床旧表查询计数0、正常源库写入尝试0、错源读取计数0；源库数据与序列前后指纹一致。PDF沿正式055登记对象读取，创建的是合成文书，不调用快照persist。外部HTTP/模型由原护栏拒绝，未访问任何现有数据库。声明的062夹具不等于现场全库。

前端其余4项路由超时经限2个worker重跑通过（41通过、1失败）；剩余1项为上述确定的既有保护快照差异。该Vue文件BASE与当前blob均为`307b51e931cd5cf8a2bc37feb6d6a68b9ba929fa`，没有修改这项非本任务快照来凑绿。

单源核心本机／PG16验收：`SINGLE_DONGHUA_CDM_LOCAL_ACCEPTANCE_PASS`。无本机单源候选阻断；完整前端仍有披露的既有保护断言失败，不宣称全仓CI／测试全部通过。现场发布窗口、实际权限与材料完整性尚未验收。

## 原医学合同夹具的部署模式

首次全量质量门因真实默认改为固定CDM，115个旧本地fake源/重启任务夹具被门禁挡住（11846通过），不是已判定医学方向变化。已将旧单元夹具显式设为legacy_compat；新单源集合独立设置fixed_donghua_cdm并测试真实默认，PG16也显式固定新模式。没有修改执行器、删除失败断言或放宽网络，待全门重跑结果单列记录，不沿用旧11961通过数。

## 扩展隔离集合与独立导出验证

最终增加`test_independent_cdm_connection.py`后，本机合成/固定应答集合为**212通过、0失败、0跳过**（17.98秒），包含只读engine、源库故障、凭据及缓存边界。候选自检携带所需Python运行源码、公开规则资源与测试包入口；只打包storage目录中的Python模块，不打包数据库、会话、患者资料或运行文件。独立导出预检的26项单源入口回归通过；正式ZIP解压后的校验/回归结果另附在交付目录，不把预检占位资源冒充正式前端。

最终代码、前端构建及ZIP身份以PACKAGE.json/FRONTEND-BUILD.json为准；外部验收记录说明最终CI状态及SHA256。GitHub推送仅限本独立分支以触发隔离CI，没有创建合并或部署动作。
