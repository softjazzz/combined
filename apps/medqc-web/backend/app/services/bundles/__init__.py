"""
Bundle contracts and minimal assembly entrypoints.

This module intentionally contains only skeleton logic for the bundle layer.
Rule engines should consume the normalized bundle payloads, while table-level
queries and mapping details are implemented incrementally in dedicated services.
"""

from .contracts import (
    BUNDLE_SCHEMA_COMPAT_READABLE_VERSIONS,
    BUNDLE_DOMAINS,
    BUNDLE_SCHEMA_VERSION_CURRENT,
    BUNDLE_SCENES,
    get_bundle_contract,
    get_settlement_structured_context_contract,
    is_bundle_schema_readable,
)
from .factory import (
    build_coding_bundle,
    build_final_record_bundle,
    build_frontpage_bundle,
    build_running_record_bundle,
    build_settlement_bundle,
)
from .assembly import (
    assemble_bundle_from_visit_index,
    assemble_coding_bundle,
    assemble_domain_bundle,
    assemble_final_record_bundle,
    assemble_frontpage_bundle,
    ensure_domain_bundle_tables,
    assemble_running_record_bundle,
    assemble_settlement_bundle,
    ensure_scene_bundle_tables,
    load_domain_bundle,
    load_or_assemble_domain_bundle,
    load_coding_payload_from_bundle,
    load_frontpage_payload_from_bundle,
    load_settlement_payload_from_bundle,
    refresh_domain_bundles_for_rows,
    refresh_scene_bundles_for_rows,
)
from .refresh_manager import (
    SUPPORTED_BUNDLE_SCENES,
    create_bundle_refresh_job,
    ensure_bundle_refresh_tables,
    list_bundle_refresh_failures,
    list_bundle_refresh_jobs,
    set_bundle_refresh_job_running,
    complete_bundle_refresh_job,
)

__all__ = [
    "BUNDLE_SCHEMA_VERSION_CURRENT",
    "BUNDLE_SCHEMA_COMPAT_READABLE_VERSIONS",
    "BUNDLE_DOMAINS",
    "BUNDLE_SCENES",
    "is_bundle_schema_readable",
    "get_bundle_contract",
    "get_settlement_structured_context_contract",
    "build_running_record_bundle",
    "build_final_record_bundle",
    "build_frontpage_bundle",
    "build_coding_bundle",
    "build_settlement_bundle",
    "assemble_bundle_from_visit_index",
    "assemble_running_record_bundle",
    "assemble_final_record_bundle",
    "assemble_frontpage_bundle",
    "assemble_coding_bundle",
    "assemble_settlement_bundle",
    "assemble_domain_bundle",
    "ensure_scene_bundle_tables",
    "ensure_domain_bundle_tables",
    "load_domain_bundle",
    "load_or_assemble_domain_bundle",
    "refresh_domain_bundles_for_rows",
    "refresh_scene_bundles_for_rows",
    "load_frontpage_payload_from_bundle",
    "load_coding_payload_from_bundle",
    "load_settlement_payload_from_bundle",
    "SUPPORTED_BUNDLE_SCENES",
    "ensure_bundle_refresh_tables",
    "create_bundle_refresh_job",
    "set_bundle_refresh_job_running",
    "complete_bundle_refresh_job",
    "list_bundle_refresh_failures",
    "list_bundle_refresh_jobs",
]
