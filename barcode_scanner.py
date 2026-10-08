"""
ATTEND-X: Barcode & QR Scanner Module
Detects and decodes barcodes and QR codes from OpenCV frames.
Includes multi-stage preprocessing (inverted, CLAHE, sharpening, thresholding),
card presence detection, and OCR fallback for physical printed ID cards.
"""

import os
import re
import time
import logging
import cv2
import numpy as np

logger = logging.getLogger(__name__)

# ─── Pyzbar initialization ──────────────────────────────────────────────────
try:
    from pyzbar import pyzbar as _pyzbar
    PYZBAR_AVAILABLE = True
except ImportError:
    _pyzbar = None
    PYZBAR_AVAILABLE = False
    logger.warning("pyzbar not available – barcode/QR scanning disabled.")

# ─── Pytesseract initialization (OCR Fallback) ──────────────────────────────
PYTESSERACT_AVAILABLE = False
try:
    import pytesseract
    tess_paths = [
        r"C:\Program Files\Tesseract-OCR\tesseract.exe",
        r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
    ]
    for p in tess_paths:
        if os.path.exists(p):
            pytesseract.pytesseract.tesseract_cmd = p
            break
    PYTESSERACT_AVAILABLE = True
except Exception as e:
    logger.info("pytesseract OCR fallback not active: %s", e)

_cv_qr_detector = None


def _get_cv_qr_detector():
    global _cv_qr_detector
    if _cv_qr_detector is None:
        if hasattr(cv2, "QRCodeDetector"):
            try:
                _cv_qr_detector = cv2.QRCodeDetector()
            except Exception:
                pass
    return _cv_qr_detector


# ─── Debug Diagnostics State ────────────────────────────────────────────────
_debug_state = {
    "camera": "ONLINE",
    "barcode_detector": "ACTIVE" if PYZBAR_AVAILABLE else "INACTIVE",
    "qr_detector": "ACTIVE",
    "ocr_fallback": "READY" if PYTESSERACT_AVAILABLE else "UNAVAILABLE",
    "last_scan": "NONE",
    "decode": "IDLE",
    "reason": "Ready for detection",
    "method": "NONE",
    "timestamp": "",
}


def get_debug_info() -> dict:
    """Return a snapshot of current scanner debug metrics."""
    return dict(_debug_state)


def _update_debug(last_scan: str, decode: str, reason: str, method: str = "NONE"):
    _debug_state["last_scan"] = last_scan
    _debug_state["decode"] = decode
    _debug_state["reason"] = reason
    _debug_state["method"] = method
    _debug_state["timestamp"] = time.strftime("%H:%M:%S")


# ─── Normalization & Student ID Extraction ──────────────────────────────────

def normalize_scanned_data(raw_data: str) -> str:
    """Normalize raw scanned barcode/QR data."""
    if not raw_data:
        return ""
    return str(raw_data).strip().upper()


def extract_student_id(raw_data: str) -> str:
    """
    Extract a valid student ID from raw decoded/OCR string.
    Handles:
      - ' IU2441230311 '
      - 'iu2441230311'
      - 'IU2441230311\\n'
      - 'Student ID: IU2441230311'
      - 'ID=IU2441230311'
      - 'ID : IU2441230311'
      - Multi-line card OCR text (e.g. OCR 1U... -> IU...)
    """
    if not raw_data:
        return ""

    s = str(raw_data).strip()

    # 1. Check known prefixes
    prefix_match = re.search(
        r"(?:student\s*id|id|barcode|card)[\s:=]+([A-Za-z0-9_-]+)",
        s,
        re.IGNORECASE
    )
    if prefix_match:
        return prefix_match.group(1).strip().upper()

    # 2. Check lines for formatted student ID pattern (e.g. IU2441230311 or 1U... for OCR)
    lines = [line.strip().upper() for line in s.splitlines() if line.strip()]
    for line in lines:
        pm = re.search(r"(?:STUDENT\s*ID|ID)[\s:=]+([A-Za-z0-9_-]+)", line)
        if pm:
            return pm.group(1).strip()

        # Check standard university roll number format: IU + 10 digits
        # Also handle OCR confusing 'I' with '1' or 'l'
        m_id = re.search(r"\b([1IlI]U\d{8,12})\b", line)
        if m_id:
            val = m_id.group(1)
            if val.startswith("1U") or val.startswith("lU"):
                val = "IU" + val[2:]
            return val

    # 3. Clean token fallback
    # If the string is a single token
    token_match = re.match(r"^([A-Za-z0-9_-]+)$", s.strip())
    if token_match:
        return token_match.group(1).upper()

    return s.strip().upper()


