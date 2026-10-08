"""
ATTEND-X: Camera Module
Manages the camera capture loop, automatic face/barcode detection,
and publishes detection events via a callback.
"""

import threading
import logging
import time
import queue
from pathlib import Path

import cv2

import barcode_scanner
import face_recognition_module as frm

logger = logging.getLogger(__name__)

FACES_DIR = Path("faces")


class DetectionEvent:
    """Carries detection results from the camera thread to the GUI thread."""
    FACE            = "FACE"
    BARCODE         = "BARCODE"
    CARD_UNREADABLE = "CARD_UNREADABLE"
    NONE            = "NONE"

    def __init__(self, kind: str, data=None, frame=None, metadata: dict = None):
        self.kind     = kind   # FACE | BARCODE | CARD_UNREADABLE | NONE
        self.data     = data   # face locations list  OR  barcode string value
        self.frame    = frame  # current BGR frame (may be None)
        self.metadata = metadata or {}


class CameraManager:
    """
    Runs a background thread that continuously reads frames.
    - Detects barcodes/cards every frame (fast staged multi-pass).
    - Detects/identifies faces every N frames (heavier).
    - On detection, invokes the `on_detection` callback in the calling thread
      via a thread-safe queue.
    - Publishes raw frames for the preview via `on_frame` callback.
    """

    FACE_DETECT_INTERVAL = 8   # run face detection every N frames
    COOLDOWN_SECONDS     = 3.0 # seconds to wait after a detection before next

    def __init__(self, camera_index: int = 0):
        self.camera_index   = camera_index
        self.cap            = None
        self._running       = False
        self._thread        = None
        self._event_queue   = queue.Queue(maxsize=4)
        self._known_encodings: list = []

        # Callbacks set by GUI
        self.on_frame     = None   # on_frame(frame: np.ndarray)
        self.on_detection = None   # on_detection(event: DetectionEvent)

        # State
        self._last_detection_time       = 0.0
        self._frame_counter             = 0
        self._card_unreadable_counter   = 0
        self._paused                    = False
        self.available                  = False

    # ─── Public API ───────────────────────────────────────────────────────────

    def set_known_encodings(self, encodings: list):
        """Thread-safe update of known face encodings."""
        self._known_encodings = encodings

    def start(self) -> bool:
        """Open camera and start background thread. Returns True on success."""
        try:
            self.cap = cv2.VideoCapture(self.camera_index, cv2.CAP_DSHOW)
            if not self.cap.isOpened():
                self.cap = cv2.VideoCapture(self.camera_index)
            if not self.cap.isOpened():
                logger.error("Could not open camera index %d", self.camera_index)
                self.available = False
                return False

            self.cap.set(cv2.CAP_PROP_FRAME_WIDTH,  640)
            self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
            self.cap.set(cv2.CAP_PROP_FPS,          30)

            self.available = True
            self._running  = True
            self._thread   = threading.Thread(target=self._loop, daemon=True)
            self._thread.start()
            logger.info("Camera started (index %d)", self.camera_index)
            return True
        except Exception as e:
            logger.error("Camera start error: %s", e)
            self.available = False
            return False

    def stop(self):
        self._running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2)
        if self.cap:
            try:
                if self.cap.isOpened():
                    self.cap.release()
            except Exception:
                pass
            self.cap = None
        self.available = False

    def pause(self):
        """Pause detection (used during face capture / registration)."""
        self._paused = True

    def resume(self):
        """Resume detection."""
        self._paused = False
        self._last_detection_time = time.time()  # restart cooldown

    def trigger_cooldown(self, seconds: float = None):
        """Call after processing a detection to block further events briefly."""
        self._last_detection_time = time.time() + (seconds or self.COOLDOWN_SECONDS)

    def capture_still(self):
        """Capture a single frame. Thread-safe."""
        if hasattr(self, "_last_frame") and self._last_frame is not None:
            return self._last_frame.copy()
        if self.cap and self.cap.isOpened():
            ret, frame = self.cap.read()
            return cv2.flip(frame, 1) if ret else None
        return None

    def drain_events(self):
        """Drain pending detection events; returns list of DetectionEvent."""
        events = []
        try:
            while True:
                events.append(self._event_queue.get_nowait())
        except queue.Empty:
            pass
        return events

    # ─── Background loop ──────────────────────────────────────────────────────

    def _loop(self):
        while self._running:
            if not self.cap or not self.cap.isOpened():
                time.sleep(0.1)
                continue

            ret, frame = self.cap.read()
            if not ret:
                time.sleep(0.05)
                continue

            # Flip for natural mirror feel
            frame = cv2.flip(frame, 1)
            self._frame_counter += 1
            self._last_frame = frame

            # Always publish frame for preview
            if self.on_frame:
                try:
                    self.on_frame(frame.copy())
                except Exception:
                    pass

            if self._paused:
                time.sleep(0.03)
                continue

            now = time.time()
            in_cooldown = now < self._last_detection_time

            if not in_cooldown:
                # ── Barcode / ID Card scan (staged: fast multi-pass first) ──
                scan_res = barcode_scanner.scan_frame(frame, allow_ocr=False)
                if scan_res["found"]:
                    self._card_unreadable_counter = 0
                    self._emit(DetectionEvent(
                        DetectionEvent.BARCODE,
                        data=scan_res["student_id"],
                        frame=frame.copy(),
                        metadata=scan_res
                    ))
                    self._last_detection_time = now + self.COOLDOWN_SECONDS
                    continue

                if scan_res["card_detected"]:
                    self._card_unreadable_counter += 1
                    # If card held steady for ~4 frames without QR decode:
                    if self._card_unreadable_counter >= 4:
                        # Stage 4: Try OCR fallback
                        ocr_res = barcode_scanner.scan_frame(frame, allow_ocr=True)
                        if ocr_res["found"]:
                            self._card_unreadable_counter = 0
                            self._emit(DetectionEvent(
                                DetectionEvent.BARCODE,
                                data=ocr_res["student_id"],
                                frame=frame.copy(),
                                metadata=ocr_res
                            ))
                            self._last_detection_time = now + self.COOLDOWN_SECONDS
                            continue
                        else:
                            # Card visible in scanning area but could not be decoded
                            self._card_unreadable_counter = 0
                            self._emit(DetectionEvent(
                                DetectionEvent.CARD_UNREADABLE,
                                data=None,
                                frame=frame.copy(),
                                metadata=ocr_res
                            ))
                            self._last_detection_time = now + 2.5
                            continue
                else:
                    self._card_unreadable_counter = 0

                # ── Face detection (every N frames – heavier) ──
                if self._frame_counter % self.FACE_DETECT_INTERVAL == 0:
                    face_locs = frm.detect_faces_in_frame(frame)
                    if face_locs:
                        if frm.FACE_RECOGNITION_AVAILABLE and self._known_encodings:
                            match_info = frm.identify_face(frame, self._known_encodings, tolerance=0.50)
                            if match_info is not None:
                                evt = DetectionEvent(DetectionEvent.FACE,
                                                     data=match_info,
                                                     frame=frame.copy())
                            else:
                                evt = DetectionEvent(DetectionEvent.FACE,
                                                     data={"matched": False, "locations": face_locs},
                                                     frame=frame.copy())
                        else:
                            evt = DetectionEvent(DetectionEvent.FACE,
                                                 data={"matched": False, "locations": face_locs},
                                                 frame=frame.copy())
                        self._emit(evt)
                        self._last_detection_time = now + self.COOLDOWN_SECONDS

            time.sleep(0.03)  # ~30 fps target

    def _emit(self, event: DetectionEvent):
        """Put event on queue; discard if full."""
        try:
            self._event_queue.put_nowait(event)
        except queue.Full:
            pass


# ─── Photo capture helper ─────────────────────────────────────────────────────

def capture_student_photo(cap: cv2.VideoCapture, student_id: str,
                           num_samples: int = 1) -> list[str]:
    """
    Capture `num_samples` frames and save them as student face photos.
    Returns list of saved file paths.
    """
    FACES_DIR.mkdir(exist_ok=True)
    saved = []
    for i in range(num_samples):
        ret, frame = cap.read()
        if not ret:
            break
        frame = cv2.flip(frame, 1)
        path = str(FACES_DIR / f"{student_id}_{i}.jpg")
        cv2.imwrite(path, frame)
        saved.append(path)
        if num_samples > 1:
            time.sleep(0.3)
    return saved
