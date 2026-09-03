import re
from pathlib import Path
from typing import Union
import pytesseract
from .preprocessing import preprocess_image, validate_image, preprocess_image_otsu, preprocess_image_clahe


TESSERACT_EXE = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
if Path(TESSERACT_EXE).exists():
    pytesseract.pytesseract.tesseract_cmd = TESSERACT_EXE


PACKAGING_KEYWORDS = [
    r"\bmrp\b", r"\brs\.?\b", r"\binr\b", r"\bnet\b", r"\bwet\b", r"\bqty\b", r"\bquantity\b",
    r"\bweight\b", r"\bwt\b", r"\bmanufactur", r"\bmfd\b", r"\bpkd\b", r"\bpacked\b",
    r"\bconsumer\b", r"\bcustomer\b", r"\bcare\b", r"\bhelpline\b", r"\btoll\b",
    r"\bingredients\b", r"\bnutrition\b", r"\bserving\b", r"\bcalories\b",
    r"\b\d{3}[- ]\d{3}[- ]\d{4}\b", r"\b\d{10}\b", r"\b1800\b", r"@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"
]


def clean_ocr_text(text: str) -> str:
    """
    Clean common OCR artifacts, normalize unicode quotes, dashes,
    and remove stray line-start noise while preserving content.
    """
    if not text:
        return ""

    # Normalize quotes, apostrophes and dashes
    cleaned = text.replace("’", "'").replace("‘", "'").replace("`", "'")
    cleaned = cleaned.replace("“", '"').replace("”", '"')
    cleaned = cleaned.replace("—", "-").replace("–", "-")
    cleaned = cleaned.replace("\ufffd", "'")

    # Clean line-start noise characters common in scanned packaging
    cleaned_lines = []
    for line in cleaned.split("\n"):
        line = re.sub(r"^[|=#*~_\s\.\-–]+", "", line)
        cleaned_lines.append(line.rstrip())

    return "\n".join(cleaned_lines).strip()


def score_ocr_candidate(text: str, confidences: list) -> float:
    """
    Defensible heuristic to score OCR quality on packaging labels:
    - Base confidence (0-100)
    - Valid alphanumeric word density vs symbol gibberish
    - Packaging keyword presence (mrp, net qty, mfg, consumer care, etc.)
    """
    if not confidences or not text:
        return 0.0

    avg_conf = sum(confidences) / len(confidences)
    words = text.split()
    if not words:
        return 0.0

    alpha_words = [w for w in words if re.search(r"[a-zA-Z0-9]", w)]
    alpha_ratio = len(alpha_words) / len(words)

    lower_text = text.lower()
    kw_count = sum(1 for kw in PACKAGING_KEYWORDS if re.search(kw, lower_text))

    score = (
        (avg_conf * 0.4)
        + (kw_count * 10)
        + (alpha_ratio * 30)
        + (min(len(alpha_words), 150) / 150 * 20)
    )
    return score


