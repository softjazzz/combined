# 2026-10-07 文书质量016两项最小修复

基线 `57b863d2b328b2d93b004ffb6e49da55be76d804`。仅处理[审计报告](2026-10-07-round2-document-quality-audit.md) DQ-01、DQ-02，不扩展017、018、074、077。未提交、推送、重启，无真实模型或工程模型替身调用，无客户PG读写。

## 修改

- `backend/app/services/luxian_0609/course_quality/rules_016_017.py`：016使用专属比较归一化，保留临床日期、时间、大小写、小数点、斜线、阳阴性和其他医学符号；只忽略空白、普通逗号及分号/中文句号。两个数字之间的逗号保留，避免删除数值分隔符。017原有相似度归一化不变。
- `backend/app/services/luxian_0609/course_quality_result_mapping.py`：仅允许016的`data_gap / required_field_missing`以缺省或空比较facts通过发布合同。未伪造相似度，未修改状态/原因或判定所有权；确定性结论、未知原因、非空残缺facts仍拒绝。
- 独立新增 `backend/tests/integration/test_round2_016_copy_boundaries.py`，不改并发代理测试或共享renderer。

## 红绿反馈

命令：`python -m pytest backend/tests/integration/test_round2_016_copy_boundaries.py -q --tb=short --disable-warnings`。

修复前14项中7失败、7通过：4项临床日期/小数/阳阴性/数值分隔符差异误报；3项空字符串/纯空白/null病例特点在实际`CanonicalResultStore.replace_for_job`调用被合同拒绝。相同、仅句读差异、外围换行空白3项正常对照及4项非法合同保护通过。

修复后14项全部通过。每个临床/排版/空字段用例从正式snapshot/materials进入原生执行器、决策绑定/reducer和正式聚合，然后创建隔离内存SQLite表，调用CanonicalResultStore保存、commit，再开新Session正式load_selected回读。保存前后状态与原因保持一致；空字段保留data_gap与missing_fields，不生成复制比较事实。该验证比原审计的“动态校验器+保存源码定位”更进一步，已真实走通隔离存取；不等同客户PG任务更新。

兼容保护命令：`python -m pytest backend/tests/unit/test_luxian_0609_native_course_quality_execution.py -k "016 or copy" -q --tb=short --disable-warnings`，24通过、200未选。两项变更和新测试的Ruff通过，生产diff检查通过。未运行全量测试。

原始审计8例另存重放结果 `.tmp/0910-full-audit/round2-document-quality-private/results-after-fix-private.json`：三项医学差异改为不完全相同，空字段data_gap校验通过；原两份0910源副本及相同/句读对照均保持原结论。原始冻结预期与修复前结果保留。患者材料不进入本记录。

## 合同兼容与限制

修复只收窄016“完全相同”的比较，并补足已知资料不足终态的保存合法性，不改变规则允许状态、发布DTO或数据表。016旧兼容入口和typed入口共用目标段落比较，因此同步修正；017比较函数不变。模型调用与Token没有增加。

纯排版保护限于已明确保留的空白和普通句读；未知符号不做激进去除，避免继续抹掉医学差异。不声称所有排版等价形式或其他四规则已完成临床验证。需要上线时另按发布流程处理，本轮未进行发布。
