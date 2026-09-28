# V3.6 现代申诉来源 Implementation Plan

**Goal:** 补齐04/51共用的现代申诉来源链，先实现独立可测的可信目标解析，不提前宣称整项完成。

**Architecture:** 工作台来源以Canonical Envelope为权威，不以QCResultBiz代替。申诉状态及审核继续归QCAppeal/QCAppealReview；公开创建入口必须等对象授权合同及持久化接通，来源解析本身不授予任何用户权限。

**Tech Stack:** SQLAlchemy、FastAPI、pytest；后续前端Vue。

## 已核实证据与纠正

- record_review_service已有唯一ready DTO读取、三坐标、root job/envelope、rule set/version及锁内scene解析；复用这些校验，不复制大段逻辑。
- 现代workspace不依赖QCResultBiz。将其新增scene并串改首页/编码/结算保存入口不能解决当前workspace申诉问题，故不采用。
- task_manual_defect_service创建人工缺陷不赋旧result_id；可信关联在唯一manual_create历史的task/run/job及三坐标。不得伪造qc_result_id。
- score_result当前按需计分、不持久化。后续评分申诉须绑定结果信封和标准版本，冻结服务端重算快照，不能把提交时最新分数冒认为用户看到的分数。
- SysUser.department可由本人修改，且没有机构绑定；不是申诉写权限。用户管理页面仍为模拟，不能声称已有管理员范围配置。

## 待确认业务口径

- 科室全部病例或本人主管/管床病例；科室方案需要管理员维护机构化授权，不信个人资料。
- 运行当前科室、终末出院科室、门急诊就诊科室，或缺陷产生时冻结责任科室。
- 人工缺陷仅审核通过可申诉，或待审核也可申诉。

上述问题已异步询问。未确认前不新增有权创建的角色推断、不开放医生结果读取、不迁移/写真实库。

## 第一批独立交付

1. 结果引用：record_review_service仅暴露薄的公开解析方法，复用现有身份/ready/anchor/scene校验；不改变原审核行为。新申诉来源服务验证预期job/envelope与当前结果相同，返回冻结来源，不写库。
2. 自动缺陷：target为同一Envelope内唯一rule_id，必须是客户投影中is_confirmed_issue=True；不以defect_item文案作身份，不重判引擎事实。
3. 人工缺陷：target为defect_id，校验现代人工来源、完整三坐标、冻结scene与唯一创建历史，按对应task/run/job定位来源。不将原创建人的任务受领权限套给临床申诉人；解析与授权分离，后续创建接口必须先完成授权。
4. 测试：跨院同号、缺失/冲突anchor、重复规则、非确认缺陷、坏历史、无旧result_id、源读取失败。使用SQLite/假workspace，禁止真实数据库连接。

事务边界：现有workspace DTO选择器自行读取数据库，传入session不等于把它自动纳入调用方事务。第一批只能证明调用时候选与调用方session回读的精确目标一致，不能声称阻止新job并发成为最新结果。后续创建必须明确最新性政策并重验，不能直接缓存该引用后脱离事务写入；本批不为此修改引擎或所有job写入口。

## 后续完整链

- 确认授权后，显式范围管理、申诉创建DTO/原子写入/幂等、同表审核、scene列表/计数、前端实际入口和51统计逐层贯通。
- schema现代分支允许旧qc_result_id/record_id为空，不能塞envelope或就诊号冒充；历史旧行保留不回填。具体迁移在源合同稳定后编写，不先定错误外键。
- 主协调复核、聚焦pytest/Ruff及适用前端门禁后中文提交。第一批解析器不计04/51完整，Goal保持4/10。
