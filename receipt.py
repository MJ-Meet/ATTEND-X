"""
ATTEND-X: Attendance Receipt Generator
Generates a digital attendance verification receipt as a high-resolution PNG image.
"""

import logging
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

logger = logging.getLogger(__name__)

RECEIPTS_DIR = Path("exports") / "receipts"

# Card dimensions
RECEIPT_W = 540
RECEIPT_H = 680

# Colors (terminal security palette)
BG_COLOR      = (10, 12, 16)       # #0a0c10
SURFACE_COLOR = (18, 22, 32)       # #121620
BORDER_COLOR  = (0, 210, 150)      # emerald accent
TEXT_COLOR    = (230, 232, 235)    # near-white
MUTED_COLOR   = (120, 130, 145)    # muted grey
CYAN_COLOR    = (56, 189, 248)     # cyan accent


def _font(size: int, bold: bool = False):
    candidates = (
        ["consolab.ttf", "arialbd.ttf"] if bold else
        ["consola.ttf", "cour.ttf", "arial.ttf"]
    )
    for name in candidates:
        try:
            return ImageFont.truetype(name, size)
        except (IOError, OSError):
            continue
    return ImageFont.load_default()


def generate_receipt_image(receipt_data: dict, output_path: str = None) -> str | None:
    """
    Renders receipt_data into a PNG image and saves it.
    receipt_data keys:
      name, student_id, subject_name, subject_code, date, time, method, status, attendance_id
    """
    RECEIPTS_DIR.mkdir(parents=True, exist_ok=True)

    att_id = receipt_data.get("attendance_id") or "AX-RECEIPT"
    if output_path is None:
        safe_id = "".join(c if c.isalnum() or c in "-_" else "_" for c in att_id)
        output_path = str(RECEIPTS_DIR / f"{safe_id}.png")

    try:
        img = Image.new("RGB", (RECEIPT_W, RECEIPT_H), BG_COLOR)
        draw = ImageDraw.Draw(img)

        # Outer border
        draw.rectangle([0, 0, RECEIPT_W - 1, RECEIPT_H - 1], outline=BORDER_COLOR, width=2)
        # Inner subtle box
        draw.rectangle([12, 12, RECEIPT_W - 13, RECEIPT_H - 13], outline=SURFACE_COLOR, width=1)

        # Header banner
        draw.rectangle([12, 12, RECEIPT_W - 13, 85], fill=SURFACE_COLOR)
        draw.line([(12, 85), (RECEIPT_W - 13, 85)], fill=BORDER_COLOR, width=1)

        f_title = _font(22, bold=True)
        f_sub = _font(13)
        draw.text((RECEIPT_W // 2, 34), "ATTEND-X", font=f_title, fill=BORDER_COLOR, anchor="mm")
        draw.text((RECEIPT_W // 2, 62), "ATTENDANCE VERIFIED", font=f_sub, fill=CYAN_COLOR, anchor="mm")

        # Content area
        f_lbl = _font(12)
        f_val = _font(18, bold=True)
        f_val_sm = _font(14, bold=True)
        f_mono = _font(15, bold=True)

        y = 105

        # Student block
        draw.text((36, y), "STUDENT", font=f_lbl, fill=MUTED_COLOR)
        y += 20
        draw.text((36, y), receipt_data.get("name", "Unknown"), font=f_val, fill=TEXT_COLOR)
        y += 26
        draw.text((36, y), receipt_data.get("student_id", ""), font=f_mono, fill=BORDER_COLOR)
        y += 34

        draw.line([(36, y), (RECEIPT_W - 36, y)], fill=SURFACE_COLOR, width=1)
        y += 16

        # Subject block
        draw.text((36, y), "SUBJECT", font=f_lbl, fill=MUTED_COLOR)
        y += 20
        draw.text((36, y), receipt_data.get("subject_name", "General"), font=f_val_sm, fill=TEXT_COLOR)
        y += 24
        draw.text((36, y), receipt_data.get("subject_code", ""), font=f_mono, fill=CYAN_COLOR)
        y += 34

        draw.line([(36, y), (RECEIPT_W - 36, y)], fill=SURFACE_COLOR, width=1)
        y += 18

        # Metadata grid
        meta_items = [
            ("DATE", receipt_data.get("date", "")),
            ("TIME", receipt_data.get("time", "")),
            ("METHOD", receipt_data.get("method", "FACE")),
            ("STATUS", receipt_data.get("status", "PRESENT")),
        ]

        for label, val in meta_items:
            draw.text((36, y), label, font=f_lbl, fill=MUTED_COLOR)
            draw.text((160, y), val, font=f_mono, fill=BORDER_COLOR if label == "STATUS" else TEXT_COLOR)
            y += 28

        y += 10
        draw.line([(36, y), (RECEIPT_W - 36, y)], fill=SURFACE_COLOR, width=1)
        y += 20

        # Attendance ID
        draw.text((36, y), "ATTENDANCE ID", font=f_lbl, fill=MUTED_COLOR)
        y += 22
        draw.text((36, y), att_id, font=f_mono, fill=BORDER_COLOR)
        y += 45

        # Verified badge
        badge_y = RECEIPT_H - 75
        draw.rectangle([36, badge_y, RECEIPT_W - 36, badge_y + 44], fill=SURFACE_COLOR, outline=BORDER_COLOR, width=1)
        draw.text((RECEIPT_W // 2, badge_y + 22), "✓  OFFICIALLY RECORDED IN DATABASE",
                  font=_font(13, bold=True), fill=BORDER_COLOR, anchor="mm")

        img.save(output_path, "PNG", dpi=(150, 150))
        logger.info("Receipt image saved: %s", output_path)
        return output_path
    except Exception as e:
        logger.error("Failed to generate receipt image: %s", e)
        return None
