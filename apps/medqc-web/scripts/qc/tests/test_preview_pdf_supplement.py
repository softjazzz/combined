"""仅合成材料，验证预览解析及保守比较；不导入应用或连接业务库。"""

import importlib.util
import sys
from pathlib import Path

import pytest

path = Path(__file__).resolve().parents[1] / "preview_pdf_supplement.py"
spec = importlib.util.spec_from_file_location("pdf_preview", path)
preview = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = preview
spec.loader.exec_module(preview)


def lines(*values):
    return [preview.Line(page, text) for page,text in values]


def test_cross_page_content_stays_with_original_heading():
    docs, issues = preview.segment_course(lines(
        (1,"首次病程记录"), (1,"2026-10-01 09:01"), (1,"既往于2025-01-01入院。"),
        (2,"续页正文。"), (2,"2026-10-02 10:03 主治医师查房记录"), (2,"次日查房正文。")))
    assert not issues
    assert len(docs)==2
    assert docs[0]["page_end"]==2
    assert "续页正文" in docs[0]["content"]
    assert docs[0]["record_time"]=="2026-10-01T09:01+08:00"
    assert docs[0]["time_precision"]=="minute"


def test_unknown_heading_is_preserved_as_its_own_document():
    docs,_ = preview.segment_course(lines(
        (1,"2026-10-01 09:01 日常病程记录"), (1,"前一条正文"),
        (1,"2026-10-02 09:01 未知操作记录"), (1,"未知操作正文")))
    assert len(docs)==2
    assert docs[1]["boundary_review_required"]
    assert docs[1]["table"] is None
    assert "未知操作正文" not in docs[0]["content"]


def test_invalid_calendar_time_fails_closed():
    docs,issues=preview.segment_course(lines((1,"2026-02-31 09:01 日常病程记录"),(1,"正文")))
    assert docs[0]["record_time"] is None
    assert docs[0]["boundary_review_required"]
    assert issues[0]["reason"]=="invalid_heading_time"


def test_signature_timestamp_never_becomes_record_timestamp():
    docs,_=preview.segment_course(lines((1,"2026-10-01 09:01 日常病程记录"),
        (1,"正文；签署时间：2026-10-03 09:02")))
    assert len(docs)==1
    assert docs[0]["record_time"]=="2026-10-01T09:01+08:00"


def test_historical_sentence_is_not_document_boundary():
    docs,_=preview.segment_course(lines((1,"2026-10-01 09:01 日常病程记录"),
        (1,"2025-09-01 09:00 曾住院，随后转院治疗。")))
    assert len(docs)==1


@pytest.mark.parametrize("title,table", [
    ("输血记录","bloodtrans_record"), ("输血后评价记录","bloodtrans_assessment_record"),
    ("术后首次病程记录","postsurg_firstcourse_record"),
    ("副主任医师查房记录","senior_course_record"),
])
def test_document_types(title,table):
    assert preview.document_type(title)==table


def test_exact_duplicate_and_dose_difference_are_not_equivalent():
    content="每日临床观察项目"*15+"剂量1.5g。"
    doc=dict(table="daily_course_record",content=content,record_time="2026-10-01T09:01+08:00")
    row=dict(_table="daily_course_record",record_content=content,document_id="synthetic-1")
    assert preview.comparison(doc,[row])["action"]=="duplicate"
    changed=dict(doc,content=content.replace("1.5g","15g"))
    assert preview.comparison(changed,[row])["action"]!="duplicate"


def test_only_same_signature_does_not_match_documents():
    doc=dict(table="daily_course_record",content="甲病历正文"*30+"医师签名：合成医生",record_time="2026-10-01T09:01+08:00")
    row=dict(_table="daily_course_record",record_content="乙病历正文"*30+"医师签名：合成医生",document_id="synthetic-2")
    assert not preview.comparison(doc,[row])["matches"]


def test_time_alone_only_creates_review_candidate():
    doc=dict(table="daily_course_record",content="全新内容"*30,record_time="2026-10-01T09:01+08:00")
    row=dict(_table="daily_course_record",record_content="完全不同"*30,record_time="2026-10-01 09:01:56+08:00",document_id="synthetic-3")
    assert preview.comparison(doc,[row])["action"]=="review"


