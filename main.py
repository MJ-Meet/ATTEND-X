"""
ATTEND-X: Main Entry Point
Initializes logging, checks dependencies, and launches the GUI.

Run with:
    python main.py
"""

import sys
import os
import logging
from pathlib import Path

# ─── Ensure project root is on the path ──────────────────────────────────────
sys.path.insert(0, str(Path(__file__).parent))

# ─── Create required directories before anything else ────────────────────────
for d in ("data", "faces", "generated_cards", "exports", "assets"):
    Path(d).mkdir(exist_ok=True)

# ─── Logging ─────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
    ]
)
logger = logging.getLogger("ATTEND-X")


# ─── Dependency check ─────────────────────────────────────────────────────────
def check_dependencies():
    missing = []
    optional_missing = []

    required_packages = {
        "cv2":      "opencv-python",
        "PIL":      "Pillow",
        "qrcode":   "qrcode[pil]",
    }
    optional_packages = {
        "pyzbar":            "pyzbar",
        "face_recognition":  "face_recognition",
    }

    for mod, pkg in required_packages.items():
        try:
            __import__(mod)
        except ImportError:
            missing.append(pkg)

    for mod, pkg in optional_packages.items():
        try:
            __import__(mod)
        except ImportError:
            optional_missing.append((mod, pkg))

    return missing, optional_missing


def _print_banner():
    banner = r"""
   /\    _____ _____ _____  _   _ ____       __  __
  /  \  |_   _|_   _| ____|| \ | |  _ \    \ \/ /
 / /\ \   | |   | | |  _|  |  \| | | | |    \  /
/ ____ \  | |   | | | |___ | |\  | |_| |    /  \
\/    \/  |_|   |_| |_____||_| \_|____/    /_/\_\

 CAMPUS ATTENDANCE TERMINAL
 ─────────────────────────────────────────────
"""
    print(banner)


def main():
    _print_banner()
    logger.info("Starting ATTEND-X…")

    # Check dependencies
    missing, opt_missing = check_dependencies()

    if missing:
        logger.error("Missing required packages: %s", ", ".join(missing))
        print("\n[ERROR] Required packages not installed.")
        print("Run:  pip install " + " ".join(missing))
        print()
        sys.exit(1)

    if opt_missing:
        for mod, pkg in opt_missing:
            if mod == "pyzbar":
                logger.warning(
                    "pyzbar not installed — QR/barcode scanning disabled.\n"
                    "Install with:  pip install pyzbar\n"
                    "Windows may also need:  https://github.com/NaturalHistoryMuseum/pyzbar#installation"
                )
            elif mod == "face_recognition":
                logger.warning(
                    "face_recognition not installed — face identification disabled.\n"
                    "ID card scanning still works.\n"
                    "Install with:  pip install face_recognition\n"
                    "(Also requires: pip install cmake dlib)"
                )

    # Import GUI (after dependency check)
    try:
        import database as db
        db.initialize_database()
        logger.info("Database ready.")
    except Exception as e:
        logger.error("Database init failed: %s", e)
        print(f"\n[ERROR] Database initialization failed: {e}")
        sys.exit(1)

    # Launch GUI
    try:
        from gui import AttendXApp
        app = AttendXApp()
        logger.info("GUI launched.")
        app.mainloop()
    except Exception as e:
        logger.exception("Fatal GUI error: %s", e)
        print(f"\n[FATAL] Application crashed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
