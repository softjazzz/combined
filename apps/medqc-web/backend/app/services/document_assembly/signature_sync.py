"""只有同一文书正文主体逐字一致时，允许用明确签名栏补空名单；不推定角色。"""

import re

from .signatures import body_physician_signatures


_LABEL = re.compile(r"(?:医师|医生)签名\s*[:：]")
_ROLE_FIELDS = ("physician_sign", "recorder_sign", "attending_physician_sign", "senior_physician_sign")


def safe_body_signature_supplement(candidate):
    local = candidate.variants.get("local")
    if not local or any(str(local.get(field) or "").strip() for field in _ROLE_FIELDS):
        return ()
    local_text = str(local.get("record_content") or "")
    labels = list(_LABEL.finditer(local_text))
    if len(labels) > 1:
        return ()
    local_core = local_text[:labels[0].start()] if labels else local_text
    local_core = "".join(local_core.split())
    if not local_core or body_physician_signatures(local_text):
        return ()
    candidates = []
    for source in ("clinical_data", "homology"):
        row = candidate.variants.get(source) or {}
        if any(str(row.get(field) or "").strip() for field in _ROLE_FIELDS):
            continue
        text = str(row.get("record_content") or "")
        names = body_physician_signatures(text)
        labels = list(_LABEL.finditer(text))
        if names and len(labels) == 1 and "".join(text[:labels[0].start()].split()) == local_core:
            candidates.append(names)
    if not candidates or any(set(names) != set(candidates[0]) for names in candidates[1:]):
        return ()
    return candidates[0]
