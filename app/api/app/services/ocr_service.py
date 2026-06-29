from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import numpy as np
    from numpy.typing import NDArray

logger = logging.getLogger(__name__)

_ocr_engine = None


def _get_ocr():
    global _ocr_engine
    if _ocr_engine is None:
        from paddleocr import PaddleOCR

        _ocr_engine = PaddleOCR(use_angle_cls=True, lang="ch")
    return _ocr_engine


def is_scanned_pdf(file_path: str) -> bool:
    import pdfplumber

    empty_count = 0
    with pdfplumber.open(file_path) as pdf:
        total = len(pdf.pages)
        if total == 0:
            return False
        for page in pdf.pages:
            text = page.extract_text() or ""
            if len(text.strip()) < 20:
                empty_count += 1
    return empty_count > total / 2


def pdf_to_images(file_path: str, dpi: int = 250) -> list[NDArray]:
    import fitz
    import numpy as np

    doc = fitz.open(file_path)
    images = []
    zoom = dpi / 72
    mat = fitz.Matrix(zoom, zoom)
    for page in doc:
        pix = page.get_pixmap(matrix=mat)
        img = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.h, pix.w, pix.n)
        if pix.n == 4:
            import cv2
            img = cv2.cvtColor(img, cv2.COLOR_RGBA2BGR)
        elif pix.n == 1:
            import cv2
            img = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
        else:
            import cv2
            img = cv2.cvtColor(img, cv2.COLOR_RGB2BGR)
        images.append(img)
    doc.close()
    return images


def remove_red_seal(image: NDArray) -> NDArray:
    import cv2

    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    mask1 = cv2.inRange(hsv, (0, 80, 80), (10, 255, 255))
    mask2 = cv2.inRange(hsv, (160, 80, 80), (180, 255, 255))
    mask = mask1 | mask2
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
    mask = cv2.dilate(mask, kernel, iterations=2)
    return cv2.inpaint(image, mask, inpaintRadius=5, flags=cv2.INPAINT_TELEA)


def ocr_images(images: list[NDArray]) -> list[str]:
    engine = _get_ocr()
    pages_text: list[str] = []
    for img in images:
        result = engine.ocr(img, cls=True)
        if not result or not result[0]:
            pages_text.append("")
            continue
        lines = []
        for line_info in result[0]:
            box, (text, _confidence) = line_info
            top_y = min(pt[1] for pt in box)
            left_x = min(pt[0] for pt in box)
            lines.append((top_y, left_x, text))
        lines.sort(key=lambda t: (t[0], t[1]))
        pages_text.append("\n".join(t[2] for t in lines))
    return pages_text


def vl_extract(images: list[NDArray], db=None) -> list[str] | None:
    return None


def ocr_parse_pdf(file_path: str) -> str:
    images = pdf_to_images(file_path)
    cleaned = [remove_red_seal(img) for img in images]
    pages = ocr_images(cleaned)
    return "\n".join(pages)
