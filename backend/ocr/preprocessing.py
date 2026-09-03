import cv2
import numpy as np


def validate_image(image_path: str) -> np.ndarray:
    """Validate image existence and loadability, returning BGR numpy array."""
    image = cv2.imread(image_path)
    if image is None:
        raise ValueError(f"Could not read image: {image_path}")
    return image


def preprocess_image_clahe(image: np.ndarray) -> np.ndarray:
    """
    Enhance contrast using CLAHE (Contrast Limited Adaptive Histogram Equalization)
    and cubic resize. Ideal for colored, variable-lighting, and low-contrast labels.
    """
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    enhanced = clahe.apply(gray)
    # 1.5x upscale with bicubic interpolation optimizes Tesseract font recognition
    # without introducing high-frequency interpolation noise.
    resized = cv2.resize(
        enhanced,
        None,
        fx=1.5,
        fy=1.5,
        interpolation=cv2.INTER_CUBIC
    )
    return resized


def preprocess_image_otsu(image: np.ndarray) -> np.ndarray:
    """
    Classic Otsu binarization pipeline preserved as fallback for clean, high-contrast labels.
    """
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    resized = cv2.resize(
        gray,
        None,
        fx=2.0,
        fy=2.0,
        interpolation=cv2.INTER_CUBIC
    )
    blurred = cv2.GaussianBlur(resized, (3, 3), 0)
    processed = cv2.threshold(
        blurred,
        0,
        255,
        cv2.THRESH_BINARY + cv2.THRESH_OTSU
    )[1]
    return processed


def preprocess_image(image_path: str, mode: str = "enhanced") -> np.ndarray:
    """
    Main preprocessing entrypoint.
    Modes:
      - 'enhanced': CLAHE contrast enhancement (default, best for packaging)
      - 'otsu': Classic binarization (fallback)
    """
    image = validate_image(image_path)
    if mode == "otsu":
        return preprocess_image_otsu(image)
    return preprocess_image_clahe(image)