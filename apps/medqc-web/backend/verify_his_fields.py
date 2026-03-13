"""验证 _prefill_from_cdm 能正确读取 V-ZS-001 的新 HIS 字段并通过 Pydantic Schema"""
import os, sys, asyncio
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))

from app.services.frontpage_extraction_service import FrontPageExtractionService
from app.schemas.frontpage import FrontPageDraft

async def main():
    svc = FrontPageExtractionService()
    fp_data = await svc._prefill_from_cdm("V-ZS-001")

    print("=== basic_info HIS fields ===")
    basic = fp_data.get("basic_info", {})
    new_fields = [
        "birthplace", "nativeplace",
        "current_address_phone", "current_address_zip",
        "household_address", "household_address_zip",
        "work_unit", "work_unit_phone", "work_unit_zip",
        "contact_address"
    ]
    ok = 0
    for f in new_fields:
        v = basic.get(f)
        status = "[OK]" if v else "[EMPTY]"
        print(f"  {status:8s} {f:30s} = {repr(v or '')}")
        if v:
            ok += 1

    print(f"\n=== hospitalization fields ===")
    hosp = fp_data.get("hospitalization", {})
    for f in ["hospital_name", "organization_code"]:
        v = hosp.get(f)
        status = "[OK]" if v else "[EMPTY]"
        print(f"  {status:8s} {f:30s} = {repr(v or '')}")
        if v:
            ok += 1

    print(f"\nHIT {ok}/{len(new_fields)+2} fields")

    print("\n=== Pydantic validation ===")
    try:
        draft = FrontPageDraft(**fp_data)
        bi = draft.basic_info
        print("[PASS] FrontPageDraft validated OK")
        print(f"  birthplace          = {bi.birthplace!r}")
        print(f"  nativeplace         = {bi.nativeplace!r}")
        print(f"  current_address_zip = {bi.current_address_zip!r}")
        print(f"  household_address   = {bi.household_address!r}")
        print(f"  work_unit           = {bi.work_unit!r}")
        print(f"  contact_address     = {bi.contact_address!r}")
        print(f"  hospital_name       = {draft.hospitalization.hospital_name!r}")
        print(f"  organization_code   = {draft.hospitalization.organization_code!r}")
    except Exception as e:
        print(f"[FAIL] Pydantic validation error: {e}")

asyncio.run(main())
