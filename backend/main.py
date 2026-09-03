
from typing import List, Optional
from pathlib import Path
import shutil
import cv2
import numpy as np
from starlette.datastructures import UploadFile as StarletteUploadFile
from fastapi import FastAPI, UploadFile, File, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from ocr.engine import extract_text, extract_text_with_confidence
from extraction.extractor import extract_fields, combine_product_evidence
from rules.engine import evaluate_rules, calculate_compliance


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
        from fastapi.responses import RedirectResponse
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
    # 1. Collect uploaded files (supports both 'files' list and legacy 'file' single parameter)
    upload_list: List[UploadFile] = []
    if files:
        if isinstance(files, list):
            upload_list.extend([f for f in files if _is_valid_upload(f)])
        elif _is_valid_upload(files):
            upload_list.append(files)

    if _is_valid_upload(file):
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
            "ocr_text": ocr_result["cleaned_text"],
            "cleaned_text": ocr_result["cleaned_text"],
            "confidence": ocr_result["confidence"],
            "psm_selected": ocr_result.get("psm_selected", 3)
        })

    # 5. Combine OCR evidence across all images of the same product
    combined_extraction = combine_product_evidence(images_meta)
    fields = combined_extraction["fields"]
    details = combined_extraction["details"]
    conflicts = combined_extraction["conflicts"]

    # 6. Evaluate compliance rules on combined fields
    rule_results = evaluate_rules(fields, conflicts)

    # Calculate mean OCR confidence across all scanned views
    avg_ocr_confidence = (
        sum(img["confidence"] for img in images_meta) / len(images_meta)
        if images_meta else 0.0
    )

    compliance = calculate_compliance(
        rule_results,
        round(avg_ocr_confidence, 2)
    )

    # 7. Build and return consolidated response
    primary_filename = upload_list[0].filename if len(upload_list) == 1 else ", ".join(f.filename or "image" for f in upload_list)
    combined_ocr_text = "\n\n--- NEXT IMAGE ---\n\n".join(img["cleaned_text"] for img in images_meta)

    return {
        "images": images_meta,
        "filename": primary_filename,
        "ocr_text": combined_ocr_text,
        "fields": fields,
        "details": details,
        "conflicts": conflicts,
        "checks": rule_results,
        "compliance": compliance,
        "ocr_confidence": round(avg_ocr_confidence, 2)
    }