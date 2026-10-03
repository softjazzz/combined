# 病案首页默认评分实施计划

> 按 executing-plans 分工实施与复核；起点8a5906f4c。用户批准57/60，来源核查后本批集中完成60首页子能力。

**目标：** 既有首页FQ规则注册为只读配置目录，本次形式质控结果消费首页默认评分标准，不改变引擎判定、通过率或历史保存分数。

**架构：** frontpage独立评分场景沿用标准CRUD、CAS与计分owner；FQ目录直接派生既有引擎定义。完整可信报告映射确认缺陷后由score_result计分，配置缺失/异常明确不可用，不阻断既有形式质控。

**技术：** FastAPI、SQLAlchemy/Alembic、Vue/Ant Design Vue、SQLite/pytest与Vitest。

## 前置结论

- 57尚无正式outpatient规则集；本机medqc以只读事务核对：qc自定义草稿7条仅running/final，public规则表空。681条已发布版本分类均为住院文书，描述提及门急诊不构成适用范围。远程库连接失败，不能宣称所有医院来源均无规则。已询问用户正式规则文件路径。
- 门急诊现有禁创建/拒执行不解除，不另建空入口。病案首页已有FrontpageFormalQC完整规则与实际validate链，可在不改规则的前提下配置计分。
- 本批仅形式质控FQ，不包含编码质控（按用户要求暂停）；不把终末标准当首页标准，不使用本机旧scoring_rules行默认值代填权威扣分。

## 分工与边界

1. v36a：新增frontpage_rule_catalog.py，只读内置key frontpage_formal_v1/version 2026-10-03；rule_set_version_service窄解析、scoring_standard_service增加frontpage配置场景及测试。不要把首页加入住院任务规则集。
2. v36b：评分API/types与既有评分页新增首页tab，实际形式质控页面显示本次scoring；不新建页面，账号/病例/重跑切换清理旧评分。
3. v36i：frontpage_scoring_service及qc.py消费，一次默认读取，严格完整报告/规则全集校验，服务端病例科室，配置失效/不兼容不可用；真实FQ+SQLite标准的集成测试。
4. root：模型CHECK与迁移084、迁移测试、联合回归、关键diff复核和台账。三个代理沿用Sol6.1 medium，复用原树，不删除其他工作。

## 验收

- 配置：首页与运行/终末/门急诊默认互不影响，规则key不能跨场景；CAS、停用、无默认均有真实持久测试。
- 消费：FQ布尔结果仅搬运，不重判；未知/重复/缺失规则不算完整分；保留历史分与通过率；服务端真实科室不可信时不可用。
- 迁移：仅改评分标准scene CHECK，qc/public各自精确预检，漂移或部分部署拒绝；降级有frontpage标准则拒绝，无真实库执行。
- 门禁：聚焦pytest/Ruff与Vitest，root串行完整type-check/只读ESLint、暂存编码与diff检查；不修改CI、不跑真实LLM。
- 60仍有门急诊缺口，57仍阻塞，不提高整项数。无真实库写/迁移/部署/推送授权，合成验证不等于真实患者验收。
