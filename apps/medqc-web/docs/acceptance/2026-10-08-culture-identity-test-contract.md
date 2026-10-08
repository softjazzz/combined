# 培养身份全文测试协议适配

固定基线 `21f4a93e103a34002a1f9d36f9d895f226c0122f`。本次仅修改 `test_luxian_0609_culture_identified_organism.py` 的一个完整段落 AST literal，将两处旧015身份文字替换为冻结四段协议 `LX0609-06-03-04`；医学正文、输入、响应、参数、其它期待与断言全部不变。仍以 `assert new in prompt` 完整逐字比较原段落，不缩短正文、不改为关键词/regex，也不改变 `old` 历史否定政策文字。

独立原门禁两文件45项为44通过、1旧身份literal失败（2.64秒，exit1），证据保留在 `F:/MedQC-worktrees/review-artifacts/iml-evidence-current/first-run.log` 及 `legacy-oracle-static.json`。现行冻结映射与生产Prompt已使用四段ID；本次不修生产，也不据此推断其它临床输入不截断。

新分支 `codex/qc-fix-culture-identity-test-20261008` 从指定基线建立，旧分支保留，开始前工作树clean。216作者提交经root等价cherry-pick `fad64946e` 集成且在该基线祖先中，三路径blob相同；216本身因cherry-pick非字面祖先，不混淆提交身份。

AST反向还原这一literal后整文件AST完全相同，证明医学习语与其它输入/断言没有变化；新完整literal与当前冻结Prompt AST字符串逐字匹配。机器对照 `.tmp/culture-identity-test/ast-identity-comparison.json` 同时保存原/新全文及hash，不调用Prompt生成器或模型来作静态证明。

同两文件45项严格离线门禁实际收集45，45 passed、1 warning，2.92秒，exit0。原分层统计为10项直接native/binding/reducer保护、33项共享投影、1项parser、1项全文oracle，不能称45项临床语义金标。guard阻env/凭据、私有临床路径、真实DB、网络/HTTP模型与安装后subprocess，socketpair只允许精确stdlib路径。

本次无PG/env/真实病例/真实模型/network，不改其他测试或生产。Python静态与真实Husky编码作为提交门禁；前端无源/package/config变化，按根资源调度复用同源码lint，不重复type-check或前端unit，不声称本轮执行了全量前端。

实际runner/source/test/pytest.ini运行前后hash完全一致，所有加载的app模块均位于本树固定backend，未跳过节点或弱化断言。新日志 `.tmp/culture-identity-test/adapted45.log`、JUnit及manifest另存；原独审44/1文件未修改。AST机器对照及结果hash在同目录保留，生产app零diff。
