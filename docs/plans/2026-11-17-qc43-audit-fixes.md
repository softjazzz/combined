# 43项质控审查：集中修复

固定基线：9872cdca0。独立分支：codex/qc43-audit-fixes-20261117。
仅合成材料、隔离函数测试；不连接业务库、不读取历史患者材料、不调用模型、不执行质控任务、不改配置、不合并部署。
保留无首页、身份来源、严格引用、不可重试、暂停项及历史结果/快照。

## Task 1: 共享抽取错误合同与肿瘤计划否定保护

负责GPT F8、F9及F3。以原审查报告为依据，先复现再修复。
所有权：native_exam_lab_execution.py、exam_lab_result_mapping.py、pathology_documentation_extraction.py、native_tumor_pathology_execution.py、chemotherapy_administration_facts.py、extended_document/antimicrobial_order_reason.py、consultation_disposition_record.py、course_body_fact_extraction.py，及直接必要的安全错误公共辅助与独立测试。
不得编辑native_extended_document_execution.py；需要其映射接续时交给主代理。不得重构规则判断或放松引用。
固定安全错误类别及显式retryable=false穿过抽取、判定、结果投影到补跑计划；保留隐私与预算拒绝。正常语义无法判断与传输/格式/程序错误区分。肿瘤随访计划排除明确否定、单纯既往事实。
用合成异常和固定响应覆盖404/程序错误不可重试、瞬时故障有界重试、隐私错误、合法未知语义，及计划否定/历史/阳性。仅相关测试。

## Task 2: 确定性边界与供给合同

主代理负责其他文件。修复F1重叠医嘱、F2转科科室、F4自动出院否定/空正文、F5出院处方整组漏写、F6取消/拟换医师、F7正文未供给、F10无关病程依赖。
Claude新增：死亡中文时间、查房角色不明被迟到记录掩盖；先复现多台手术遗漏、首页来源污染和缺失准入保护，再修明确缺陷。纠正执行方式元数据但不改变医学阈值。
争议单列：稳定期/整例门控、相似度阈值与最终判定、存在性成熟窗口，未经确认不改。

## Task 3: 固定提交集中复审

汇总实际命中的反例及定向保护，检查diff/编码，本地提交后独立复审。发现只修对应问题，复跑命中集合。不以通过数量冒充医学效果验收。