def test_json_metadata_never_becomes_clinical_content():
    assert preview.originals({'record_time':'2026-10-01','x':[{'original_text':'原始临床正文'}]})==['原始临床正文']


def test_no_heading_keeps_source_for_review():
    docs,issues=preview.segment_course(lines((1,"只有临床正文，没有可靠标题时间。")))
    assert not docs
    assert issues==[{'reason':'no_reliable_document_boundaries'}]


def test_missing_record_time_is_not_implicitly_filled_from_other_timestamps():
    doc=dict(table="discharge_record",content="出院内容"*30,record_time=None,
             submit_datetime="2026-10-03T10:01+08:00",sign_time="2026-10-04T11:01+08:00")
    assert preview.comparison(doc,[])["reason"]=="record_time_unavailable"
    assert doc["record_time"] is None


def test_repeated_identity_header_is_removed_but_heading_and_body_remain():
    class Page:
        number = 1
        rect = type("Rect", (), {"height": 800})()

        def get_text(self, *_args, **_kwargs):
            return {"blocks": [{"lines": [
                {"bbox": (0,30,100,45), "spans": [{"text":"某医院病程记录"}]},
                {"bbox": (0,85,100,99), "spans": [{"text":"姓名：合成人员"}]},
                {"bbox": (110,85,220,99), "spans": [{"text":"住院号：SYNTHETIC"}]},
                {"bbox": (0,106,220,116), "spans": [{"text":"2026-10-01 09:01 日常病程记录"}]},
                {"bbox": (0,135,220,150), "spans": [{"text":"需要完整保留的临床正文"}]},
                {"bbox": (0,775,100,789), "spans": [{"text":"第2页"}]},
            ]}]}

    result=preview.read_page_lines(Page())
    assert len(result)==2
    assert result[0].text.startswith("2026-10-01")
    assert result[1].text=="需要完整保留的临床正文"


def test_single_header_label_does_not_erase_top_of_page_content():
    class Page:
        number=0
        rect=type("Rect", (), {"height":800})()

        def get_text(self,*_args,**_kwargs):
            return {"blocks":[{"lines":[
                {"bbox":(0,30,200,50),"spans":[{"text":"重要的顶部正文"}]},
                {"bbox":(0,70,200,90),"spans":[{"text":"科室：合成科"}]},
            ]}]}

    assert len(preview.read_page_lines(Page()))==2


def test_terminal_document_reads_only_explicit_record_time_label():
    result=preview.explicit_record_time(lines(
        (1,"入院时间：2026-10-01 08:00"),
        (1,"签署时间：2026-10-10 12:00"),
        (2,"记录时间：2026-10-09 09:23:12")))
    assert result["value"]=="2026-10-09T09:23:12+08:00"
    assert result["evidence"][0]["page"]==2


def test_terminal_record_time_conflict_fails_closed():
    result=preview.explicit_record_time(lines(
        (1,"记录时间：2026-10-01 08:00"),(2,"记录时间：2026-10-02 08:00")))
    assert result["conflict"]
    assert result["value"] is None


def test_terminal_chinese_record_time_is_distinct_from_discharge_time():
    result=preview.explicit_record_time(lines(
        (1,"出院时间：2026年10月11日 08:27"),(2,"记录时间：2026年10月11日 22:37")))
    assert result["value"]=="2026-10-11T22:37+08:00"


def test_parenthesized_page_footer_is_removed_only_in_footer_area():
    class Page:
        number = 0
        rect = type("Rect", (), {"height": 842})()

        def get_text(self, *_args, **_kwargs):
            return {"blocks": [{"lines": [
                {"bbox": (0,200,100,215), "spans": [{"text":"第(6)页"}]},
                {"bbox": (0,802,100,812), "spans": [{"text":"第(6)页"}]},
            ]}]}

    assert [line.text for line in preview.read_page_lines(Page())] == ["第(6)页"]
