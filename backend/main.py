import sys
import os
from pathlib import Path
from typing import List, Optional
import cv2
import numpy as np
from dotenv import load_dotenv
from supabase import create_client, Client
from starlette.datastructures import UploadFile as StarletteUploadFile
from fastapi import FastAPI, UploadFile, File, HTTPException, Request
from fastapi.responses import RedirectResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

BACKEND_DIR = Path(__file__).resolve().parent
ROOT_DIR = BACKEND_DIR.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from ocr.engine import extract_text, extract_text_with_confidence
from extraction.extractor import extract_fields, combine_product_evidence
from rules.engine import evaluate_rules, calculate_compliance

# Load environment variables
load_dotenv(dotenv_path=ROOT_DIR / ".env")
load_dotenv(dotenv_path=BACKEND_DIR / ".env")

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

supabase: Optional[Client] = None
if SUPABASE_URL and SUPABASE_KEY:
    try:
        supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
        print("Connected to Supabase database successfully.")
    except Exception as e:
        print(f"Warning: Failed to connect to Supabase: {e}")


app = FastAPI(
    title="Legal Metrology Compliance API",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(exist_ok=True)

ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tiff"}

FRONTEND_DIR = Path(__file__).parent.parent / "frontend"
if FRONTEND_DIR.exists():
    app.mount("/ui", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="ui")



@app.get("/")
def root(request: Request):
    accept = request.headers.get("accept", "")
    if "text/html" in accept and FRONTEND_DIR.exists():
        return RedirectResponse(url="/ui/")
    return {
        "message": "Legal Metrology Compliance API is running"
    }


def _is_valid_upload(obj) -> bool:
    return obj is not None and (
        isinstance(obj, (UploadFile, StarletteUploadFile))
        or (hasattr(obj, "filename") and hasattr(obj, "read"))
    )


@app.post("/scan")
async def scan_product(
    files: Optional[List[UploadFile]] = File(default=None),
    file: Optional[UploadFile] = File(default=None)
):
    try:
        # 1. Collect uploaded files (supports both 'files' list and legacy 'file' single parameter)
        upload_list: List[UploadFile] = []
        if files:
            if isinstance(files, list):
                for f in files:
                    if f is not None and _is_valid_upload(f):
                        upload_list.append(f)
            elif isinstance(files, (UploadFile, StarletteUploadFile)):
                upload_list.append(files)

        if file is not None and _is_valid_upload(file):
            upload_list.append(file)

        # 2. Validate file count (1 to 4 images)
        if not upload_list:
            raise HTTPException(
                status_code=400,
                detail="No image files provided. Must upload between 1 and 4 images."
            )

        if len(upload_list) > 4:
            raise HTTPException(
                status_code=400,
                detail=f"Maximum 4 images allowed per product scan. Received {len(upload_list)} images."
            )

        # 3. Validate each file (extension, non-empty, valid image decodability)
        validated_buffers = []
        for idx, f in enumerate(upload_list, start=1):
            filename = f.filename or f"image_{idx}.jpg"
            ext = Path(filename).suffix.lower()
            if ext not in ALLOWED_EXTENSIONS:
                raise HTTPException(
                    status_code=400,
                    detail=f"Unsupported file format for '{filename}'. Allowed formats: JPG, JPEG, PNG, WEBP, BMP, TIFF."
                )

            contents = await f.read()
            if len(contents) == 0:
                raise HTTPException(
                    status_code=400,
                    detail=f"Uploaded file '{filename}' is empty (0 bytes)."
                )

            nparr = np.frombuffer(contents, np.uint8)
            decoded = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            if decoded is None:
                raise HTTPException(
                    status_code=400,
                    detail=f"Uploaded file '{filename}' is corrupted or not a valid image."
                )

            validated_buffers.append((filename, contents))

        # 4. Save and run OCR on each image independently
        images_meta = []
        for idx, (filename, contents) in enumerate(validated_buffers, start=1):
            saved_path = UPLOAD_DIR / f"img_{idx}_{filename}"
            with open(saved_path, "wb") as buffer:
                buffer.write(contents)

            ocr_result = extract_text_with_confidence(str(saved_path))
            images_meta.append({
                "image_id": idx,
                "filename": filename,
                "ocr_text": ocr_result.get("cleaned_text", ""),
                "cleaned_text": ocr_result.get("cleaned_text", ""),
                "confidence": ocr_result.get("confidence", 0.0),
                "psm_selected": ocr_result.get("psm_selected", 3)
            })

        # 5. Combine OCR evidence across all images of the same product
        combined_extraction = combine_product_evidence(images_meta)
        fields = combined_extraction.get("fields", {})
        details = combined_extraction.get("details", {})
        conflicts = combined_extraction.get("conflicts", {})

        # 6. Evaluate compliance rules on combined fields
        rule_results = evaluate_rules(fields, conflicts)

        # Calculate mean OCR confidence across all scanned views
        avg_ocr_confidence = (
            sum(float(img.get("confidence", 0)) for img in images_meta) / len(images_meta)
            if images_meta else 0.0
        )

        compliance = calculate_compliance(
            rule_results,
            round(avg_ocr_confidence, 2)
        )

        # 7. Build consolidated metadata
        primary_filename = upload_list[0].filename if len(upload_list) == 1 else ", ".join(f.filename or "image" for f in upload_list)
        combined_ocr_text = "\n\n--- NEXT IMAGE ---\n\n".join(str(img.get("cleaned_text", "")) for img in images_meta)

        # 8. Log to Supabase database if available
        saved_product_id = None
        try:
            saved_product_id = save_scan_to_supabase(fields, rule_results, primary_filename)
        except Exception as db_err:
            print(f"Warning: Supabase logging failed: {db_err}")

        return {
            "images": images_meta,
            "filename": primary_filename,
            "ocr_text": combined_ocr_text,
            "fields": fields,
            "details": details,
            "conflicts": conflicts,
            "checks": rule_results,
            "compliance": compliance,
            "ocr_confidence": round(avg_ocr_confidence, 2),
            "db_product_id": saved_product_id
        }

    except HTTPException:
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail=f"Scanning failed: {str(e)}"
        )


