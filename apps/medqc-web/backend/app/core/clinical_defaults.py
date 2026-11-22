"""临床来源与机构的部署默认值。"""

import os
from dataclasses import dataclass


FIXED_CDM_MODE = "fixed_donghua_cdm"
LEGACY_COMPAT_MODE = "legacy_compat"
INDEPENDENT_CDM = "independent_cdm"
LEGACY_PG = "legacy_pg"
LEGACY_SOURCE_NAME = "原有数据源"
CDM_PROFILE_NAME = "服务器CDM"
UNCONFIGURED_INSTITUTE_ID = "LOCAL-HOSPITAL"

_LEGACY_HOSPITAL_NAME = "泸县人民医院"
_LEGACY_CASE_INSTITUTE = "机构号"
_LEGACY_RESULT_EPOCH = "7cecd40f-047d-4458-b964-8741d0ea7399"
_LEGACY_RESULT_BINDING = "cdm-read-v1:d6426d946c655b24ec8ad3915e7441e7cb5033dd69c7397a70c7431f5a3dea08"


@dataclass(frozen=True)
class ClinicalDefaults:
    hospital_name_override: str
    hospital_code: str
    sync_institute_id: str
    source_mode: str
    compat_source: str
    cdm_profile_name: str
    fixed_cdm_name: str
    saved_result_case_institute: str
    saved_result_epoch: str
    saved_result_binding_override: str
    saved_result_receipt_binding: str

    @property
    def hospital_name(self) -> str:
        return self.hospital_name_override or _LEGACY_HOSPITAL_NAME


def get_clinical_defaults() -> ClinicalDefaults:
    """按调用读取部署环境，保留未配置时的历史默认值。"""
    hospital_name_override = os.getenv("MEDQC_HOSPITAL_NAME", "").strip()
    hospital_name = hospital_name_override or _LEGACY_HOSPITAL_NAME
    case_institute = os.getenv("MEDQC_SAVED_RESULT_CASE_INSTITUTE", "").strip() or _LEGACY_CASE_INSTITUTE
    epoch = os.getenv("MEDQC_SAVED_RESULT_SOURCE_EPOCH", "").strip()
    binding = os.getenv("MEDQC_SAVED_RESULT_SOURCE_BINDING", "").strip()
    cdm_name = os.getenv("MEDQC_CDM_SOURCE_NAME", "").strip()
    compat_source = os.getenv("MEDQC_DEFAULT_CLINICAL_SOURCE", "").strip() or LEGACY_PG
    mode = os.getenv("MEDQC_CLINICAL_SOURCE_MODE", FIXED_CDM_MODE).strip()
    legacy_institute_pair = (hospital_name, case_institute) == (_LEGACY_HOSPITAL_NAME, _LEGACY_CASE_INSTITUTE)
    # 现场核定过的回执只属于原机构对。新机构映射不能继承原院的归属证明。
    return ClinicalDefaults(
        hospital_name_override=hospital_name_override,
        hospital_code=os.getenv("MEDQC_HOSPITAL_CODE", "").strip() or (
            "H51052100267" if hospital_name == _LEGACY_HOSPITAL_NAME else ""
        ),
        sync_institute_id=os.getenv("MEDQC_DEFAULT_INSTITUTE_ID", "").strip() or UNCONFIGURED_INSTITUTE_ID,
        source_mode=mode,
        compat_source=compat_source if mode == LEGACY_COMPAT_MODE else LEGACY_PG,
        cdm_profile_name=cdm_name or CDM_PROFILE_NAME,
        fixed_cdm_name=cdm_name or "东华CDM",
        saved_result_case_institute=case_institute,
        saved_result_epoch=epoch or (_LEGACY_RESULT_EPOCH if legacy_institute_pair else ""),
        saved_result_binding_override=binding,
        saved_result_receipt_binding=binding or (_LEGACY_RESULT_BINDING if legacy_institute_pair else ""),
    )
