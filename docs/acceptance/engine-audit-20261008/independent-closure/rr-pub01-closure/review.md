# RR-PUB01 固定提交独立复核

固定候选为 `bb3d0b5c3762ea7a0c8aa0580af8ec666794347b`，父提交 `58e29ffe9edc559bee552c734dc66ebed9ebf32c`。生产差分恰为Finalizer通用fallback的两行 identity sentinel 回退；另有新专属测试和设计说明共三路径。原unknown/known测试未修改，Store、Renderer、目录、规则状态与医学合同未修改。

结论：固定候选在本次公开sentinel、已知事实合同及隔离SQLite Store消费边界内独立37/37通过，无可确认新增缺陷，支持RR-PUB01限定工程闭环和集成。正式工作端点、真实历史库与部署未运行，不能据此宣称通过。只写本artifact目录；不改生产/共享测试、不访问`.env`、PG、真实病例或模型。

## 合同检查

公开 `validate_luxian_0609_published_customer_display_facts` 与执行器validator原联合返回类型已经包含NotImplemented。未知规则的字典在执行器fallback返回sentinel，父提交公开入口继续调用.get导致AttributeError。固定提交在既有None失败门禁前 `if validated is NotImplemented: return NotImplemented`，保留同一sentinel，不转换为raw/空字典，也不吞掉已知合同错误。

未知规范化LX ID的None/非dict保持None；空dict与非空dict应返回同一NotImplemented并不修改输入。已知时限、抗菌药、死亡诊断scope_conflict事实应保持原样，非法必需字段和矛盾状态继续拒绝。规则族白名单语义分别保留，不能泛称所有额外字段都抛错。

`qc_workspace.canonical_result_store.safe_customer_display_facts` 只在共享公开validator返回dict时复制公开facts，否则返回{}。因此未知LX原始/private facts不能沿这个客户事实出口透传。`validated_customer_explanation` 对未知LX non_compliant且没有可审计事实/failed criterion继续ValueError，正常replace_for_job仍受登记规则/状态合同拒绝未知LX。`load_selected` 调用共享公开validator检验历史Envelope，不就地清除内部decision_facts；客户出口另调用safe facts/projection。不能要求非LX内部Envelope的原文接受LX专属过滤。

## 冻结探针与方法边界

`expectations.json` 在执行前冻结反例和合同，candidate SHA在固定提交产生后绑定。最终 `probe.py` 从git-show固定完整public app源码快照加载真实Finalizer/Store、规则族合同及其依赖；仅抑制包初始化，没有替换validator、renderer、enrichment、material或settings模块实现。按root既有离线runner关闭dotenv、阻断PG驱动和socket，并把该子进程环境清空后仅设置合成值，因此不消费主机部署凭据。实际SQLAlchemy仅使用新建、task-local合成SQLite，实际Store保存/回读采用新Engine与新Store实例。workspace仅提取真实表工厂，schema显式为None；不导入应用门面或运行工作端点。父Finalizer完整固定模块另加载用于复现unknown AttributeError及known兼容。

首轮进程约1.23秒，以ModuleNotFoundError退出：未用到的evidence-enrichment导入链触到bundle assembly的app.database。固定快照有意未导出数据库配置，此处停止且没有访问PG/环境。未改变冻结反例、生产源码或合同函数。失败记录见 `harness-first-failure.txt`，槽释放已回报。

后续约0.733秒的表工厂加载因probe namespace遗漏真实 `@lru_cache` 而停止，补标准库lru_cache后约0.706秒执行进入公开validator，但consultation模块还需未使用的 `project_selected_grouped_document_refs` 导出；均已作为拒绝入口补齐，仅属probe fixture。记录分别保留 `harness-second-failure.txt` / `harness-third-failure.txt`，未把导入失败当产品缺陷或完成合同观测。

第四轮约0.865秒在exam_lab→CT→source_reader间接数据库导入处再次停止，记录 `harness-fourth-failure.txt`。root要求不继续扩假导入，于是最终撤掉全部上述依赖替身，改用完整固定真实模块与其既有离线启动阻断方式。前四轮仅属支撑/夹具失败，没有输出完成的37项结果；它们不是产品缺陷，也未计通过。

最终获独占槽执行 `python -B F:/MedQC-worktrees/review-artifacts/rr-pub01-closure/probe.py`，进程约1.452秒，37 passed / 0 failed，主逻辑约0.139秒。完成后立即释放。冻结期望SHA256 `645f3270588c4a96ec4195c7cdf8ecf88bd60f17c98ea86a91b69b933062a6e2`；期望未因fixture失败而调整。最终逐项结果与task-local SQLite路径见 `results.json`，实际正常保存仍拒绝unknown LX，内部history raw保留和客户safe facts空分开断言。

实际37项观测覆盖未知ID规范化×None/dict/非dict、Store未知事实空投影、不合规解释与身份冲突拒绝、三类known保持/非法/矛盾状态、抗菌药额外字段原白名单过滤、pending_definition空事实策略、父提交反例、未知LX正常保存拒绝、三类known新实例回读，以及直接构造合成历史未知LX行的内部raw保留/客户safe facts为空。父提交的两个unknown字典仍出现AttributeError；三类known在父/候选均保持相同facts。

该验证是固定模块方法与隔离SQLite消费，不是完整应用API/正式任务/真实历史库/客户安装或部署门禁。历史未知行直接在新SQLite中构造，不能解释为正常保存放宽或真实数据迁移通过。完整客户API投影函数的执行在owner专属测试中，本独立probe明确只执行Store的共享客户facts出口；app门面投影源码已静态核查。

## 开发证据和此前夹具假设错误

owner给出最终固定红30项（10个NotImplemented.get AttributeError、20通过）→321聚焦绿，含新29专属用例。作为开发证据记录，不冒充本次独立结果。此前夹具错误分别为：抗菌药既有白名单允许过滤额外字段，应以非法必需字段验证拒绝；SQLite正常保存必须完整提供result_status/is_compliant；非LX内部Envelope不归LX客户合同过滤；公开空facts字段可省略，不必须输出空键。owner最终红在撤去两行后重新跑过、恢复两行后绿，原旧测试保持。上述错误不列为产品缺陷。

## 产物

`expectations.json`、`probe.py`、`results.json`、`source-hashes.json`、`source/`固定public源码快照、`baseline_finalizer.fixed.py`、`workspace.fixed.py`、4份harness失败记录及唯一合成SQLite。无生产编辑、pytest、PG、`.env`读取、真实病例/模型或外发。

`source-hashes.json`逐字节核对5个关键Finalizer/Store/family文件均与固定git-show一致。Finalizer blob `2b0ee67861e072ab932b42d9eaea290254c2499e`，SHA256 `e7e73f283d2dc9313b41dbe48d8e659ff85c190c05eb3cdc40bfa3148e51eb43`；Store blob `4c217f88909954006d13f0dbaa5310f02fa623b0`，SHA256 `67d80d42efdd4c0010684017932d49c86856f5c2950d83af4f1eb5516b2bdf4a`。源码基线未混读owner后续未提交修改。

可确认findings/defects/blockers为空；独立通过只归本次限定合同与隔离SQLite消费。最终集成SHA聚焦回归由root串行执行，正式端点与客户部署门禁继续保留。
