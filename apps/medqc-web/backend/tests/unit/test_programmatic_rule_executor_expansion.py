import pytest

from app.services.programmatic_rule_executor import (
    PROGRAMMATIC_RULE_SPECS,
    ProgrammaticRuleExecutor,
)


def test_programmatic_rule_specs_should_expand_to_20_plus():
    # P1 目标：程序化规则从 10 条扩展到 20~30 条高价值规则
    assert len(PROGRAMMATIC_RULE_SPECS) >= 20
    assert "SC-022" in PROGRAMMATIC_RULE_SPECS
    assert "SC-048" in PROGRAMMATIC_RULE_SPECS
    assert "SC-049" in PROGRAMMATIC_RULE_SPECS
    assert "SC-096" in PROGRAMMATIC_RULE_SPECS
    assert "LXE-18" in PROGRAMMATIC_RULE_SPECS
    assert "LXE-35" in PROGRAMMATIC_RULE_SPECS
    assert "LX-026" in PROGRAMMATIC_RULE_SPECS


def test_sc104_exists_all_should_fail_when_missing_any_required_record():
    executor = ProgrammaticRuleExecutor()
    result = executor.evaluate(
        rule={"rule_id": "SC-104", "name": "术后首次病程与麻醉术后访视记录完整性"},
        medical_record={
            "content": "已见术后首次病程记录，未见麻醉访视内容",
            "evidence_payload": {
                "programmatic_timeline": {
                    "documents": {
                        "surgery_record": [{"document_id": "S1", "authored_at": "2026-04-01 10:00:00"}],
                    }
                }
            },
        },
    )

    assert result["status"] == "non_compliant"
    assert "缺失关键词" in str(result.get("evidence") or "")


def test_sc022_8h_time_window_should_detect_timeout():
    executor = ProgrammaticRuleExecutor()
    result = executor.evaluate(
        rule={"rule_id": "SC-022", "name": "首次病程记录8小时完成"},
        medical_record={
            "content": (
                "入院时间：2026-04-01 08:00\n"
                "记录时间：2026-04-01 18:30\n"
                "首次病程记录内容完整"
            )
        },
    )

    assert result["status"] == "non_compliant"
    assert "间隔=10.5h" in str(result.get("evidence") or "")


@pytest.mark.parametrize("rule_id", ["SC-096", "LX-026"])
def test_surgery_24h_time_window_should_pass_when_in_time(rule_id: str):
    executor = ProgrammaticRuleExecutor()
    result = executor.evaluate(
        rule={"rule_id": rule_id, "name": "术后24小时完成"},
        medical_record={
            "content": (
                "手术结束时间：2026-04-01 10:00\n"
                "记录时间：2026-04-02 08:00\n"
                "手术记录内容"
            ),
            "evidence_payload": {
                "programmatic_timeline": {
                    "documents": {
                        "surgery_record": [{"document_id": "S1", "authored_at": "2026-04-01 10:00:00"}],
                    }
                }
            },
        },
    )

    assert result["status"] == "compliant"


@pytest.mark.parametrize("rule_id", ["SC-096", "LX-026"])
def test_surgery_24h_time_window_should_return_uncertain_when_anchor_year_is_dirty(rule_id: str):
    executor = ProgrammaticRuleExecutor()
    result = executor.evaluate(
        rule={"rule_id": rule_id, "name": "术后24小时完成"},
        medical_record={
            "content": (
                "手术结束时间：2000-02-03 16:30\n"
                "记录时间：2026-02-03 17:57\n"
                "手术记录内容"
            ),
            "evidence_payload": {
                "programmatic_timeline": {
                    "documents": {
                        "surgery_record": [{"document_id": "S1", "authored_at": "2026-02-03 17:57:00"}],
                    }
                }
            },
        },
    )

    assert result["status"] == "uncertain"
    assert "脏值" in str(result.get("findings") or "")


def test_sc048_should_use_timeline_for_attending_round():
    executor = ProgrammaticRuleExecutor()
    result = executor.evaluate(
        rule={"rule_id": "SC-048", "name": "入院48小时内主治医师首次查房"},
        medical_record={
            "content": "",
            "evidence_payload": {
                "programmatic_timeline": {
                    "admission_time": "2026-04-01 08:00:00",
                    "documents": {
                        "first_course_record": [],
                        "daily_course_record": [
                            {
                                "document_id": "D1",
                                "title": "主治医师查房记录",
                                "authored_at": "2026-04-02 07:00:00",
                                "author_role": "attending",
                            }
                        ],
                        "senior_course_record": [],
                    },
                    "risk_flags": ["normal"],
                }
            },
        },
    )

    assert result["status"] == "compliant"
    assert result["metadata"]["evidence_source"] == "timeline"


