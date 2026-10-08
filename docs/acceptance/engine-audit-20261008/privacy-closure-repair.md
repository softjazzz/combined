# 0609 隐私边界限定修复与剩余缺口

固定起点 `6930540f27e9c279241d35ac05d1c1c6e9134f82`。本轮 PRIV005、004 已提交，PRIV002 已实现并经合成接缝验证，等待协调串行提交和独立复核。既有 `7aa4737fe` 已知身份 gate 保留；归档171项未重跑。本轮不认领正式应用E2E、全部患者身份完整性或临床结果验收。真实模型、网络发送、PG、`.env`、真实患者材料读取均为0。

## 已提交修复与准确钩子历史

- PRIV005：`041b3be67`。0609 scope 内上游HTTP错误只发布固定错误枚举与有效整数HTTP状态，不发布响应正文、任意code、request_id或配置身份。快照构建日志只记固定 `snapshot_build_error`，不含异常message/traceback。非0609错误行为保持兼容。原提交本地 `.husky/_` 缺失，未运行钩子；不能将后续钩子补齐回写为旧提交已通过。
- PRIV004：`6b8fa3e58`。准生产runner显式建立病例scope，execution绑定provider，实际client每attempt在observation/capture/transport前检查。完整三坐标一致且存活的嵌套scope组合provider；任一失效拒发。私有无身份值lease在外层finally关闭，延迟子task不能发送，同病例内层退出不提前关闭外层。标准Husky实际通过：lint-staged无匹配Python任务，encoding检查5个暂存文本通过。

本地钩子按协调授权从既有D树只读复制；D未修改。F树两个node_modules junction只读复用F集成依赖，未安装依赖，未改Git common config。PRIV002的提交/钩子尚未执行，等待主协调串行窗口。

## PRIV002：本次已读身份来源的内存闭合

独立来源审阅固定 `e256e8ea926f0bcb19cb000cd826dd781e157eaf`：worker collect已有完整MedicalRecordFrontpage ORM读取；普通投影已有原patient_name/mr_no/inpat_no，hydrate保留/补姓名，其他证件/联系人字段在投影时丢失。已有无首页registration/admission/discharge锚点同样读取整ORM。独立报告：`F:/MedQC-worktrees/review-artifacts/privacy002-source-design.md`，SHA256 `e59447b460df670553acffce4c0b87715a19f4fc8156d5bb09a67ef85571562f`。

本次只在这些既有读完成后采集实例 `vars` 中已加载字段，不调用可能触发lazy query的getattr，不新增查询、refresh或assembly改动。白名单为 `name,mr_no,inpat_no,id_card_no,insurance_no,contact_number,contact_name,contact_address,contact_telephone,nativeplace,currentaddress,work_unit`。hydrate补充既有record中的patient_name/mr_no/inpat_no。医生、药名、诊断、正文不递归采集。

collector是操作局部slots对象，按完整CaseRef三坐标分桶，固定repr并拒绝序列化；原值不进入record、filters、bundle、API、trace、log或持久化。worker真实单病例wrapper建立强制来源scope，正式既有decorator仅同完整病例继承，execution组合材料provider并将同一组合结果交给wrapper。缓存hit/miss均使用collect来源；任一provider失败、原姓名空或masked、collector关闭、来源错病例或坐标不足均固定拒发。上游worker授权A被loader带到B或缺坐标时，私有失效标记跨正式入口保留，不能靠新bundle声明三坐标恢复；只有独立显式worker合法来源上下文可以重建。

collector在取消/异常finally及自动重试前关闭并清空；并发病例只消费匹配holder，每次实际attempt重读。请求本地映射不是全局缓存。正常同病例隐私处理文本可送达内存transport，130mg、1.5h等临床数值保留。本次仍不覆盖未在现有查询中读出的patient_information专有身份；不声称全部身份闭合，也不以禁用正常模型路径代替修复。

## 合成反例与验证

专属目录：`apps/medqc-web/backend/tests/privacy_closure_20261008/`。测试加载完整纯privacy模块，执行当前源码AST中的runner、execution绑定、repository已有查询/serializer、runtime loader、worker病例wrapper和client实际attempt。业务适配/聚合、Session/Query、cache/assembly以及observation/capture/transport均为内存替身；没有应用启动或config导入。runner的compliant DTO来自聚合替身，不能当作规则验收。

- 004首轮18项：17通过/1失败，父scope退出后延迟child仍触及三个替身各1次；lease修复后绿。同病例provider覆盖红测20项中2失败；组合provider后20通过。
- 002当前聚焦67项全部通过（3.29秒）：005的8项、004的12项、002的47项。新增覆盖12身份字段×缓存hit/miss、正常临床文本、现有查询/公开record合同不变、不同CaseRef同visit、空/遮罩姓名、非序列化、来源异常值、正式既有decorator嵌套、错病例/缺坐标、并发、取消/异常finally、关闭collector和兼容入口绑定检查。
- 002固定旧worker负向对照：读取 `6b8fa3e58` 真实worker wrapper AST，保留当前collector/gate，仅替换来源绑定接缝。姓名/病案号×缓存hit/miss共4项均未抛预期隐私错误，各触及observation/capture/transport1次，现有模拟读事件只有mr/close；复现旧wrapper缺少来源绑定。这是限定接缝对照，不是整个旧应用重放。

命令：`PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest --noconftest -q --tb=short -o showlocals=False backend/tests/privacy_closure_20261008`。红测脚本及旧源码位于本地忽略的 `backend/.tmp/privacy-closure-20261008/`，不纳入产品合同。

PRIV002修改范围：identity/scope/execution、record_repository、custom_qc_workspace_service仅私有回调透传、sichuan_workspace_batch_worker，以及专属测试/报告。assembly、其他引擎、共享旧断言未修改。目标Ruff检查6个修改生产文件及专属测试目录全部通过，git diff --check通过；完整前端检查和归档171项由主协调安排，本轮未运行。

## PRIV003：已定位患者路径，仍未修复

| 脚本 | 实际来源/出口 | 边界 |
|---|---|---|
| run_luxian_0609_consultation_ordinary_shadow_validation.py | ordinary consultation来源→三坐标evidence session→_RecordingClient.generate直达client | 含患者路径，scope/wrapper缺口开放 |
| review_luxian_0609_semantic20.py | case-map三坐标、默认daily/senior/consultation row_loader→两处直接generate | 含患者二次语义复核路径，开放 |
| run_luxian_0609_028_synthetic_golden.py | 固定合成scenario/内存row_reader，但创建实际runtime配置client | 合成输入仍可联网；未运行、未修改 |
| surgery/exam-lab synthetic golden | 仅继承初始审计索引 | 本轮未逐文件复核，不追加安全结论 |

002已读来源的限定实现仍待固定提交独立复核；003和未读专有身份缺口保留。没有授权真实病例外发。
