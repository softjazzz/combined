from pydantic import BaseModel
from typing import Optional, List, Dict, Any


class LLMParseResultSave(BaseModel):
    record_number: Optional[str] = None
    patient_name: Optional[str] = None
    patient_age: Optional[int] = None
    patient_gender: Optional[str] = None
    department: Optional[str] = None
    primary_diagnosis: Optional[str] = None
    secondary_diagnosis: Optional[List[str]] = None
    major_surgery: Optional[str] = None
    documents: Optional[List[dict]] = None
    confidence: Optional[int] = None
    content: Optional[str] = None
    method: Optional[str] = None
    parse_metadata: Optional[Dict[str, Any]] = None

