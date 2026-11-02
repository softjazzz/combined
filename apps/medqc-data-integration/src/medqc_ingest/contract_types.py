"""源字段合同的数据类型，不依赖运行时领域或数据库。"""

from typing import TypedDict

FieldMappingData = tuple[str | None, str, str]


class PublishContractData(TypedDict):
    target: str
    primary_key: tuple[str, ...]
    required_columns: tuple[str, ...]
    mappings: tuple[FieldMappingData, ...]
