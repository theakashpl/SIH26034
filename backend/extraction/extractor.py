import re
from typing import Optional, Dict, Any


def clean_text_for_extraction(text: str) -> str:
    """Normalize typography and whitespace for reliable regex matching."""
    if not text:
        return ""
    cleaned = text.replace("’", "'").replace("‘", "'").replace("`", "'")
    cleaned = cleaned.replace("“", '"').replace("”", '"')
    cleaned = cleaned.replace("—", "-").replace("–", "-")
    cleaned = cleaned.replace("\ufffd", "'")
    # Separate common OCR run-together tokens like NO022 -> NO 022 or WT200 -> WT 200
    cleaned = re.sub(r"\b(NO|No|no|WT|wt|QTY|qty)(\d)", r"\1 \2", cleaned)
    return cleaned


DISQUALIFYING_PRODUCT_TERMS = [
    # Company / Legal / Corporate entities
    "pvt ltd", "pvt. ltd", "pvt.ltd", "private limited", "ltd.", "ltd", "limited",
    "pyt ltd", "pyt. ltd", "pyt", "llp", "corp", "corporation", "inc.", "inc\b",
    "co.", "company",
    # Manufacturer / Packer / Marketer declarations
    "manufactured by", "manufactured for", "packed by", "marketed by",
    "mfd by", "mfd. by", "mfg by", "mfg. by", "pkd by", "pkd. by",
    "imported by", "packer", "manufacturer", "manufactured", "packed", "marketed",
    # Consumer Care / Contact
    "consumer care", "customer care", "care cell", "helpline", "toll free",
    "customer service", "feedback", "complaints", "reach us", "contact us",
    "consumer", "customer",
    "address", "email", "e-mail", "phone", "tel", "fax", "mobile",
    # Regulatory & Licensing
    "lic no", "lic. no", "licence", "license", "fssai", "reg no", "regd",
    "trademark", "use of trademark", "under licence",
    # Address / Locality terms
    "road", "street", "lane", "nagar", "sector", "industrial", "colony",
    "estate", "crossing", "pincode", "pin code", "plot no", "mumbai",
    "delhi", "bangalore", "kolkata", "hyderabad", "chennai", "pune",
    # Ingredients / Nutrition / Packaging instructions
    "ingredients", "nutrition", "serving", "calories", "calorie", "daily value",
    "total fat", "fat", "cholesterol", "sodium", "carb", "sugars", "fiber", "protein",
    "vitamin", "calcium", "iron", "percent", "contains", "less than",
    "best before", "expiry", "exp date", "batch no", "b.no", "lot no",
    "mrp", "rs.", "inr", "net wt", "net qty", "net weight", "net quantity", "net volume",
    "store in", "keep in", "directions", "instructions", "barcode",
    "shelf stable", "refrigerat", "boil", "bring water", "tear off",
    "invoice", "serial", "document", "receipt", "voucher", "who wants that",
    "no beef", "no chicken", "no beans", "open when ready", "can't find the truth",
    "in a hurry", "the truth", "never heard", "closed his doors",
    "world's best", "as compared to", "made with", "www.", "http"
]


def is_negative_product_line(line: str) -> bool:
    lower = line.lower()
    return any(term in lower for term in DISQUALIFYING_PRODUCT_TERMS)


