"""首页质控 V2：按 2016 版首页填写规范与评分表执行的确定性质控（不调用模型）。

设计与口径见 docs/frontpage-qc-v2/。
"""
from .adapter import build_frontpage_doc
from .catalog import RULES, RULES_BY_ID
from .config import RULESET_KEY, RULESET_VERSION
from .document import FrontpageDoc
from .engine import evaluate_frontpage
from .loader import FrontpageRef, RawFrontpage, load_frontpage_raw
from .model import FrontpageQcOutcome, Verdict

__all__ = [
    "RULES",
    "RULES_BY_ID",
    "RULESET_KEY",
    "RULESET_VERSION",
    "FrontpageDoc",
    "FrontpageQcOutcome",
    "FrontpageRef",
    "RawFrontpage",
    "Verdict",
    "build_frontpage_doc",
    "evaluate_frontpage",
    "load_frontpage_raw",
]
