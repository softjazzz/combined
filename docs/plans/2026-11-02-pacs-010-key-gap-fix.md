# 独立PACS与010缺键保护收口

基线：联合dfdc1d2ed，同步PR26为661135442，业务线d2a94df3b不动。原8项反例稳定复现3失败；检查结构前置直接放行仅含exam_id的报告行，Native将原资料不足变成不合规。

最小边界：独立PACS仍不要求HIS外键。仅在实际提供的有效CT/MRI医嘱中存在缺身份行时，要求检查/报告自身以明确exam_id及唯一精确的检查或报告时刻证明独立范围；否则保留association_failed。报告材料本身缺失仍优先required_field_missing。检查后48小时/24小时、语义判断、输出与保存合同均不改。不得从HIS/提交/修改时间补时，不按名称/最近时间拼关联。

计划：
1. 保留原3项失败不改断言；增加完整PACS带缺键HIS可继续、空壳/冲突/纯日期不可放行、取消/耗材不误触发及正式Native→Binding→Finalizer→Canonical保护。
2. 执行器结构前置补最小失败关闭，不让Renderer或保存层重判；确认它在模型及主冻结读取之前执行。
3. 严格OfflineIsolation，固定应答、合成材料和内存保存验证；运行相关完整检查族和原零模型门，不读.env/业务PG或患者材料。
4. 本地提交修复，在独立同步分支同步同一代码以收口PR26 CI，联合分支另行记录合并前限制；不合并业务线、不部署、不运行病历质控。

## 已实现与验证

执行器新增同ID的独立PACS时刻完整性前置。只有实际有效CT/MRI医嘱存在缺order_id时使用，不恢复HIS/PACS外键强制关系；复用既有parse_authoritative_datetime，分别验证检查/报告角色时刻，不从提交或修改时间补齐，不把纯日期补成零点。空壳、缺身份、未知/无效或角色时间冲突返回association_failed；材料缺失仍保留required_field_missing优先级。

原8项测试原样保留并全部通过。新增12项保护：完整独立PACS带缺键HIS、4类时间/身份不足、3类取消/耗材/无关医嘱排除、仅报告2类边界、正式结果链2类对照。Native→Binding→Aggregator客户结果及Canonical内存SQLite保存读取均核对状态、原因、规则ID、展示事实；两类确定性路径均零模型请求，读写模型冻结被测试显式禁止。

冻结说明：结构前置在_extract_exam_lab_batch和主冻结读取之前执行，缺键不足的010从eligible列表移除，旧主冻结不能跳过本次结构保护；其他完整事件/其他规则未改，无须改Prompt或失效所有检查族冻结。

### 隔离命令与结果

在backend目录运行：

```powershell
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD='1'
$env:PYTHONIOENCODING='utf-8'
@'
import sys
from pathlib import Path
root=Path.cwd();sys.path[:0]=[str(root),str(root/'tests/unit')]
from tests.scheduler_support import OfflineIsolation
with OfflineIsolation():
    import pytest
    names=['test_luxian_0609_independent_pacs_reports.py',
           'test_luxian_0609_010_missing_order_key.py',
           'test_luxian_0609_010_order_key_native.py',
           'test_luxian_0609_native_exam_lab_execution.py',
           'test_exam_result_pair_recovery.py','test_exam_poc_acceptance.py']
    raise SystemExit(pytest.main(['-q','--capture=sys','--tb=short',
        '-p','pytest_asyncio.plugin','-p','no:cacheprovider','-o','addopts=',
        '--confcutdir='+str(root/'tests/unit'),
        *[str(root/'tests/unit'/n) for n in names]]))
'@ | py -3.10 -B -
```

279 passed、1 skipped（私有原报告显式回放入口），1条既有Pydantic弃用警告。网络、.env、真实PG和子进程持续阻断，仅合成材料/固定应答/内存SQLite。相关Ruff及编码检查通过。前端和迁移零修改，沿用父版本已通过的类型/Lint/PG迁移保护，不为本次纯执行器修复重新启动PG。

没有更改规则时限、语义Prompt、医学证据ID、输出状态或保存模型；未运行患者质控。CI是否通过以PR26新Head实际结果为准，本地279不能冒充远端质量门通过。