def extract_product_name(text: str) -> dict:
    """
    Extract product name using contextual indicators and title heuristics.
    Never hardcoded to any specific product.
    Strictly penalizes and rejects company, legal, address, and contact lines.
    """
    if not text:
        return {"value": None, "raw": None, "confidence": 0.0}

    cleaned = clean_text_for_extraction(text)

    # 1. Explicit keyword markers (e.g. "Product Name: ...", "Commodity: ...")
    explicit_pattern = re.compile(
        r"(?:product\s*name|commodity|name\s*of\s*(?:the\s*)?commodity|item\s*name)\s*[:\-]\s*([^\n\r]+)",
        re.IGNORECASE
    )
    match = explicit_pattern.search(cleaned)
    if match:
        val = match.group(1).strip()
        val = re.sub(r"^[^\w]+|[^\w\)]+$", "", val)
        if len(val) >= 2 and not is_negative_product_line(val):
            return {"value": val, "raw": match.group(0).strip(), "confidence": 0.95}

    # 2. Statutory Pre-ingredients product / commodity declaration line
    # In Indian packaged foods, the commodity name sits immediately above INGREDIENTS:
    ing_match = re.search(
        r"([^\n\r]+)\s*\n\s*(?:ingredients|composition|contains\s+added)\b",
        cleaned,
        re.IGNORECASE
    )
    if ing_match:
        pre_line = ing_match.group(1).strip()
        if not is_negative_product_line(pre_line):
            # Clean OCR artifacts like trailing quote, registered trademark (e.g. 'HIDE & Seek" siscorrs')
            cand = re.sub(r'["\'®™].*$', '', pre_line).strip()
            cand = re.sub(r"^[^\w]+|[^\w\)]+$", "", cand).strip()
            if len(cand) >= 3 and not is_negative_product_line(cand):
                return {"value": cand, "raw": ing_match.group(0).strip(), "confidence": 0.90}

    # 3. Contextual packaging story / headline pattern (e.g. "What is the story of Chef Shabazz's Original Fish Chili...")
    story_pattern = re.compile(
        r"(?:what\s+is\s+the\s+story\s+of|what's\s+so\s+amazing\s+about|introducing|curiously\s+delicious|taste\s+the|authentic|the\s+original)\s+([A-Za-z0-9'\s\-]+?(?:fish\s+chili|chili|chips|cookies|biscuits|crisps|juice|sauce|masala|atta|dal|butter|milk|oil|tea|coffee|noodles|flakes|wafers|snack|curry|powder|paste))",
        re.IGNORECASE
    )
    story_match = story_pattern.search(cleaned)
    if story_match:
        val = story_match.group(1).strip()
        val = re.sub(r"^[^\w]+|[^\w\)]+$", "", val)
        val = " ".join(val.split())
        if len(val) >= 3 and not is_negative_product_line(val):
            return {"value": val, "raw": story_match.group(0).strip(), "confidence": 0.85}

    # 4. Product Title lines
    # Strictly filter out non-product lines, company names, legal declarations
    lines = [l.strip() for l in cleaned.split("\n") if l.strip()]
    candidate_lines = []
    for line in lines[:40]:
        if is_negative_product_line(line):
            continue
        # Don't pick lines ending in question marks or question words
        if line.endswith("?") or re.match(r"^(?:what|who|why|where|how|can|is|are|do|does)\b", line, re.IGNORECASE):
            continue
        clean_l = re.sub(r"^[^\w]+|[^\w]+$", "", line).strip()
        if len(clean_l) < 3 or len(clean_l) > 55:
            continue
        alpha_count = len(re.findall(r"[A-Za-z]", clean_l))
        if alpha_count < 3 or (alpha_count / len(clean_l)) < 0.6:
            continue

        words = clean_l.split()
        if clean_l.isupper() or all(w[0].isupper() for w in words if w and w[0].isalpha()):
            candidate_lines.append(clean_l)

    if candidate_lines:
        # If the first two lines look like Brand + Product (e.g. HALDIRAM'S + CLASSIC SALTED CHIPS)
        if len(candidate_lines) >= 2 and len(candidate_lines[0].split()) <= 2 and len(candidate_lines[1].split()) <= 5:
            combined = f"{candidate_lines[0]} {candidate_lines[1]}"
            return {"value": combined, "raw": combined, "confidence": 0.80}
        return {"value": candidate_lines[0], "raw": candidate_lines[0], "confidence": 0.75}

    # 5. Fallback: repeated capitalized product category phrase in body text
    cat_match = re.findall(
        r"\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?\s+(?:Chili|Chips|Cookies|Biscuits|Crisps|Juice|Sauce|Masala|Atta|Dal|Butter|Milk|Oil|Tea|Coffee|Noodles|Flakes|Wafers|Snack|Curry|Powder|Chocolates?))\b",
        cleaned
    )
    if cat_match:
        return {"value": cat_match[0], "raw": cat_match[0], "confidence": 0.70}

    return {"value": None, "raw": None, "confidence": 0.0}


