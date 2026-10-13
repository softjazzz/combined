# 手术族 freeze 的 MR 输入合同纠正

本次仅纠正测试夹具和目录集合期待，生产仍固定于 `62cbbc240e6a072795220ef3cd91dd49b230eb19`（与集成 `fac4ef67c` 相关源码相同）。不改手术事件事实合同、SQL读取、关联算法、模型权限或医学标准。

## 因果与历史红证据

旧 freeze 将 surgery_record 的 `_surgery()` 行直接放入 mr_surgery：有 `surgery_begin_time/end_time` aware datetime，没有 MR 权威 `surgery_begin_datetime/end_datetime` naive datetime。MR 行有传统手术等级却缺可信时间，现行关联器必须保留额外事件未知，返回 data_gap/association_failed。该 MR 来源合同早于本轮；不能扩大生产别名或忽略未知行来恢复旧 C。

授权纠正前严格短对照实际 6 项：原 freeze029 精确节点保持原输入及 C/reason 期待，真实红 1 项；正确 MR schema、未知 MR、同名不同事件和 unavailable/truncated 来源保护 5 项通过，3.02 秒，退出 1。原 C 红文件、原逐值输入及未跑冻结预期保持在 `F:/MedQC-worktrees/review-artifacts/surgery-029-preparation/`，未覆写。

## 最小测试变更

- 新 `_mr_surgery` 将原 UTC 08:00/09:00 表达成医院 Asia/Shanghai naive 16:00/17:00，仍是同一绝对时刻；补稳定 surgery_id，不动原正文、术式、术者、等级、麻醉方式或文书ID。仅029这一处 MR 夹具调用改用该来源 helper；另外五处保留原输入，正式 surgery_record helper 不变。
- 旧 freeze 的状态、reason、facts、fact refs 精确坐标、evidence、findings 等医学期待全部保持。新专属测试明确断言转换前后绝对时刻相等，防止任改临床时间改善答案。
- 族集合仅显式追加既有 031/032（04-01-04/05）字面值；目录漂移与 029 医学因果分开，不从生产集合生成期待。
- 新专属六项保护保留旧错误来源字段形状作为明确 gap；同时保护 qualified MR 缺权威时间、同名两台不能共享一份小结、来源 unavailable/truncated。没有将旧错误形状的历史 C 红隐藏成新生产绿。

AST 对照在仅归一 MR helper 调用名之后，所有原 freeze 函数（仅排除显式族目录 tuple）完全相同，参数化输入的医学内容和所有原断言不变。实际完整旧 freeze 门禁须验证全部 facts/坐标，而非仅状态通过。

## 验收范围

严格 guard 完整运行原 348 项（六受影响文件不筛选）加新六项，共 354；缩窄后实际354 passed、1 warning、5.31秒、exit0，完整freeze10全通过。runner 拒绝 `.env` 和 `.env.*`、DNS、外部 socket 与真实数据库连接，仅 exact stdlib socketpair 路径豁免。无真实模型、PG、病例；本轮是测试协议纠正，不能据此关闭 029/030 多医嘱归属语义。

Python Ruff、diff check、静态保护及真实 Husky 编码作为提交门禁。前端无源码/package/config改动，按根资源调度复用此前 N12 同源码 lint 证据，不重复全量前端/type-check/unit。提交前由独审核 diff；不绕过钩子。

首次完整354门禁曾对六处MR夹具一起纠正，实际351通过、3失败（1 warning，5.62秒，exit1）。029所有原医学/公开facts/refs/evidence断言、目录集合与新六项保护通过；035/036/037因材料内容哈希改变而让同一解码坐标换序，停在原tuple顺序比较。该次超本业务点的夹具调整不是产品代码回退，也未证明这三条完整医学保护通过。按根裁定仅保留029一处纠正，其余五处恢复原输入，原坐标期待及比较器原样不动；该失败日志 strict-354.txt 保留，待同354复跑结果另记。

最终仅029改MR调用的同354重跑：354 passed、1 warning，5.31秒，exit0。完整freeze10原状态/reason/facts/严格坐标tuple/evidence/findings断言均实际到达并通过；新增六项保护通过。`strict-354-retry.txt` 与退出文件保留，首次351/3日志未覆盖。没有把未知MR反例改为合规，也没有生产修改。
