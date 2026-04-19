"""
QC input adapters.

This package bridges new bundle payloads to legacy QC service inputs
without changing existing rule engines.
"""

from .running_final_bundle_adapter import (
    adapt_bundle_to_qc_service_payload,
    adapt_bundle_to_sichuan_eval_args,
    extract_bundle_documents,
)
from .running_final_bundle_runtime import (
    evaluate_running_final_bundle,
    load_running_final_bundle,
)

__all__ = [
    "adapt_bundle_to_qc_service_payload",
    "adapt_bundle_to_sichuan_eval_args",
    "extract_bundle_documents",
    "load_running_final_bundle",
    "evaluate_running_final_bundle",
]
