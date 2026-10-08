# 029 MR夹具字段合同独立静态复核

固定ledger `62cbbc240e6a072795220ef3cd91dd49b230eb19` 与 root `fac4ef67c0f68da1625f419ea5dddb47f38aa78b`。独立比较四个git blob，与准备包hash一致。没有运行测试、读取PG/.env/模型/病例，也没有改生产或共享测试。

**可以将029原正常夹具的问题作为单独test-only来源schema纠正；这份原输入不足以证明本次生产回归。** 原MR复用了正式手术记录的 `surgery_begin_time/end_time` 与aware datetime，既不是MR SQL批准字段，也不是MR权威时间类型。原医学C与全部证据断言应保留；原非法行另作负向保护，原C红证据不可覆盖。

## 具体证据

1. MR源白名单在 `source_evidence_reader.py:208-224` 只有 `surgery_begin_datetime/end_datetime`；SQL reader `:1569-1585` 依白名单投影并要求 `surgical_level` 与 `begin_datetime`。typed测试自定义reader保留旧别名并不代表生产SQL批准它。
2. MR ORM `database/models/cdm.py:254-277` 定义 `DateTime`（没有timezone=True）；`trusted_performed_surgery_times :983-998` 仅接收naive datetime。该限定在 `92ee14e3897`（2026-07-17）已存在。
3. 正式记录严格aware时间先转医院Asia/Shanghai后去tz，见 `source_evidence_reader.py:948-975`。原UTC08/09对应MR医院naive16/17，绝对时刻不改变。不能仅去tz写成MR08/09，那会改变时刻。
4. 三级MR已属qualified候选，但无可信MR时间、无同surgery_id可信副本，则 `surgery_event_association.py:264-299` 保持association_failed。该保护来自 `f6f91778ae9`（2026-09-13），不是62新增。不能忽略未知MR来宣称全病例只有一台手术。
5. 正式记录和MR关联按同码或完整名称及严格实际时间双射，`surgery_event_association.py:779-837`；不比较两来源物理主键。新增MR surgery_id须是MR自己的稳定键，不能伪造与正式记录同键。

准备包既有6项短检查记录为5通过、原正常C节点1红。正确MR形状同绝对时刻案例C，缺权威时间/同名多事件/来源失败/截断四项gap符合保护。此独审只读取该日志，没有新跑，不能算独立绿测。

## 推荐的test-only改动边界

仅为原MR行构造正确来源字段：保留 `document_id=mr-surgery-1`，补本来源 `surgery_id=mr-surgery-1`，将原aware begin/end分别转Asia/Shanghai后去tz，使用MR `*_datetime` 字段。正式记录、手术名、三级资格、普通正文“拟行腹腔镜阑尾切除术”、原C/requirement_satisfied、display_facts、fact_ref_coordinates、evidence、findings断言全部原样。

原错误字段输入及其原C红日志保留在准备包；另新增以原非法MR字段为输入的 `data_gap/association_failed` 来源负向保护。不得把原C期望改gap抹除历史，或修改生产接受别名、跳过qualified未知行、添加正文标签换绿。

**尚未关闭的证据缺口：** 正确MR短对照只断言状态、原因和调用量，没有断言原完整冻结的公开facts及全部坐标。之后经root授权领取测试槽的owner须跑纠正后的原完整节点和新增负向保护，成功后才可宣布测试合同收口；本轮不代跑。

## family tuple独立目录漂移

生产族现有9项，旧静态expected仅7项；缺少的明确字面值为 `LX0609-04-01-04`（原031）、`LX0609-04-01-05`（原032）。native族常量:53-63与当前规则总表均已存在，active/customer_confirmed，分别有SC-081/SC-085来源证明。可在独立test-only变更中显式追加这两个字面值，保留原七项顺序及Aggregator无重判断言；不得动态从生产常量构造expected，也不得移除目录失败。

029多医嘱覆盖、030事件关联与真实患者来源覆盖仍是独立事项，这次夹具schema纠正不能自动关闭。详细hash、字段证据与允许/禁止边界见 `review.json`。

## 最终单点test-only WIP复核

根审收缩后的最终diff仅029一处MRhelper，另外五处原输入恢复；独立全文件AST归一对照证明全部原医学及证据/坐标断言原样，生产0diff。族tuple仅追加两个固定字面值，新六项来源保护保留。静态可提交，等待作者最终354及真实hook；六处版本351/3日志保留。详细WIP hashes见 `final-test-only-static-review.json`，没有新增独审测试。

最终更新：root确认最小diff作者严格354/354通过（1 warning，5.31秒），原029完整facts/refs/evidence已验证。三paths静态接受无阻断，可以真实hook提交；独审测试仍0，初次351/3证据保留。
