# 09299阶段小结30天周期交付

## 口径与实现

客户《附件三：终末质控.xlsx》评分标准第239行：住院超过30天缺阶段小结，交接班及转科记录可替代。用户2026-10-26确认按附件执行，不增加31天出院豁免。院内书写规范第2160–2166行说明每满30天总结、交接班/转科替代后重新起算。

新增`LX0609-10-04-01`，使用现有`extended_document`执行族，纯程序、0模型调用、`acceptance_only`。原17项映射及3处已确认差异未改判。

- 真实入院时刻复用`extract_admission_anchor`既有优先级；不接受文书创建时间冒充入院，也不将只有日期解释为精确入院时刻。
- 评价终点复用同一次Evidence Session的冻结终点。精确时刻直接核对；只有日期时按整日区间判断，结论可能随日内时刻改变则资料不足，不虚构午夜。
- 新增已实际存在的`summary_record`受控有界来源，按三坐标及limit+1查询。登记版本v35，仅新增来源，原来源query_version不变。原入院/终点读取逻辑未修改，legacy预取仅增加本规则依赖，不扩张旧执行族的公共预取。
- 有效阶段小结、交班/接班、转入/转出文书按标题、非空正文和权威完成时间确定；正式提交时间只在前序权威时间为空时使用。held/version_review候选、冻结终点后的记录不满足当前周期。
- 精确等于30天尚未触发“超过”条件。长住院逐周期核对，小结或有效替代记录重新起算下一30天；迟到补记不能抹掉已经超期的周期。不存在31天出院豁免。
- 无文书且来源完整可报周期缺口；来源不可用/截断、缺权威时间/正文、同源同ID不同内容或时钟冲突均保留资料不足。周期及候选数量受控，超过现有公开事实100项容量时资料不足，不截掉后面的缺口。
- 连续医疗公开事实白名单只校验类型和允许字段，不重算周期。Renderer展示已经裁定的周期截止时刻；Canonical沿用既有source_ref坐标保护与evidence键保存，不改变或重新选择文书。

## 真实材料验证

独立原生PG连接强制`REPEATABLE READ READ ONLY`，只读提取1026-PDF补全27例的必要材料后关闭连接。随后在禁网、禁dotenv、禁止非SQLite连接的启动器内执行正式Snapshot→Native→Binding→Finalizer→Canonical内存保存读取：

| 结果     | 数量 | 验证含义                                               |
| -------- | ---- | ------------------------------------------------------ |
| 合规     | 3    | 各已到期周期有小结或替代记录                           |
| 不合规   | 2    | 存在已超过30天的周期缺口                               |
| 不适用   | 16   | 当前冻结住院范围尚未超过30天                           |
| 资料不足 | 6    | 当前批准的出院终点来源缺失，不以其他字段或当前时间补值 |

可判定21例的状态及缺失周期数量与独立SQL排序、LAG和ceil计算一致；SQL参考与执行器while逐周期路径不同。27例均完成保存读取，状态、原因及公开事实保留。5例有7份真实阶段小结，未为制造正例修改文书、时刻或PDF状态。

这证明代码及当前只读材料执行链，不代表人工专家逐份复判、隔离服务部署、HTTP/浏览器或业务库验收。没有PG写入，没有启动模型或恢复历史质控任务。

患者身份、正文、原始时刻、提取脚本和逐例产物仅在`.tmp/0910-full-audit/stage09299-20261026-private/`，Git忽略，不提交。公开文档只保留数量及证据边界。

## 自动化与保护

- 新规则48项聚焦用例覆盖精确边界、长期重复周期、替代与迟到、未知版本、日期精度、来源异常、真实读取SQL的三坐标/白名单/limit+1，以及正式执行与Canonical保存读取。
- 相关较大回归1341项通过、2项API测试因离线启动器不提供client fixture而明确排除。包括原死亡规则、文书执行器、来源、注册目录、连续医疗/交接班、公开事实、Renderer、保存读取保护和27例真实材料。仅既有Pydantic弃用警告。
- 双轴静态复核无确定缺陷：旧四JSON条目逐键一致；去除新增ID及分派后，原执行器与provider AST等价；未改V7.1、前端、迁移、默认选择或历史读取。
- 本轮修改的Python经Ruff、差异经空白检查；提交前编码及凭据门禁另跑。前端无差异，本轮不重复运行前端类型及Vitest；不把前轮前端结果计作本轮验证。

复现：在backend目录经`python scripts/run_pr8_offline_tests.py`显式选择以下文件并加`-m "not api"`：

```text
tests/unit/test_luxian_0609_stage_summary_timeliness.py
tests/unit/test_luxian_0609_death_record_timeliness.py
tests/unit/test_luxian_0609_native_extended_document_execution.py
tests/unit/test_luxian_0609_evidence_snapshot_provider.py
tests/unit/test_luxian_0609_source_evidence_reader.py
tests/unit/test_luxian_0609_rule_master.py
tests/unit/test_luxian_0609_rule_catalog.py
tests/unit/test_luxian_0609_rule_contracts.py
tests/unit/test_luxian_0609_native_package.py
tests/unit/test_luxian_0609_phase_scope.py
tests/unit/test_luxian_0609_continuity_result_mapping.py
tests/unit/test_luxian_0609_continuity_public_boundary.py
tests/unit/test_luxian_0609_physician_handoff.py
tests/unit/test_luxian_0609_customer_renderer.py
tests/unit/test_luxian_0609_read_side_projection_boundary.py
tests/unit/test_luxian_0609_second_precision_timeliness.py
../.tmp/0910-full-audit/stage09299-20261026-private/test_pg_fixture_private.py
```

整批goal继续active：新点5项已有09659、09299两项代码及可用真实材料离线验证；血尿常规、第一术者术前查看及已有映射的逐项核验仍需推进。6例终点字段缺失按病例记录，不把整个阶段小结规则或其余条目一并豁免。
