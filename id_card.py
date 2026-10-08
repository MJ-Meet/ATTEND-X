"""
ATTEND-X: ID Card Generator
Generates a printable college-style ID card as a PNG image.
Includes the student photo, name, ID, branch, semester, and a QR code.
"""

import logging
import os
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
import qrcode

logger = logging.getLogger(__name__)

CARDS_DIR = Path("generated_cards")
FACES_DIR = Path("faces")

# Card dimensions (pixels at 150 DPI → ~5.4 × 3.4 inches)
CARD_W = 810
CARD_H = 510

# Colors  (dark terminal palette)
BG_COLOR      = (15, 17, 21)       # near-black
SURFACE_COLOR = (22, 26, 34)       # dark surface
BORDER_COLOR  = (0, 210, 150)      # green accent
TEXT_COLOR    = (230, 232, 235)    # near-white
MUTED_COLOR   = (110, 118, 129)    # muted grey
ACCENT_COLOR  = (0, 210, 150)      # green

# ─── Font helpers ──────────────────────────────────────────────────────────────

def _font(size: int):
    """Try to load a system monospace or sans font; fall back to default."""
    candidates = [
        "consola.ttf",  "consolab.ttf",  # Consolas (Windows)
        "cour.ttf",                        # Courier New
        "DejaVuSansMono.ttf",
        "LiberationMono-Regular.ttf",
        "arial.ttf",
    ]
    for name in candidates:
        try:
            return ImageFont.truetype(name, size)
        except (IOError, OSError):
            continue
    return ImageFont.load_default()


def _font_bold(size: int):
    candidates = [
        "consolab.ttf",
        "arialbd.ttf",
        "DejaVuSans-Bold.ttf",
        "LiberationMono-Bold.ttf",
    ]
    for name in candidates:
        try:
            return ImageFont.truetype(name, size)
        except (IOError, OSError):
            continue
    return ImageFont.load_default()


# ─── QR code generation ────────────────────────────────────────────────────────

def generate_qr(data: str, box_size: int = 6, border: int = 3) -> Image.Image:
    qr = qrcode.QRCode(
        version=None,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=box_size,
        border=border,
    )
    qr.add_data(data)
    qr.make(fit=True)
    # Standard high-contrast QR (dark modules on white background) for reliable printing and webcam detection
    img = qr.make_image(fill_color=(15, 17, 21), back_color=(255, 255, 255))
    return img.convert("RGB")


# ─── Card generation ───────────────────────────────────────────────────────────

