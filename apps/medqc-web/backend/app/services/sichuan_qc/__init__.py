"""四川质控服务的受控拆分模块。"""

from .legacy_rule_service import evaluate_legacy_rule_for_visit

__all__ = ["evaluate_legacy_rule_for_visit"]