def test_sc048_should_allow_title_based_attending_identification_when_author_role_missing():
    executor = ProgrammaticRuleExecutor()
    result = executor.evaluate(
        rule={"rule_id": "SC-048", "name": "入院48小时内主治医师首次查房"},
        medical_record={
            "content": "",
            "evidence_payload": {
                "programmatic_timeline": {
                    "admission_time": "2026-04-01 08:00:00",
                    "documents": {
                        "first_course_record": [],
                        "daily_course_record": [
                            {
                                "document_id": "D1",
                                "title": "主治医师查房记录",
                                "authored_at": "2026-04-02 06:30:00",
                                "author_role": "",
                            }
                        ],
                        "senior_course_record": [],
                    },
                    "risk_flags": ["normal"],
                }
            },
        },
    )

    assert result["status"] == "compliant"


def test_sc048_should_not_treat_responsible_doctor_as_attending_round():
    executor = ProgrammaticRuleExecutor()
    result = executor.evaluate(
        rule={"rule_id": "SC-048", "name": "入院48小时内主治医师首次查房"},
        medical_record={
            "content": "",
            "evidence_payload": {
                "programmatic_timeline": {
                    "admission_time": "2026-04-01 08:00:00",
                    "documents": {
                        "first_course_record": [],
                        "daily_course_record": [
                            {
                                "document_id": "D1",
                                "title": "责任医师查房记录",
                                "authored_at": "2026-04-01 20:00:00",
                                "author_role": "attending",
                            }
                        ],
                        "senior_course_record": [],
                    },
                    "risk_flags": ["normal"],
                }
            },
        },
    )

    assert result["status"] == "non_compliant"
    assert "未找到主治医师首次查房记录" in result["findings"]


def test_sc049_should_fail_when_senior_round_exceeds_72h():
    executor = ProgrammaticRuleExecutor()
    result = executor.evaluate(
        rule={"rule_id": "SC-049", "name": "入院72小时内副主任/主任医师首次查房"},
        medical_record={
            "content": "",
            "evidence_payload": {
                "programmatic_timeline": {
                    "admission_time": "2026-04-01 08:00:00",
                    "documents": {
                        "first_course_record": [],
                        "daily_course_record": [],
                        "senior_course_record": [
                            {
                                "document_id": "D2",
                                "title": "副主任医师查房记录",
                                "authored_at": "2026-04-04 12:30:00",
                                "author_role": "senior",
                            }
                        ],
                    },
                    "risk_flags": ["normal"],
                }
            },
        },
    )

    assert result["status"] == "non_compliant"
    assert "72" in result["findings"]


def test_sc049_should_not_accept_medical_group_leader_as_senior_round():
    executor = ProgrammaticRuleExecutor()
    result = executor.evaluate(
        rule={"rule_id": "SC-049", "name": "入院72小时内副主任/主任医师首次查房"},
        medical_record={
            "content": "",
            "evidence_payload": {
                "programmatic_timeline": {
                    "admission_time": "2026-04-01 08:00:00",
                    "documents": {
                        "first_course_record": [],
                        "daily_course_record": [],
                        "senior_course_record": [
                            {
                                "document_id": "D2",
                                "title": "医疗组长查房记录",
                                "authored_at": "2026-04-02 09:00:00",
                                "author_role": "senior",
                            }
                        ],
                    },
                    "risk_flags": ["normal"],
                }
            },
        },
    )

    assert result["status"] == "non_compliant"
    assert "副主任/主任医师" in result["findings"]


def test_sc049_should_not_accept_generic_senior_title_without_deputy_or_chief():
    executor = ProgrammaticRuleExecutor()
    result = executor.evaluate(
        rule={"rule_id": "SC-049", "name": "入院72小时内副主任/主任医师首次查房"},
        medical_record={
            "content": "",
            "evidence_payload": {
                "programmatic_timeline": {
                    "admission_time": "2026-04-01 08:00:00",
                    "documents": {
                        "first_course_record": [],
                        "daily_course_record": [],
                        "senior_course_record": [
                            {
                                "document_id": "D2",
                                "title": "高级职称查房记录",
                                "authored_at": "2026-04-02 09:00:00",
                                "author_role": "senior",
                            }
                        ],
                    },
                    "risk_flags": ["normal"],
                }
            },
        },
    )

    assert result["status"] == "non_compliant"
    assert "副主任/主任医师" in result["findings"]


