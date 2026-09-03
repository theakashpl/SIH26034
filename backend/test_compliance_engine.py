import unittest
from pathlib import Path
import sys

BACKEND_DIR = Path(__file__).parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from rules.engine import evaluate_rules, calculate_compliance, load_rules
from extraction.extractor import combine_product_evidence


class TestComplianceRuleEngine(unittest.TestCase):

    def setUp(self):
        self.complete_fields = {
            "product_name": "EVEREST CHANA MASALA",
            "manufacturer": "Everest Food Products Pvt Ltd",
            "net_quantity": "100 g",
            "mrp": "₹75",
            "consumer_care": "1800-227-888"
        }

    # 1. All 5 fields present -> 100%, COMPLIANT
    def test_01_all_five_fields_present(self):
        checks = evaluate_rules(self.complete_fields)
        self.assertEqual(len(checks), 5)
        for check in checks:
            self.assertEqual(check["status"], "PASS", f"Failed on check: {check['name']}")

        compliance = calculate_compliance(checks)
        self.assertEqual(compliance["score"], 100)
        self.assertEqual(compliance["status"], "COMPLIANT")
        self.assertEqual(compliance["passed"], 5)
        self.assertEqual(compliance["failed"], 0)
        self.assertEqual(compliance["total"], 5)
        self.assertIn("COMPLIANT", compliance["summary"])

    # 2. Product Name missing -> 80%, NON_COMPLIANT
    def test_02_product_name_missing(self):
        fields = dict(self.complete_fields)
        fields["product_name"] = None
        checks = evaluate_rules(fields)
        p_check = [c for c in checks if c["rule_id"] == "LM-001"][0]
        self.assertEqual(p_check["status"], "FAIL")
        self.assertIn("not detected", p_check["reason"])

        compliance = calculate_compliance(checks)
        self.assertEqual(compliance["score"], 80)
        self.assertEqual(compliance["status"], "NON_COMPLIANT")
        self.assertEqual(compliance["passed"], 4)
        self.assertEqual(compliance["failed"], 1)

    # 3. Manufacturer missing -> 80%, NON_COMPLIANT
    def test_03_manufacturer_missing(self):
        fields = dict(self.complete_fields)
        fields["manufacturer"] = None
        checks = evaluate_rules(fields)
        mfr_check = [c for c in checks if c["rule_id"] == "LM-002"][0]
        self.assertEqual(mfr_check["status"], "FAIL")

        compliance = calculate_compliance(checks)
        self.assertEqual(compliance["score"], 80)
        self.assertEqual(compliance["status"], "NON_COMPLIANT")

    # 4. Net Quantity missing -> 80%, NON_COMPLIANT
    def test_04_net_quantity_missing(self):
        fields = dict(self.complete_fields)
        fields["net_quantity"] = None
        checks = evaluate_rules(fields)
        qty_check = [c for c in checks if c["rule_id"] == "LM-003"][0]
        self.assertEqual(qty_check["status"], "FAIL")

        compliance = calculate_compliance(checks)
        self.assertEqual(compliance["score"], 80)
        self.assertEqual(compliance["status"], "NON_COMPLIANT")

    # 5. MRP missing -> 80%, NON_COMPLIANT
    def test_05_mrp_missing(self):
        fields = dict(self.complete_fields)
        fields["mrp"] = None
        checks = evaluate_rules(fields)
        mrp_check = [c for c in checks if c["rule_id"] == "LM-004"][0]
        self.assertEqual(mrp_check["status"], "FAIL")

        compliance = calculate_compliance(checks)
        self.assertEqual(compliance["score"], 80)
        self.assertEqual(compliance["status"], "NON_COMPLIANT")

    # 6. Consumer Information missing -> 80%, NON_COMPLIANT
    def test_06_consumer_information_missing(self):
        fields = dict(self.complete_fields)
        fields["consumer_care"] = None
        checks = evaluate_rules(fields)
        care_check = [c for c in checks if c["rule_id"] == "LM-005"][0]
        self.assertEqual(care_check["status"], "FAIL")

        compliance = calculate_compliance(checks)
        self.assertEqual(compliance["score"], 80)
        self.assertEqual(compliance["status"], "NON_COMPLIANT")

    # 7. Multiple fields missing -> correct score (e.g. 2 missing = 60%, 3 missing = 40%)
    def test_07_multiple_fields_missing(self):
        # 2 missing -> 60%
        fields_2_missing = dict(self.complete_fields)
        fields_2_missing["mrp"] = None
        fields_2_missing["net_quantity"] = None
        checks_2 = evaluate_rules(fields_2_missing)
        comp_2 = calculate_compliance(checks_2)
        self.assertEqual(comp_2["score"], 60)
        self.assertEqual(comp_2["status"], "NON_COMPLIANT")
        self.assertEqual(comp_2["passed"], 3)
        self.assertEqual(comp_2["failed"], 2)

        # 3 missing -> 40%
        fields_3_missing = dict(fields_2_missing)
        fields_3_missing["manufacturer"] = None
        checks_3 = evaluate_rules(fields_3_missing)
        comp_3 = calculate_compliance(checks_3)
        self.assertEqual(comp_3["score"], 40)
        self.assertEqual(comp_3["status"], "NON_COMPLIANT")

    # 8. Empty string field -> FAIL
    def test_08_empty_string_field_fails(self):
        fields = dict(self.complete_fields)
        fields["product_name"] = "   "  # whitespace
        fields["mrp"] = ""             # empty string
        checks = evaluate_rules(fields)

        p_check = [c for c in checks if c["rule_id"] == "LM-001"][0]
        mrp_check = [c for c in checks if c["rule_id"] == "LM-004"][0]

        self.assertEqual(p_check["status"], "FAIL")
        self.assertIsNone(p_check["value"])
        self.assertEqual(mrp_check["status"], "FAIL")
        self.assertIsNone(mrp_check["value"])

    # 9. All fields missing -> 0%, NON_COMPLIANT
    def test_09_all_fields_missing(self):
        empty_fields = {
            "product_name": None,
            "manufacturer": None,
            "net_quantity": None,
            "mrp": None,
            "consumer_care": None
        }
        checks = evaluate_rules(empty_fields)
        for c in checks:
            self.assertEqual(c["status"], "FAIL")

        compliance = calculate_compliance(checks)
        self.assertEqual(compliance["score"], 0)
        self.assertEqual(compliance["status"], "NON_COMPLIANT")
        self.assertEqual(compliance["passed"], 0)
        self.assertEqual(compliance["failed"], 5)

    # 10. Conflicting MRP -> MRP must not PASS, conflict visible, status NON_COMPLIANT
    def test_10_conflicting_mrp_fails_and_prevents_compliant(self):
        conflicts = {
            "mrp": [
                {"value": 50, "source_image_id": 1},
                {"value": 55, "source_image_id": 2}
            ]
        }
        checks = evaluate_rules(self.complete_fields, conflicts=conflicts)
        mrp_check = [c for c in checks if c["rule_id"] == "LM-004"][0]

        self.assertEqual(mrp_check["status"], "FAIL")
        self.assertIsNone(mrp_check["value"])
        self.assertIn("Conflicting MRP values", mrp_check["reason"])

        compliance = calculate_compliance(checks)
        self.assertEqual(compliance["status"], "NON_COMPLIANT")
        self.assertEqual(compliance["score"], 80)

    # 11. Conflicting Net Quantity -> detected and prevents COMPLIANT
    def test_11_conflicting_net_quantity_prevents_compliant(self):
        conflicts = {
            "net_quantity": [
                {"value": 100, "unit": "g", "source_image_id": 1},
                {"value": 200, "unit": "g", "source_image_id": 2}
            ]
        }
        checks = evaluate_rules(self.complete_fields, conflicts=conflicts)
        qty_check = [c for c in checks if c["rule_id"] == "LM-003"][0]

        self.assertEqual(qty_check["status"], "FAIL")
        self.assertIsNone(qty_check["value"])
        self.assertIn("Conflicting net quantity", qty_check["reason"])

        compliance = calculate_compliance(checks)
        self.assertEqual(compliance["status"], "NON_COMPLIANT")
        self.assertEqual(compliance["score"], 80)

    # 12. Four-image product with fields distributed across images -> all five rules PASS, 100%, COMPLIANT
    def test_12_four_image_distributed_all_pass_compliant(self):
        img1 = {"image_id": 1, "cleaned_text": "BRITANNIA GOOD DAY CASHEW COOKIES"}
        img2 = {"image_id": 2, "cleaned_text": "MRP: Rs. 40.00"}
        img3 = {"image_id": 3, "cleaned_text": "Net Quantity: 120 g"}
        img4 = {"image_id": 4, "cleaned_text": "Manufactured by: Britannia Industries Ltd.\nCustomer Service: 1800-425-4449"}

        combined = combine_product_evidence([img1, img2, img3, img4])
        checks = evaluate_rules(combined["fields"], conflicts=combined["conflicts"])

        self.assertEqual(len(checks), 5)
        for check in checks:
            self.assertEqual(check["status"], "PASS", f"Check {check['name']} unexpectedly failed")

        compliance = calculate_compliance(checks)
        self.assertEqual(compliance["score"], 100)
        self.assertEqual(compliance["status"], "COMPLIANT")
        self.assertEqual(compliance["passed"], 5)
        self.assertEqual(compliance["failed"], 0)
        self.assertIn("All required declarations", compliance["summary"])


if __name__ == "__main__":
    unittest.main()
