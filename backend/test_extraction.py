import unittest
from pathlib import Path
import sys

# Ensure backend directory is in path
BACKEND_DIR = Path(__file__).parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from extraction.extractor import (
    extract_product_name,
    extract_mrp,
    extract_net_quantity,
    extract_manufacturer,
    extract_consumer_information,
    extract_fields
)
from ocr.engine import extract_text_with_confidence


class TestInformationExtraction(unittest.TestCase):

    def test_01_all_five_fields_present_chips(self):
        text = """
        HALDIRAM'S
        CLASSIC SALTED POTATO CHIPS
        Net Quantity: 100 g
        MRP ₹ 30.00 (incl. of all taxes)
        Manufactured by: Haldiram Snacks Pvt. Ltd.
        Plot No. 12, Sector 58, Noida, UP 201301
        Consumer Care: For feedback or complaints, contact 1800-102-4567 or customercare@haldiram.com
        """
        fields = extract_fields(text)
        self.assertIn("POTATO CHIPS", fields["product_name"].upper())
        self.assertEqual(fields["mrp"], "₹30")
        self.assertEqual(fields["details"]["mrp"]["value"], 30)
        self.assertEqual(fields["net_quantity"], "100 g")
        self.assertEqual(fields["details"]["net_quantity"]["value"], 100)
        self.assertEqual(fields["details"]["net_quantity"]["unit"], "g")
        self.assertIn("Haldiram Snacks", fields["manufacturer"])
        self.assertEqual(fields["consumer_care"], "1800-102-4567")
        self.assertEqual(fields["details"]["consumer_information"]["email"], "customercare@haldiram.com")

    def test_02_missing_mrp_biscuits(self):
        text = """
        BRITANNIA GOOD DAY CASHEW COOKIES
        Net Wt. 200 g
        Manufactured & Packed by: Britannia Industries Ltd., Bangalore 560001
        Customer Care Helpline: 1800-425-4449
        Email: feedback@britindia.com
        """
        fields = extract_fields(text)
        self.assertIn("COOKIES", fields["product_name"].upper())
        self.assertIsNone(fields["mrp"])
        self.assertIsNone(fields["details"]["mrp"]["value"])
        self.assertEqual(fields["net_quantity"], "200 g")
        self.assertIn("Britannia Industries", fields["manufacturer"])
        self.assertEqual(fields["consumer_care"], "1800-425-4449")

    def test_03_missing_net_quantity_spice_packet(self):
        text = """
        EVEREST CHANA MASALA
        MRP Rs. 75.00
        Mfd. by: Everest Food Products Pvt Ltd, Mumbai, Maharashtra
        For complaints contact Toll Free: 1800-227-888 or customercare@everestspices.com
        """
        fields = extract_fields(text)
        self.assertIn("CHANA MASALA", fields["product_name"].upper())
        self.assertEqual(fields["mrp"], "₹75")
        self.assertIsNone(fields["net_quantity"])
        self.assertIsNone(fields["details"]["net_quantity"]["value"])
        self.assertIn("Everest Food", fields["manufacturer"])
        self.assertEqual(fields["consumer_care"], "1800-227-888")

    def test_04_missing_manufacturer_beverage(self):
        text = """
        Product Name: Real Fruit Power Mango Juice
        Net Volume: 1 L
        MRP: Rs 110
        Customer Care: 1800-103-1644
        """
        fields = extract_fields(text)
        self.assertEqual(fields["product_name"], "Real Fruit Power Mango Juice")
        self.assertEqual(fields["mrp"], "₹110")
        self.assertEqual(fields["net_quantity"], "1 l")
        self.assertIsNone(fields["manufacturer"])
        self.assertEqual(fields["consumer_care"], "1800-103-1644")

    def test_05_missing_consumer_info_packaged_food(self):
        text = """
        Commodity: TATA SAMPANN UNPOLISHED TOOR DAL
        Net Weight: 1 kg
        MRP ₹ 165
        Packed by: Tata Consumer Products Ltd, Kolkata 700001
        Batch No: B124
        """
        fields = extract_fields(text)
        self.assertEqual(fields["product_name"], "TATA SAMPANN UNPOLISHED TOOR DAL")
        self.assertEqual(fields["mrp"], "₹165")
        self.assertEqual(fields["net_quantity"], "1 kg")
        self.assertIn("Tata Consumer Products", fields["manufacturer"])
        self.assertIsNone(fields["consumer_care"])
        self.assertIsNone(fields["details"]["consumer_information"]["phone"])

    def test_06_multiple_mrp_formats(self):
        cases = [
            ("MRP ₹50", 50),
            ("MRP: ₹ 50.00", 50),
            ("MRP Rs. 50", 50),
            ("MRP: Rs 50", 50),
            ("MRP INR 50", 50),
            ("Maximum Retail Price ₹50", 50),
            ("Maximum Retail Price: Rs. 50", 50),
            ("Max Retail Price Rs. 56/-", 56),
            ("M.R.P. (inclusive of all taxes) ₹ 120.00", 120),
            ("₹ 45.00 (incl. of all taxes)", 45),
            ("MRP: ₹30.00", 30),
            ("MRP: ₹ 30.00", 30),
            ("MRP: Rs. 30.00", 30),
            ("MRP: Rs.30.00", 30),
            ("MRP: 30.00", 30),
            ("MRP 30.00", 30),
            ("MRP: & 30.00", 30),
            ("MRP: = 30.00", 30),
            ("MRP: a 30.00", 30),
            ("MRP: ee 30.00", 30),
            ("MRP:\n\n¥ 30.00\n(Inclusive of all taxes)", 30),
            ("MRP: ₹ 1,250.00", 1250),
        ]
        for snippet, expected_val in cases:
            res = extract_mrp(snippet)
            self.assertEqual(res["value"], expected_val, f"Failed on snippet: {snippet}")
            self.assertEqual(res["currency"], "INR")

    def test_07_multiple_quantity_formats(self):
        cases = [
            ("Net Qty: 500 g", 500, "g"),
            ("Net Quantity: 500g", 500, "g"),
            ("Net Wt. 200 gm", 200, "g"),
            ("Net Weight: 1 kg", 1, "kg"),
            ("Net Content: 100g", 100, "g"),
            ("Net Volume: 750 ml", 750, "ml"),
            ("Net Vol: 1 L", 1, "l"),
            ("500 g", 500, "g"),
            ("250 ml", 250, "ml")
        ]
        for snippet, expected_val, expected_unit in cases:
            res = extract_net_quantity(snippet)
            self.assertEqual(res["value"], expected_val, f"Failed val on snippet: {snippet}")
            self.assertEqual(res["unit"], expected_unit, f"Failed unit on snippet: {snippet}")

    def test_08_manufacturer_variations(self):
        cases = [
            ("Manufactured by: ABC Foods Ltd, Mumbai 400001", "ABC Foods Ltd"),
            ("Manufactured & Packed by: XYZ Agro Pvt Ltd", "XYZ Agro Pvt Ltd"),
            ("Packed by: Heritage Foods, Hyderabad", "Heritage Foods"),
            ("Mfd. by: Sun Agri Corp, Pune", "Sun Agri Corp")
        ]
        for snippet, expected_name in cases:
            res = extract_manufacturer(snippet)
            self.assertEqual(res["name"], expected_name, f"Failed on snippet: {snippet}")

    def test_09_consumer_care_detection(self):
        text = """
        For complaints contact Customer Service Executive:
        Toll Free: 1800-200-1234
        Email: help@example.com
        """
        res = extract_consumer_information(text)
        self.assertEqual(res["phone"], "1800-200-1234")
        self.assertEqual(res["email"], "help@example.com")

    def test_10_irrelevant_numbers_rejected(self):
        # Must NOT confuse invoice, serial, barcode, nutrition numbers, or unit sale price with MRP/Qty/Care
        text = """
        INVOICE # 9876543210
        Serial Number: 800-999-0000
        Item Count: 450
        Barcode: 8 93773 00204 9
        Nutrition Facts:
        Serving Size: 1 sec spray (.5ml)
        Serving Per Container: 354
        Calories: 2000
        Sodium 0mg
        """
        fields = extract_fields(text)
        self.assertIsNone(fields["mrp"])
        self.assertIsNone(fields["net_quantity"])
        self.assertIsNone(fields["consumer_care"])

        # Specifically ensure unit sale price (e.g. ₹ 0.15 per g) is never extracted as MRP
        usp_text = """
        UNIT SALE PRICE:
        ₹ 0.15 per g
        BATCH NO: BN123
        """
        usp_fields = extract_fields(usp_text)
        self.assertIsNone(usp_fields["mrp"])

    def test_11_real_sample_product1_ocr(self):
        img_path = Path(r"c:\SIH26034\sample_images\product1.jpg")
        if img_path.exists():
            ocr_res = extract_text_with_confidence(str(img_path))
            self.assertGreater(ocr_res["confidence"], 60.0)
            self.assertIn("Fish Chili", ocr_res["cleaned_text"])

            fields = extract_fields(ocr_res["cleaned_text"])
            # Dynamic product name extraction (not hardcoded)
            self.assertIsNotNone(fields["product_name"])
            self.assertIn("Fish Chili", fields["product_name"])
            # Consumer phone extracted contextually
            self.assertEqual(fields["consumer_care"], "800-123-4567")
            # Missing fields correctly return None
            self.assertIsNone(fields["mrp"])
            self.assertIsNone(fields["net_quantity"])
            self.assertIsNone(fields["manufacturer"])

    def test_12_net_weight_variants(self):
        cases = [
            ("NET WEIGHT: 200 g", 200, "g"),
            ("NET WT. 500 g", 500, "g"),
            ("NET WT. : 500 g", 500, "g"),
            ("NET QTY: 1 kg", 1, "kg"),
            ("NET QUANTITY 250 ml", 250, "ml"),
            ("NET CONTENTS: 100 ml", 100, "ml"),
            ("NET CONTENT: 50 g", 50, "g")
        ]
        for snippet, expected_val, expected_unit in cases:
            res = extract_net_quantity(snippet)
            self.assertEqual(res["value"], expected_val, f"Failed value on snippet: {snippet}")
            self.assertEqual(res["unit"], expected_unit, f"Failed unit on snippet: {snippet}")

    def test_13_company_name_not_product_name(self):
        text = """
        PARLE PRODUCTS PVT. LTD.
        NORTH LEVEL CROSSING, VILE PARLE EAST, MUMBAI 400057
        HIDE & SEEK BISCUITS
        INGREDIENTS: WHEAT FLOUR, CHOCOLATE
        """
        p_res = extract_product_name(text)
        self.assertIsNotNone(p_res["value"])
        self.assertNotIn("PVT", p_res["value"].upper())
        self.assertNotIn("LTD", p_res["value"].upper())
        self.assertIn("HIDE", p_res["value"].upper())

    def test_14_consumer_care_not_manufacturer(self):
        text = """
        MANUFACTURED FOR:
        CONSUMER CARE CELL
        PARLE PRODUCTS PVT. LTD.
        NORTH LEVEL CROSSING, MUMBAI 400057
        """
        m_res = extract_manufacturer(text)
        self.assertIsNotNone(m_res["name"])
        self.assertNotIn("CONSUMER CARE", m_res["name"].upper())
        self.assertIn("PARLE PRODUCTS", m_res["name"].upper())

    def test_15_real_sample_parle_hide_seek(self):
        img_path = Path(r"c:\SIH26034\sample_images\parle_hide_seek.jpg")
        if img_path.exists():
            ocr_res = extract_text_with_confidence(str(img_path))
            fields = extract_fields(ocr_res["cleaned_text"])
            self.assertIsNotNone(fields["product_name"])
            self.assertIn("HIDE", fields["product_name"].upper())
            self.assertNotIn("PVT", fields["product_name"].upper())
            self.assertEqual(fields["net_quantity"], "200 g")
            self.assertIsNotNone(fields["manufacturer"])
            self.assertIn("PARLE PRODUCTS", fields["manufacturer"].upper())
            self.assertNotIn("CONSUMER CARE", fields["manufacturer"].upper())
            self.assertIsNone(fields["mrp"])
            self.assertIn("parle.biz", fields["consumer_care"])

    def test_16_real_sample_sunrise_biscuits(self):
        sample_dir = Path(__file__).parent.parent / "sample_images"
        possible_paths = [
            sample_dir / "sunrise_digestive_biscuits.jpeg",
            sample_dir / "WhatsApp Image 2026-09-03 at 11.16.58 AM.jpeg"
        ]
        img_path = None
        for p in possible_paths:
            if p.exists():
                img_path = p
                break

        if img_path:
            ocr_res = extract_text_with_confidence(str(img_path))
            fields = extract_fields(ocr_res["cleaned_text"])
            self.assertIsNotNone(fields["product_name"])
            self.assertIn("CHOCOLATE DIGESTIVE BISCUITS", fields["product_name"].upper())
            self.assertIsNotNone(fields["manufacturer"])
            self.assertIn("SUNRISE FOODS", fields["manufacturer"].upper())
            self.assertEqual(fields["net_quantity"], "200 g")
            self.assertIsNotNone(fields["details"]["mrp"]["value"])
            self.assertEqual(fields["details"]["mrp"]["value"], 30)
            self.assertIn(fields["mrp"], ["₹30", "₹30.00"])
            self.assertIn("1800-123-5678", fields["consumer_care"])

            from rules.engine import evaluate_rules, calculate_compliance
            checks = evaluate_rules(fields)
            compliance = calculate_compliance(checks)
            self.assertEqual(compliance["score"], 100)
            self.assertEqual(compliance["status"], "COMPLIANT")


    def test_17_company_after_repacked_and_marketed_by_not_product_name(self):
        text = """
        Repacked & Marketed by
        CLICKCART.
        House No-226, Padmavati Nagar, Jodhpur
        """
        p_res = extract_product_name(text)
        self.assertTrue(p_res["value"] is None or "CLICKCART" not in p_res["value"])

    def test_18_company_after_manufactured_by_not_product_name(self):
        text = """
        Manufactured by:
        ABC FOODS PVT. LTD.
        Plot No. 45, Industrial Area, Pune 411001
        """
        p_res = extract_product_name(text)
        self.assertTrue(p_res["value"] is None or "ABC FOODS" not in p_res["value"])

    def test_19_mrp_inclusive_taxes_and_usp_rejection(self):
        mrp_text = "MRP (Incl. of all taxes) : ₹499.00"
        res = extract_mrp(mrp_text)
        self.assertEqual(res["value"], 499)

        usp_text = "USP: ₹2.00 per g"
        res_usp = extract_mrp(usp_text)
        self.assertIsNone(res_usp["value"])


if __name__ == "__main__":
    unittest.main()