# ─── Card Boundary / Presence Detection ──────────────────────────────────────

def detect_card_in_frame(frame) -> tuple[bool, tuple | None]:
    """
    Detect if an ID card is visible in the frame via contour analysis.
    Returns (True, (x, y, w, h)) if a card-like rectangular region is detected,
    or (False, None) otherwise.
    """
    if frame is None or frame.size == 0:
        return False, None

    fh, fw = frame.shape[:2]
    frame_area = fh * fw

    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    blur = cv2.GaussianBlur(gray, (5, 5), 0)
    edges = cv2.Canny(blur, 40, 140)

    # Small dilation to connect broken card border segments
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
    edges = cv2.dilate(edges, kernel, iterations=1)

    contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    best_bbox = None
    best_area = 0

    for c in contours:
        area = cv2.contourArea(c)
        # Card should occupy at least 3.5% of webcam frame and no more than 85%
        if 0.035 * frame_area <= area <= 0.85 * frame_area:
            peri = cv2.arcLength(c, True)
            approx = cv2.approxPolyDP(c, 0.04 * peri, True)
            x, y, w, h = cv2.boundingRect(approx)
            if h <= 0:
                continue
            aspect = float(w) / h
            # Landscape card aspect (~1.3 - 2.0) or portrait card aspect (~0.5 - 0.8)
            if (1.1 <= aspect <= 2.2) or (0.45 <= aspect <= 0.9):
                if area > best_area:
                    best_area = area
                    best_bbox = (x, y, w, h)

    if best_bbox is not None:
        return True, best_bbox

    return False, None


# ─── Multi-Stage Decode Pipeline ─────────────────────────────────────────────

def _try_decode_image(img_gray, method_label: str = ""):
    """Helper: attempt pyzbar and OpenCV QR detection on a single grayscale image."""
    # 1. Pyzbar
    if PYZBAR_AVAILABLE:
        try:
            try:
                from pyzbar.pyzbar import ZBarSymbol
                symbols = [
                    ZBarSymbol.QRCODE,
                    ZBarSymbol.CODE128,
                    ZBarSymbol.CODE39,
                    ZBarSymbol.EAN13,
                    ZBarSymbol.EAN8,
                    ZBarSymbol.UPCA,
                    ZBarSymbol.UPCE,
                ]
                decoded_objects = _pyzbar.decode(img_gray, symbols=symbols)
            except Exception:
                decoded_objects = _pyzbar.decode(img_gray)
            for obj in decoded_objects:
                try:
                    data = obj.data.decode("utf-8").strip()
                    if data:
                        return data, f"pyzbar ({method_label})"
                except Exception:
                    pass
        except Exception:
            pass

    # 2. OpenCV QR detector
    detector = _get_cv_qr_detector()
    if detector is not None:
        try:
            val, pts, _ = detector.detectAndDecode(img_gray)
            val = (val or "").strip()
            if val:
                return val, f"opencv_qr ({method_label})"
        except Exception:
            pass

    return None, None


