"""
ATTEND-X: Face Recognition Module
Wraps the `face_recognition` library with graceful fallback if unavailable.
"""

import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)

FACES_DIR = Path("faces")

# ─── Availability check ───────────────────────────────────────────────────────

try:
    import face_recognition as _fr
    import numpy as np
    FACE_RECOGNITION_AVAILABLE = True
    logger.info("face_recognition library loaded successfully.")
except ImportError:
    FACE_RECOGNITION_AVAILABLE = False
    logger.warning(
        "face_recognition not available. Face identification will be disabled. "
        "ID card scanning still works."
    )


# ─── Encoding ─────────────────────────────────────────────────────────────────

def encode_face_from_frame(frame):
    """
    Given an OpenCV BGR frame, detect the largest face and return its encoding.
    Returns (encoding, face_location) or (None, None) if no face found.
    """
    if not FACE_RECOGNITION_AVAILABLE:
        return None, None

    import cv2
    try:
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        locations = _fr.face_locations(rgb, model="hog")
        if not locations:
            return None, None
        # Pick the largest face
        locations_sorted = sorted(
            locations,
            key=lambda loc: (loc[2] - loc[0]) * (loc[1] - loc[3]),
            reverse=True
        )
        loc = locations_sorted[0]
        encodings = _fr.face_encodings(rgb, [loc])
        if not encodings:
            return None, None
        return encodings[0], loc
    except Exception as e:
        logger.error("encode_face_from_frame error: %s", e)
        return None, None


def encode_face_from_image_path(image_path: str):
    """
    Load an image file and return the face encoding.
    Returns encoding or None.
    """
    if not FACE_RECOGNITION_AVAILABLE:
        return None
    try:
        image = _fr.load_image_file(image_path)
        encs  = _fr.face_encodings(image)
        return encs[0] if encs else None
    except Exception as e:
        logger.error("encode_face_from_image_path error: %s", e)
        return None


# ─── Detection (no identification) ────────────────────────────────────────────

def detect_faces_in_frame(frame) -> list:
    """
    Returns a list of face bounding boxes (top, right, bottom, left) in the frame.
    Returns empty list if face_recognition is unavailable or no faces found.
    """
    if not FACE_RECOGNITION_AVAILABLE:
        return _detect_faces_opencv(frame)

    import cv2
    try:
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        return _fr.face_locations(rgb, model="hog")
    except Exception as e:
        logger.error("detect_faces error: %s", e)
        return []


_cached_cascade = None


def _get_cascade():
    global _cached_cascade
    if _cached_cascade is None:
        import cv2
        try:
            if hasattr(cv2, "data") and hasattr(cv2.data, "haarcascades") and hasattr(cv2, "CascadeClassifier"):
                cascade_path = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
                if os.path.exists(cascade_path):
                    casc = cv2.CascadeClassifier(cascade_path)
                    if not casc.empty():
                        _cached_cascade = casc
        except Exception as e:
            logger.debug("Failed to load OpenCV cascade: %s", e)
    return _cached_cascade


def _detect_faces_opencv(frame) -> list:
    """
    Fallback face detection using OpenCV Haar cascades.
    Returns list of (top, right, bottom, left) tuples.
    """
    import cv2
    try:
        cascade = _get_cascade()
        if cascade is None:
            return []
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        faces = cascade.detectMultiScale(
            gray, scaleFactor=1.1, minNeighbors=5, minSize=(60, 60)
        )
        result = []
        for (x, y, w, h) in faces:
            result.append((y, x + w, y + h, x))  # top, right, bottom, left
        return result
    except Exception as e:
        logger.error("OpenCV face detection error: %s", e)
        return []


# ─── Identification ───────────────────────────────────────────────────────────

def identify_face(frame, known_encodings: list, tolerance: float = 0.50) -> dict | None:
    """
    Identify a face in the given frame against a list of known encodings.

    known_encodings: list of {student_id, name, encoding}

    Returns:
      - dict with {"matched": True, "student_id": ..., "name": ..., "distance": ...} if matched within tolerance.
      - dict with {"matched": False, "student_id": None, "name": None, "distance": ...} if face detected but no student matches.
      - None if no face detected in frame.
    """
    if not FACE_RECOGNITION_AVAILABLE:
        return None

    try:
        query_enc, loc = encode_face_from_frame(frame)
        if query_enc is None:
            return None

        if not known_encodings:
            return {
                "matched": False,
                "student_id": None,
                "name": None,
                "distance": 1.0,
                "location": loc,
            }

        stored_encs  = [e["encoding"] for e in known_encodings]
        distances    = _fr.face_distance(stored_encs, query_enc)
        best_idx     = int(distances.argmin())
        best_dist    = float(distances[best_idx])

        if best_dist <= tolerance:
            match = known_encodings[best_idx]
            return {
                "matched":    True,
                "student_id": match["student_id"],
                "name":       match["name"],
                "distance":   round(best_dist, 4),
                "location":   loc,
            }
        else:
            return {
                "matched":    False,
                "student_id": None,
                "name":       None,
                "distance":   round(best_dist, 4),
                "location":   loc,
            }
    except Exception as e:
        logger.error("identify_face error: %s", e)
        return None


# ─── Drawing helpers ──────────────────────────────────────────────────────────

def draw_face_boxes(frame, face_locations: list, label: str = ""):
    """Draw green boxes around detected faces."""
    import cv2
    for (top, right, bottom, left) in face_locations:
        cv2.rectangle(frame, (left, top), (right, bottom), (0, 210, 150), 2)
        if label:
            cv2.putText(frame, label, (left, top - 8),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 210, 150), 1)
    return frame
