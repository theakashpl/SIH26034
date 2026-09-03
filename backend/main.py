
from starlette import staticfiles
from fastapi import FastAPI, UploadFile, File
from pathlib import Path
import shutil

from ocr.engine import extract_text, extract_text_with_confidence
from extraction.extractor import extract_fields
from rules.engine import evaluate_rules, calculate_compliance


app = FastAPI(
    title="Legal Metrology Compliance API",
    version="1.0.0"
)


UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(exist_ok=True)


@app.get("/")
def root():
    return {
        "message": "Legal Metrology Compliance API is running"
    }


@app.post("/scan")
async def scan_product(file: UploadFile = File(...)):
    file_path = UPLOAD_DIR / (file.filename or "uploaded_file")

    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    ocr_result = extract_text_with_confidence(str(file_path))
    ocr_text = ocr_result["text"]
    ocr_confidence = ocr_result["confidence"]

    fields = extract_fields(ocr_text)

    rule_results = evaluate_rules(fields)

    compliance = calculate_compliance(
    rule_results,
    ocr_confidence
)

    return {
        "filename": file.filename,
        "ocr_text": ocr_text,
        "fields": fields,
        "checks": rule_results,
        "compliance": compliance,
        "ocr_confidence": ocr_confidence
    }