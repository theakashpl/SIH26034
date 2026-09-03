import pytesseract

from .preprocessing import preprocess_image


pytesseract.pytesseract.tesseract_cmd = (
    r"C:\Program Files\Tesseract-OCR\tesseract.exe"
)


def extract_text(image_path: str) -> str:
    processed_image = preprocess_image(image_path)

    text = str(
        pytesseract.image_to_string(
            processed_image,
            config="--psm 6"
        )
    )

    return text.strip()

def extract_text_with_confidence(image_path: str) -> dict:
    processed_image = preprocess_image(image_path)

    data = pytesseract.image_to_data(
        processed_image,
        config="--psm 6",
        output_type=pytesseract.Output.DICT,
    )

    confidences = []

    for i, word in enumerate(data["text"]):
        word = word.strip()

        if not word:
            continue

        try:
            confidence = float(data["conf"][i])
        except (ValueError, TypeError):
            continue

        if confidence >= 0:
            confidences.append(confidence)

    average_confidence = (
        sum(confidences) / len(confidences)
        if confidences
        else 0
    )

    return {
        "text": extract_text(image_path),
        "confidence": round(average_confidence, 2),
    }