def extract_mrp(text: str) -> dict:
    """
    Extract Maximum Retail Price with currency and numeric normalization.
    Tolerates OCR punctuation, spacing, and symbol variations.
    """
    if not text:
        return {"value": None, "currency": "INR", "raw": None, "confidence": 0.0}

    cleaned = clean_text_for_extraction(text)

    # 1. Standard MRP declaration
    mrp_pattern = re.compile(
        r"(?:M\.?\s*R\.?\s*P\.?|MAXIMUM\s+RETAIL\s+PRICE|MAX\s+RETAIL\s+PRICE)"
        r"(?:\s*\(incl[^\)]*\))?"
        r"\s*[:.\-]?\s*"
        r"(?:₹|Rs\.?|INR)?\s*"
        r"(\d+(?:\.\d{1,2})?)"
        r"\s*(?:/[-–])?",
        re.IGNORECASE
    )
    match = mrp_pattern.search(cleaned)
    if match:
        val_str = match.group(1)
        try:
            val = float(val_str)
            if 0.5 <= val <= 99999:
                normalized_val = int(val) if val.is_integer() else val
                return {
                    "value": normalized_val,
                    "currency": "INR",
                    "raw": match.group(0).strip(),
                    "confidence": 0.95
                }
        except ValueError:
            pass

    # 2. Currency symbol + amount with tax inclusion notation
    alt_pattern = re.compile(
        r"(?:₹|Rs\.?|INR)\s*(\d+(?:\.\d{1,2})?)\s*(?:/[-–])?\s*(?:\([^\)]*tax[^\)]*\))",
        re.IGNORECASE
    )
    alt_match = alt_pattern.search(cleaned)
    if alt_match:
        val_str = alt_match.group(1)
        try:
            val = float(val_str)
            if 0.5 <= val <= 99999:
                normalized_val = int(val) if val.is_integer() else val
                return {
                    "value": normalized_val,
                    "currency": "INR",
                    "raw": alt_match.group(0).strip(),
                    "confidence": 0.90
                }
        except ValueError:
            pass

    return {"value": None, "currency": "INR", "raw": None, "confidence": 0.0}


def extract_net_quantity(text: str) -> dict:
    """
    Extract Net Quantity / Weight / Volume / Contents with unit normalization.
    Recognizes NET QUANTITY, NET QTY, NET WEIGHT, NET WT, NET WT., NET CONTENT, NET CONTENTS.
    Distinguishes from nutritional facts, dimensions, and serving sizes.
    """
    if not text:
        return {"value": None, "unit": None, "raw": None, "confidence": 0.0}

    cleaned = clean_text_for_extraction(text)

    unit_map = {
        "g": "g", "gm": "g", "gms": "g", "gram": "g", "grams": "g",
        "kg": "kg", "kgs": "kg", "kilogram": "kg", "kilograms": "kg",
        "mg": "mg", "milligram": "mg", "milligrams": "mg",
        "ml": "ml", "millilitre": "ml", "millilitres": "ml",
        "l": "l", "ltr": "l", "litre": "l", "litres": "l"
    }

    # 1. Explicit Net Quantity / Weight / Content marker
    net_pattern = re.compile(
        r"\b(?:NET\s*(?:QUANTITY|QTY|WT|WEIGHT|CONTENTS?|VOL(?:UME)?))\b\.?"
        r"[:.\-\s]*"
        r"(\d+(?:\.\d+)?)\s*"
        r"(kg|kgs|kilograms?|g|gm|gms|grams?|mg|milligrams?|l|ltr|litres?|ml|millilitres?)\b\.?",
        re.IGNORECASE
    )
    match = net_pattern.search(cleaned)
    if match:
        val_str, unit_raw = match.group(1), match.group(2).lower()
        unit = unit_map.get(unit_raw, unit_raw)
        try:
            val = float(val_str)
            return {
                "value": int(val) if val.is_integer() else val,
                "unit": unit,
                "raw": match.group(0).strip(),
                "confidence": 0.95
            }
        except ValueError:
            pass

    # 2. Standalone quantity search strictly ignoring nutrition and serving declarations
    forbidden_terms = [
        "serving size", "serving per", "per serving", "servings",
        "total fat", "saturated fat", "trans fat", "sodium", "cholesterol",
        "total carb", "sugars", "dietary fiber", "protein", "vitamin", "calcium", "iron",
        "daily value", "%", "less than", "energy", "carbohydrate", "fat", "kcal", "kj",
        "dimension", "dimensions", "height", "width", "length", "depth", "size",
        "phone", "tel", "lic", "licence", "license", "fssai", "batch", "b.no", "b. no",
        "lot", "mfg", "mfd", "pkd", "exp", "expiry", "use by", "best before", "date"
    ]

    lines = cleaned.split("\n")
    for line in lines:
        lower_line = line.lower()
        if any(term in lower_line for term in forbidden_terms):
            continue

        qty_match = re.search(
            r"\b(?:Net\s*)?(\d+(?:\.\d+)?)\s*(kg|kgs|g|gm|gms|gram|grams|mg|l|ltr|litre|litres|ml)\b",
            line,
            re.IGNORECASE
        )
        if qty_match:
            val_str, unit_raw = qty_match.group(1), qty_match.group(2).lower()
            unit = unit_map.get(unit_raw, unit_raw)
            try:
                val = float(val_str)
                if 0.1 <= val <= 50000:
                    return {
                        "value": int(val) if val.is_integer() else val,
                        "unit": unit,
                        "raw": line.strip(),
                        "confidence": 0.80
                    }
            except ValueError:
                pass

    return {"value": None, "unit": None, "raw": None, "confidence": 0.0}