def save_scan_to_supabase(fields: dict, checks: list, primary_filename: str):
    if not supabase:
        return None
    try:
        product_record = {
            "product_name": fields.get("product_name") or primary_filename or "Unknown Product",
            "mrp": str(fields.get("mrp") or "") or None,
            "net_quantity": str(fields.get("net_quantity") or "") or None,
            "manufacturer": str(fields.get("manufacturer") or "") or None,
            "consumer_info": str(fields.get("consumer_care") or fields.get("consumer_info") or "") or None,
        }
        res_p = supabase.table("products").insert(product_record).execute()
        if not res_p.data:
            return None
        product_id = res_p.data[0]["id"]

        check_records = []
        for c in checks:
            check_records.append({
                "product_id": product_id,
                "field_name": c.get("field") or c.get("name") or "unknown",
                "extracted_value": str(c.get("extracted_value") or "") or None,
                "status": c.get("status") or "FAIL",
                "message": c.get("reason") or c.get("message") or ""
            })
        if check_records:
            supabase.table("compliance_checks").insert(check_records).execute()
        return product_id
    except Exception as e:
        print(f"Error logging scan to Supabase: {e}")
        return None


@app.get("/supabase/status")
def get_supabase_status():
    if not supabase:
        return {
            "status": "disconnected",
            "message": "Supabase credentials missing or client not initialized."
        }
    try:
        rules_res = supabase.table("rules").select("id").execute()
        products_res = supabase.table("products").select("id").execute()
        return {
            "status": "connected",
            "supabase_url": SUPABASE_URL,
            "connected_tables": ["rules", "products", "compliance_checks", "compliance_summary"],
            "rules_count": len(rules_res.data or []),
            "products_logged": len(products_res.data or [])
        }
    except Exception as e:
        return {
            "status": "error",
            "message": str(e)
        }


@app.get("/history")
def get_scan_history(limit: int = 10):
    if not supabase:
        return {"history": [], "message": "Supabase not configured"}
    try:
        res = supabase.table("products").select("*, compliance_summary(*)").order("created_at", desc=True).limit(limit).execute()
        return {"history": res.data or []}
    except Exception as e:
        return {"error": str(e)}

