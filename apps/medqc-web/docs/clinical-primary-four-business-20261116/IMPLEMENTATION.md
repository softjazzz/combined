# 四类 clinical 优先业务适配交付

**业务代码适配及合成材料链验证完成，独立复审无未闭合P1/P2。真实现场联验未执行，生产未部署，功能默认关闭。**

业务起点 `7ba8a94a9029a784aa6ec629219b4fbccc21cb63`。本地交付提交为包含本说明的提交，使用 `git log -1 --format=%H -- apps/medqc-web/docs/clinical-primary-four-business-20261116/IMPLEMENTATION.md` 精确定位；外部交接单记录提交号，避免文档自引用改变commit。

同步固定依据：`cb437e611e802c5117f212c1e9743d2748ec4127`，`clinical-primary-four-v1`，`clinical-primary-real-fields-v2`。复用 `3123e046865c28155c227a3d05d54599e2286859` 的既有证据，已核对相关运行源与三个JSON字节相同；没有重跑同步侧232项或真实65+44行材料。

## 1. 复用与新增

复用既有 SQLAlchemy CDM连接、短只读REPEATABLE READ事务、`case-material-v1`不可变全文副本、源reader、目录/Bundle/全文渲染及来源权限。旧daily-v3固定只读闭包保持不变。1026/PDF登记和重试来源代码不修改，普通病历仍只读独立CDM；不新增源库或同步通道。

新增 `backend/app/services/primary_material_readonly.py`：从固定源按定义提取只读闭包，不带迁移、采集、poll、写仓储或源库结构检查。`read_primary_in_transaction`只借用现有SQLAlchemy的driver_connection，cursor由自身关闭，调用者连接/事务不提交、不回滚、不关闭。原始 `read_in_transaction` 和选择器逐字保留，读取显式列，禁止SELECT *。

新增唯一owner `primary_material_projection.py`：载入显式批准policy，消费原选择DTO，不重写选择或去重算法；完成选中版本→统一业务行/目录/范围状态投影。批准native三键映射到canonical三键，原键与来源版本仍保留。其余层只搬运元数据，不重新判定来源。

接入文件：`case_material_capture.py`、`automatic_material_scope.py`、`daily_material_projection.py`、`bundles/assembly.py`、`bundles/current_view.py`、`luxian_0609/source_evidence_reader.py`、`sample_programmatic_evidence.py`。三个reader、时间线及程序材料都使用同一选中版本；目录里的替代版不会重新进入正式规则事实。`bundles/emr_view.py`、`routers/emr_render.py`及前端EMRViewer/DetailSidebar搬运来源、版本、选中/待核和空正文/技术失败状态，摘要不透出完整raw payload。

## 2. 版本、正文及时间合同

仅覆盖日常病程、术前小结、手术记录、术后首次病程。clinical准入优先；空白正文、生命周期待核或发布健康拒绝时，只有固定选择器实际选中的可靠Caché整份版本可用。不逐字段拼接正文，不让空值覆盖可靠版本，不按文本相同跨号去重。

手术正文只取 `surgery_process`，`record_content`保持原值。正文冲突只屏蔽相关正文事实；结构化独立可靠字段保留。规则metadata删除可绕回冲突正文/未知时间的raw/native/target/source_payload通道，完整原值仍在任务材料副本和目录中。

原始record/submit/modified/summary/surgery/签署等角色不互相替代。clinical未确认角色不进入时间规则；Caché缺新增角色状态的旧合同兼容仍需EXPLICIT_OFFSET且未被uncertain_fields拒绝。固定Cache手术映射是`*_time`而DTO读取`*_datetime`，当前两个角色为MISSING；术后首次病程缺record_datetime。业务不自行补映射、时区或记录时间，这些缺口由同步合同方确认。

原始`is_deleted/record_status/document_status`不由业务解释0/1、NULL或Save。HOLD和未准入版本只作待核展示；当前同步读取会重新核对发布健康、回执、目标payload及新主键，因此旧COMPLETE不能冒充本次补充完成。覆盖不足不等于临床未书写；连接、权限、身份或完整性异常继续失败，不当成功零行。

## 3. 默认关闭与未部署兼容

`QC_PRIMARY_FOUR_MATERIAL_ENABLED`未设时关闭。启用后需`QC_PRIMARY_FOUR_POLICY_FILE`指向受保护绝对JSON路径：`policies`每项含原始policy、精确policy_hash、当前CDM source_binding。不是从数据库管理表推定批准，不授予primary_attempt读取权。与旧daily开关同时开启时新owner优先，不重复读取两套选择。

六个必要元数据对象通过同事务`to_regclass`探测：候选对象未部署明确为NOT_DEPLOYED，保持原基础CDM读取和事务可用；对象已存在但读取权限/合同失败不降级。四类current目标不存在或发布回执过期时按固定选择DTO门控处理，不绕过清单直接UNION当前源。

同事务冻结完整选择DTO（包括替代版、排除依据、覆盖/健康、原始时间及发布证据）与实际正文、输入和版本定位信息。旧快照缺新字段走原协议，不查最新CDM；重试使用原快照，新发布不能改变历史结果或材料。不更改暂停规则、无首页取材或C03待确认口径。

## 4. 实际只读闭包与权限

