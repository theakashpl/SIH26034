import json
from pathlib import Path


RULES_PATH = Path(__file__).parent / "rules.json"


def load_rules() -> list:
    with open(RULES_PATH, "r", encoding="utf-8") as file:
        return json.load(file)


def evaluate_rules(fields: dict) -> list:
    rules = load_rules()
    results = []

    field_map = {
        "LM-001": "product_name",
        "LM-002": "manufacturer",
        "LM-003": "net_quantity",
        "LM-004": "mrp",
        "LM-005": "packed_date",
        "LM-006": "consumer_care",
    }

    for rule in rules:
        field_name = field_map.get(rule["id"])
        value = fields.get(field_name)

        status = "PASS" if value else "FAIL"

        results.append({
            "rule_id": rule["id"],
            "name": rule["name"],
            "severity": rule["severity"],
            "status": status,
            "value": value,
        })

    return results


def calculate_compliance(results: list, ocr_confidence: float = 100) -> dict:
    OCR_REVIEW_THRESHOLD = 75
    total = len(results)
    passed = sum(
        1 for result in results
        if result["status"] == "PASS"
    )
    failed = total - passed

    score = round((passed / total) * 100) if total else 0

    if failed == 0:
        status = "PASS"
    elif ocr_confidence < OCR_REVIEW_THRESHOLD:
        status = "MANUAL REVIEW"
    elif score >= 70:
        status = "MANUAL REVIEW"
    else:
        status = "FAIL"

    return {
        "score": score,
        "status": status,
        "passed": passed,
        "failed": failed,
        "total": total,
    }