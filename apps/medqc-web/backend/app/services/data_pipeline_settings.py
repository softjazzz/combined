"""抽取链路配置唯一所有者；不切换业务engine，不在保存时联网。"""
from __future__ import annotations

import json
import os
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import text
from .clinical_source_policy import fixed_cdm

TABLE = "qc.sync_config_registry"
NAMESPACE, KEY = "sync", "data_pipelines_v1"


class PipelineError(ValueError):
    def __init__(self, code: str, status: int = 503):
        self.code, self.status = code, status
        super().__init__(code)


class PipelineSettings(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    version: int = Field(default=0, ge=0)
    default_pipeline: Literal["legacy_pg", "independent_cdm"] = "legacy_pg"
    independent_enabled: bool = False


def load(session) -> tuple[PipelineSettings, str | None]:
    row = session.execute(text(
        f"SELECT payload_json FROM {TABLE} WHERE namespace=:ns AND config_key=:key"
    ), {"ns": NAMESPACE, "key": KEY}).first()
    if row is None:
        return PipelineSettings(default_pipeline="independent_cdm") if fixed_cdm() else PipelineSettings(), None
    try:
        value=PipelineSettings.model_validate(json.loads(row[0]))
        return value.model_copy(update={"default_pipeline":"independent_cdm"}) if fixed_cdm() else value, row[0]
    except (ValueError, TypeError):
        raise PipelineError("data_pipeline_configuration_invalid") from None


def save(session, proposed: PipelineSettings, actor_id: str) -> PipelineSettings:
    current, raw = load(session)
    if fixed_cdm():
        proposed=proposed.model_copy(update={"default_pipeline":"independent_cdm"})
    if proposed.version != current.version:
        raise PipelineError("data_pipeline_configuration_changed", 409)
    if not fixed_cdm() and proposed.default_pipeline == "independent_cdm" and not proposed.independent_enabled:
        raise PipelineError("independent_pipeline_disabled", 422)
    if proposed.independent_enabled:
        from .sync_control_client import deployment
        deployment()  # 仅静态校验；不创建HTTP或数据库连接。
    saved = proposed.model_copy(update={"version": current.version + 1})
    params = {"ns": NAMESPACE, "key": KEY, "value": saved.model_dump_json(), "actor": actor_id}
    if raw is None:
        statement = text(f"""INSERT INTO {TABLE}
            (namespace,config_key,payload_json,updated_by,source,change_reason,updated_at)
            VALUES (:ns,:key,:value,:actor,'data_pipeline_settings','configure pipelines',CURRENT_TIMESTAMP)
            ON CONFLICT(namespace,config_key) DO NOTHING""")
    else:
        params["old"] = raw
        statement = text(f"""UPDATE {TABLE} SET payload_json=:value,updated_by=:actor,
            source='data_pipeline_settings',change_reason='configure pipelines',updated_at=CURRENT_TIMESTAMP
            WHERE namespace=:ns AND config_key=:key AND payload_json=:old""")
    if session.execute(statement, params).rowcount != 1:
        raise PipelineError("data_pipeline_configuration_changed", 409)
    session.commit()
    return saved


def runtime_status() -> dict:
    """只报告部署状态，不探测服务器、不泄漏凭据或连接串。"""
    from ..database import clinical_connection
    from .sync_control_client import deployment
    control_configured = False
    try:
        deployment()
        control_configured = True
    except PipelineError:
        pass
    cdm_valid = True
    try:
        # 只构造连接池/校验passfile；不checkout连接，不连接CDM。
        clinical_connection.get_engine()
    except (clinical_connection.ClinicalSourceConfigurationError, PipelineError, ValueError):
        cdm_valid = False
    return {
        "control_configured": control_configured,
        "control_profile": os.getenv("SYNC_CONTROL_PROFILE", "accepted_manual"),
        "clinical_read_source": "independent_cdm" if clinical_connection.configured() else "business_cdm",
        "cdm_url_configured": bool(os.getenv("CDM_DATABASE_URL", "").strip()),
        "cdm_configuration_valid": cdm_valid,
        "read_scope": "Bundle/LX0609已适配读取入口；病例列表、旧ORM和其他领域须分别验收",
        "pdf_source": "original_business_database",
        "automatic_extraction": False,
        "automatic_qc": False,
    }