固定三JSON及指纹在 `backend/app/data/clinical_primary_contracts/`：原始SOURCE_FINGERPRINTS及扩展READONLY_FINGERPRINTS。扩展记录10个源模块、33个运行定义、23个类方法及裁剪/路径适配；明确区分原始类hash和裁剪后运行hash。生成入口 `backend/scripts/build_primary_readonly_closure.py` 仅离线处理固定ZIP。

运行闭包包括：PrimaryPolicy、固定selector；registered/health/receipt/target/read_in_transaction；real_contracts/metadata映射及裁剪Contract；DTO规范化/digest/接口spec；baseline catalogue及cache_spec；SQL标识符校验。三个JSON是实际运行依赖，冻结重放/试跑工具不是。

精确权限草案见 `READONLY-PERMISSIONS-PROPOSAL.sql`，14个对象：policy/head/manifest/coverage、contract/receipt、四clinical_current和四Caché基础CDM表。列清单来自实际target_columns，全部语句注释化，未执行授权。manifest.result_json含整份材料，列级授权不能替代机构/病例授权。病例来源批准、目标对象部署及现场权限由院方/同步/运维闭合。

## 5. 必要定向验证

各组有重复覆盖，**不累加为独立总数，不声称全量通过**。测试均为合成材料；模型和医学规则执行为0。

| 范围 | 结果 | 边界 |
| --- | --- | --- |
| 固定只读闭包单元 | 13通过，退出0 | SQL显式列、连接所有权、合同/政策/回执拒绝、源码及JSON指纹 |
| owner/capture合成 | 初始16通过，退出0 | 四类reader/Bundle/程序材料、政策映射、HOLD/冲突隔离、旧副本/PDF分流 |
| 复审时间修复 | 新反例先失败，修后与相关原用例2通过 | Caché缺新增状态兼容；clinical未确认/MISSING继续屏蔽 |
| 旧daily适配回归 | 42通过，退出0 | 原窄合同、桥/投影及时间线接缝兼容 |
| 前端定向 | 23通过，退出0 | 目录状态、版本、全文失败与空态；非现场浏览器验收 |
| 后端展示透传 | 最终新增3通过；此前相关41通过 | 两组有重叠；路由读取冻结状态不回查CDM |
| 联验工具 | 2通过，退出0 | 准备态不导入应用、授权拒绝、5条日常材料和截断停止 |
| 定向类型/ESLint | 退出0 | helper严格类型、两个Vue组件；既有两页8条格式警告未扩改 |

PG16.15使用便携二进制、新端口55866和随机`delivery_cdm_*`专属库，只读reader与合成发布者分离。共5个不同场景：同连接四类输入/完整副本；并发head和正文更新下RR不混版、旧副本不变；最新clinical阻断保留Cache；可选元数据缺失不中止基础事务而权限拒绝显式失败；冲突只限制相关正文。

首次5节点中3通过、2因夹具漏设来源binding失败；补齐**合成夹具**后仅复跑该2节点，均通过。时间兼容修复后仅再跑受影响的Cache回退节点，通过。三个专属集群均停止，保留外部报告目录的`pg16-first`、`pg16-fixture-fix`、`pg16-cache-time-final`，没有接触现有业务库。

另一次混合历史/PDF收集触及超出本轮范围的模拟医学/路由节点，14项初始化失败；未逐例基线对照，故不宣称其为旧失败，也不作为本轮通过证据。停止扩大该集合，未运行真实规则或模型。真实PG现场角色、业务服务并发及浏览器链路不在本次合成验证结论内。

可复跑入口（仅按需，不要求重跑已通过集合）：

```text
# backend，离线闭包/新增联验工具；不读取应用配置
python -B -m pytest -c pytest.ini --noconftest -p no:cacheprovider -o "addopts=-q --tb=short --strict-markers" tests/unit/test_primary_material_readonly.py tests/unit/test_primary_material_trial.py

# backend，新建专属PG16；REPORT必须尚不存在。可加--test-node只运行受影响节点。
python -B scripts/run_primary_material_pg_tests.py --pg-bin PATH_TO_PG16_BIN --port 55866 --report-dir NEW_PRIVATE_REPORT_DIR

# apps/medqc-web，复用已有node_modules
node node_modules/vitest/vitest.mjs run tests/unit/views/workstation-v4/documentMaterialDisplay.spec.ts tests/unit/views/workstation-v4/DetailSidebar.spec.ts tests/unit/components/EMRViewer.spec.ts
```

## 6. 独立复审及待现场条件

独立复审核对固定ZIP/指纹、权限闭包、各reader接缝、时间/正文隔离、历史/PDF与UI透传。发现并关闭2项P2：Cache可靠时间过度屏蔽；新联验工具默认3行造成版本比较误报。未确认遗留P1/P2。完整只读复审记录在外部交接目录`review-primary-four-business.md`。

责任方待办：院方确认两例机构/类型/生命周期；同步方完成真实发布与policy/selection证据、确认时间合同；运维确认最小只读权限和受保护政策来源；业务方在另获授权后按 `ONSITE-TRIAL-NOT-EXECUTED.md` 运行一次两例材料链并核对页面同版本。真实clinical仍HELD就停在准备态，不以此扩大到全院历史供给审计。

本轮不推送、不合并、不部署、不改配置、不重启现有服务；没有现场连接、模型/规则/QC执行、真实材料重放或历史数据改写。未建新的业务任务，旧冻结和历史结果保持原状。
