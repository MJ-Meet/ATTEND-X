"""
ATTEND-X: Barcode & QR Scanner Module
Detects and decodes barcodes and QR codes from OpenCV frames.
Includes multi-stage preprocessing (inverted, CLAHE, sharpening, thresholding),
card presence detection, and OCR fallback for physical printed ID cards.
"""

import os
import re
import time
import shutil
import logging
import cv2
import numpy as np

logger = logging.getLogger(__name__)

# ─── Pyzbar initialization ──────────────────────────────────────────────────
_pyzbar = None
PYZBAR_AVAILABLE = False
PYZBAR_STATUS = "INACTIVE"
try:
    from pyzbar import pyzbar as _pz
    _pyzbar = _pz
    PYZBAR_AVAILABLE = True
    PYZBAR_STATUS = "ACTIVE"
except ImportError:
    PYZBAR_STATUS = "INACTIVE (pyzbar package not installed)"
    logger.info("pyzbar package not installed.")
except Exception as e:
    PYZBAR_STATUS = f"INACTIVE ({e})"
    logger.warning("pyzbar import error: %s", e)

# ─── OpenCV Barcode Detector initialization ──────────────────────────────────
_cv_barcode_detector = None
CV_BARCODE_AVAILABLE = False
try:
    if hasattr(cv2, "barcode") and hasattr(cv2.barcode, "BarcodeDetector"):
        _cv_barcode_detector = cv2.barcode.BarcodeDetector()
        CV_BARCODE_AVAILABLE = True
    elif hasattr(cv2, "barcode_BarcodeDetector"):
        _cv_barcode_detector = cv2.barcode_BarcodeDetector()
        CV_BARCODE_AVAILABLE = True
except Exception as e:
    logger.info("OpenCV BarcodeDetector unavailable: %s", e)

# Composite Barcode Detector status
if PYZBAR_AVAILABLE and CV_BARCODE_AVAILABLE:
    BARCODE_DETECTOR_STATUS = "ACTIVE (pyzbar + opencv)"
elif PYZBAR_AVAILABLE:
    BARCODE_DETECTOR_STATUS = "ACTIVE (pyzbar)"
elif CV_BARCODE_AVAILABLE:
    BARCODE_DETECTOR_STATUS = "ACTIVE (opencv)"
else:
    BARCODE_DETECTOR_STATUS = "INACTIVE (pyzbar & opencv barcode unavailable)"

# ─── OpenCV QR Detectors initialization ─────────────────────────────────────
_cv_qr_detector = None
_cv_qr_detector_aruco = None
QR_DETECTOR_AVAILABLE = False

try:
    if hasattr(cv2, "QRCodeDetectorAruco"):
        _cv_qr_detector_aruco = cv2.QRCodeDetectorAruco()
        QR_DETECTOR_AVAILABLE = True
except Exception as e:
    logger.debug("OpenCV QRCodeDetectorAruco init: %s", e)

try:
    if hasattr(cv2, "QRCodeDetector"):
        _cv_qr_detector = cv2.QRCodeDetector()
        QR_DETECTOR_AVAILABLE = True
except Exception as e:
    logger.debug("OpenCV QRCodeDetector init: %s", e)

if PYZBAR_AVAILABLE and _cv_qr_detector_aruco is not None:
    QR_DETECTOR_STATUS = "ACTIVE (pyzbar + aruco)"
elif PYZBAR_AVAILABLE:
    QR_DETECTOR_STATUS = "ACTIVE (pyzbar)"
elif _cv_qr_detector_aruco is not None:
    QR_DETECTOR_STATUS = "ACTIVE (aruco)"
elif _cv_qr_detector is not None:
    QR_DETECTOR_STATUS = "ACTIVE (opencv_qr)"
else:
    QR_DETECTOR_STATUS = "INACTIVE (no QR decoder available)"


def _get_cv_qr_detector():
    return _cv_qr_detector


def _get_cv_qr_detector_aruco():
    return _cv_qr_detector_aruco


def _get_cv_barcode_detector():
    return _cv_barcode_detector


# ─── Pytesseract initialization (OCR Fallback) ──────────────────────────────
PYTESSERACT_AVAILABLE = False
OCR_STATUS_MESSAGE = "UNAVAILABLE"
OCR_DETAIL = ""

