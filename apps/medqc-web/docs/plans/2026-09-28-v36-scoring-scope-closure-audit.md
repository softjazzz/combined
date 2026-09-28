# V3.6 规则与评分适用范围收口审计

## 结论

- 优先收口 61“评分项目组配置”；58“住院规则配置”暂不作为本批整项完成。
- PRD 要求配置生效科室、文书范围及是否生效到医生端，但没有规定空科室范围代表全部还是无、医生端开关默认值，亦未规定 `all/selected` 的请求合同。不得从历史文件中的多数值推导默认值。
- 61 可采用“新配置必须显式选择适用模式，历史未补齐配置不得激活”的失败关闭合同，无需猜测默认值。58 即使采用显式配置，仍缺少现代医生端消费入口，单纯保存开关不能形成整项闭环。

## 已有事实所有者

1. 规则集版本的启停 owner 是 `QCRuleSetVersion.entries_json` 与 `rule_set_version_service.py`。版本 entry 当前只有 `rule_id/state`，`active/paused/offline` 是现代执行链的启停事实。
2. 评分 owner 是 `QCScoringStandard`、`QCScoringGroup`、`QCScoringItem` 与 `scoring_standard_service.py`；`scoring_service.score_result()` 是扣分 owner。当前评分项没有科室、文书或医生端适用字段，评分时也没有适用范围门控。
3. 现代规则目录已有 `source_document/applicable_documents`，执行链会消费该事实。评分配置若允许选择文书，只能保存并校验规则文书范围的显式子集，不能成为与规则目录冲突的第二 owner。
4. 结果后处理和裁决已有 `can_show_to_doctor` 安全事实。配置中的医生端开关只能与该事实做 AND 门控，不能把原结果的 `false` 改成 `true`。
5. 旧 `QCRule.scope/department_id/applicable_documents` 及 `department_qc_rules.py` 未进入现代冻结版本与任务执行链，不能复用为现代权威 owner。

## 原始配置资产的适用边界

`assets/data/（运行病历）住院质量评定标准_433377418703_2024-04-03_09-59-13.csv` 包含评分项目组、质控文书、生效科室、是否启用和是否生效到医生端，可证明适用范围位于具体评分内容或规则层级。

该文件不能直接成为现代运行合同：

- 质控点使用旧数字 ID，尚无到现代 LX/SC `rule_id` 的已核实映射。
- 科室值为分号分隔的名称；现有转换脚本按逗号拆分，前端加载器又使用子串匹配，均不能用于权威适用判断。
- 少量禁用行的科室为空，但文件未定义空值语义。
- 科室名称不包含机构身份。不同机构可能存在同名科室，不能以当前部署看似单院为由，将名称全局唯一当成长期合同。

因此该资产只能作为经人工核对的导入来源，不能自动迁移为现代配置，也不能用于推导默认值。

## 61 最小整项合同

适用范围应归属于 `QCScoringItem`，因为原始配置中不同评分内容的范围不同：

- `department_scope_mode`: `all | selected`
- `department_refs`: 选择模式下非空、去重、精确匹配的机构内科室引用
- `document_scope_mode`: `all | selected`
- `document_types`: 选择模式下非空、去重，并校验为该版本规则文书范围的子集

新建或编辑草稿必须显式提交两个 mode。`selected` 必须有值，`all` 必须为空。历史数据迁移可保持未知以便读取，但在范围补齐前不得激活或设为默认。评分服务收到明确的病例机构、科室和文书上下文后，先执行 `enabled + applicability` 门控，再进入现有扣分逻辑；选择范围但上下文缺失时失败关闭。不得使用科室子串匹配。

科室引用必须至少在机构内稳定。现有病例和任务链大量使用科室名称，只能作为兼容显示或过渡输入；没有机构约束的裸名称无法排除跨机构同名科室误用，不能把“当前看似单院”当作绕过理由。若暂时没有稳定科室 ID，应保存并比较 `(institute_id, normalized_department_name)`，同时明确后续字典映射迁移边界。

需要贯通的最小文件范围：

- `backend/app/database/models/qc.py` 与独立迁移
- `backend/app/services/scoring_standard_service.py`
- `backend/app/services/scoring_service.py`
- `backend/app/services/scoring_standard_excel_service.py`
- `backend/app/routers/scoring.py`
- `src/api/scoring.ts`
- `src/views/qc/scoring/scoringStandardModel.ts`
- `src/views/qc/scoring/ScoringStandardEditor.vue`
- 上述模块对应的后端与前端聚焦测试

验收必须覆盖跨机构同名科室、缺少上下文、非法文书子集、历史未知配置不可激活、Excel/API/UI 往返，以及 `score_case`、`score_cases`、`score_workstation_page` 的同一适用结果。

## 58 的真实阻断

58 的生效范围属于规则版本，而不是评分标准。完整实现需要把显式科室、文书和医生端配置纳入版本 entry、摘要与发布冻结，并由执行调度在进入规则执行前按冻结上下文过滤。

当前没有已核实的现代医生端结果投影或接口消费该开关；演示性质的 DoctorWorkstation 与 running QC service 不能作为验收 owner。医生端开关还必须与 `can_show_to_doctor` 做 AND 门控并接受对象授权约束。在这些消费与授权合同明确前，只新增存储字段仍是部分实现，不能把 58 标记为代码完整。

