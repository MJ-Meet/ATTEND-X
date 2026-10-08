"""
ATTEND-X: ID Card Attendance Verification Suite
Tests all 10 requirements from Section 16 of the task:
  1. Printed normally
  2. Slightly rotated
  3. Slightly tilted
  4. Different distance from webcam
  5. Different lighting
  6. Card slightly off-center
  7. Repeated scan (duplicate prevention + Verification ID preservation)
  8. Student enrolled in current subject
  9. Student not enrolled
  10. No active session
"""

import os
import sys
import cv2
import numpy as np

# Ensure project root is in path
sys.path.insert(0, os.path.abspath("."))

import database as db
import subjects as sub_mod
import attendance as att_mod
import barcode_scanner

STUDENT_ID = "IU2441230311"


def create_simulated_webcam(card_img, scale=0.5, angle=0.0, offset=(0, 0), brightness=0, contrast=1.0, tilt=False):
    """Embed card image inside a 640x480 webcam frame with simulated real-world conditions."""
    h, w = card_img.shape[:2]
    nw, nh = max(10, int(w * scale)), max(10, int(h * scale))
    resized = cv2.resize(card_img, (nw, nh), interpolation=cv2.INTER_AREA)

    if tilt:
        # Perspective tilt
        pts1 = np.float32([[0, 0], [nw, 0], [0, nh], [nw, nh]])
        pts2 = np.float32([[15, 8], [nw - 10, 20], [0, nh - 10], [nw - 15, nh - 5]])
        M_p = cv2.getPerspectiveTransform(pts1, pts2)
        resized = cv2.warpPerspective(resized, M_p, (nw, nh), borderValue=(130, 130, 130))

    if angle != 0:
        M = cv2.getRotationMatrix2D((nw // 2, nh // 2), angle, 1.0)
        resized = cv2.warpAffine(resized, M, (nw, nh), borderValue=(130, 130, 130))

    if contrast != 1.0 or brightness != 0:
        resized = cv2.convertScaleAbs(resized, alpha=contrast, beta=brightness)

    frame = np.full((480, 640, 3), 130, dtype=np.uint8)
    ox = max(0, min(640 - nw, 100 + offset[0]))
    oy = max(0, min(480 - nh, 80 + offset[1]))
    frame[oy:oy + nh, ox:ox + nw] = resized
    return frame


def run_tests():
    print("=" * 65)
    print(f"RUNNING ATTEND-X ID CARD TESTS FOR STUDENT: {STUDENT_ID}")
    print("=" * 65)

    card_path = f"generated_cards/{STUDENT_ID}_card.png"
    assert os.path.exists(card_path), f"Card file not found: {card_path}"
    card_img = cv2.imread(card_path)
    assert card_img is not None, "Failed to load card image"

    # ── Test 1: Printed Normally ──────────────────────────────────────────────
    print("\n[TEST 1] Printed Normally...")
    f1 = create_simulated_webcam(card_img, scale=0.5)
    r1 = barcode_scanner.scan_frame(f1)
    assert r1["found"] and r1["student_id"] == STUDENT_ID, f"Test 1 Failed: {r1}"
    print(f"  PASS: Decoded {r1['student_id']} via {r1['method']}")

    # ── Test 2: Slightly Rotated ─────────────────────────────────────────────
    print("\n[TEST 2] Slightly Rotated (15 degrees)...")
    f2 = create_simulated_webcam(card_img, scale=0.5, angle=15)
    r2 = barcode_scanner.scan_frame(f2)
    assert r2["found"] and r2["student_id"] == STUDENT_ID, f"Test 2 Failed: {r2}"
    print(f"  PASS: Decoded {r2['student_id']} via {r2['method']}")

    # ── Test 3: Slightly Tilted ──────────────────────────────────────────────
    print("\n[TEST 3] Slightly Tilted (Perspective tilt)...")
    f3 = create_simulated_webcam(card_img, scale=0.5, tilt=True)
    r3 = barcode_scanner.scan_frame(f3)
    assert r3["found"] and r3["student_id"] == STUDENT_ID, f"Test 3 Failed: {r3}"
    print(f"  PASS: Decoded {r3['student_id']} via {r3['method']}")

    # ── Test 4: Different Distance (Far & Close) ─────────────────────────────
    print("\n[TEST 4] Different Distance...")
    # Far (scale 0.38)
    f4_far = create_simulated_webcam(card_img, scale=0.38)
    r4_far = barcode_scanner.scan_frame(f4_far)
    assert r4_far["found"] and r4_far["student_id"] == STUDENT_ID, f"Test 4 Far Failed: {r4_far}"
    print(f"  PASS (Far distance): Decoded {r4_far['student_id']} via {r4_far['method']}")

    # Close (scale 0.72)
    f4_close = create_simulated_webcam(card_img, scale=0.72)
    r4_close = barcode_scanner.scan_frame(f4_close)
    assert r4_close["found"] and r4_close["student_id"] == STUDENT_ID, f"Test 4 Close Failed: {r4_close}"
    print(f"  PASS (Close distance): Decoded {r4_close['student_id']} via {r4_close['method']}")

    # ── Test 5: Different Lighting ───────────────────────────────────────────
    print("\n[TEST 5] Different Lighting (Low contrast & glare)...")
    f5 = create_simulated_webcam(card_img, scale=0.5, contrast=0.75, brightness=35)
    r5 = barcode_scanner.scan_frame(f5)
    assert r5["found"] and r5["student_id"] == STUDENT_ID, f"Test 5 Failed: {r5}"
    print(f"  PASS: Decoded {r5['student_id']} via {r5['method']}")

    # ── Test 6: Card Slightly Off-Center ─────────────────────────────────────
    print("\n[TEST 6] Card Slightly Off-Center (Offset)...")
    f6 = create_simulated_webcam(card_img, scale=0.48, offset=(180, 70))
    r6 = barcode_scanner.scan_frame(f6)
    assert r6["found"] and r6["student_id"] == STUDENT_ID, f"Test 6 Failed: {r6}"
    print(f"  PASS: Decoded {r6['student_id']} via {r6['method']}")

    # ── Subject & Session Setup for Tests 7, 8, 9, 10 ─────────────────────────
    # Store initial active session to restore at the end
    orig_active = db.get_active_session()
    if orig_active:
        sub_mod.end_current_session()

    # Create two temporary test subjects: one enrolled, one not enrolled
    subj_enrolled = db.get_subject_by_code("TEST_ENR")
    if not subj_enrolled:
        sub_mod.add_subject("TEST_ENR", "Card Enrolled Subject", "CSE", "5", "Prof. Test", "R-101")
        subj_enrolled = db.get_subject_by_code("TEST_ENR")

    subj_not_enr = db.get_subject_by_code("TEST_NOENR")
    if not subj_not_enr:
        sub_mod.add_subject("TEST_NOENR", "Card Not Enrolled Subject", "CSE", "5", "Prof. Test", "R-102")
        subj_not_enr = db.get_subject_by_code("TEST_NOENR")

    # Set enrollment: STUDENT_ID in TEST_ENR, NOT in TEST_NOENR
    sub_mod.set_enrolled_students(subj_enrolled["id"], [STUDENT_ID])
    sub_mod.set_enrolled_students(subj_not_enr["id"], ["TEST_SOMEONE_ELSE"])

    # ── Test 10: No Active Session ───────────────────────────────────────────
    print("\n[TEST 10] No Active Session Check...")
    # Verify no session is active right now
    assert db.get_active_session() is None
    res_nosess = att_mod.mark_by_barcode(STUDENT_ID)
    assert res_nosess["status"] == "no_session", f"Expected 'no_session', got: {res_nosess}"
    print(f"  PASS: Blocked marking attendance when no session active (status={res_nosess['status']})")

    # ── Test 9: Student Not Enrolled ─────────────────────────────────────────
    print("\n[TEST 9] Student Not Enrolled in Current Subject...")
    ok, sess_noenr = sub_mod.start_attendance_session(subj_not_enr["id"])
    assert ok, f"Failed to start session: {sess_noenr}"
    res_notenr = att_mod.mark_by_barcode(f"Student ID: {STUDENT_ID}")
    assert res_notenr["status"] == "not_enrolled", f"Expected 'not_enrolled', got: {res_notenr}"
    print(f"  PASS: Blocked unenrolled student (status={res_notenr['status']}, msg='{res_notenr['message']}')")
    sub_mod.end_current_session()

    # ── Test 8: Student Enrolled in Current Subject ──────────────────────────
    print("\n[TEST 8] Student Enrolled in Current Subject...")
    ok, sess_enr = sub_mod.start_attendance_session(subj_enrolled["id"])
    assert ok, f"Failed to start session: {sess_enr}"
    res_enr = att_mod.mark_by_barcode(STUDENT_ID)
    assert res_enr["status"] == "ok", f"Expected 'ok', got: {res_enr}"
    assert res_enr["method"] == "ID CARD", f"Expected method 'ID CARD', got: {res_enr['method']}"
    assert res_enr["attendance_id"].startswith("AX-"), f"Invalid attendance_id: {res_enr['attendance_id']}"
    orig_att_id = res_enr["attendance_id"]
    print(f"  PASS: Marked attendance via ID CARD: {res_enr['student_name']} ({res_enr['student_id']})")
    print(f"        Generated Verification ID: {orig_att_id}")

    # ── Test 7: Repeated Scan / Duplicate Check ──────────────────────────────
    print("\n[TEST 7] Repeated Scan (Duplicate Check & Verification ID)...")
    res_dup = att_mod.mark_by_barcode(f"ID={STUDENT_ID}")
    assert res_dup["status"] == "duplicate", f"Expected 'duplicate', got: {res_dup}"
    assert res_dup["attendance_id"] == orig_att_id, f"Verification ID changed! Expected {orig_att_id}, got {res_dup['attendance_id']}"
    print(f"  PASS: Prevented duplicate attendance (status=duplicate)")
    print(f"        Preserved original Verification ID: {res_dup['attendance_id']}")

    # Clean up test subjects & restore previous session
    sub_mod.end_current_session()
    sub_mod.delete_subject(subj_enrolled["id"])
    sub_mod.delete_subject(subj_not_enr["id"])
    if orig_active:
        sub_mod.start_attendance_session(orig_active["subject_id"])
        print(f"\nRestored active session #{orig_active['id']} for {orig_active['subject_code']}")

    print("\n" + "=" * 65)
    print("ALL 10 REQUIREMENTS FROM SECTION 16 PASSED SUCCESSFULLY!")
    print("=" * 65)


if __name__ == "__main__":
    run_tests()