def decode_frame_multi_pass(frame) -> tuple[str | None, str]:
    """
    Multi-stage decoding pipeline:
      Stage 1: Quick decode (original grayscale & inverted grayscale).
      Stage 2: Contrast enhanced (CLAHE normal & inverted).
      Stage 3: Sharpening (normal & inverted).
      Stage 4: Thresholding (Otsu & Adaptive Gaussian, normal & inverted).
      Stage 5: Cropped Card Region of Interest (if card boundary is detected).

    Returns (decoded_value, detection_method).
    """
    if frame is None or frame.size == 0:
        return None, "NONE"

    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

    # ── Stage 1: Fast Grayscale & Inverted Grayscale (takes ~3-5ms) ──
    # Note: Inverted grayscale is CRITICAL for existing dark-themed ID cards!
    val, m = _try_decode_image(gray, "gray")
    if val:
        return val, m

    inv_gray = cv2.bitwise_not(gray)
    val, m = _try_decode_image(inv_gray, "inverted_gray")
    if val:
        return val, m

    # ── Stage 2: CLAHE Contrast Enhancement ──
    try:
        clahe = cv2.createCLAHE(clipLimit=2.5, tileGridSize=(8, 8))
        cl = clahe.apply(gray)
        val, m = _try_decode_image(cl, "clahe")
        if val:
            return val, m
        val, m = _try_decode_image(cv2.bitwise_not(cl), "inverted_clahe")
        if val:
            return val, m
    except Exception:
        pass

    # ── Stage 3: Sharpening (for blurry/out-of-focus webcam captures) ──
    try:
        sharp_kernel = np.array([[0, -1, 0], [-1, 5, -1], [0, -1, 0]])
        sharp = cv2.filter2D(gray, -1, sharp_kernel)
        val, m = _try_decode_image(sharp, "sharp")
        if val:
            return val, m
        val, m = _try_decode_image(cv2.bitwise_not(sharp), "inverted_sharp")
        if val:
            return val, m
    except Exception:
        pass

    # ── Stage 4: Thresholding (Otsu & Adaptive) ──
    try:
        _, otsu = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        val, m = _try_decode_image(otsu, "otsu")
        if val:
            return val, m
        val, m = _try_decode_image(cv2.bitwise_not(otsu), "inverted_otsu")
        if val:
            return val, m

        adaptive = cv2.adaptiveThreshold(
            gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 25, 7
        )
        val, m = _try_decode_image(adaptive, "adaptive")
        if val:
            return val, m
        val, m = _try_decode_image(cv2.bitwise_not(adaptive), "inverted_adaptive")
        if val:
            return val, m
    except Exception:
        pass

    # ── Stage 5: Card Region Crop & Rescale ──
    has_card, bbox = detect_card_in_frame(frame)
    if has_card and bbox is not None:
        x, y, w, h = bbox
        # Pad ROI slightly
        pad_x = int(w * 0.05)
        pad_y = int(h * 0.05)
        x1 = max(0, x - pad_x)
        y1 = max(0, y - pad_y)
        x2 = min(frame.shape[1], x + w + pad_x)
        y2 = min(frame.shape[0], y + h + pad_y)

        roi_gray = gray[y1:y2, x1:x2]
        if roi_gray.size > 0:
            # Test direct ROI & inverted ROI
            val, m = _try_decode_image(roi_gray, "roi_gray")
            if val:
                return val, m
            val, m = _try_decode_image(cv2.bitwise_not(roi_gray), "inverted_roi_gray")
            if val:
                return val, m

            # Upscale small card ROI for distant captures
            if w < 300:
                roi_up = cv2.resize(roi_gray, (w * 2, h * 2), interpolation=cv2.INTER_CUBIC)
                val, m = _try_decode_image(roi_up, "roi_upscaled")
                if val:
                    return val, m
                val, m = _try_decode_image(cv2.bitwise_not(roi_up), "inverted_roi_upscaled")
                if val:
                    return val, m

    return None, "NONE"