try:
    import pytesseract

    tess_paths = [
        os.environ.get("TESSERACT_CMD", ""),
        r"C:\Program Files\Tesseract-OCR\tesseract.exe",
        r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
    ]
    path_tess = shutil.which("tesseract")
    if path_tess:
        tess_paths.insert(0, path_tess)

    tess_found = False
    for p in tess_paths:
        if p and os.path.exists(p):
            pytesseract.pytesseract.tesseract_cmd = p
            tess_found = True
            break

    if not tess_found:
        OCR_STATUS_MESSAGE = "UNAVAILABLE (tesseract.exe not found)"
        OCR_DETAIL = "Tesseract-OCR executable not found at C:\\Program Files\\Tesseract-OCR\\tesseract.exe"
        logger.info("Tesseract binary not found in standard paths.")
    else:
        try:
            ver = pytesseract.get_tesseract_version()
            PYTESSERACT_AVAILABLE = True
            OCR_STATUS_MESSAGE = f"READY (Tesseract {ver})"
            OCR_DETAIL = f"Tesseract engine version {ver} active"
            logger.info("OCR fallback initialized: Tesseract %s", ver)
        except Exception as te:
            OCR_STATUS_MESSAGE = f"ERROR ({te})"
            OCR_DETAIL = f"Error querying tesseract executable: {te}"
            logger.warning("Error invoking tesseract: %s", te)

except ImportError:
    OCR_STATUS_MESSAGE = "UNAVAILABLE (pytesseract package not installed)"
    OCR_DETAIL = "pytesseract Python package is missing. Install with: pip install pytesseract"
    logger.info("pytesseract package not installed.")
except Exception as e:
    OCR_STATUS_MESSAGE = f"UNAVAILABLE ({e})"
    OCR_DETAIL = str(e)
    logger.warning("pytesseract initialization error: %s", e)


