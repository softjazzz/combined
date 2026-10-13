# N12最终同ID标记承载补证

固定源码 `e5f225bd40062fb124218af75171f91b2ee680cc`，ledger树保持clean。原375/旧fullID marker测试不变，仅在本目录写有界纯合成补证。

先人工冻结两例原body、原spans、body总长和各span长度，再一次执行实际生产helper→正式privacy wrapper→fake delegate捕获。2例/3份文书均通过，exit0；无长期handle，结束即释放测试槽。首例正文内`SPAN_END d1:s1`与`SPAN_BEGIN d1:s3`分别位于同ID实际span中；第二例同时保留d1尾空格及d2自身s1/s3首尾文本，验证跨文书未混位。逐字主断言使用actual==gold，未放宽includes/regex；marker构造辅助rstrip不替代全文/每span严格相等。

- `same-id-end-and-begin-single-document`：正文字符数d1=36；原正文、原每span、顺序/长度、独立文书边界逐字相等。
- `same-id-two-documents-and-data-trailing-space`：正文字符数d1=37, d2=36；原正文、原每span、顺序/长度、独立文书边界逐字相等。

`results.json`保存正式delegate实际完整prompt、独立按metadata字符长度消费后的每文书/原span和原调用参数。内部同IDEND/BEGIN文本完整保留，不由标记文本提前结束/切换文书，原换行与尾空格完整，body拼接不增加分隔符；metadata与实际原body/span长度完全一致。响应固定合法unknown，helper parser ready仅表示回执合法，不是医学C或真实模型可用性。每例逻辑1/delegate1，真实模型HTTP0；schema/budget仍4096 completion且allow_length_retry=False。

严格guard拒绝.env及.env.*、PG/DB连接、网络/HTTP、真实模型发送和guard安装后子进程，仅精确stdlib asyncio socketpair开放。DATABASE_URL合成空值，不读取真实.env；日志唯一提示数据库未配置。原source/guard/probe/冻结文件before-after SHA一致，未写生产/已冻结tests/分支。

冻结expectations SHA-256 `29ff29ebd377c2b04cccf3f8eac5536000eb8e36f53c699dd82eb27483785240`；probe `5c2e52f41d8a94c5f73ce1e40ab246028dc57a92fbde5690fb5ea939579112d5`；实际capture results `7d2347873272ef148be05f77bc7c11aa52936f39f38ce6125b5f959757c9c608`。详见report.json与integrity.json。

本结论只补这两例最终同ID载体完整性，不外推任意恶意标记/非法metadata的全组合，也不证明真实模型通读、引用或临床语义。未发现这两例的真实承载反例；当前补证不需要生产修改。
