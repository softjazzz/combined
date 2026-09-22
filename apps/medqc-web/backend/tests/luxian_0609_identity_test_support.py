"""0609 身份迁移测试的发布顺序辅助函数。"""

from app.services.luxian_0609_rule_master import load_luxian_0609_rule_master


def published_rule_ids(start: int, end: int) -> tuple[str, ...]:
    """按权威总表发布顺序取闭区间，避免测试生成已废弃的三位编号。"""

    if start < 1 or end < start:
        raise ValueError("invalid published rule range")
    rule_ids = tuple(entry.rule_id for entry in load_luxian_0609_rule_master())
    return rule_ids[start - 1:end]
