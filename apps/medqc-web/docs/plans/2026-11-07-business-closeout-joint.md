# 业务收口联合适配：不含0916

## 固定范围与来源

- 远端业务基线已重新fetch核实：`6ad6817b1b66c21b7c94542772a8452215250de5`。
- 联合工作树：`D:/MedQC-worktrees/business-closeout-joint-20261107`。
- 联合分支：`codex/business-closeout-joint-20261107`；不移动业务集成分支，不使用其工作树运行服务。
- 通过本地cherry-pick汇集已完成修复，未执行GitHub合并或推送：
  - 出院终点`8e31894cf` → 等价提交`7be119ef1`。
  - PR #45的GET只读修复`0c92b275c` → 等价提交`e87c06799`。
  - A目录丢选红色回归`1d9db5e2` → `03088463b`。
  - B的PR证据说明`55aff2869` → `b68294e07`。
- A/B/C/D四路及E独立复核均按用户要求使用GPT-6.1 Sol high。公共源码和联合Git索引由主协调维护，未修改0916。
- 原出院工作树中的未跟踪收口计划仅复制到本联合树保留，未删除或覆盖原材料。

## 本轮确认并修复的三个问题

### 1. CDM目录先按旧出院日期筛选，正式取材无法补回漏选

真实路径：`RecordRepository.collect_records/list_records` → `clinical_case_catalog.case_identities` → `catalog`日期筛选 → 正式三坐标取材/冻结。

合成例登记02-05、首页02-06、文书02-09：显式取材冻结为登记日，但目录原来按文书日筛选。按02-05筛选时返回0例。

最小修复：目录出院优先级与正式取材一致，登记→首页→有效出院文书；不使用入院文书的非约定出院字段。仅出院字段空白归空，文书明确无效状态复用既有状态owner。其余筛选、机构范围、只读选源及未确认在院语义不变。

A使用实际目录和RecordRepository调用构造SQLite反例，修前失败、修后命中1例且目录日期与冻结一致。SQLite日期CAST的方言差异只在测试中用date函数承载，未据此声称已验证PG16。

### 2. 保存后热重载再次覆盖分析客户端，丢失角色和默认选型标记

真实路径：页面保存/重载 → `LLMConfigLoader.reload_config_for_service`正确构造一审/分析双方 → `SichuanQCService.reload_config`重新用部分字段构造分析客户端。

第二次构造丢掉`task_role_models`与`qc_use_selected_model`，固定HTTP出口的三个角色都回到旧环境裁决模型。

最小修复：删除重复构造，保留Loader已原子校验的双方客户端。并发策略和Prompt构造器同步继续沿原逻辑。角色子客户端实际请求的model、Thinking、输出预算和双方冻结身份均有定向断言；已有隔离任务继续持有旧客户端。

模型角色提示仅改文字：新建任务使用新配置，在途保留冻结配置，排队/恢复任务身份不匹配时需重新创建。不改变页面样式、权限、保存协议或主动连接模型。

### 3. Linux暂存器未检查材料快照目录是否随release切换

旧stage只检查business.env文件，没有阻断材料目录指向release或不稳定相对路径。

最小修复：复制新release前，只读解析有效材料目录，遵循`QC_CASE_MATERIAL_DIR`优先、其次dispatch父目录推导，与应用dotenv插值/进程环境优先级一致。拒绝相对目录、release/current及其符号链接别名；允许尚未首次创建的持久目录。不创建、搬迁或删除材料，不修改.env或代理配置，不自动切换current。

部署继续使用已有业务venv。python-dotenv已是应用固定依赖1.0.0，没有新增应用依赖；缺失时明确拒绝。CI工具环境显式准备该既有依赖，测试仍在原网络命名空间/socket隔离下执行。

## 各路收口