def generate_id_card(student: dict, output_path: str = None) -> str | None:
    """
    Generate a PNG ID card for the given student dict.
    Returns the saved file path, or None on error.

    student dict keys: student_id, name, branch, semester, photo_path
    """
    CARDS_DIR.mkdir(exist_ok=True)

    if output_path is None:
        raw_id = str(student.get("student_id", "card"))
        safe_id = "".join(c if c.isalnum() or c in "-_" else "_" for c in raw_id)
        output_path = str(CARDS_DIR / f"{safe_id}_card.png")

    try:
        card = Image.new("RGB", (CARD_W, CARD_H), BG_COLOR)
        draw = ImageDraw.Draw(card)

        # ── Outer border ──
        draw.rectangle([0, 0, CARD_W - 1, CARD_H - 1],
                        outline=BORDER_COLOR, width=3)

        # ── Header strip ──
        draw.rectangle([0, 0, CARD_W, 60], fill=SURFACE_COLOR)
        draw.line([(0, 60), (CARD_W, 60)], fill=BORDER_COLOR, width=1)

        header_font  = _font_bold(20)
        subhead_font = _font(13)

        draw.text((CARD_W // 2, 18), "ATTEND-X",
                  font=header_font, fill=ACCENT_COLOR, anchor="mm")
        draw.text((CARD_W // 2, 44), "CAMPUS ATTENDANCE TERMINAL",
                  font=subhead_font, fill=MUTED_COLOR, anchor="mm")

        # ── Photo area (left column) ──
        photo_x, photo_y = 40, 90
        photo_w, photo_h = 160, 180

        photo_loaded = False
        photo_path = student.get("photo_path")
        if photo_path and Path(photo_path).exists():
            try:
                photo_img = Image.open(photo_path).convert("RGB")
                photo_img = photo_img.resize((photo_w, photo_h), Image.LANCZOS)
                card.paste(photo_img, (photo_x, photo_y))
                draw.rectangle(
                    [photo_x, photo_y, photo_x + photo_w, photo_y + photo_h],
                    outline=BORDER_COLOR, width=2
                )
                photo_loaded = True
            except Exception:
                pass

        if not photo_loaded:
            # Placeholder box
            draw.rectangle(
                [photo_x, photo_y, photo_x + photo_w, photo_y + photo_h],
                outline=BORDER_COLOR, width=2, fill=SURFACE_COLOR
            )
            ph_font = _font(11)
            draw.text((photo_x + photo_w // 2, photo_y + photo_h // 2),
                      "PHOTO", font=ph_font, fill=MUTED_COLOR, anchor="mm")

        # ── Student info (right column) ──
        info_x = photo_x + photo_w + 36
        info_y = 90

        name_font   = _font_bold(26)
        id_font     = _font(18)
        label_font  = _font(12)
        value_font  = _font_bold(14)

        # Name
        draw.text((info_x, info_y), student.get("name", "Unknown"),
                  font=name_font, fill=TEXT_COLOR)
        info_y += 38

        # Student ID – accented
        draw.text((info_x, info_y), student.get("student_id", ""),
                  font=id_font, fill=ACCENT_COLOR)
        info_y += 34

        # Thin separator
        draw.line([(info_x, info_y), (CARD_W - 40, info_y)],
                  fill=SURFACE_COLOR, width=1)
        info_y += 12

        # Branch
        draw.text((info_x, info_y), "BRANCH", font=label_font, fill=MUTED_COLOR)
        info_y += 17
        draw.text((info_x, info_y), student.get("branch", "—"),
                  font=value_font, fill=TEXT_COLOR)
        info_y += 28

        # Semester
        draw.text((info_x, info_y), "SEMESTER", font=label_font, fill=MUTED_COLOR)
        info_y += 17
        draw.text((info_x, info_y), f"Semester {student.get('semester', '—')}",
                  font=value_font, fill=TEXT_COLOR)

        # ── QR Code ──
        qr_data = student.get("barcode_value") or student.get("student_id", "")
        qr_size = 160
        qr_img  = generate_qr(qr_data, box_size=5, border=3)
        qr_img  = qr_img.resize((qr_size, qr_size), Image.LANCZOS)

        qr_x = CARD_W - qr_size - 40
        qr_y = 80
        # High-contrast white badge container for printable QR code
        draw.rectangle(
            [qr_x - 4, qr_y - 4, qr_x + qr_size + 4, qr_y + qr_size + 4],
            fill=(255, 255, 255), outline=BORDER_COLOR, width=2
        )
        card.paste(qr_img, (qr_x, qr_y))

        # QR label
        qr_label_font = _font(10)
        draw.text((qr_x + qr_size // 2, qr_y + qr_size + 10),
                  "SCAN FOR ATTENDANCE",
                  font=qr_label_font, fill=MUTED_COLOR, anchor="mm")

        # ── Footer ──
        footer_y = CARD_H - 42
        draw.line([(0, footer_y), (CARD_W, footer_y)], fill=SURFACE_COLOR, width=1)
        footer_font = _font(11)
        draw.text((20, footer_y + 12),
                  "Face data stored locally.  No footage recorded.  — ATTEND-X",
                  font=footer_font, fill=MUTED_COLOR)

        # ── Accent bar on left edge ──
        draw.rectangle([0, 0, 5, CARD_H], fill=ACCENT_COLOR)

        card.save(output_path, "PNG", dpi=(150, 150))
        logger.info("ID card saved: %s", output_path)
        return output_path

    except Exception as e:
        logger.error("ID card generation error: %s", e)
        return None


def get_card_path(student_id: str) -> str:
    return str(CARDS_DIR / f"{student_id}_card.png")
