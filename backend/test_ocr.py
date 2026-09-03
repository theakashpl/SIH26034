import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent
ROOT_DIR = BACKEND_DIR.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from ocr.engine import extract_text

IMAGE_PATH = ROOT_DIR / "sample_images" / "kurkure.jpg.jpeg"


if __name__ == "__main__":
    text = extract_text(str(IMAGE_PATH))

    print("\n================ OCR RESULT ================\n")
    print(text)
    print("\n=============================================\n")