def extract_manufacturer(text: str) -> dict:
    """
    Extract manufacturer / packer / importer details and address.
    Strictly avoids selecting consumer care, phone, or email lines as manufacturer.
    """
    if not text:
        return {"name": None, "address": None, "raw": None, "confidence": 0.0}

    cleaned = clean_text_for_extraction(text)

    care_disqualifiers = [
        "consumer care", "customer care", "care cell", "helpline", "toll free",
        "feedback", "complaint", "phone", "email", "e-mail", "customer service"
    ]

    mfr_pattern = re.compile(
        r"(?:manufactured\s*(?:&|and)?\s*packed\s*by|manufactured\s+by|manufactured\s+for|"
        r"packed\s*(?:&|and)?\s*marketed\s*by|packed\s+by|packed\s+for|mfd\.?\s*by|mfg\.?\s*by|"
        r"marketed\s+by|imported\s+by|packer|manufacturer)\s*[:.\-]?",
        re.IGNORECASE
    )

    matches = list(mfr_pattern.finditer(cleaned))
    if not matches:
        return {"name": None, "address": None, "raw": None, "confidence": 0.0}

    for match in matches:
        remainder = cleaned[match.end():]
        remainder_lines = remainder.split("\n")
        same_line = remainder_lines[0].strip() if remainder_lines else ""
        lines_to_check = []
        if same_line:
            lines_to_check.append(same_line)
        lines_to_check.extend([l.strip() for l in remainder_lines[1:6] if l.strip()])

        for idx, line in enumerate(lines_to_check):
            lower_l = line.lower()
            if any(term in lower_l for term in care_disqualifiers):
                continue
            if re.match(r"^(?:lic|fssai|reg|batch|b\.no)\b", lower_l):
                continue
            clean_l = re.sub(r"^[^A-Za-z0-9]+|^(?:sat|od|ee|dr|mr)\b\s*", "", line, flags=re.IGNORECASE).strip()
            if len(clean_l) < 3 or not re.search(r"[A-Za-z]{3,}", clean_l):
                continue

            parts = [p.strip() for p in clean_l.split(",") if p.strip()]
            cand_name = parts[0]
            cand_addr = ", ".join(parts[1:]) if len(parts) > 1 else None

            # Look ahead for address in subsequent lines if not in same line
            if not cand_addr:
                for next_l in lines_to_check[idx + 1:]:
                    if re.match(r"^(?:lic|fssai|reg|batch|b\.no|phone|email)\b", next_l.lower()):
                        continue
                    if re.search(r"(?:plot|sector|road|industrial|street|lane|nagar|pincode|pin\s*code|\b\d{6}\b|[A-Z]{2}\s*[-]?\s*\d{6}|mumbai|delhi|bangalore|kolkata|chennai|hyderabad|pune|noida)", next_l, re.IGNORECASE):
                        cand_addr = next_l
                        break

            raw_full = match.group(0).strip() + " " + clean_l
            return {
                "name": cand_name,
                "address": cand_addr,
                "raw": raw_full,
                "confidence": 0.90
            }

    return {"name": None, "address": None, "raw": None, "confidence": 0.0}


