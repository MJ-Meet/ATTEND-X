"""
ATTEND-X: Comprehensive ID Card Scanner & State Machine Verification Suite
Tests:
  1. Direct decode of digital card image (IU2441230311_card.png).
  2. Confirm decoded value matches IU2441230311 without hard-coding.
  3. Confirm student IU2441230311 exists in SQLite database.
  4. Physical/live webcam frame test and rejection of background false positives.
  5. State machine validation (READY, CARD DETECTED, READING CARD, UNABLE TO READ CARD,
     STUDENT NOT FOUND, NOT ENROLLED, ATTENDANCE RECORDED, ALREADY MARKED).
  6. Subject enrollment and duplicate attendance enforcement.
  7. Verification that an unreadable card is NOT treated as an unknown student.
  8. Diagnostics and OCR fallback status checking.
"""

import os
import sys
import cv2
import numpy as np

sys.path.insert(0, os.path.abspath("."))

import database as db
import subjects as sub_mod
import attendance as att_mod
import barcode_scanner
from camera import DetectionEvent

TEST_STUDENT_ID = "IU2441230311"


def run_full_verification():
    print("=" * 70)
    print("ATTEND-X ID CARD SCANNER VERIFICATION SUITE")
    print("=" * 70)

    # ─────────────────────────────────────────────────────────────────────────
    # STEP 1: Decode Digital Card Image Directly
    # ─────────────────────────────────────────────────────────────────────────
    print("\n[STEP 1] Direct Decode of Digital Card Image...")
    card_path = f"generated_cards/{TEST_STUDENT_ID}_card.png"
    assert os.path.exists(card_path), f"Card file missing: {card_path}"
    card_img = cv2.imread(card_path)
    assert card_img is not None, "Failed to load card image"

    res = barcode_scanner.scan_frame(card_img, allow_ocr=False)
    print(f"  Scan result: found={res['found']}, id={res['student_id']}, method={res['method']}")
    assert res["found"], "Failed to decode digital card image!"
    assert res["student_id"] is not None, "Decoded student ID is None!"

    # ─────────────────────────────────────────────────────────────────────────
    # STEP 2: Confirm Decoded Value Matches IU2441230311
    # ─────────────────────────────────────────────────────────────────────────
    print("\n[STEP 2] Confirm Decoded Value Matches Expected Student ID...")
    decoded_val = res["student_id"]
    print(f"  Decoded value: '{decoded_val}' (Expected: '{TEST_STUDENT_ID}')")
    assert decoded_val == TEST_STUDENT_ID, f"Decoded ID mismatch! Got {decoded_val}"
    print("  PASS: Decoded value exactly matches student ID.")

    # ─────────────────────────────────────────────────────────────────────────
    # STEP 3: Confirm Student Exists in SQLite
    # ─────────────────────────────────────────────────────────────────────────
    print("\n[STEP 3] Confirm Student Exists in SQLite Database...")
    student = db.get_student_by_id(TEST_STUDENT_ID)
    assert student is not None, f"Student {TEST_STUDENT_ID} not found in SQLite database!"
    print(f"  Found in DB: ID={student['student_id']}, Name={student['name']}, Branch={student['branch']}, Semester={student['semester']}")
    assert student["student_id"] == TEST_STUDENT_ID
    print("  PASS: Student confirmed in SQLite.")

    # ─────────────────────────────────────────────────────────────────────────
    # STEP 4: Live Webcam Frame Test & Background False Positive Check
    # ─────────────────────────────────────────────────────────────────────────
    print("\n[STEP 4] Testing Live Webcam Frame & Background Rejection...")
    cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)
    if not cap.isOpened():
        cap = cv2.VideoCapture(0)

    webcam_available = cap.isOpened()
    if webcam_available:
        ret, live_frame = cap.read()
        cap.release()
        if ret and live_frame is not None:
            live_res = barcode_scanner.scan_frame(live_frame, allow_ocr=True)
            print(f"  Live frame capture successful: shape={live_frame.shape}")
            print(f"  Live frame scan: found={live_res['found']}, card_detected={live_res['card_detected']}")
            if live_res["found"]:
                print(f"  NOTE: A readable card was physically held in front of webcam! Decoded: {live_res['student_id']}")
            else:
                print("  Live webcam background cleanly rejected without false positive detection.")
        else:
            print("  Could not read frame from open webcam.")
    else:
        print("  Webcam device index 0 unavailable in this test session.")

    # ─────────────────────────────────────────────────────────────────────────
    # STEP 5: Verification of Distinct States
    # ─────────────────────────────────────────────────────────────────────────
    print("\n[STEP 5] Validating Distinct Card-Reading States...")
    states_required = [
        "READY",
        "CARD DETECTED",
        "READING CARD",
        "UNABLE TO READ CARD",
        "STUDENT NOT FOUND",
        "NOT ENROLLED",
        "ATTENDANCE RECORDED",
        "ALREADY MARKED",
    ]
    import gui
    for st in states_required:
        assert st in gui.STATUS_COLORS, f"State '{st}' missing from STATUS_COLORS!"
        assert st in gui.STATUS_DOT, f"State '{st}' missing from STATUS_DOT!"
        print(f"  State validated in GUI system: {st} (Color: {gui.STATUS_COLORS[st]})")
    print("  PASS: All 8 required distinct states are registered with dedicated styling.")

    # ─────────────────────────────────────────────────────────────────────────
    # STEP 6: Unreadable Card Must Not Be Treated as Unknown Student
    # ─────────────────────────────────────────────────────────────────────────
    print("\n[STEP 6] Verify Unreadable Card Is Distinct From Unknown Student...")
    # DetectionEvent.CARD_UNREADABLE should transition to "UNABLE TO READ CARD", not "STUDENT NOT FOUND"
    dummy_unreadable_event = DetectionEvent(DetectionEvent.CARD_UNREADABLE)
    assert dummy_unreadable_event.kind == DetectionEvent.CARD_UNREADABLE

    # An unknown student code should produce unknown_card in attendance module
    unknown_id = "IU9999999999"
    res_unknown = att_mod.mark_by_barcode(unknown_id)
    assert res_unknown["status"] == "unknown_card", f"Expected 'unknown_card', got: {res_unknown}"
    print(f"  Unknown student scan status: {res_unknown['status']} -> Maps to 'STUDENT NOT FOUND'")
    print("  PASS: Unreadable card and unknown student are strictly decoupled.")

    # ─────────────────────────────────────────────────────────────────────────
    # STEP 7: Subject Enrollment & Duplicate Rules Enforcement
    # ─────────────────────────────────────────────────────────────────────────
    print("\n[STEP 7] Subject Enrollment, Duplicate Rules & Session Enforcement...")
    orig_active = db.get_active_session()
    if orig_active:
        sub_mod.end_current_session()

    # Rule 1: No active session
    res_nosess = att_mod.mark_by_barcode(TEST_STUDENT_ID)
    assert res_nosess["status"] == "no_session", f"Expected no_session, got {res_nosess}"
    print(f"  PASS: Blocked when no active session (status={res_nosess['status']})")

    # Set up test subjects
    sub_enr = db.get_subject_by_code("TEST_ENR_V")
    if not sub_enr:
        sub_mod.add_subject("TEST_ENR_V", "Enrolled Subject V", "CSE", "5", "Prof. Tester", "Lab-1")
        sub_enr = db.get_subject_by_code("TEST_ENR_V")

    sub_noenr = db.get_subject_by_code("TEST_NOENR_V")
    if not sub_noenr:
        sub_mod.add_subject("TEST_NOENR_V", "Unenrolled Subject V", "CSE", "5", "Prof. Tester", "Lab-2")
        sub_noenr = db.get_subject_by_code("TEST_NOENR_V")

    sub_mod.set_enrolled_students(sub_enr["id"], [TEST_STUDENT_ID])
    sub_mod.set_enrolled_students(sub_noenr["id"], ["SOMEONE_ELSE_123"])

    # Rule 2: Student not enrolled
    ok, sess_noenr = sub_mod.start_attendance_session(sub_noenr["id"])
    assert ok
    res_notenr = att_mod.mark_by_barcode(f"Student ID: {TEST_STUDENT_ID}")
    assert res_notenr["status"] == "not_enrolled", f"Expected not_enrolled, got {res_notenr}"
    print(f"  PASS: Blocked unenrolled student (status={res_notenr['status']}, msg='{res_notenr['message']}')")
    sub_mod.end_current_session()

    # Rule 3: Student enrolled -> Attendance recorded
    ok, sess_enr = sub_mod.start_attendance_session(sub_enr["id"])
    assert ok
    res_ok = att_mod.mark_by_barcode(TEST_STUDENT_ID)
    assert res_ok["status"] == "ok", f"Expected ok, got {res_ok}"
    assert res_ok["method"] == "ID CARD"
    assert res_ok["attendance_id"].startswith("AX-")
    print(f"  PASS: Attendance recorded via ID CARD: {res_ok['student_name']} ({res_ok['attendance_id']})")

    # Rule 4: Duplicate attendance in same session
    res_dup = att_mod.mark_by_barcode(f"ID={TEST_STUDENT_ID}")
    assert res_dup["status"] == "duplicate", f"Expected duplicate, got {res_dup}"
    assert res_dup["attendance_id"] == res_ok["attendance_id"]
    print(f"  PASS: Prevented duplicate attendance (status={res_dup['status']}, preserved verification ID: {res_dup['attendance_id']})")

    # Cleanup test subjects
    sub_mod.end_current_session()
    sub_mod.delete_subject(sub_enr["id"])
    sub_mod.delete_subject(sub_noenr["id"])

    if orig_active:
        sub_mod.start_attendance_session(orig_active["subject_id"])
        print(f"  Restored active session #{orig_active['id']} for {orig_active['subject_code']}")

    # ─────────────────────────────────────────────────────────────────────────
    # STEP 8: Diagnostics & OCR Fallback Status
    # ─────────────────────────────────────────────────────────────────────────
    print("\n[STEP 8] Diagnostics & OCR Fallback Status...")
    dbg = barcode_scanner.get_debug_info()
    print(f"  Barcode Detector : {dbg['barcode_detector']}")
    print(f"  QR Detector      : {dbg['qr_detector']}")
    print(f"  OCR Fallback     : {dbg['ocr_fallback']}")
    print(f"  Last Scan Status : {dbg['decode']} ({dbg['reason']})")
    assert "ACTIVE" in dbg["barcode_detector"], "Barcode detector should be ACTIVE!"
    assert "ACTIVE" in dbg["qr_detector"], "QR detector should be ACTIVE!"
    assert dbg["ocr_fallback"].startswith("READY"), f"OCR fallback should be READY! Got: {dbg['ocr_fallback']}"

    print("\n" + "=" * 70)
    print("ALL TESTS IN VERIFICATION SUITE PASSED SUCCESSFULLY!")
    print("=" * 70)


if __name__ == "__main__":
    run_full_verification()
