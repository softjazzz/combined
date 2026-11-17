# 四类 clinical 优先业务适配实施计划

> 执行既定业务交接，不扩展同步平台；按互不冲突的文件责任并行实施，最后一次独立整体复审。

**目标：** 将固定 cb437e611 的四类材料选择接入既有独立 CDM、统一 Provider、Bundle、目录和全文任务材料副本；准备限定范围无模型联验，不执行现场联验。

**代码起点：** `7ba8a94a9029a784aa6ec629219b4fbccc21cb63`，现有独立工作树、无未提交修改；保留该提交的两项抗菌理由暂停，不混改其他规则。

**合同：** `clinical-primary-four-v1`、`clinical-primary-real-fields-v2`；固定源提交 `cb437e611e802c5117f212c1e9743d2748ec4127`。`3123e046865c28155c227a3d05d54599e2286859`仅作已有验证依据，相关运行依赖字节一致，不引入试跑工具。

## 规格和边界

- 仅 daily_course_record、presurg_summary、surgery_record、postsurg_firstcourse_record；默认关闭，不修改现场或本地运行配置。
- 正式业务只读独立 CDM；同步选择器拥有来源选择及去重，业务只搬运 selected_version 对应的整份版本。
- clinical为空、不可用或被门控时，只使用合同真正选中的可靠 Caché 整份版本；不拼接字段，不把替代/HOLD版本加回规则。
- 手术正文为 surgery_process，record_content不补填。保留原始时间角色及未确认状态，不补日期、时区或跨角色赋值。
- 在现有SQLAlchemy只读RR事务中借用同步driver连接；不另开连接，不提交、回滚或关闭调用者事务。
- 现有 daily-v3 窄闭包保持固定版本；新合同建立可审查只读定义闭包，含必要JSON依赖及指纹，不携带同步写入口。
- 批准政策必须由显式批准输入提供，缺失时拒绝新合同准入，不从NULL/位值、当前文书或机构占位值推定批准。不擅读primary_attempt等管理对象。
- 未部署候选对象时，在同事务内明确探测并保留基础CDM能力；启用后的权限、连接、身份、完整性错误不能伪装为成功零行。
- 整份DTO固定在现有不可变材料副本中；旧快照不回查当前CDM，新重试仍用原副本，1026/PDF来源绑定不变。
- 缺口仅限制相关事实，不能以缺文书推断临床未书写，也不能压掉其他独立可靠事实。
- 禁止连接现场库、模型、OCR、同步或医学规则执行器；不创建真实质控任务，不重跑27份，不改历史数据，不推送、合并、部署或重启现有服务。

## 职责和任务

1. **固定只读闭包与连接桥。** 新增 primary_material_readonly 及固定合同JSON/指纹，暴露PrimaryPolicy、real_contracts、固定read_in_transaction；桥仅借用已有SQLAlchemy连接。用合成游标核对SQL、所有权、完整依赖和拒绝边界。
2. **唯一四类业务投影。** 新增统一owner，并接入现有capture、live_context、Bundle两处取行、当前目录、三类源reader、timeline、programmatic捕获及目录合并、automatic scope。保持旧daily兼容；同一组selected版本贯穿所有入口，未选版本仅展示。
3. **页面搬运。** 沿用既有material来源字段及scope提示，展示选中来源/版本、冲突/待核/空正文/技术失败；手术使用既有正文渲染。只补必要类型及组件/投影测试，不重做页面。
4. **一次性PG16材料链。** 使用现有便携PG16二进制、新建专属端口和随机delivery_cdm合成库，验证实际SQLAlchemy连接、选择与正文同事务并发一致性、四类输入、完整副本、版本定位、捕获后更新及旧副本兼容。无模型、无规则判定，不重跑同步侧矩阵。
5. **交付和独立复审。** 固定本地提交，记录实际读取闭包/列权限草案、复用项、定向验证和未覆盖项、旧快照兼容及限定现场无模型操作单。真实clinical依然HELD时明确待批准/发布，不伪造许可。

## 接口约定

- 只读库保留同步固定入口 `read_in_transaction(dbapi_connection, policy, contracts)` 和原选择DTO；业务桥允许现有同步SQLAlchemy Connection，绝不创建engine。
- 业务层以新合同owner为唯一转换入口；现有稳定字段 source_version_key、version_id、source_record_identity、source_namespace、source_object 继续有效。
- 页面继续消费既有 material_selected、material_rule_usable、material_source_label、material_notice 等元数据；新增选择状态元数据先固定在材料副本中再投影，不重判。
- `QC_PRIMARY_FOUR_MATERIAL_ENABLED`仅在代码中声明默认关闭；如需文件提供批准政策，使用显式保护路径，不生成真实批准配置或改环境文件。政策供给及policy_hash核对列为真实联验前提。

## 预检冲突与裁定

| 责任交界 | 风险 | 裁定 |
| --- | --- | --- |
| 只读闭包 → 业务owner | DTO或政策含义被重实现 | 保留固定选择器和校验代码；owner仅转换选中整份版本 |
| owner → capture/历史 | 双事务或回放读最新 | 借现有capture连接，冻结完整DTO，历史无新增字段走旧协议 |
| owner → Bundle/规则 | 目录替代版回灌规则 | 四类来源统一剔除原目录候选，再使用选中规则行 |
| owner → 展示 | 空正文、HOLD和技术失败混为一类 | 展示状态搬运明确，正式规则只消费selected_version |
| 元数据 → 时间规则 | 固定Cache手术映射为*_time，DTO读取*_datetime而MISSING | 保留此合同事实和原值，不代同步侧补映射；只限制相关时间依据 |
| 合成PG → 现场 | fixture的批准被误当真实批准 | 使用随机隔离库和明确合成政策，现场方案另列批准缺口 |

## 完成记录

实施及独立复审完成。完整交付记录、接缝、命令、验证和剩余现场条件见 `apps/medqc-web/docs/clinical-primary-four-business-20261116/IMPLEMENTATION.md`；精确14对象列权限草案及两例限定无模型操作单在同目录。

- 五项计划均完成，复用旧连接/全文副本/reader/UI，不重写同步选择器。
- 13项固定闭包、16项owner/capture、23项前端、3项最终展示及42项旧daily验证已通过；各组有重叠不累计。复审时间修复以新反例及相关原用例2项验证；联验工具2项通过。
- 独立PG16五个不同材料场景最终均通过。首轮两个缺少合成来源绑定的夹具已修，仅读取这两个失败节点复跑；时间修复后只追加受影响Cache节点。三个集群均已停止。
- 独立复审的Cache时间过度抑制、联验默认三行两项P2已修复并复核，无遗留P1/P2。
- 混合历史/PDF集合14项初始化失败未逐例基线核对，不计本轮通过证据，未扩大执行。
- 真实批准政策、生命周期和发布/权限仍由院方/同步/运维确认；真实材料链、浏览器及生产并发未执行，功能保持默认关闭，现有本地服务与配置不变。
- 未推送、合并、部署、连接现场库、调用模型、医学执行器或真实质控任务；旧快照和历史任务结果不改写。