def _run_ocr_fallback(frame, bbox=None) -> str | None:
    """Run OCR on the card region or frame as fallback."""
    if not PYTESSERACT_AVAILABLE:
        return None

    try:
        if bbox is not None:
            x, y, w, h = bbox
            crop = frame[max(0, y):min(frame.shape[0], y + h),
                         max(0, x):min(frame.shape[1], x + w)]
        else:
            crop = frame

        if crop is None or crop.size == 0:
            return None

        # Convert to grayscale and enhance contrast for OCR
        gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        enhanced = clahe.apply(gray)

        # Run tesseract
        text = pytesseract.image_to_string(enhanced)
        if not text.strip():
            # Try inverted OCR for dark card
            text = pytesseract.image_to_string(cv2.bitwise_not(enhanced))

        extracted_id = extract_student_id(text)
        if extracted_id and len(extracted_id) >= 2:
            return extracted_id
    except Exception as e:
        logger.debug("OCR fallback exception: %s", e)

    return None


# ─── High-Level Scan API ─────────────────────────────────────────────────────

def scan_frame(frame, allow_ocr: bool = False) -> dict:
    """
    Comprehensive scan of a frame.
    Returns dict:
      {
         "found": bool,
         "student_id": str | None,
         "raw_data": str | None,
         "card_detected": bool,
         "card_bbox": tuple | None,
         "method": str,
      }
    """
    card_detected, card_bbox = detect_card_in_frame(frame)

    raw_val, method = decode_frame_multi_pass(frame)

    if raw_val:
        student_id = extract_student_id(raw_val)
        _update_debug(
            last_scan=student_id,
            decode="SUCCESS",
            reason="Barcode/QR decoded successfully",
            method=method
        )
        return {
            "found": True,
            "student_id": student_id,
            "raw_data": raw_val,
            "card_detected": card_detected,
            "card_bbox": card_bbox,
            "method": method,
        }

    # If barcode/QR failed, check OCR fallback if requested and card is visible
    if allow_ocr and card_detected and PYTESSERACT_AVAILABLE:
        ocr_id = _run_ocr_fallback(frame, card_bbox)
        if ocr_id:
            _update_debug(
                last_scan=ocr_id,
                decode="SUCCESS",
                reason="Student ID recognized via OCR fallback",
                method="OCR"
            )
            return {
                "found": True,
                "student_id": ocr_id,
                "raw_data": ocr_id,
                "card_detected": True,
                "card_bbox": card_bbox,
                "method": "OCR",
            }

    # Nothing found
    if card_detected:
        _update_debug(
            last_scan="NONE",
            decode="FAILED",
            reason="Card detected but barcode/QR unreadable",
            method="NONE"
        )
    else:
        _update_debug(
            last_scan="NONE",
            decode="FAILED",
            reason="No barcode/QR or card detected",
            method="NONE"
        )

    return {
        "found": False,
        "student_id": None,
        "raw_data": None,
        "card_detected": card_detected,
        "card_bbox": card_bbox,
        "method": "NONE",
    }


def decode_frame(frame) -> list[str]:
    """
    Backward-compatible scan: returns list of decoded student IDs found.
    """
    res = scan_frame(frame, allow_ocr=False)
    if res["found"] and res["student_id"]:
        return [res["student_id"]]
    return []


def has_potential_code(frame) -> bool:
    """Quick check: returns True if scanning should proceed."""
    return True


def draw_detections(frame, detections: list):
    """
    Draw bounding boxes and labels for found codes onto the frame.
    Returns the annotated frame.
    """
    if not detections or frame is None:
        return frame

    try:
        # If pyzbar is available, draw its detected polygons
        if PYZBAR_AVAILABLE:
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            # Try normal and inverted decode for drawing
            objs = _pyzbar.decode(gray) or _pyzbar.decode(cv2.bitwise_not(gray))
            for obj in objs:
                pts = obj.polygon
                if pts and len(pts) >= 4:
                    pts_array = np.array([[p.x, p.y] for p in pts], dtype=int)
                    cv2.polylines(frame, [pts_array], True, (0, 210, 150), 2)
                (x, y, w, h) = obj.rect
                raw = obj.data.decode("utf-8", errors="ignore").strip()
                label = extract_student_id(raw)[:20]
                cv2.putText(
                    frame, label, (x, max(15, y - 10)),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 210, 150), 2
                )
    except Exception as e:
        logger.debug("Draw detections error: %s", e)

    return frame