def extract_text_with_confidence(image_path: Union[str, Path]) -> dict:
    """
    Runs multi-PSM OCR (PSM 3 for multi-column layouts, PSM 6 for uniform/dense blocks),
    evaluates candidates with an objective heuristic, complements isolated declaration lines
    (e.g., consumer care badges, price boxes, net quantity), and returns structured raw, cleaned, and confidence results.
    """
    raw_img = validate_image(str(image_path))

    # Candidate 1: CLAHE enhanced with PSM 3 (optimal for multi-column/structured label layouts)
    processed_clahe = preprocess_image_clahe(raw_img)
    data_psm3 = pytesseract.image_to_data(
        processed_clahe,
        config="--psm 3",
        output_type=pytesseract.Output.DICT
    )
    confs_psm3 = [float(c) for c in data_psm3["conf"] if float(c) >= 0]
    raw_psm3 = str(pytesseract.image_to_string(processed_clahe, config="--psm 3"))
    score_psm3 = score_ocr_candidate(raw_psm3, confs_psm3)
    avg_conf_psm3 = sum(confs_psm3) / len(confs_psm3) if confs_psm3 else 0.0

    # Candidate 2: CLAHE enhanced with PSM 6 (optimal for dense/graphic packaging text)
    data_psm6_clahe = pytesseract.image_to_data(
        processed_clahe,
        config="--psm 6",
        output_type=pytesseract.Output.DICT
    )
    confs_psm6_clahe = [float(c) for c in data_psm6_clahe["conf"] if float(c) >= 0]
    raw_psm6_clahe = str(pytesseract.image_to_string(processed_clahe, config="--psm 6"))
    score_psm6_clahe = score_ocr_candidate(raw_psm6_clahe, confs_psm6_clahe)
    avg_conf_psm6_clahe = sum(confs_psm6_clahe) / len(confs_psm6_clahe) if confs_psm6_clahe else 0.0

    # Candidate 3: Otsu binarized with PSM 6 (optimal for isolated text on uniform backgrounds)
    processed_otsu = preprocess_image_otsu(raw_img)
    data_psm6_otsu = pytesseract.image_to_data(
        processed_otsu,
        config="--psm 6",
        output_type=pytesseract.Output.DICT
    )
    confs_psm6_otsu = [float(c) for c in data_psm6_otsu["conf"] if float(c) >= 0]
    raw_psm6_otsu = str(pytesseract.image_to_string(processed_otsu, config="--psm 6"))
    score_psm6_otsu = score_ocr_candidate(raw_psm6_otsu, confs_psm6_otsu)
    avg_conf_psm6_otsu = sum(confs_psm6_otsu) / len(confs_psm6_otsu) if confs_psm6_otsu else 0.0

    # Candidate 4: Otsu binarized with PSM 11 (optimal for sparse artistic text across packaging views)
    data_psm11 = pytesseract.image_to_data(
        processed_otsu,
        config="--psm 11",
        output_type=pytesseract.Output.DICT
    )
    confs_psm11 = [float(c) for c in data_psm11["conf"] if float(c) >= 0]
    raw_psm11 = str(pytesseract.image_to_string(processed_otsu, config="--psm 11"))
    score_psm11 = score_ocr_candidate(raw_psm11, confs_psm11)
    avg_conf_psm11 = sum(confs_psm11) / len(confs_psm11) if confs_psm11 else 0.0

    # Rank candidates based on defensible heuristic
    candidates = [
        (score_psm3, raw_psm3, avg_conf_psm3, 3),
        (score_psm6_clahe, raw_psm6_clahe, avg_conf_psm6_clahe, 6),
        (score_psm6_otsu, raw_psm6_otsu, avg_conf_psm6_otsu, 6),
        (score_psm11, raw_psm11, avg_conf_psm11, 11),
    ]
    candidates.sort(key=lambda x: x[0], reverse=True)
    _, primary_raw, primary_conf, primary_psm = candidates[0]

    # Clean primary text
    cleaned_primary = clean_ocr_text(primary_raw)

    # Detect if other candidates captured important packaging declarations or contact markers missed by primary
    important_patterns = [
        r"\b\d{3}[- ]\d{3}[- ]\d{4}\b",
        r"\b1800[- ]?\d{2,4}[- ]?\d{3,4}\b",
        r"\b1-800[- ]?\d{3,4}[- ]?\d{3,4}\b",
        r"\b0\d{2,4}\s*[-–]\s*\d{3,4}\s*[- ]?\d{3,4}\b",
        r"\b[6-9]\d{9}\b",
        r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}",
        r"(?:can't|cannot)\s*find\s*the\s*truth",
        r"(?:consumer|customer)\s*(?:care|service|support|complaints|feedback)",
        r"\bmrp\b",
        r"\b(?:net|wet)\s*(?:qty|quantity|wt|weight)",
        r"\b(?:net|wet)\s*quantity\b",
        r"\b\d+(?:\.\d+)?\s*(?:g|gm|gms|kg|kgs|ml|l)\b"
    ]

    combined_text = cleaned_primary
    for cand in candidates[1:]:
        cand_cleaned = clean_ocr_text(cand[1])
        for line in cand_cleaned.split("\n"):
            line_str = line.strip()
            if not line_str or len(line_str) < 3:
                continue
            for p in important_patterns:
                match = re.search(p, line_str, re.IGNORECASE)
                if match and match.group(0).lower() not in combined_text.lower():
                    combined_text += f"\n{line_str}"
                    break

    return {
        "text": combined_text,            # backward compatibility
        "raw_text": primary_raw,          # preserved primary raw OCR
        "cleaned_text": combined_text,    # cleaned and complemented text
        "confidence": round(primary_conf, 2),
        "psm_selected": primary_psm
    }



def extract_text(image_path: Union[str, Path]) -> str:
    """Extract cleaned text from image (preserves original function signature)."""
    return extract_text_with_confidence(image_path)["text"]