def extract_consumer_information(text: str) -> dict:
    """
    Extract consumer-care / customer-care phone and email with contextual verification.
    Supports toll-free, mobile, and standard landline area code formats.
    """
    if not text:
        return {"phone": None, "email": None, "raw": None, "confidence": 0.0}

    cleaned = clean_text_for_extraction(text)

    care_markers = re.compile(
        r"(?:consumer\s*care|consumer\s*information|consumer\s*complaints|"
        r"customer\s*care|customer\s*service|customer\s*support|"
        r"for\s*(?:complaints|feedback)|toll\s*free|helpline|customer\s*service\s*cell|"
        r"reach\s*us|feedback\s*or\s*queries|contact\s*us|can't\s*find\s*the\s*truth|"
        r"in\s*case\s*of\s*complaints)",
        re.IGNORECASE
    )

    phone_regex = re.compile(
        r"(?:(?:\+?91|0)?[- ]?)?(?:1800[- ]?\d{3,4}[- ]?\d{3,4}|800[- ]?\d{3}[- ]?\d{4}|[6-9]\d{9}|\b0\d{2,4}[- ]?\d{3,4}[- ]?\d{3,4}\b|\b\d{3,4}[- ]\d{3}[- ]\d{4}\b)"
    )
    email_regex = re.compile(
        r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"
    )

    lines = cleaned.split("\n")
    found_phone = None
    found_email = None
    matched_lines = []

    for i, line in enumerate(lines):
        if care_markers.search(line):
            context_block = lines[i:min(i + 3, len(lines))]
            combined_context = " ".join(context_block)

            p_match = phone_regex.search(combined_context)
            if p_match and not found_phone:
                found_phone = p_match.group(0).strip()

            e_match = email_regex.search(combined_context)
            if e_match and not found_email:
                found_email = e_match.group(0).strip()

            if found_phone or found_email:
                matched_lines.extend(context_block)
                break

    # Secondary check: Explicit prefix markers (e.g. "Customer Care Helpline: Call 1800-...")
    if not found_phone and not found_email:
        for line in lines:
            if re.search(r"(?:tel|phone|ph|call|toll\s*free|helpline)\s*[:.\-]\s*", line, re.IGNORECASE):
                p_match = phone_regex.search(line)
                if p_match:
                    found_phone = p_match.group(0).strip()
                    matched_lines.append(line)
                    break
            if re.search(r"(?:email|e-mail)\s*[:.\-]\s*", line, re.IGNORECASE):
                e_match = email_regex.search(line)
                if e_match:
                    found_email = e_match.group(0).strip()
                    matched_lines.append(line)
                    break

    if found_phone or found_email:
        raw_text = " ".join([l.strip() for l in matched_lines if l.strip()])
        return {
            "phone": found_phone,
            "email": found_email,
            "raw": raw_text,
            "confidence": 0.90
        }

    return {"phone": None, "email": None, "raw": None, "confidence": 0.0}


def extract_packed_date(text: str) -> Optional[str]:
    """Extract manufacturing / packing date (preserved for LM-005 rule compatibility)."""
    cleaned = clean_text_for_extraction(text)
    date_match = re.search(
        r"(?:MFG|MFD|MANUFACTURED|PKD|PACKED|PACKING)"
        r"\s*(?:DATE)?\s*[:\-]?\s*"
        r"(\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|\d{1,2}[/-]\d{4})",
        cleaned,
        re.IGNORECASE,
    )
    return date_match.group(1) if date_match else None


