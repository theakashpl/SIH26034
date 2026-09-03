from ocr.engine import extract_text


IMAGE_PATH = "sample_images/product1.jpg"


if __name__ == "__main__":
    text = extract_text(IMAGE_PATH)

    print("\n================ OCR RESULT ================\n")
    print(text)
    print("\n=============================================\n")