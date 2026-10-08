# N10 只读准备结论

固定读取根 aa7a98c7e43bc23439db485fa56cd90ea6da4bd1。报告期根推进，但 helper/native/reader 三 SHA256 未变，见 evidence-index.json。未测试、导入生产、执行 Git/Node、读 .env/私有病例、调用 PG/模型；仅写本目录。

**明确残留：** 历史独立 round6 报告第 70–76 行观察两规则把“2026-07-02 09:00 主任医师查房记录”加签名、“张三主任医师查房记录”判 compliant。当前 _has_course_body 仍只整行匹配固定标题/签名，额外前缀仍进入正文。继承旧补丁排除纯标题/纯签名的 20 项历史保护；不冒称本轮重跑或真实患者误判。

**结构闭环未确认：** reader 白名单确有 document_title、权威时间、author_name/title（253–279），SQL 仅取实际存在列（1569–1583）。公共历史报告没有完整原冻结 row，不能证明原例具备精确独立 title/time/author。不得从正文造元数据或给原例补 author 后称关闭。只有已有脱敏工件证实独立字段且整行无其他文字，才可零调用排除元数据标题行；缺字段的原姓名例需要语义合同，不能补日期/姓名/前缀关键词。

**实际消费点：** discharge_course.py:13 helper；native_extended_document_execution.py:3864/3886（065 无时/术后72小时行）；discharge_course.py:98 与 native:4163（067 出院日及前一日）。064/066/068 不直接共用此 helper，列同族保护。保持事件、成熟度、死亡、时间、来源与引用映射；一份有效正文存在，不被另一份未知遮挡。明确空壳沿用 data_gap/required_field_missing，不改成漏写文书。

**最小下一步：** 原元数据证据未齐，不安排宣称关闭 N10 的结构补丁。若无法补齐合法脱敏证据，先批准两个 program_only/max0 合同改变，再用独占小 course_body_fact_extraction.py 返回正文 present/absent/unknown 和同文书坐标；复用已有 span/三态/引用校验，不建新框架。模型不判事件、时间或结论。新专属测试/doc 可独占；helper/native 两片段、两条合同/Prompt及窄客户文案须 root 分配现有 owner。

原两空壳/短真实正文口径已冻结，无需重新发明业务标准。新歧义自由文本才需业务口径；未知保留资料不足。保护旧空壳、短正文、标题后真实内容、多事件72小时、出院窗口、有效正文+未知、来源上限和全部 refs。人工 facts 不证明真实模型语义，正常0→1调用须披露。

minimal-candidates.json 是四个公共重建候选，非完整原冻结夹具、未执行。运行前须证明进入正文分支，不能靠错误时间载体引发早期 gap 假通过。当前 N10 保持开放。