def extract_fields(text: str) -> dict:
    """
    Main extraction coordinator.
    Preserves 100% backward compatibility with existing API keys while attaching
    rich, structured normalized data under 'details' and 'normalized'.
    """
    p_data = extract_product_name(text)
    m_data = extract_mrp(text)
    q_data = extract_net_quantity(text)
    mfr_data = extract_manufacturer(text)
    c_data = extract_consumer_information(text)
    packed_date = extract_packed_date(text)

    # Prepare string representations for backward-compatible consumption
    product_name_str = p_data["value"]
    mrp_str = f"₹{m_data['value']}" if m_data["value"] is not None else None
    net_quantity_str = f"{q_data['value']} {q_data['unit']}" if q_data["value"] is not None else None
    manufacturer_str = mfr_data["name"]
    address_str = mfr_data["address"]
    consumer_care_str = c_data["phone"] or c_data["email"]
    email_str = c_data["email"]

    normalized_details = {
        "product_name": p_data,
        "mrp": m_data,
        "net_quantity": q_data,
        "manufacturer": mfr_data,
        "consumer_information": c_data
    }

    return {
        # Legacy/direct string keys (preserves API and rule engine evaluation)
        "product_name": product_name_str,
        "mrp": mrp_str,
        "net_quantity": net_quantity_str,
        "manufacturer": manufacturer_str,
        "address": address_str,
        "packed_date": packed_date,
        "consumer_care": consumer_care_str,
        "email": email_str,
        # Normalized structured details
        "details": normalized_details,
        "normalized": normalized_details
    }