| 路 | 结论 |
|---|---|
| A 出院 | 确认目录前置筛选漏选，已由主协调修复；原DTO秒级精度作为既有兼容限制，不扩大为本轮新缺陷 |
| B GET/CI | PR #45仍Draft，Head0c92b275c，7/7检查成功；两个精确GET与readonly列表保持认证、created_by和历史来源保护，无新运行修复 |
| C 配置 | 确认并修复service热重载旁路；其余角色/代理/P9证据按相同代码范围复用，不宣称所有规则族都已分角色 |
| D Linux | 修复暂存材料目录门禁，补临时合成文件保护及回滚说明，不构建正式包 |
| E 复核 | 对最终公共代码、各路证据和CI覆盖只读独立复核，未确认新增跨模块阻断；不重复执行全量测试 |

## 实际验证与证据边界

在`apps/medqc-web/backend`执行：

```text
python -B scripts/run_qc_scheduler_tests.py --profile offline tests/unit/test_business_closeout_configuration.py tests/unit/test_discharge_horizon_document_fallback.py::test_clinical_candidate_catalog_uses_the_same_discharge_authority_as_task_freeze tests/unit/test_workspace_metadata_readonly.py
```

19通过：真实热重载固定出口1项、目录丢选1项、只读GET/权限及列表17项。运行主动剥离配置并阻断真实网络及非SQLite连接；没有应用lifespan或业务服务启动。

```text
python -B scripts/run_pr8_offline_tests.py tests/unit/test_case_material_snapshot.py::test_frozen_material_survives_native_binding_and_canonical tests/unit/test_case_material_snapshot.py::test_worker_capture_failure_keeps_other_case_results
```

4通过：3个合成场景经材料回放→06-01-04 Native→Binding/Finalizer→Aggregator→Canonical内存保存读取，分别覆盖合规、不合规和资料缺口；1项Worker取材失败保留其他病例成功结果。主抽取/专项均固定应答，不代表真实医学质量或完整HTTP/PG现场验收。

C另外运行了热重载及旧客户端绑定4项、旧继承/快照2项。与上述19项有重叠，不累计成新的独立病例数。历史角色/代理及B相同运行代码的30后端/14前端证据仅按其原Head和范围复用。

Linux工具使用socket拒绝、临时合成文件，按更新后的CI发现入口执行：

```text
python -B -m unittest discover -s apps/medqc-web/scripts/linux_app_upgrade -p "test_*.py"
```

该命令在本轮由外层socket拒绝包装执行。共23项：21通过、2项因Windows符号链接权限跳过。测试仅产生并清理微型合成夹具包，没有制作交付包、启动应用或连接数据库。实际Ubuntu符号链接、依赖包复用冒烟仍待CI/现场验收。

静态检查：相关Python AST、两份workflow YAML、UTF-8/LF和diff格式；相关文件Ruff通过。`sichuan_qc_service.py`全文件有7项既有Ruff诊断，已对6ad基线与当前源码逐项比较一致，无新增，未顺手扩大清理。

## CI覆盖与最终限制

- 出院专项加入既有data-pipelines suite；私有六例入口无显式材料时仍跳过。
- 只读GET专项加入既有来源/历史回归step。
- 角色step增加真实service重载与旧客户端绑定专项。
- Linux两个工具验证入口均发现`test_*.py`，新增目录预检不再只是无人调用的文件。
- 不删除或放宽门禁、不修改网络隔离，不触发新的远端CI。本地19/4/工具21通过不能冒称联合Head远端全绿。
- 063/064既有迁移链仅静态核对，未运行迁移或重新进行PG矩阵；定时计划默认关闭。
- 没有连接业务库、独立CDM、客户机、代理或模型服务；未调用模型、重跑27份、启用自动任务、重启服务、推送、合并或部署。
- 未改0916代码、范围、启用状态和验收结论。

当前结论：本地联合候选已完成本轮必要工程收口，可以交PR审查；尚未得到联合Head远端CI和最终Linux交付/现场冒烟证据。后续制包须绑定最终应用源码及准确Commit，不能用旧完整包内容冒称新版本；现场PG16、材料路径权限、CDM发布窗口和真实模型质量继续单列验收。
