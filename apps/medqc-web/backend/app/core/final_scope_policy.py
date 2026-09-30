"""终末场景口径（V3.6，2026-09-30 用户确认口径 B 并推广到全部终末场景）。

医院归档标记来源（archive_sign）未接入前：
- 终末（final）= 已出院且有病历资料的住院病例，不核验是否已归档；
- 运行（running）= 当前在院；
- 报表、列表、批量质控、导出、抽查任务的终末场景统一按此口径，并在界面显式标注“未核验归档”。
归档来源接入后，在此收窄终末口径，调用方不各自判断。
"""

from __future__ import annotations

from typing import Any

# 终末口径下归档状态固定为未核验。
FINAL_ARCHIVE_STATUS = "unverified"

# 住院类批量质控/重跑可执行的范围；门急诊不在住院批量链路内，空值与未知值一律拒绝。
EXECUTABLE_INPATIENT_SCOPES = frozenset({"running", "final", "all"})

UNSUPPORTED_SCOPE_DETAIL = "unsupported_scope: 质控范围无效，只支持运行、终末或全部住院病历"


def normalize_scope(value: Any) -> str:
    return str(value or "").strip().lower()


def is_executable_inpatient_scope(scope: Any) -> bool:
    return normalize_scope(scope) in EXECUTABLE_INPATIENT_SCOPES
