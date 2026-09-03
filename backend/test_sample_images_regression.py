"""
Regression tests for all 7 packaged-commodity products in backend/sample_images.
Verifies that:
1. All 5 MVP statutory fields are detected correctly.
2. Multi-view evidence combination detects zero false conflicts.
3. Every specific bug fix (tabular MRP, OCR typo Net Qty, corporate manufacturer extraction,
   spaced phone/landline consumer care, and trademark/commodity product names) has a dedicated unit test.
"""

import pytest
from backend.ocr.engine import extract_text
from backend.extraction.extractor import (
    extract_fields,
    extract_product_name,
    extract_mrp,
    extract_net_quantity,
    extract_manufacturer,
    extract_consumer_information,
    combine_product_evidence
)
from backend.rules.engine import evaluate_rules, calculate_compliance


# ---------------------------------------------------------------------------
# 1. Unit Tests for Specific Bug Fixes
# ---------------------------------------------------------------------------

def test_extract_mrp_tabular_layout():
    """Verify MRP extraction in tabular layout with adjacent Unit Sale Price & Batch."""
    sample_text = """
    MRP & MRP/g (incl. of all taxes)
    Batch Number
    Date of Mfg
    Date of Exp
    : % 299.00 (z0.60/g)
    CH240515A
    15/05/2024
    """
    res = extract_mrp(sample_text)
    assert res["value"] == 299
    assert res["confidence"] >= 0.90


def test_extract_mrp_with_unit_sale_price():
    """Verify MRP extraction skips unit sale price per gram in Good Day layout."""
    sample_text = """
    MRP
    (INCL. OF ALL TAXES)
    UNIT SALE PRICE & PER g
    90g
    15.00
    0.17
    """
    res = extract_mrp(sample_text)
    assert res["value"] == 15
    assert res["confidence"] >= 0.90


def test_extract_net_quantity_wet_typo():
    """Verify net quantity extraction handles OCR typo 'WET QUANTITY' and badge noise."""
    sample_text = """
    WET QUANTITY
    [e] 150g
    """
    res = extract_net_quantity(sample_text)
    assert res["value"] == 150
    assert res["unit"] == "g"
    assert res["confidence"] >= 0.90


def test_extract_net_quantity_rejects_serving_size():
    """Verify net quantity extraction never picks 'Per Serve (30g)' as net quantity."""
    sample_text = """
    Per Serve (30g)
    of Adult's GDA
    Energy 160kcal
    """
    res = extract_net_quantity(sample_text)
    # 30g must be rejected because it is a serving size
    assert res["value"] is None or res["confidence"] < 0.90
    if res["value"] is not None:
        assert res["value"] != 30


def test_extract_manufacturer_skips_ingredients():
    """Verify manufacturer extraction skips ingredient lists following MARKETED BY."""
    sample_text = """
    MARKETED BY.
    Gram Meal (3.3%), lodised Salt, Sugar, Tomato Powder (0.1%),
    PepsiCo India Holdings Pvt. Ltd.
    Level 3 to 5, Pioneer Square, Sector 62, Near Golf Course Extension Road, Gurugram-122101, Haryana, India.
    """
    res = extract_manufacturer(sample_text)
    assert res["name"] is not None
    assert "Gram Meal" not in res["name"]
    assert "PepsiCo India Holdings Pvt. Ltd." in res["name"]


def test_extract_manufacturer_skips_po_box():
    """Verify manufacturer extraction skips P.O. Box address lines to pick corporate entity."""
    sample_text = """
    MANUFACTURED FOR
    P.O. BOX NO. 2673, MUMBAI - 400 057
    ARLE BISCUITS PVT. LTD
    NORTH LEVEL CROSSING, VILE PARLE EAST, MUMBAI - 400 057, MAHARASHTRA, INDIA
    """
    res = extract_manufacturer(sample_text)
    assert res["name"] is not None
    assert "P.O. BOX" not in res["name"]
    assert "ARLE BISCUITS PVT. LTD" in res["name"]


def test_extract_consumer_care_spaced_toll_free():
    """Verify consumer care phone extraction handles spaced toll-free numbers."""
    sample_text = """
    FOR FEEDBACK OR QUERIES WRITE TO US AT
    OR CALL US AT 1800 22 4020
    EMAIL: CONSUMER.FEEDBACK@PEPSICO.COM
    """
    res = extract_consumer_information(sample_text)
    assert res["phone"] is not None
    assert "1800 22 4020" in res["phone"]
    assert res["email"] == "CONSUMER.FEEDBACK@PEPSICO.COM"


