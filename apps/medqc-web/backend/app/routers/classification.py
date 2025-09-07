from fastapi import APIRouter
from ..services.records_ingest_service import get_classification_mapping

router = APIRouter(prefix="/api", tags=["classification"], include_in_schema=False)


@router.get("/test-classification-mapping")
async def test_classification_mapping():
    mapping = await get_classification_mapping()
    return {
        "success": True,
        "mapping": mapping,
        "categories_count": len(mapping.get("categories", {})),
        "types_count": len(mapping.get("types", {})),
    }

