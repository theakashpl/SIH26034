import unittest
import asyncio
import io
from pathlib import Path
import sys
import numpy as np
import cv2

BACKEND_DIR = Path(__file__).parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from fastapi import UploadFile, HTTPException
from main import scan_product
from extraction.extractor import combine_product_evidence, extract_fields


def create_dummy_jpeg(color=(128, 128, 128)) -> bytes:
    """Create a minimal valid JPEG image in memory."""
    img = np.full((120, 120, 3), color, dtype=np.uint8)
    # Add a little text so OCR doesn't choke
    cv2.putText(img, "TEST", (20, 60), cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)
    success, buffer = cv2.imencode(".jpg", img)
    return buffer.tobytes()


class TestMultiImageScanning(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.valid_jpeg_bytes = create_dummy_jpeg()

    # --- TEST 1: One image -> accepted ---
    def test_01_one_image_accepted(self):
        f1 = UploadFile(filename="front.jpg", file=io.BytesIO(self.valid_jpeg_bytes))
        res = asyncio.run(scan_product(files=[f1]))
        self.assertIn("images", res)
        self.assertEqual(len(res["images"]), 1)
        self.assertEqual(res["images"][0]["image_id"], 1)
        self.assertEqual(res["images"][0]["filename"], "front.jpg")
        self.assertIn("fields", res)
        self.assertIn("conflicts", res)
        self.assertIn("compliance", res)

    # --- TEST 2: Two images -> accepted ---
    def test_02_two_images_accepted(self):
        f1 = UploadFile(filename="front.jpg", file=io.BytesIO(self.valid_jpeg_bytes))
        f2 = UploadFile(filename="back.jpg", file=io.BytesIO(self.valid_jpeg_bytes))
        res = asyncio.run(scan_product(files=[f1, f2]))
        self.assertEqual(len(res["images"]), 2)
        self.assertEqual(res["images"][0]["image_id"], 1)
        self.assertEqual(res["images"][1]["image_id"], 2)

    # --- TEST 3: Three images -> accepted ---
    def test_03_three_images_accepted(self):
        files = [
            UploadFile(filename=f"view_{i}.jpg", file=io.BytesIO(self.valid_jpeg_bytes))
            for i in range(1, 4)
        ]
        res = asyncio.run(scan_product(files=files))
        self.assertEqual(len(res["images"]), 3)

    # --- TEST 4: Four images -> accepted ---
    def test_04_four_images_accepted(self):
        files = [
            UploadFile(filename=f"view_{i}.png", file=io.BytesIO(self.valid_jpeg_bytes))
            for i in range(1, 5)
        ]
        res = asyncio.run(scan_product(files=files))
        self.assertEqual(len(res["images"]), 4)

    # --- TEST 5: Five images -> rejected ---
    def test_05_five_images_rejected(self):
        files = [
            UploadFile(filename=f"view_{i}.jpg", file=io.BytesIO(self.valid_jpeg_bytes))
            for i in range(1, 6)
        ]
        with self.assertRaises(HTTPException) as ctx:
            asyncio.run(scan_product(files=files))
        self.assertEqual(ctx.exception.status_code, 400)
        self.assertIn("Maximum 4 images allowed", ctx.exception.detail)

    # --- TEST 6: Zero images -> rejected ---
    def test_06_zero_images_rejected(self):
        with self.assertRaises(HTTPException) as ctx:
            asyncio.run(scan_product(files=[]))
        self.assertEqual(ctx.exception.status_code, 400)
        self.assertIn("No image files provided", ctx.exception.detail)

    # --- TEST 7: Invalid/unsupported image -> rejected ---
    def test_07_invalid_unsupported_image_rejected(self):
        # Unsupported format
        bad_format = UploadFile(filename="doc.pdf", file=io.BytesIO(b"%PDF-1.4"))
        with self.assertRaises(HTTPException) as ctx1:
            asyncio.run(scan_product(files=[bad_format]))
        self.assertEqual(ctx1.exception.status_code, 400)
        self.assertIn("Unsupported file format", ctx1.exception.detail)

        # Empty file
        empty = UploadFile(filename="empty.jpg", file=io.BytesIO(b""))
        with self.assertRaises(HTTPException) as ctx2:
            asyncio.run(scan_product(files=[empty]))
        self.assertEqual(ctx2.exception.status_code, 400)
        self.assertIn("is empty", ctx2.exception.detail)

        # Corrupt file
        corrupt = UploadFile(filename="corrupt.jpg", file=io.BytesIO(b"gibberish not a real image header"))
        with self.assertRaises(HTTPException) as ctx3:
            asyncio.run(scan_product(files=[corrupt]))
        self.assertEqual(ctx3.exception.status_code, 400)
        self.assertIn("corrupted or not a valid image", ctx3.exception.detail)

    # --- TEST 8: Required fields distributed across 2 images -> correctly combined ---
    def test_08_fields_distributed_across_2_images(self):
        img1 = {
            "image_id": 1,
            "filename": "front.jpg",
            "cleaned_text": "EVEREST CHANA MASALA\nMRP Rs. 75.00"
        }
        img2 = {
            "image_id": 2,
            "filename": "back.jpg",
            "cleaned_text": "Net Weight: 100 g\nMfd. by: Everest Food Products Pvt Ltd\nCustomer Care Helpline: 1800-227-888"
        }
        combined = combine_product_evidence([img1, img2])
        fields = combined["fields"]
        details = combined["details"]

        # Check all 5 core fields are populated
        self.assertIn("CHANA MASALA", fields["product_name"])
        self.assertEqual(fields["mrp"], "₹75")
        self.assertEqual(fields["net_quantity"], "100 g")
        self.assertIn("Everest Food", fields["manufacturer"])
        self.assertEqual(fields["consumer_care"], "1800-227-888")

        # Check source image IDs
        self.assertEqual(details["product_name"]["source_image_id"], 1)
        self.assertEqual(details["mrp"]["source_image_id"], 1)
        self.assertEqual(details["net_quantity"]["source_image_id"], 2)
        self.assertEqual(details["manufacturer"]["source_image_id"], 2)
        self.assertEqual(details["consumer_information"]["source_image_id"], 2)

    # --- TEST 9: Required fields distributed across 4 images -> correctly combined ---
    def test_09_fields_distributed_across_4_images(self):
        img1 = {"image_id": 1, "filename": "front.jpg", "cleaned_text": "BRITANNIA GOOD DAY CASHEW COOKIES"}
        img2 = {"image_id": 2, "filename": "price_side.jpg", "cleaned_text": "MRP: Rs. 40.00"}
        img3 = {"image_id": 3, "filename": "qty_bottom.jpg", "cleaned_text": "Net Quantity: 120 g"}
        img4 = {"image_id": 4, "filename": "back_contact.jpg", "cleaned_text": "Manufactured & Packed by: Britannia Industries Ltd.\nCustomer Service: 1800-425-4449"}

        combined = combine_product_evidence([img1, img2, img3, img4])
        fields = combined["fields"]
        details = combined["details"]

        self.assertIn("COOKIES", fields["product_name"])
        self.assertEqual(fields["mrp"], "₹40")
        self.assertEqual(fields["net_quantity"], "120 g")
        self.assertIn("Britannia", fields["manufacturer"])
        self.assertEqual(fields["consumer_care"], "1800-425-4449")

        self.assertEqual(details["product_name"]["source_image_id"], 1)
        self.assertEqual(details["mrp"]["source_image_id"], 2)
        self.assertEqual(details["net_quantity"]["source_image_id"], 3)
        self.assertEqual(details["manufacturer"]["source_image_id"], 4)
        self.assertEqual(details["consumer_information"]["source_image_id"], 4)
        self.assertEqual(len(combined["conflicts"]), 0)

    # --- TEST 10: Duplicate MRP across images -> one final MRP ---
    def test_10_duplicate_mrp_across_images(self):
        img1 = {"image_id": 1, "cleaned_text": "MRP ₹ 50.00"}
        img2 = {"image_id": 2, "cleaned_text": "Maximum Retail Price: Rs 50"}
        combined = combine_product_evidence([img1, img2])

        self.assertEqual(combined["fields"]["mrp"], "₹50")
        self.assertEqual(combined["details"]["mrp"]["value"], 50)
        self.assertEqual(len(combined["conflicts"]), 0)

    # --- TEST 11: Conflicting MRP across images -> conflict reported ---
    def test_11_conflicting_mrp_reported(self):
        img1 = {"image_id": 1, "cleaned_text": "MRP ₹ 50.00"}
        img2 = {"image_id": 2, "cleaned_text": "MRP ₹ 55.00"}
        combined = combine_product_evidence([img1, img2])

        self.assertIn("mrp", combined["conflicts"])
        self.assertEqual(len(combined["conflicts"]["mrp"]), 2)
        self.assertEqual(combined["conflicts"]["mrp"][0]["value"], 50)
        self.assertEqual(combined["conflicts"]["mrp"][0]["source_image_id"], 1)
        self.assertEqual(combined["conflicts"]["mrp"][1]["value"], 55)
        self.assertEqual(combined["conflicts"]["mrp"][1]["source_image_id"], 2)

    # --- TEST 12: Existing single-image extraction tests still pass ---
    def test_12_existing_single_image_still_passes(self):
        text = """
        HALDIRAM'S
        CLASSIC SALTED POTATO CHIPS
        Net Quantity: 100 g
        MRP ₹ 30.00 (incl. of all taxes)
        Manufactured by: Haldiram Snacks Pvt. Ltd.
        Consumer Care: 1800-102-4567
        """
        fields = extract_fields(text)
        self.assertIn("POTATO CHIPS", fields["product_name"])
        self.assertEqual(fields["mrp"], "₹30")
        self.assertEqual(fields["net_quantity"], "100 g")
        self.assertIn("Haldiram Snacks", fields["manufacturer"])
        self.assertEqual(fields["consumer_care"], "1800-102-4567")


if __name__ == "__main__":
    unittest.main()