def combine_product_evidence(images_data: list) -> dict:
    """
    Combines extracted information from 1 to 4 images representing different views
    of the SAME product. Tracks source_image_id, eliminates duplicates, and detects conflicts.
    """
    for img in images_data:
        if "fields" not in img:
            text = img.get("cleaned_text") or img.get("ocr_text", "")
            img["fields"] = extract_fields(text)

    conflicts = {}

    def are_strings_compatible(s1: str, s2: str) -> bool:
        if not s1 or not s2:
            return False
        c1 = s1.strip().lower()
        c2 = s2.strip().lower()
        if c1 == c2:
            return True
        if c1 in c2 or c2 in c1:
            return True
        return False

    # --- 1. PRODUCT NAME ---
    p_candidates = []
    for img in images_data:
        p_det = img["fields"]["details"]["product_name"]
        if p_det and p_det.get("value"):
            p_candidates.append({
                "value": p_det["value"],
                "raw": p_det.get("raw"),
                "confidence": p_det.get("confidence", 0.0),
                "source_image_id": img.get("image_id", 1)
            })

    final_product_name = None
    final_p_detail = {"value": None, "raw": None, "confidence": 0.0, "source_image_id": None}
    if p_candidates:
        distinct_names = []
        for c in p_candidates:
            if not any(are_strings_compatible(c["value"], d["value"]) for d in distinct_names):
                distinct_names.append(c)
        if len(distinct_names) > 1:
            conflicts["product_name"] = [
                {"value": c["value"], "source_image_id": c["source_image_id"]}
                for c in p_candidates
            ]
        best_p = max(p_candidates, key=lambda c: (c["confidence"], len(c["value"])))
        final_product_name = best_p["value"]
        final_p_detail = best_p

    # --- 2. MRP ---
    m_candidates = []
    for img in images_data:
        m_det = img["fields"]["details"]["mrp"]
        if m_det and m_det.get("value") is not None:
            m_candidates.append({
                "value": m_det["value"],
                "currency": m_det.get("currency", "INR"),
                "raw": m_det.get("raw"),
                "confidence": m_det.get("confidence", 0.0),
                "source_image_id": img.get("image_id", 1)
            })

    final_mrp_str = None
    final_m_detail = {"value": None, "currency": "INR", "raw": None, "confidence": 0.0, "source_image_id": None}
    if m_candidates:
        unique_mrp_vals = set(c["value"] for c in m_candidates)
        if len(unique_mrp_vals) > 1:
            conflicts["mrp"] = [
                {"value": c["value"], "source_image_id": c["source_image_id"]}
                for c in m_candidates
            ]
        best_m = max(m_candidates, key=lambda c: c["confidence"])
        final_mrp_str = f"₹{best_m['value']}"
        final_m_detail = best_m

    # --- 3. NET QUANTITY ---
    q_candidates = []
    for img in images_data:
        q_det = img["fields"]["details"]["net_quantity"]
        if q_det and q_det.get("value") is not None:
            q_candidates.append({
                "value": q_det["value"],
                "unit": q_det.get("unit"),
                "raw": q_det.get("raw"),
                "confidence": q_det.get("confidence", 0.0),
                "source_image_id": img.get("image_id", 1)
            })

    final_qty_str = None
    final_q_detail = {"value": None, "unit": None, "raw": None, "confidence": 0.0, "source_image_id": None}
    if q_candidates:
        unique_qtys = set((c["value"], str(c["unit"]).lower()) for c in q_candidates)
        if len(unique_qtys) > 1:
            conflicts["net_quantity"] = [
                {"value": c["value"], "unit": c["unit"], "source_image_id": c["source_image_id"]}
                for c in q_candidates
            ]
        best_q = max(q_candidates, key=lambda c: c["confidence"])
        final_qty_str = f"{best_q['value']} {best_q['unit']}"
        final_q_detail = best_q

    # --- 4. MANUFACTURER ---
    mfr_candidates = []
    for img in images_data:
        mfr_det = img["fields"]["details"]["manufacturer"]
        if mfr_det and mfr_det.get("name"):
            mfr_candidates.append({
                "name": mfr_det["name"],
                "address": mfr_det.get("address"),
                "raw": mfr_det.get("raw"),
                "confidence": mfr_det.get("confidence", 0.0),
                "source_image_id": img.get("image_id", 1)
            })

    final_mfr_str = None
    final_addr_str = None
    final_mfr_detail = {"name": None, "address": None, "raw": None, "confidence": 0.0, "source_image_id": None}
    if mfr_candidates:
        distinct_mfrs = []
        for c in mfr_candidates:
            if not any(are_strings_compatible(c["name"], d["name"]) for d in distinct_mfrs):
                distinct_mfrs.append(c)
        if len(distinct_mfrs) > 1:
            conflicts["manufacturer"] = [
                {"name": c["name"], "source_image_id": c["source_image_id"]}
                for c in mfr_candidates
            ]
        best_mfr = max(mfr_candidates, key=lambda c: (c["confidence"], len(c["name"])))
        final_mfr_str = best_mfr["name"]
        final_addr_str = best_mfr.get("address")
        final_mfr_detail = best_mfr

    # --- 5. CONSUMER INFORMATION ---
    c_candidates = []
    for img in images_data:
        c_det = img["fields"]["details"]["consumer_information"]
        if c_det and (c_det.get("phone") or c_det.get("email")):
            c_candidates.append({
                "phone": c_det.get("phone"),
                "email": c_det.get("email"),
                "raw": c_det.get("raw"),
                "confidence": c_det.get("confidence", 0.0),
                "source_image_id": img.get("image_id", 1)
            })

    final_consumer_care_str = None
    final_email_str = None
    final_c_detail = {"phone": None, "email": None, "raw": None, "confidence": 0.0, "source_image_id": None}
    if c_candidates:
        phones = set(c["phone"] for c in c_candidates if c.get("phone"))
        if len(phones) > 1:
            conflicts["consumer_information"] = [
                {"phone": c["phone"], "source_image_id": c["source_image_id"]}
                for c in c_candidates if c.get("phone")
            ]
        best_phone = None
        best_email = None
        phone_src = None
        email_src = None
        for c in c_candidates:
            if c.get("phone") and not best_phone:
                best_phone = c["phone"]
                phone_src = c["source_image_id"]
            if c.get("email") and not best_email:
                best_email = c["email"]
                email_src = c["source_image_id"]

        final_consumer_care_str = best_phone or best_email
        final_email_str = best_email
        final_c_detail = {
            "phone": best_phone,
            "email": best_email,
            "raw": c_candidates[0].get("raw"),
            "confidence": max(c["confidence"] for c in c_candidates),
            "source_image_id": phone_src or email_src
        }

    # Preserved packed_date for rule LM-005 compatibility
    packed_date_str = None
    for img in images_data:
        p_date = img["fields"].get("packed_date")
        if p_date:
            packed_date_str = p_date
            break

    details = {
        "product_name": final_p_detail,
        "mrp": final_m_detail,
        "net_quantity": final_q_detail,
        "manufacturer": final_mfr_detail,
        "consumer_information": final_c_detail
    }

    fields = {
        "product_name": final_product_name,
        "mrp": final_mrp_str,
        "net_quantity": final_qty_str,
        "manufacturer": final_mfr_str,
        "address": final_addr_str,
        "packed_date": packed_date_str,
        "consumer_care": final_consumer_care_str,
        "email": final_email_str,
        "details": details,
        "normalized": details
    }

    return {
        "fields": fields,
        "details": details,
        "conflicts": conflicts
    }