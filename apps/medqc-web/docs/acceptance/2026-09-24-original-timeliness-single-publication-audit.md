# 原始时效族：单次发布重复投影审计

主协调只读检查与内存探针，基线 `4dea8dd88`。未修改生产代码、访问业务数据库或调用模型。

## 已复现

运行现有 `test_luxian_0609_basic_timeliness_architecture_freeze.py::test_basic_timeliness_family_canonical_behavior_is_frozen_without_sha_assertions`，仅包裹真实 `validate_luxian_0609_executor_customer_display_facts` 计数，不替换它的实现。该测试经过冻结证据会话、真实 native 执行器、绑定/归约和聚合发布。

原始001、002、005、006（四段编号分别为 `LX0609-01-01-01`、`LX0609-01-02-01`、`LX0609-02-01-01`、`LX0609-02-01-02`）每条均调用两次内部事实投影。原始004在此材料中无抢救事件、无相应事实，不能据此证明其非空分支调用次数。

`canonical_result_finalizer.py::finalize_luxian_0609_reduced_customer_result` 先取得 `safe_facts` 并渲染，再调用 `finalize_luxian_0609_executor_customer_display_facts`；后者仅在收到 `_validated_facts` 时复用，否则重新投影。当前复用白名单是两条新增规则，原始时效族没有进入。

## 替代方案技术探针

在同一测试第二次运行中，仅在内存包装器里把第一次实际投影的返回值传入既有 `_validated_facts` 参数，保持其余执行路径不变。四条规则调用次数各从2降到1，五条完整输出（状态、原因、文案、公开事实和证据等）逐字段相等；原测试全部断言也通过。

此证据说明原始时效族正常分支可以复用已有结果，不需要新增发布框架。尚未证明无事实、损坏事实、抢救非空事件及所有异常分支等价，也不能据此扩展到全规则。

## 下一小闭环

先完成已在独立工作树进行的原始001公开读取校验修复，再在固定基线上补原始001/004的正常、异常及缺事实回归，证明只投影一次仍保持失败关闭。沿用既有发布参数，删除对应第二次解释；不改变 native 医学判断、Prompt、调用模型与并发设置。与读取修复分开提交，主协调独立验收。
