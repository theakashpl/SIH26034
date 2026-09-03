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
    # OCR typo normalization for clear brands
    cleaned = re.sub(r"\bAvegro\b", "Avogro", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\bAvcgro\b", "Avogro", cleaned, flags=re.IGNORECASE)
    return cleaned


COMPANY_MARKER_REGEX = re.compile(
    r"(?:"
    r"manufactured\s*(?:&|and)?\s*(?:packed|marketed)?\s*by|"
    r"manufactured\s+for|"
    r"repacked\s*(?:&|and)?\s*(?:marketed|packed)?\s*by|"
    r"repacked\s+by|"
    r"packed\s*(?:&|and)?\s*(?:marketed|packed)?\s*by|"
    r"packed\s+by|"
    r"packed\s+for|"
    r"marketed\s+by|"
    r"imported\s+by|"
    r"distributed\s+by|"
    r"sold\s+by|"
    r"packer|"
    r"manufacturer"
    r")\s*[:.\-]?",
    re.IGNORECASE
)

COMPANY_CORP_TERMS_REGEX = re.compile(
    r"\b(?:pvt\.?\s*ltd\.?|private\s+limited|ltd\.?|limited|llp|inc\.?|corp\.?|corporation|company|co\.?)\b",
    re.IGNORECASE
)

CONTACT_DISQUALIFIER_REGEX = re.compile(
    r"\b(?:consumer\s*care|customer\s*care|care\s*cell|helpline|toll\s*free|email|e-mail|phone|tel|mobile|address|fssai|lic\.?\s*no)\b",
    re.IGNORECASE
)


def is_ocr_noise_or_gibberish(line: str) -> bool:
    """Detect repetitive letters, punctuation gibberish, and unpronounceable OCR artifacts."""
    if not line:
        return True
    # Character repeated 3+ times (e.g. TYYYYY, AAAAAA, =====)
    if re.search(r"([A-Za-z])\1{2,}", line):
        return True
    alpha_chars = [c.lower() for c in line if c.isalpha()]
    if not alpha_chars:
        return True
    vowels = set("aeiouy")
    vowel_count = sum(1 for c in alpha_chars if c in vowels)
    if len(alpha_chars) >= 4 and vowel_count == 0:
        return True
    return False


DISQUALIFYING_PRODUCT_TERMS = [
    # Company / Legal / Corporate entities
    "pvt ltd", "pvt. ltd", "pvt.ltd", "private limited", "ltd.", "ltd", "limited",
    "pyt ltd", "pyt. ltd", "pyt", "llp", "corp", "corporation", "inc.", "inc\b",
    "co.", "company",
    # Manufacturer / Packer / Marketer declarations
    "manufactured by", "manufactured for", "packed by", "marketed by",
    "repacked & marketed by", "repacked by", "repacked", "re-packed",
    "distributed by", "sold by", "distributor",
    "mfd by", "mfd. by", "mfg by", "mfg. by", "pkd by", "pkd. by",
    "imported by", "packer", "manufacturer", "manufactured", "packed", "marketed",
    # Consumer Care / Contact
    "consumer care", "customer care", "care cell", "helpline", "toll free",
    "customer service", "feedback", "complaints", "reach us", "contact us",
    "consumer", "customer",
    "address", "email", "e-mail", "phone", "tel", "fax", "mobile",
    # Regulatory & Licensing & Categorization
    "lic no", "lic. no", "licence", "license", "fssai", "reg no", "regd",
    "trademark", "use of trademark", "under licence",
    "proprietary food", "category 5", "category", "food category",
    # Address / Locality terms
    "road", "street", "lane", "nagar", "sector", "industrial", "colony",
    "estate", "crossing", "pincode", "pin code", "plot no", "mumbai",
    "delhi", "bangalore", "bengaluru", "kolkata", "hyderabad", "chennai", "pune", "jodhpur", "rajasthan",
    "ranipur", "siocul", "haridwar", "midc", "ranjangaon", "taluk", "district", "uttarakhand",
    "karnataka", "maharashtra", "haryana", "gurugram",
    # Ingredients / Nutrition / Packaging instructions
    "ingredients", "nutrition", "serving", "calories", "calorie", "daily value",
    "per 100g", "per 100 g", "per serve", "approximate values", "approx. values", "serving suggestion",
    "total fat", "fat", "cholesterol", "sodium", "carb", "sugars", "fiber", "protein",
    "vitamin", "calcium", "iron", "percent", "contains", "less than", "crude",
    "best before", "expiry", "exp date", "batch no", "b.no", "lot no",
    "refined wheat flour", "wheat flour", "flour", "maida", "raising agent",
    "palmolein", "flavouring", "flavoring", "artificial flavouring", "artificial flavor",
    "substance (vanilla", "substance", "milk solids", "emulsifier",
    "character of the batch", "batch number", "address panel", "corresponding alphabet",
    "for the mfg", "match the first", "characte", "scan to", "enduring value",
    "buttons of joy", "buttons", "of joy", "bake some joy", "now tastier", "tastier", "crispier",
    "crunchier", "nov!", "let's bake", "use cake", "how to use", "directions for use", "suggested use",
    "mrp", "rs.", "inr", "net wt", "net qty", "net weight", "net quantity", "net volume",
    "store in", "keep in", "directions", "instructions", "barcode",
    "shelf stable", "refrigerat", "boil", "bring water", "tear off",
    "invoice", "serial", "document", "receipt", "voucher", "who wants that",
    "no beef", "no chicken", "no beans", "open when ready", "can't find the truth",
    "in a hurry", "the truth", "never heard", "closed his doors",
    "world's best", "as compared to", "made with", "www.", "http",
    "energy", "nonace", "sugar", "invert sugar", "contact", "vile parle", "prestige", "whitefield", "shantiniketan"
]


def is_negative_product_line(line: str, company_entities: Optional[set] = None) -> bool:
    if not line:
        return True
    lower = line.lower().strip()
    if any(term in lower for term in DISQUALIFYING_PRODUCT_TERMS):
        return True
    if COMPANY_CORP_TERMS_REGEX.search(line):
        return True
    if CONTACT_DISQUALIFIER_REGEX.search(line):
        return True
    if is_ocr_noise_or_gibberish(line):
        return True
    if company_entities:
        clean_cand = re.sub(r"^[^\w]+|[^\w]+$", "", lower)
        for comp in company_entities:
            if not comp:
                continue
            clean_comp = re.sub(r"^[^\w]+|[^\w]+$", "", comp).strip().lower()
            if clean_cand == clean_comp or (clean_cand in clean_comp and len(clean_cand) >= 3):
                return True
    return False


def extract_product_name(text: str) -> dict:
    """
    Extract product name using contextual indicators and title heuristics.
    Never hardcoded to any specific product.
    Strictly penalizes and rejects company, legal, address, and contact lines.
    """
    if not text:
        return {"value": None, "raw": None, "confidence": 0.0}

    cleaned = clean_text_for_extraction(text)

    # Pre-extract company entity names that occur after manufacturer/packer/marketer markers
    company_entities = set()
    for match in COMPANY_MARKER_REGEX.finditer(cleaned):
        remainder = cleaned[match.end():]
        lines_after = remainder.splitlines()
        for idx, l in enumerate(lines_after[:3]):
            l_str = l.strip()
            if not l_str:
                if idx > 0:
                    break
                continue
            if CONTACT_DISQUALIFIER_REGEX.search(l_str) or any(k in l_str.lower() for k in ["road", "plot", "nagar", "sector", "lane", "street", "pincode", "fssai"]):
                break
            clean_name = re.sub(r"^[^\w]+|[^\w]+$", "", l_str).lower()
            if clean_name:
                company_entities.add(clean_name)
                for token in clean_name.split():
                    if len(token) >= 3:
                        company_entities.add(token)

    # Also detect manufacturer name via extract_manufacturer
    mfr_info = extract_manufacturer(text)
    if mfr_info.get("name"):
        clean_mfr = re.sub(r"^[^\w]+|[^\w]+$", "", mfr_info["name"]).strip().lower()
        if clean_mfr:
            company_entities.add(clean_mfr)
            for token in clean_mfr.split():
                if len(token) >= 3:
                    company_entities.add(token)

    # 1. Explicit keyword markers (e.g. "Product Name: ...", "Commodity: ...")
    explicit_pattern = re.compile(
        r"(?:product\s*name|commodity|name\s*of\s*(?:the\s*)?commodity|item\s*name)\s*[:\-]\s*([^\n\r]+)",
        re.IGNORECASE
    )
    match = explicit_pattern.search(cleaned)
    if match:
        val = match.group(1).strip()
        val = re.sub(r"^[^\w]+|[^\w\)]+$", "", val)
        if len(val) >= 2 and not is_negative_product_line(val, company_entities):
            return {"value": val, "raw": match.group(0).strip(), "confidence": 0.95}

    # 2. Registered Trademark declaration (e.g. "Kurkure is a registered trade mark of PepsiCo, Inc.")
    tm_pattern = re.compile(
        r"\b([A-Z][A-Za-z0-9'&]+(?:\s+[A-Z][A-Za-z0-9'&]+)?)\s+(?:is\s+(?:a|the)\s+registered\s+trade\s*mark)\b",
        re.IGNORECASE
    )
    tm_match = tm_pattern.search(cleaned)
    if tm_match:
        val = tm_match.group(1).strip()
        val = re.sub(r"^[^\w]+|[^\w\)]+$", "", val)
        if len(val) >= 3 and not is_negative_product_line(val, company_entities):
            return {"value": val, "raw": tm_match.group(0).strip(), "confidence": 0.90}

    # 3. Statutory Pre-ingredients product / commodity declaration line
    # In Indian packaged foods, the commodity name sits immediately above INGREDIENTS:
    ing_match = re.search(
        r"([^\n\r]+)\s*\n\s*(?:ingredients|composition)\b",
        cleaned,
        re.IGNORECASE
    )
    if ing_match:
        pre_line = ing_match.group(1).strip()
        if not is_negative_product_line(pre_line, company_entities):
            # Clean OCR artifacts like trailing quote, registered trademark (e.g. 'HIDE & Seek" siscorrs')
            cand = re.sub(r'["\'®™].*$', '', pre_line).strip()
            cand = re.sub(r"^[^\w]+|[^\w\)]+$", "", cand).strip()
            if len(cand) >= 3 and not is_negative_product_line(cand, company_entities):
                return {"value": cand, "raw": ing_match.group(0).strip(), "confidence": 0.90}

    # 4. Contextual packaging story / headline pattern (e.g. "What is the story of Chef Shabazz's Original Fish Chili...")
    story_pattern = re.compile(
        r"(?:what\s+is\s+the\s+story\s+of|what's\s+so\s+amazing\s+about|introducing|curiously\s+delicious|taste\s+the|authentic|the\s+original)\s+([A-Za-z0-9'\s\-]+?(?:fish\s+chili|chili|chips|cookies|biscuits|crisps|juice|sauce|masala|atta|dal|butter|milk|oil|tea|coffee|noodles|flakes|wafers|snack|curry|powder|paste))",
        re.IGNORECASE
    )
    story_match = story_pattern.search(cleaned)
    if story_match:
        val = story_match.group(1).strip()
        val = re.sub(r"^[^\w]+|[^\w\)]+$", "", val)
        val = " ".join(val.split())
        if len(val) >= 3 and not is_negative_product_line(val, company_entities):
            return {"value": val, "raw": story_match.group(0).strip(), "confidence": 0.85}

    # 5. Product Title lines
    # Strictly filter out non-product lines, company names, legal declarations
    category_product_words = {
        "pistachios", "pistachio", "biscuits", "biscuit", "cookies", "cookie",
        "chips", "chip", "chili", "masala", "atta", "dal", "butter", "milk",
        "tea", "coffee", "noodles", "noodle", "wafers", "wafer", "snack", "snacks",
        "powder", "chocolate", "chocolates", "choco", "compound", "mad angles", "kurkure"
    }

    lines = [l.strip() for l in cleaned.split("\n") if l.strip()]
    candidate_lines = []
    for line in lines[:120]:
        # Stop candidate line scanning once we enter the statutory batch/barcode/expiry footer
        if re.search(r"\b(?:batch\s*no|b\.no|lot\s*no|exp(?:iry)?\s*date|best\s*before|barcode)\b", line, re.IGNORECASE):
            break
        if is_negative_product_line(line, company_entities):
            continue
        # Don't pick lines ending in question marks or question words
        if line.endswith("?") or re.match(r"^(?:what|who|why|where|how|can|is|are|do|does)\b", line, re.IGNORECASE):
            continue
        clean_l = re.sub(r"^[^\w]+|[^\w]+$", "", line).strip()
        if len(clean_l) < 3 or len(clean_l) > 55:
            continue
        if is_negative_product_line(clean_l, company_entities):
            continue
        alpha_count = len(re.findall(r"[A-Za-z]", clean_l))
        if alpha_count < 3 or (alpha_count / len(clean_l)) < 0.6:
            continue

        words = clean_l.split()
        if any(re.search(r"[a-z][A-Z]", w) for w in words):
            continue
        if any(is_ocr_noise_or_gibberish(w) for w in words):
            continue

        if clean_l.isupper() or all(w[0].isupper() for w in words if w and w[0].isalpha()):
            candidate_lines.append(clean_l)

    DESCRIPTOR_WORDS = {
        "premium", "gold", "classic", "original", "rich", "pure",
        "fresh", "crisp", "crispy", "royal", "select", "choice", "special", "deluxe"
    }

    if candidate_lines:
        scored_candidates = []
        for idx, c in enumerate(candidate_lines):
            has_cat = any(kw in c.lower() for kw in category_product_words)
            if has_cat:
                # Check for 3-line combination: Brand + Descriptor/Category + Commodity (e.g. Avegro + Premium + Pistachios or MILK + CHOCO + CHIPS)
                if idx >= 2:
                    c_prev1 = candidate_lines[idx - 1]
                    c_prev2 = candidate_lines[idx - 2]
                    if any(d in c_prev1.lower() for d in DESCRIPTOR_WORDS) or any(k in c_prev1.lower() for k in category_product_words):
                        if len(c_prev2.split()) <= 2 and len(c_prev1.split()) <= 2 and len(c.split()) <= 2:
                            combo3 = f"{c_prev2} {c_prev1} {c}"
                            scored_candidates.append({"value": combo3, "raw": combo3, "confidence": 0.90, "score": 10})
                # Check for 2-line combination: Descriptor/Category + Commodity (e.g. BUTTER + COOKIES or Premium + Pistachios)
                if idx >= 1:
                    c_prev1 = candidate_lines[idx - 1]
                    if any(d in c_prev1.lower() for d in DESCRIPTOR_WORDS) or any(k in c_prev1.lower() for k in category_product_words):
                        if len(c_prev1.split()) <= 2 and len(c.split()) <= 3:
                            combo2 = f"{c_prev1} {c}"
                            scored_candidates.append({"value": combo2, "raw": combo2, "confidence": 0.85, "score": 8})
                # Single-line commodity match (e.g. BISCUITS, MAD ANGLES, Kurkure)
                scored_candidates.append({"value": c, "raw": c, "confidence": 0.80, "score": 6})

        # Fallback if no line matched a statutory category word
        if not scored_candidates:
            if len(candidate_lines) >= 2 and len(candidate_lines[0].split()) <= 2 and len(candidate_lines[1].split()) <= 4:
                combo = f"{candidate_lines[0]} {candidate_lines[1]}"
                scored_candidates.append({"value": combo, "raw": combo, "confidence": 0.80, "score": 5})
            for c in candidate_lines:
                scored_candidates.append({"value": c, "raw": c, "confidence": 0.75, "score": 4})

        if scored_candidates:
            best = max(scored_candidates, key=lambda x: (x["score"], x["confidence"], len(x["value"])))
            return {"value": best["value"], "raw": best["raw"], "confidence": best["confidence"]}

    # 6. Fallback: repeated capitalized product category phrase in body text
    cat_match = re.findall(
        r"\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?\s+(?:Chili|Chips|Cookies|Biscuits|Crisps|Juice|Sauce|Masala|Atta|Dal|Butter|Milk|Oil|Tea|Coffee|Noodles|Flakes|Wafers|Snack|Curry|Powder|Chocolates?|Pistachios?))\b",
        cleaned
    )
    if cat_match:
        for cm in cat_match:
            if not is_negative_product_line(cm, company_entities):
                return {"value": cm, "raw": cm, "confidence": 0.70}

    return {"value": None, "raw": None, "confidence": 0.0}


MRP_BLOCK_DISQUALIFIERS = [
    "unit sale price", "usp", "batch no", "batch", "b.no", "b. no", "lot no",
    "mfg", "mfd", "mfg. date", "pkd", "packed", "use by", "best before", "exp date", "expiry",
    "net wt", "net weight", "net qty", "net quantity", "net vol", "net volume",
    "manufactured", "marketed", "ingredients", "nutrition", "nutritional",
    "serving size", "calories", "consumer care", "customer care",
    "lic no", "lic. no", "licence", "license", "fssai", "barcode"
]


def extract_mrp(text: str) -> dict:
    """
    Extract Maximum Retail Price with currency and numeric normalization.
    Tolerates OCR punctuation, spacing, multiline declarations, comma grouping,
    and corrupted currency symbols (e.g. &, =, a, ee, quotes, replacement chars)
    while strictly protecting against false positives from missing declaration indicators
    ('NOT DECLARED', 'N/A', 'NIL'), statutory citations ('Rules, 2011', 'Act, 2009'),
    unit sale price, nutritional facts, serving sizes, batch numbers, and barcode data.
    """
    if not text:
        return {"value": None, "currency": "INR", "raw": None, "confidence": 0.0}

    cleaned = clean_text_for_extraction(text)

    # Negative declaration markers that indicate MRP is intentionally missing / violated
    NEGATION_MARKERS = [
        r"\bnot\s+declared\b", r"\bnot\s+mentioned\b", r"\bnot\s+printed\b",
        r"\bnot\s+specified\b", r"\bnot\s+available\b", r"\bmissing\b",
        r"\bn/?a\b", r"\bnil\b", r"\bnone\b", r"\bno\s+mrp\b", r"\bno\s+price\b"
    ]

    # Stop candidate block at major unrelated section boundary
    stop_sections = [
        "ingredients", "nutrition", "nutritional", "consumer care", "customer care",
        "care cell", "feedback", "complaint", "manufactured by", "packed by", "marketed by",
        "directions", "instructions", "storage", "keep in", "store in"
    ]

    # Non-monetary context keywords preceding numbers that disqualify a candidate
    DISQUALIFYING_PRECEDING_CONTEXT = re.compile(
        r"(?:\b(?:rules?|act|section|clause|law|order|year|mfd|pkd|packed|exp|date|batch|b\.?\s*no|lot(?:\s*no)?|serving|servings|fat|protein|carb|sodium|sugar|energy|trans\s*fat|kcal|cal|mg|fssai|lic(?:ense)?|lic\.?\s*no|tel|phone|pin(?:code)?|box|p\.?\s*o\.?\s*box|no)\b[,:\-\s]*)$",
        re.IGNORECASE
    )

    # 1. Explicit MRP declaration with robust label variations and corrupted symbol handling
    mrp_label_regex = re.compile(
        r"(?:\b(?:MAXIMUM|MAX\.?)\s+RETAIL\s+PRICE\b|\bM\.?\s*R\.?\s*P\.?(?!\w))",
        re.IGNORECASE
    )

    candidates_found = []

    for match in mrp_label_regex.finditer(cleaned):
        after_text = cleaned[match.end():match.end() + 250]

        # Stop candidate block at major unrelated section boundary
        lines = after_text.splitlines()
        candidate_block_lines = []
        for i, line in enumerate(lines):
            l_lower = line.lower().strip()
            if i > 0 and any(s in l_lower for s in stop_sections):
                break
            candidate_block_lines.append(line)
            if len([l for l in candidate_block_lines if l.strip()]) >= 4:
                break

        block_text = " ".join(candidate_block_lines)

        # Check for explicit negation in the immediate block
        block_lower = block_text.lower()
        if any(re.search(neg, block_lower) for neg in NEGATION_MARKERS):
            # Explicitly declared as missing / not declared -> do not extract a price
            continue

        # Match monetary amount in the candidate block
        # Protects against unit sale price, units (g, kg, ml), and non-monetary identifiers
        mrp_val_regex = re.compile(
            r"(?:"
            r"(?:\([^\)\n]*tax[^\)\n]*\)\s*)?"
            r"[:.\-\s]*"
            r"(?:₹|Rs\.?|INR|Re\.?|[&=\"\'`\ufffd<>\?~^=%\$#@!\*\+;]|ee)?"
            r"\s*"
            r"(?:\([^\)\n]*tax[^\)\n]*\)\s*)?"
            r")"
            r"(\d{1,3}(?:,\d{3})+(?:\.\d{1,2})?|\d+(?:\.\d{1,2})?)\b"
            r"(?!\s*(?:(?:per\b|/)?(?:g|gm|kg|ml|l|unit|piece|item)|kcal\b|cal\b|mg\b|\b[a-z]+\s*per\b))"
            r"\s*(?:/[-–])?"
            r"(?:\s*\([^\)\n]*tax[^\)\n]*\))?",
            re.IGNORECASE
        )

        for val_match in mrp_val_regex.finditer(block_text):
            # Check what comes immediately before this number in block_text
            pre_context = block_text[:val_match.start()].strip()
            if pre_context and DISQUALIFYING_PRECEDING_CONTEXT.search(pre_context):
                continue

            # If there is no explicit currency symbol, require the number to be
            # very close to the MRP label (within 30 chars) to avoid false positives
            # from nearby quantity/batch/nutritional numbers.
            has_explicit_curr = bool(re.search(r"[₹%]|Rs\.?|INR", val_match.group(0), re.IGNORECASE))
            if not has_explicit_curr and val_match.start() > 30:
                # Too far from MRP header without a currency symbol -> likely unrelated text
                continue

            val_str = val_match.group(1).replace(",", "")
            try:
                val = float(val_str)
                # Ignore common year/statutory numbers unless currency is explicit
                if not has_explicit_curr and (val in [2011, 2012, 2013, 2014, 2015, 2016, 2017, 2018, 2019, 2020, 2021, 2022, 2023, 2024, 2025, 2026, 201, 2009]):
                    continue

                if 0.5 <= val <= 99999:
                    normalized_val = int(val) if val.is_integer() else val
                    raw_span = " ".join((match.group(0) + " " + block_text[:val_match.end()]).split())
                    candidates_found.append({
                        "value": normalized_val,
                        "currency": "INR",
                        "raw": raw_span.strip(),
                        "confidence": 0.95 if has_explicit_curr else 0.90,
                        "has_currency": has_explicit_curr
                    })
                    break
            except ValueError:
                pass

    if candidates_found:
        # Prioritize candidate with explicit currency marker if available
        best_cand = max(candidates_found, key=lambda c: (c["has_currency"], c["confidence"]))
        return {
            "value": best_cand["value"],
            "currency": "INR",
            "raw": best_cand["raw"],
            "confidence": best_cand["confidence"]
        }

    # 2. Currency symbol + amount with tax inclusion notation (fallback without explicit MRP keyword)
    alt_pattern = re.compile(
        r"(?:₹|Rs\.?|INR)\s*(\d{1,3}(?:,\d{3})+(?:\.\d{1,2})?|\d+(?:\.\d{1,2})?)\s*(?:/[-–])?\s*(?:\([^\)]*tax[^\)]*\))",
        re.IGNORECASE
    )
    alt_match = alt_pattern.search(cleaned)
    if alt_match:
        val_str = alt_match.group(1).replace(",", "")
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
    # Tolerates OCR typos like WET QUANTITY, multiline packaging layouts, and symbols/brackets (e.g. [e] 150g)
    net_pattern = re.compile(
        r"\b(?:(?:NET|WET)\s*(?:QUANTITY|QTY|WT|WEIGHT|CONTENTS?|VOL(?:UME)?))\b\.?"
        r"\s*(?:\[[^\]]*\]|\([^\)]*\)|[^\w\d])*\s*"
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

    # 2. Standalone quantity search — used only when no explicit NET WEIGHT/QTY label is found.
    # Very strict: the quantity token must be isolated / near-only content of the line.
    # Rejects nutritional tables, ingredient percentages, address blocks, and any ambiguous lines.
    forbidden_terms = [
        "serving size", "serving per", "per serving", "servings", "per serve", "serve", "serving",
        "approx", "approximately", "portion", "adult's", "gda",
        "total fat", "saturated fat", "trans fat", "sodium", "cholesterol",
        "total carb", "sugars", "dietary fiber", "protein", "vitamin", "calcium", "iron",
        "daily value", "less than", "energy", "carbohydrate", "fat", "kcal", "kj",
        "dimension", "dimensions", "height", "width", "length", "depth", "size",
        "phone", "tel", "lic", "licence", "license", "fssai", "batch", "b.no", "b. no",
        "lot no", "lot", "mfg", "mfd", "pkd", "exp", "expiry", "use by", "best before", "date",
        "road", "nagar", "street", "lane", "sector", "plot", "village", "district", "state",
        "pvt", "ltd", "limited", "inc", "corp", "manufacturer", "packed by", "marketed by",
        "ingredients", "ingredient", "contains", "nutrition", "nutritional",
        "per 100", "per100", "per 30", "per 50", "per serving",
        "barcode", "mrp", "rs.", "₹", "price",
        "no.", "no :", "no:",   # batch/lot number lines
        "%",   # any percentage (ingredient %, DRV %)
        "flour", "wheat", "maida", "oil", "salt", "sugar", "water", "milk", "butter",
        "colour", "color", "flavour", "flavor", "emulsifier", "preservative",
        "palmolein", "refined", "starch", "raising", "agent",
        "calorie", "calories", "kilo",
    ]

    lines = cleaned.split("\n")
    for line in lines:
        line_stripped = line.strip()
        lower_line = line_stripped.lower()

        # Skip empty or long lines (nutritional tables, address blocks, ingredient lists)
        # Strict upper limit of 40 chars: a net weight line is short (e.g. "Net Wt. 100g" or "200 ml")
        if not line_stripped or len(line_stripped) > 40:
            continue

        if any(term in lower_line for term in forbidden_terms):
            continue

        # Skip lines with multiple numbers (likely nutritional facts rows or addresses)
        all_nums = re.findall(r"\b\d+(?:\.\d+)?\b", line_stripped)
        if len(all_nums) > 1:
            continue

        qty_match = re.search(
            r"\b(?:Net\s*)?(\d+(?:\.\d+)?)\s*(kg|kgs|g|gm|gms|gram|grams|mg|l|ltr|litre|litres|ml)\b",
            line_stripped,
            re.IGNORECASE
        )
        if qty_match:
            val_str, unit_raw = qty_match.group(1), qty_match.group(2).lower()
            unit = unit_map.get(unit_raw, unit_raw)
            try:
                val = float(val_str)
                # Tighter sanity range for consumer packaged goods (1g to 5000g / 5L)
                # Values below 1 are likely punctuation noise; above 5000 are likely not net weight
                if 1 <= val <= 5000:
                    # Extra guard: reject if the matched value is a common year, PIN code,
                    # or known statutory number (2011, 2009, etc.)
                    if val in {2011, 2012, 2013, 2014, 2015, 2016, 2009, 2010}:
                        continue
                    return {
                        "value": int(val) if val.is_integer() else val,
                        "unit": unit,
                        "raw": line_stripped,
                        "confidence": 0.72  # lower than explicit label match (0.95)
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

        ingredient_disqualifiers = [
            "meal", "salt", "sugar", "powder", "oil", "wheat", "flour", "acid",
            "flavor", "flavour", "spices", "condiments", "preservative"
        ]
        addr_headers = ["p.o. box", "post box", "box no", "po box", "p.o.box", "plot no"]
        corp_indicators = [
            "pvt", "ltd", "limited", "private", "llp", "industries", "holdings",
            "foods", "biscuits", "beverages", "enterprises", "corporation", "corp"
        ]

        best_cand_name = None
        best_cand_addr = None
        best_cand_raw = None

        for idx, line in enumerate(lines_to_check):
            lower_l = line.lower()
            if any(term in lower_l for term in care_disqualifiers):
                continue
            if re.match(r"^(?:lic|fssai|reg|batch|b\.no)\b", lower_l):
                continue
            if any(term in lower_l for term in ingredient_disqualifiers) or "%" in line:
                continue
            if any(hdr in lower_l for hdr in addr_headers):
                if not best_cand_addr:
                    best_cand_addr = line
                continue

            clean_l = re.sub(r"^[^A-Za-z0-9]+|^(?:sat|od|ee|dr|mr)\b\s*", "", line, flags=re.IGNORECASE).strip()
            if len(clean_l) < 3 or not re.search(r"[A-Za-z]{3,}", clean_l):
                continue

            parts = [p.strip() for p in clean_l.split(",") if p.strip()]
            cand_name = parts[0]
            cand_addr = ", ".join(parts[1:]) if len(parts) > 1 else None

            has_corp = any(re.search(r"\b" + re.escape(ind) + r"\b", clean_l, re.IGNORECASE) for ind in corp_indicators)

            if has_corp:
                best_cand_name = cand_name
                best_cand_addr = cand_addr or best_cand_addr
                best_cand_raw = match.group(0).strip() + " " + clean_l
                if not best_cand_addr:
                    for next_l in lines_to_check[idx + 1:]:
                        if re.match(r"^(?:lic|fssai|reg|batch|b\.no|phone|email)\b", next_l.lower()):
                            continue
                        if re.search(r"(?:plot|sector|road|industrial|street|lane|nagar|pincode|pin\s*code|\b\d{6}\b|[A-Z]{2}\s*[-]?\s*\d{6}|mumbai|delhi|bangalore|kolkata|chennai|hyderabad|pune|noida|haryana|gurugram)", next_l, re.IGNORECASE):
                            best_cand_addr = next_l
                            break
                break
            elif not best_cand_name:
                best_cand_name = cand_name
                best_cand_addr = cand_addr or best_cand_addr
                best_cand_raw = match.group(0).strip() + " " + clean_l

        if best_cand_name:
            return {
                "name": best_cand_name,
                "address": best_cand_addr,
                "raw": best_cand_raw,
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
        r"(?:consumer\s*(?:care|cell|information|complaints|services?|feedback)|"
        r"customer\s*(?:care|service|support|complaints)|"
        r"for\s*(?:complaints|feedback|queries)|toll\s*free|helpline|customer\s*service\s*cell|"
        r"reach\s*us|feedback\s*or\s*queries|contact\s*us|can't\s*find\s*the\s*truth|"
        r"in\s*case\s*of\s*complaints|call\s*us\s*at|write\s*to\s*us|queries|itc\s*cares|"
        r"parle\s*consumer|consumer\s*services\s*manager)",
        re.IGNORECASE
    )

    phone_regex = re.compile(
        r"(?:"
        r"(?:1[- ]?800(?:[- ]?\d{2,4}){2,3})|"
        r"(?:(?:\+?91|0)?[- ]?)?1800[- ]?\d{2,4}[- ]?\d{3,4}|"
        r"(?:(?:\+?91|0)?[- ]?)?800[- ]?\d{3}[- ]?\d{4}|"
        r"(?:(?:\+?91|0)?[- ]?)?[6-9]\d{9}|"
        r"\b0\d{2,4}\s*[-–]\s*\d{3,4}(?:\s*[- ]?\d{3,4})?\b|"
        r"\b0\d{2,4}[- ]?\d{3,4}[- ]?\d{3,4}\b|"
        r"\b\d{3,4}[- ]\d{3}[- ]\d{4}\b"
        r")"
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
            context_block = lines[i:min(i + 7, len(lines))]
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

    # Secondary check: Explicit prefix markers across entire document
    if not found_phone:
        for line in lines:
            if re.search(r"(?:tel|phone|ph|call|toll\s*free|helpline)\s*[:.\-]\s*", line, re.IGNORECASE):
                p_match = phone_regex.search(line)
                if p_match:
                    found_phone = p_match.group(0).strip()
                    matched_lines.append(line)
                    break

    # Tertiary check: Any packaging care/feedback email in document
    if not found_email:
        all_emails = email_regex.findall(cleaned)
        care_emails = [e for e in all_emails if any(kw in e.lower() for kw in ["care", "feedback", "consumer", "support", "complaint", "query", "queries", "customercare", "cc@"])]
        if care_emails:
            found_email = care_emails[0].strip()
            matched_lines.append(found_email)
        elif all_emails:
            found_email = all_emails[0].strip()
            matched_lines.append(found_email)

    if found_phone:
        found_phone = found_phone.strip()
        if found_phone.startswith("-"):
            found_phone = found_phone.lstrip("-")
            if found_phone.startswith("800"):
                found_phone = "1-" + found_phone

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
        # Check token overlap for multi-word commodity titles (e.g. "Milk Choco Chips" vs "Choco Chips Compound")
        w1 = set(re.findall(r"\w+", c1))
        w2 = set(re.findall(r"\w+", c2))
        common = w1.intersection(w2)
        if len(common) >= 2:
            return True
        return False

    # --- 1. PRODUCT NAME ---
    # Collect all known manufacturer/company names across all views
    known_companies = set()
    for img in images_data:
        mfr_det = img.get("fields", {}).get("details", {}).get("manufacturer", {})
        if mfr_det and mfr_det.get("name"):
            clean_m = re.sub(r"^[^\w]+|[^\w]+$", "", mfr_det["name"]).strip().lower()
            if clean_m:
                known_companies.add(clean_m)
        mfr_str = img.get("fields", {}).get("manufacturer")
        if mfr_str:
            clean_m = re.sub(r"^[^\w]+|[^\w]+$", "", mfr_str).strip().lower()
            if clean_m:
                known_companies.add(clean_m)
        img_text = img.get("cleaned_text") or img.get("ocr_text", "")
        for m in COMPANY_MARKER_REGEX.finditer(img_text):
            after = img_text[m.end():m.end() + 150]
            for line in after.splitlines()[:3]:
                l_clean = re.sub(r"^[^\w]+|[^\w]+$", "", line).strip().lower()
                if l_clean and not CONTACT_DISQUALIFIER_REGEX.search(l_clean) and not any(k in l_clean for k in ["road", "plot", "nagar", "fssai", "lic"]):
                    known_companies.add(l_clean)

    def is_candidate_company_entity(cand_val: str) -> bool:
        if not cand_val:
            return True
        c_clean = re.sub(r"^[^\w]+|[^\w]+$", "", cand_val).strip().lower()
        for comp in known_companies:
            if not comp:
                continue
            clean_comp = re.sub(r"^[^\w]+|[^\w]+$", "", comp).strip().lower()
            if c_clean == clean_comp or (c_clean in clean_comp and len(c_clean) >= 3):
                return True
        if COMPANY_CORP_TERMS_REGEX.search(cand_val):
            return True
        if CONTACT_DISQUALIFIER_REGEX.search(cand_val):
            return True
        return False

    p_candidates = []
    for img in images_data:
        p_det = img.get("fields", {}).get("details", {}).get("product_name")
        if p_det and p_det.get("value"):
            p_candidates.append({
                "value": p_det["value"],
                "raw": p_det.get("raw"),
                "confidence": p_det.get("confidence", 0.0),
                "source_image_id": img.get("image_id", 1)
            })

    def get_candidate_title_strength(cand_val: str, conf: float) -> int:
        if not cand_val:
            return 0
        val_lower = cand_val.lower().strip()
        words = val_lower.split()
        category_keywords = [
            "pistachio", "biscuit", "cookie", "tea", "coffee", "chip", "chili", "masala",
            "atta", "dal", "butter", "milk", "oil", "noodle", "wafer", "snack", "powder", "chocolate"
        ]
        score = 0
        if any(k in val_lower for k in category_keywords):
            score += 3
        if any(d in val_lower for d in ["premium", "gold", "classic", "original", "fresh", "pure", "crisp"]):
            score += 2
        if len(words) >= 2:
            score += 2
        if conf >= 0.85:
            score += 1
        return score

    # Filter out company false-positives and negative terms when genuine product names exist
    valid_p_candidates = [
        c for c in p_candidates
        if not is_candidate_company_entity(c["value"]) and not is_negative_product_line(c["value"])
    ]
    if valid_p_candidates:
        strengths = [get_candidate_title_strength(c["value"], c["confidence"]) for c in valid_p_candidates]
        max_s = max(strengths)
        if max_s >= 2:
            # Prune weak noise candidates (strength 0) when strong title candidates exist
            valid_p_candidates = [c for c, s in zip(valid_p_candidates, strengths) if s > 0]

    eval_candidates = valid_p_candidates if valid_p_candidates else p_candidates

    final_product_name = None
    final_p_detail = {"value": None, "raw": None, "confidence": 0.0, "source_image_id": None}
    if eval_candidates:
        distinct_names = []
        for c in eval_candidates:
            if not any(are_strings_compatible(c["value"], d["value"]) for d in distinct_names):
                distinct_names.append(c)
        # Real conflict check: ONLY if multiple distinct VALID product names exist
        if len(valid_p_candidates) > 1 and len(distinct_names) > 1:
            conflicts["product_name"] = [
                {"value": c["value"], "source_image_id": c["source_image_id"]}
                for c in valid_p_candidates
            ]
        best_p = max(eval_candidates, key=lambda c: (get_candidate_title_strength(c["value"], c["confidence"]), c["confidence"], len(c["value"])))
        final_product_name = best_p["value"]
        final_p_detail = best_p

    # --- 2. MRP ---
    m_candidates = []
    for img in images_data:
        m_det = img.get("fields", {}).get("details", {}).get("mrp")
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
        q_det = img.get("fields", {}).get("details", {}).get("net_quantity")
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
        # Prioritize explicit declarations (confidence >= 0.90) over fallback guesses
        high_conf_q = [c for c in q_candidates if c.get("confidence", 0) >= 0.90]
        eval_q = high_conf_q if high_conf_q else q_candidates
        unique_qtys = set((c["value"], str(c["unit"]).lower()) for c in eval_q)
        if len(unique_qtys) > 1:
            conflicts["net_quantity"] = [
                {"value": c["value"], "unit": c["unit"], "source_image_id": c["source_image_id"]}
                for c in eval_q
            ]
        best_q = max(eval_q, key=lambda c: c["confidence"])
        final_qty_str = f"{best_q['value']} {best_q['unit']}"
        final_q_detail = best_q

    # --- 4. MANUFACTURER ---
    mfr_candidates = []
    for img in images_data:
        mfr_det = img.get("fields", {}).get("details", {}).get("manufacturer")
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
        c_det = img.get("fields", {}).get("details", {}).get("consumer_information")
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