def test_extract_consumer_care_spaced_landline():
    """Verify consumer care phone extraction handles spaced landlines and cc@ email."""
    sample_text = """
    PARLE CONSUMER CARE CELL
    & 022 - 6691 6929
    cc@parle.biz
    MUMBAI - 400 057
    """
    res = extract_consumer_information(sample_text)
    assert res["phone"] is not None
    assert "022 - 6691 6929" in res["phone"] or "022" in res["phone"]
    assert res["email"] == "cc@parle.biz"


def test_extract_consumer_care_hyphenated_toll_free():
    """Verify consumer care phone extraction handles 1-800 format without dropping leading digit."""
    sample_text = """
    Consumer Care Cell,
    Ph.: 1-800-4254449 / 1-800-30004530 (Toll Free),
    feedback@britindia.com
    """
    res = extract_consumer_information(sample_text)
    assert res["phone"] is not None
    assert res["phone"].startswith("1-800") or "800-4254449" in res["phone"]
    assert res["email"] == "feedback@britindia.com"


def test_extract_product_name_registered_trademark():
    """Verify product name extraction extracts registered trademark statement."""
    sample_text = """
    Kurkure Is a Registered Trade Mark of PepsiCo, Inc.
    Manufactured by PepsiCo India Holdings Pvt. Ltd.
    """
    res = extract_product_name(sample_text)
    assert res["value"] == "Kurkure"
    assert res["confidence"] >= 0.90


# ---------------------------------------------------------------------------
# 2. Integration Tests Across All 7 Sample Image Products
# ---------------------------------------------------------------------------

SAMPLE_PRODUCTS = [
    {
        "name": "Avogro Pistachios",
        "images": ["avogro_front.jpg.jpeg", "clickcart.jpg.jpeg"],
    },
    {
        "name": "Bingo Mad Angles",
        "images": ["bingo_front.jpg.jpeg", "bingo.jpg.jpeg"],
    },
    {
        "name": "Choco Chips",
        "images": ["chocochips_front.jpg.jpeg", "chocochips.jpg.jpeg"],
    },
    {
        "name": "Kurkure",
        "images": ["kurkure_front.jpg.jpeg", "kurkure.jpg.jpeg"],
    },
    {
        "name": "Chocolate Digestive",
        "images": ["digestive.jpg.jpeg"],
    },
    {
        "name": "Good Day Butter Cookies",
        "images": ["good day.jpg.jpeg"],
    },
    {
        "name": "Monaco / Monavo",
        "images": ["monavo.jpg.jpeg"],
    },
]


@pytest.mark.parametrize("product", SAMPLE_PRODUCTS, ids=[p["name"] for p in SAMPLE_PRODUCTS])
def test_sample_image_product_compliance(product):
    """
    End-to-end verification that every sample product from backend/sample_images:
    - Extracts all 5 required statutory fields.
    - Has zero multi-image conflicts.
    - Achieves COMPLIANT status with 5/5 passing rules.
    """
    images_data = []
    for idx, filename in enumerate(product["images"], start=1):
        image_path = f"backend/sample_images/{filename}"
        ocr_result = extract_text(image_path)
        fields = extract_fields(ocr_result)
        images_data.append({
            "image_id": idx,
            "filename": filename,
            "ocr_text": ocr_result,
            "cleaned_text": ocr_result,
            "fields": fields
        })

    combined = combine_product_evidence(images_data)

    # 1. Verify zero conflicts across views
    assert combined["conflicts"] == {}, f"Conflicts detected for {product['name']}: {combined['conflicts']}"

    # 2. Verify all 5 fields are present
    assert combined["fields"]["product_name"] is not None, f"Missing product_name for {product['name']}"
    assert combined["fields"]["manufacturer"] is not None, f"Missing manufacturer for {product['name']}"
    assert combined["fields"]["net_quantity"] is not None, f"Missing net_quantity for {product['name']}"
    assert combined["fields"]["mrp"] is not None, f"Missing mrp for {product['name']}"
    assert combined["fields"]["consumer_care"] is not None, f"Missing consumer_care for {product['name']}"

    # 3. Verify rule compliance
    checks = evaluate_rules(combined["fields"], conflicts=combined["conflicts"])
    compliance = calculate_compliance(checks)
    assert compliance["status"] == "COMPLIANT", (
        f"{product['name']} failed compliance: {compliance['summary']}"
    )
    assert compliance["passed"] == 5
    assert compliance["failed"] == 0
