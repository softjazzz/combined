"""
Compatibility shim for legacy imports.

Some modules still import `qc_llm_client_runtime`, while the actual
implementation lives in `qc_llm_client.py`.
"""

from .qc_llm_client import SichuanQCLLMClient

__all__ = ["SichuanQCLLMClient"]