def test_lxe18_should_return_uncertain_when_timeline_missing():
    executor = ProgrammaticRuleExecutor()
    result = executor.evaluate(
        rule={"rule_id": "LXE-18", "name": "非危重症患者3天未完成一次病程"},
        medical_record={"content": "仅有大段病历文本，缺少时间轴"},
    )

    assert result["status"] == "uncertain"
    assert result["metadata"]["evidence_source"] == "timeline_missing"


def test_lxe35_should_fail_when_postop_day_missing():
    executor = ProgrammaticRuleExecutor()
    result = executor.evaluate(
        rule={"rule_id": "LXE-35", "name": "术后未连续3天书写病程记录"},
        medical_record={
            "content": "",
            "evidence_payload": {
                "programmatic_timeline": {
                    "admission_time": "2026-04-01 08:00:00",
                    "documents": {
                        "first_course_record": [],
                        "daily_course_record": [
                            {
                                "document_id": "P1",
                                "title": "术后病程记录",
                                "authored_at": "2026-04-02 09:00:00",
                            },
                            {
                                "document_id": "P3",
                                "title": "术后病程记录",
                                "authored_at": "2026-04-04 10:00:00",
                            },
                        ],
                        "senior_course_record": [],
                        "surgery_record": [
                            {
                                "document_id": "S1",
                                "title": "手术记录",
                                "authored_at": "2026-04-01 18:00:00",
                                "surgery_end_at": "2026-04-01 18:00:00",
                            }
                        ],
                    },
                    "risk_flags": ["normal"],
                }
            },
        },
    )

    assert result["status"] == "non_compliant"
    assert "第 2 天" in result["findings"]


def test_sc095_should_be_not_applicable_without_surgery_context():
    executor = ProgrammaticRuleExecutor()
    result = executor.evaluate(
        rule={"rule_id": "SC-095", "name": "无手术记录"},
        medical_record={
            "content": "首次病程记录\n出院记录",
            "evidence_payload": {
                "programmatic_timeline": {
                    "documents": {
                        "surgery_record": [],
                        "presurg_discussion": [],
                        "presurg_summary": [],
                        "surgery_safecheck_record": [],
                        "anesthesia_record": [],
                    }
                }
            },
        },
    )

    assert result["status"] == "not_applicable"
    assert result["applicability"]["is_applicable"] is False


def test_sc067_should_be_not_applicable_without_consultation_context():
    executor = ProgrammaticRuleExecutor()
    result = executor.evaluate(
        rule={"rule_id": "SC-067", "name": "会诊病人无会诊记录(会诊单)"},
        medical_record={
            "content": "首次病程记录\n出院记录",
            "evidence_payload": {
                "programmatic_timeline": {
                    "documents": {
                        "consultation_record": [],
                    }
                }
            },
        },
    )

    assert result["status"] == "not_applicable"
    assert result["applicability"]["is_applicable"] is False


def test_sc080_should_fail_when_presurg_summary_missing_under_surgery_context():
    executor = ProgrammaticRuleExecutor()
    result = executor.evaluate(
        rule={"rule_id": "SC-080", "name": "无术前小结"},
        medical_record={
            "content": "手术记录\n术前讨论记录",
            "evidence_payload": {
                "programmatic_timeline": {
                    "documents": {
                        "surgery_record": [
                            {
                                "document_id": "S1",
                                "authored_at": "2026-04-01 12:00:00",
                                "content": "手术记录正文",
                            }
                        ],
                        "presurg_discussion": [
                            {
                                "document_id": "P1",
                                "authored_at": "2026-04-01 10:00:00",
                                "content": "术前讨论正文",
                            }
                        ],
                        "presurg_summary": [],
                    }
                }
            },
        },
    )

    assert result["status"] == "non_compliant"
    assert "非空正文数=0" in str(result.get("evidence") or "")


def test_sc117_should_fail_when_discharge_record_written_before_discharge():
    executor = ProgrammaticRuleExecutor()
    result = executor.evaluate(
        rule={"rule_id": "SC-117", "name": "出院/死亡记录24小时内完成"},
        medical_record={
            "content": (
                "出院时间：2026-04-03 10:00\n"
                "记录时间：2026-04-02 08:00\n"
                "出院记录正文"
            )
        },
    )

    assert result["status"] == "non_compliant"
    assert "提前书写" in str(result.get("findings") or "")
