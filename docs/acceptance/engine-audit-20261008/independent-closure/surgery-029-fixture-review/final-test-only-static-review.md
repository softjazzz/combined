# 029 最小test-only最终diff静态复核

基线 `62cbbc240e6a072795220ef3cd91dd49b230eb19`。仅旧freeze测试、新MR合同测试及脱敏文档三文件；生产0diff。独审没有运行测试、PG/.env/模型或修改代码。

**静态结论：此最小diff可提交，须作者最终354有效门禁及真实提交hook通过。** 仅029正常节点使用MRhelper，其余五处原MR输入已恢复。新增helper将原UTC08/09按Asia/Shanghai变为naive16/17，保留原绝对时刻、文书ID与医学内容；补本MR来源稳定surgery_id。正式手术行与普通小结正文原样。

独立AST静态对照：仅移除新增ZoneInfo import/helper、将唯一新增MR调用归一回原_surgery，并移除显式族tuple尾部04-01-04/05后，整个旧测试文件AST与62原blob完全相同。因此所有原参数化医学预期、公开facts、精确fact_ref_coordinates、evidence、findings、调用量断言，以及坐标tuple比较器均未改；另外五处输入逐值恢复。没有修改hash排序或放宽坐标顺序来求绿。

族tuple保持原七字面值/顺序，并明确追加04-01-04/05（031/032）；Aggregator所有者断言保留，不动态取生产expected。新增六项保护实际为一项正确schema正例和五项负例：原错误MR字段、qualified缺权威时间、同名两台共享一份小结、unavailable、truncated；负例必须保持gap，真实模型调用禁止。

六处版本的354执行351/3失败记录保留：029医学与公开证据、族tuple、新六项已绿，但035/036/037解码坐标tuple因材料hash变化换序失败。最终diff恢复非029五处输入，继续原tuple比较/原期待；不能把此前351/3当全量通过。作者授权复跑结束后另记录结果，不与独审静态检查混为独立绿测。

本复核WIP三文件hash及AST证据保存在 `final-test-only-static-review.json`；本次判断不自动关闭029/030多医嘱归属问题或真实病例覆盖。

旧DD001..007、028..031只有原case冻结与结果文件，无现成逐source执行SHA manifest。其原冻结SHA为8dc0233355036eea8d585d6055572971666fa6f8847bb4b80004494c92e4d289；不能以会话初始7b894dc HEAD或后来58e29manifest倒补历史精确运行绑定。没有重新查患者或编造历史SHA。

## 最终接受

根协调回报最终严格354全通过（1 warning，5.31秒），原029完整医学事实与证据断言通过；首次351/3日志保留。复核三批准路径静态接受，无阻断，可安排作者真实hook提交。MR改动仍仅1处，其他五处原输入、全部原断言和生产0diff结论不变。当前test文件hash与此前静态审查相同；文档hash按最终状态记录。作者门禁不冒称独审执行，本审查测试次数仍0。
