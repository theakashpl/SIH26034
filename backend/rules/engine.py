import json
from pathlib import Path


RULES_PATH = Path(__file__).parent / "rules.json"


def load_rules() -> list:
    with open(RULES_PATH, "r", encoding="utf-8") as file:
        return json.load(file)


def evaluate_rules(fields: dict, conflicts: dict = None) -> list:
    """
    Evaluates the 5 MVP Legal Metrology rules against extracted product fields.
    Handles missing fields, empty strings, and conflicting evidence.
    """
    if conflicts is None:
        conflicts = {}

    rules = load_rules()
    results = []

    field_map = {
        "LM-001": "product_name",
        "LM-002": "manufacturer",
        "LM-003": "net_quantity",
        "LM-004": "mrp",
        "LM-005": "consumer_care",
    }

    reasons_map = {
        "LM-001": {
            "pass": "Product name was detected.",
            "fail": "Product name was not detected in the uploaded product images.",
            "conflict": "Conflicting product names were detected across the uploaded images."
        },
        "LM-002": {
            "pass": "Manufacturer information was detected.",
            "fail": "Manufacturer information was not detected in the uploaded product images.",
            "conflict": "Conflicting manufacturer details were detected across the uploaded images."
        },
        "LM-003": {
            "pass": "Net quantity was detected.",
            "fail": "Net quantity was not detected in the uploaded product images.",
            "conflict": "Conflicting net quantity values were detected across the uploaded images."
        },
        "LM-004": {
            "pass": "MRP was detected.",
            "fail": "MRP was not detected in the uploaded product images.",
            "conflict": "Conflicting MRP values were detected across the uploaded images."
        },
        "LM-005": {
            "pass": "Consumer care information was detected.",
            "fail": "Consumer care information was not detected in the uploaded product images.",
            "conflict": "Conflicting consumer care information was detected across the uploaded images."
        },
    }

    for rule in rules:
        rule_id = rule["id"]
        field_name = rule.get("field") or field_map.get(rule_id)
        raw_value = fields.get(field_name)

        if field_name == "consumer_care" and not raw_value:
            raw_value = fields.get("consumer_information")

        # Validate that the value is present and non-empty
        is_valid_value = False
        value_str = None
        if raw_value is not None:
            if isinstance(raw_value, str):
                if raw_value.strip():
                    is_valid_value = True
                    value_str = raw_value.strip()
            elif isinstance(raw_value, dict):
                val = raw_value.get("value") or raw_value.get("name") or raw_value.get("phone") or raw_value.get("email")
                if val and str(val).strip():
                    is_valid_value = True
                    value_str = str(val).strip()
            elif isinstance(raw_value, (int, float)):
                is_valid_value = True
                value_str = str(raw_value)

        # Check conflict for this field
        has_conflict = False
        if conflicts:
            conflict_key = field_name
            if conflict_key not in conflicts and field_name == "consumer_care":
                conflict_key = "consumer_information"
            if conflict_key in conflicts and conflicts[conflict_key]:
                has_conflict = True

        reasons = reasons_map.get(rule_id, {})
        if has_conflict:
            status = "FAIL"
            value = None
            reason = reasons.get("conflict", f"Conflicting {rule['name']} values were detected across the uploaded images.")
        elif is_valid_value:
            status = "PASS"
            value = value_str
            reason = reasons.get("pass", f"{rule['name']} was detected.")
        else:
            status = "FAIL"
            value = None
            reason = reasons.get("fail", f"{rule['name']} was not detected in the uploaded product images.")

        results.append({
            "rule_id": rule_id,
            "name": rule["name"],
            "severity": rule.get("severity", "HIGH"),
            "status": status,
            "value": value,
            "reason": reason
        })

    return results


def calculate_compliance(results: list, ocr_confidence: float = 100) -> dict:
    """
    Computes compliance score and final status based on the 5 MVP rules:
    - 5/5 -> 100% COMPLIANT
    - <5/5 or conflicts -> NON_COMPLIANT
    """
    total = len(results)
    passed = sum(1 for r in results if r["status"] == "PASS")
    failed = total - passed

    score = round((passed / total) * 100) if total else 0

    if failed == 0 and total == 5:
        status = "COMPLIANT"
        summary = "COMPLIANT - All required declarations checked by this MVP were detected."
    else:
        status = "NON_COMPLIANT"
        summary = "NON_COMPLIANT - One or more required declarations checked by this MVP are missing or conflicting."

    return {
        "score": score,
        "status": status,
        "passed": passed,
        "failed": failed,
        "total": total,
        "summary": summary
    }