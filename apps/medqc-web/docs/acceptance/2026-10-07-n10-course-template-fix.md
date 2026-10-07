# N-10 纯标题与签名模板正文修复

代码起点1f9f7f703；当前HEAD81f17237a只增加Claude复验文档。

只修改extended_document/discharge_course.py::\_has_course_body：除了原纯签名行，再排除完整独立文书标题行（如查房记录、主任医师查房记录、病程记录，可有末尾冒号）。同一行完整标题后接纯签名、术后首次病程记录也按空模板处理。不按字数判断内容，不评价临床充分性，不删除标题后真实正文。

新测试test_n10_course_template_body.py：2规则×3空模板原6失败、2规则×4正常短正文原8通过；首轮修复后14通过。独立复核追加同一行标题+签名、术后首次标题6项，先6失败14通过；补修后20通过。加原文书边界27项，47通过。
主协调另直接运行Claude原rounds065-067-private.py，14个对照按冻结预期：RC7c/7d/9b为required_field_missing；短正文/正文加签名/“医生签名:继续观察。”保留合规；原无时间保持authoritative_time_missing，迟到查房保持不合规。

无模型调用，无客户PG写入，无服务重启。测试既有conftest初始化本地demo SQLite。合成工程回归，不是临床验收，未知自由模板未穷尽。
