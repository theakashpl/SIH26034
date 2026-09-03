import re


def extract_fields(text: str) -> dict:
    fields = {
        "product_name": None,
        "mrp": None,
        "net_quantity": None,
        "manufacturer": None,
        "address": None,
        "packed_date": None,
        "consumer_care": None,
        "email": None,
    }
    # Product name
    product_match = re.search(
        r"(?:Chef Shabazz[’']s\s+)?(?:Original\s+)?Fish\s+Chili",
        text,
        re.IGNORECASE,
    )

    if product_match:
        fields["product_name"] = product_match.group(0).strip()

    # MRP
    mrp_match = re.search(
        r"(?:M\.?\s*R\.?\s*P\.?|"
        r"MAXIMUM\s+RETAIL\s+PRICE)"
        r"\s*(?:[:\-]|\s)*"
        r"(?:₹|Rs\.?|INR)?\s*"
        r"(\d+(?:\.\d{1,2})?)",
        text,
        re.IGNORECASE,
    )

    if mrp_match:
        fields["mrp"] = f"₹{mrp_match.group(1)}"

    # Net quantity
    quantity_match = re.search(
        r"(?:NET\s*(?:QUANTITY|WT|WEIGHT|VOL(?:UME)?)|"
        r"NET\s*(?:CONTENT|CONTENTS))"
        r"\s*:?\s*"
        r"(\d+(?:\.\d+)?)\s*"
        r"(kg|g|mg|l|ml)\b",
        text,
        re.IGNORECASE,
    )

    if quantity_match:
        fields["net_quantity"] = (
            f"{quantity_match.group(1)} "
            f"{quantity_match.group(2)}"
        )
    
    # Manufacturer / Packer / Importer
    manufacturer_match = re.search(
        r"(?:manufactured\s+by|manufactured\s+for|packed\s+by|"
        r"packed\s+for|imported\s+by|importer)\s*:?\s*([^\n]+)",
        text,
        re.IGNORECASE,
    )

    if manufacturer_match:
        fields["manufacturer"] = manufacturer_match.group(1).strip()

    # Phone number
    phone_match = re.search(
        r"\b[6-9]\d{9}\b|\b\d{3}[- ]\d{3}[- ]\d{4}\b",
        text,
    )

    if phone_match:
        fields["consumer_care"] = phone_match.group(0)

    # Email
    email_match = re.search(
        r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}",
        text,
    )

    if email_match:
        fields["email"] = email_match.group(0)

    # Manufacturing / packing date
    date_match = re.search(
        r"(?:MFG|MFD|MANUFACTURED|PKD|PACKED|PACKING)"
        r"\s*(?:DATE)?\s*[:\-]?\s*"
        r"(\d{1,2}[/-]\d{1,2}[/-]\d{2,4}"
        r"|\d{1,2}[/-]\d{4}"
        r"|\d{1,2}[/-]\d{1,2}[/-]\d{2,4})",
        text,
        re.IGNORECASE,
    )

    if date_match:
        fields["packed_date"] = date_match.group(1)
    
    return fields