# ─── Debug Diagnostics State ────────────────────────────────────────────────
_debug_state = {
    "camera": "ONLINE",
    "barcode_detector": BARCODE_DETECTOR_STATUS,
    "qr_detector": QR_DETECTOR_STATUS,
    "ocr_fallback": OCR_STATUS_MESSAGE,
    "ocr_detail": OCR_DETAIL,
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
    token_match = re.match(r"^([A-Za-z0-9_-]+)$", s.strip())
    if token_match:
        return token_match.group(1).upper()

    return s.strip().upper()


# ─── Card Boundary / Presence Detection ──────────────────────────────────────

def detect_card_in_frame(frame) -> tuple[bool, tuple | None]:
    """
    Detect if an ID card or readable code is visible in the frame.
    Uses:
      1. Direct code presence detection (fast QRCodeDetectorAruco / OpenCV detect).
      2. Contour analysis for realistic rectangular card geometry, aspect ratio,
         fill extent, and internal texture/contrast (preventing false alarms on
         unrelated background objects such as walls, screens, or desks).

    Returns (True, (x, y, w, h)) if a card/code is detected, or (False, None) otherwise.
    """
    if frame is None or frame.size == 0:
        return False, None

    fh, fw = frame.shape[:2]
    frame_area = fh * fw

    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY) if len(frame.shape) == 3 else frame

    # 1. Check direct code presence (super-fast, <1ms)
    try:
        if _cv_qr_detector_aruco is not None:
            ret, pts = _cv_qr_detector_aruco.detect(gray)
            if ret and pts is not None and len(pts) > 0:
                pts_reshaped = pts.reshape(-1, 2)
                x_min, y_min = np.min(pts_reshaped, axis=0)
                x_max, y_max = np.max(pts_reshaped, axis=0)
                cw = max(1, int(x_max - x_min))
                ch = max(1, int(y_max - y_min))
                cx, cy = int((x_min + x_max) / 2), int((y_min + y_max) / 2)
                # Expand to candidate card bounding box
                bw, bh = int(cw * 4.0), int(ch * 3.0)
                x1 = max(0, cx - bw // 2)
                y1 = max(0, cy - bh // 2)
                x2 = min(fw, cx + bw // 2)
                y2 = min(fh, cy + bh // 2)
                return True, (x1, y1, x2 - x1, y2 - y1)
    except Exception:
        pass

    try:
        if _cv_barcode_detector is not None:
            ret, pts = _cv_barcode_detector.detect(gray)
            if ret and pts is not None and len(pts) > 0:
                pts_reshaped = np.array(pts).reshape(-1, 2)
                x_min, y_min = np.min(pts_reshaped, axis=0)
                x_max, y_max = np.max(pts_reshaped, axis=0)
                return True, (int(x_min), int(y_min), max(1, int(x_max - x_min)), max(1, int(y_max - y_min)))
    except Exception:
        pass

    # 2. Check for physical card rectangle contour
    blur = cv2.GaussianBlur(gray, (5, 5), 0)
    edges = cv2.Canny(blur, 40, 140)

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
            approx = cv2.approxPolyDP(c, 0.035 * peri, True)
            # Require quadrilateral / convex polygon with 4 to 6 vertices
            if 4 <= len(approx) <= 6 and cv2.isContourConvex(approx):
                x, y, w, h = cv2.boundingRect(approx)
                if h <= 0 or w <= 0:
                    continue
                aspect = float(w) / h
                extent = area / float(w * h)
                # Standard ID card aspect ratio: landscape (~1.3 - 2.0) or portrait (~0.5 - 0.85)
                # and rectangular fill extent >= 0.65
                if extent >= 0.65 and ((1.15 <= aspect <= 2.2) or (0.45 <= aspect <= 0.85)):
                    roi = gray[y:y + h, x:x + w]
                    if roi.size > 0:
                        # Require internal contrast/texture characteristic of an ID card (photo/text/QR)
                        # Plain walls, empty screens, or desk surfaces have very low variance (<12)
                        lap_var = cv2.Laplacian(roi, cv2.CV_64F).var()
                        if lap_var > 18 and area > best_area:
                            best_area = area
                            best_bbox = (x, y, w, h)

    if best_bbox is not None:
        return True, best_bbox

    return False, None


# ─── Multi-Stage Decode Pipeline ─────────────────────────────────────────────

def _try_decode_image(img_input, method_label: str = "") -> tuple[str | None, str | None]:
    """
    Attempt barcode and QR detection across all available engines on an image
    (pyzbar, QRCodeDetectorAruco, QRCodeDetector, BarcodeDetector).
    """
    if img_input is None or img_input.size == 0:
        return None, None

    img_gray = cv2.cvtColor(img_input, cv2.COLOR_BGR2GRAY) if len(img_input.shape) == 3 else img_input

    # 1. Pyzbar (supports both QR codes and 1D barcodes with high speed and tolerance)
    if PYZBAR_AVAILABLE and _pyzbar is not None:
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
                    ZBarSymbol.I25,
                ]
                decoded_objects = _pyzbar.decode(img_gray, symbols=symbols)
            except Exception:
                decoded_objects = _pyzbar.decode(img_gray)

            for obj in decoded_objects:
                try:
                    data = obj.data.decode("utf-8", errors="ignore").strip()
                    if data:
                        return data, f"pyzbar ({method_label})"
                except Exception:
                    pass
        except Exception:
            pass

    # 2. OpenCV QRCodeDetectorAruco (fast, robust to rotation & perspective)
    if _cv_qr_detector_aruco is not None:
        try:
            val, pts, _ = _cv_qr_detector_aruco.detectAndDecode(img_gray)
            val = (val or "").strip()
            if val:
                return val, f"opencv_aruco ({method_label})"
        except Exception:
            pass

    # 3. OpenCV standard QRCodeDetector
    if _cv_qr_detector is not None:
        try:
            val, pts, _ = _cv_qr_detector.detectAndDecode(img_gray)
            val = (val or "").strip()
            if val:
                return val, f"opencv_qr ({method_label})"
        except Exception:
            pass

    # 4. OpenCV BarcodeDetector (for 1D barcodes if present)
    if _cv_barcode_detector is not None:
        try:
            val, btype, pts = _cv_barcode_detector.detectAndDecode(img_gray)
            if isinstance(val, (tuple, list)):
                val = next((str(v).strip() for v in val if str(v).strip()), "")
            val = str(val or "").strip()
            if val:
                return val, f"opencv_barcode ({method_label})"
        except Exception:
            pass

    return None, None


def decode_frame_multi_pass(frame) -> tuple[str | None, str]:
    """
    Multi-stage decoding pipeline:
      Stage 1: Quick decode (original grayscale, color, and inverted grayscale).
      Stage 2: Contrast enhanced (CLAHE normal & inverted).
      Stage 3: Sharpening (normal & inverted).
      Stage 4: Thresholding (Otsu & Adaptive Gaussian, normal & inverted).
      Stage 5: Cropped Card Region of Interest (ROI) & upscaled ROI.

    Returns (decoded_value, detection_method).
    """
    if frame is None or frame.size == 0:
        return None, "NONE"

    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY) if len(frame.shape) == 3 else frame

    # ── Stage 1: Fast Grayscale & Inverted Grayscale (takes ~3-10ms) ──
    val, m = _try_decode_image(gray, "gray")
    if val:
        return val, m

    # Try original color frame if available
    if len(frame.shape) == 3:
        val, m = _try_decode_image(frame, "color")
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

        # Higher contrast CLAHE for washed out webcam frames
        clahe_high = cv2.createCLAHE(clipLimit=4.0, tileGridSize=(8, 8))
        cl_high = clahe_high.apply(gray)
        val, m = _try_decode_image(cl_high, "clahe_high")
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
        pad_x = int(w * 0.08)
        pad_y = int(h * 0.08)
        x1 = max(0, x - pad_x)
        y1 = max(0, y - pad_y)
        x2 = min(frame.shape[1], x + w + pad_x)
        y2 = min(frame.shape[0], y + h + pad_y)

        roi_gray = gray[y1:y2, x1:x2]
        if roi_gray.size > 0:
            val, m = _try_decode_image(roi_gray, "roi_gray")
            if val:
                return val, m
            val, m = _try_decode_image(cv2.bitwise_not(roi_gray), "inverted_roi_gray")
            if val:
                return val, m

            # Upscale small card ROI for distant captures
            if w < 400:
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
        import pytesseract

        if bbox is not None:
            x, y, w, h = bbox
            crop = frame[max(0, y):min(frame.shape[0], y + h),
                         max(0, x):min(frame.shape[1], x + w)]
        else:
            crop = frame

        if crop is None or crop.size == 0:
            return None

        # Convert to grayscale and enhance contrast for OCR
        gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY) if len(crop.shape) == 3 else crop
        clahe = cv2.createCLAHE(clipLimit=2.5, tileGridSize=(8, 8))
        enhanced = clahe.apply(gray)

        # 1. Standard orientation with PSM 6 (uniform block of text)
        try:
            text = pytesseract.image_to_string(enhanced, config="--psm 6")
            extracted_id = extract_student_id(text)
            if extracted_id and len(extracted_id) >= 4:
                return extracted_id
        except Exception:
            pass

        # 2. Standard PSM default
        text = pytesseract.image_to_string(enhanced)
        extracted_id = extract_student_id(text)
        if extracted_id and len(extracted_id) >= 4:
            return extracted_id

        # 3. Inverted OCR for dark card
        inv = cv2.bitwise_not(enhanced)
        text_inv = pytesseract.image_to_string(inv)
        extracted_id = extract_student_id(text_inv)
        if extracted_id and len(extracted_id) >= 4:
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
            "card_detected": card_detected or True,
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
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY) if len(frame.shape) == 3 else frame

        if PYZBAR_AVAILABLE and _pyzbar is not None:
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
        elif _cv_qr_detector_aruco is not None:
            ret, pts = _cv_qr_detector_aruco.detect(gray)
            if ret and pts is not None and len(pts) > 0:
                pts_array = np.int32(pts).reshape(-1, 2)
                cv2.polylines(frame, [pts_array], True, (0, 210, 150), 2)
                x, y = pts_array[0]
                cv2.putText(
                    frame, "QR CODE", (x, max(15, y - 10)),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 210, 150), 2
                )
    except Exception as e:
        logger.debug("Draw detections error: %s", e)

    return frame
