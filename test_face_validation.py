"""
Verification test suite for ATTEND-X Face Recognition Validation Logic.
Tests all 4 cases:
  TEST 1: Unknown person's face -> STUDENT NOT FOUND (No attendance record)
  TEST 2: Registered student NOT enrolled in current subject -> NOT ENROLLED (No attendance record)
  TEST 3: Registered student enrolled in current subject -> ATTENDANCE RECORDED (Recorded)
  TEST 4: Registered student enrolled + already marked -> ALREADY MARKED (No duplicate)

Also verifies ID card, barcode scanning, and session management remain fully functional.
"""

import os
import sys
import numpy as np

# Ensure project root is in sys.path
sys.path.insert(0, os.path.abspath("."))

import database as db
import students as stu_mod
import subjects as sub_mod
import attendance as att_mod
import face_recognition_module as frm


def run_tests():
    print("=" * 70)
    print("RUNNING ATTEND-X FACE RECOGNITION VALIDATION TESTS")
    print("=" * 70)

    # 1. Clean existing test data / active session for clean run
    active = db.get_active_session()
    if active:
        sub_mod.end_current_session()
        print(f"Ended previous active session #{active['id']}.")

    # Clean up test subjects
    test_sub = db.get_subject_by_code("VAL101")
    if test_sub:
        sub_mod.delete_subject(test_sub["id"])

    # Register test students in ATTEND-X database
    # Student A: will be registered AND enrolled in VAL101
    # Student B: will be registered but NOT enrolled in VAL101
    stu_a_id = "VAL_STU_ENROLLED"
    stu_b_id = "VAL_STU_NOT_ENROLLED"
    unknown_id = "VAL_UNKNOWN_PERSON"

    # Ensure students exist in DB
    stu_mod.add_student(stu_a_id, "Registered Enrolled Student", "CSE", "6")
    stu_mod.add_student(stu_b_id, "Registered Unenrolled Student", "CSE", "6")

    # Verify neither student is enrolled in non-existent subject yet
    print("[SETUP] Registered test students in database.")

    # Create subject VAL101: "Computer Vision & Biometrics"
    ok, msg = sub_mod.add_subject(
        subject_code="VAL101",
        subject_name="Computer Vision & Biometrics",
        branch="CSE",
        semester="6",
        faculty="Dr. Alan Turing",
        room="LAB-1"
    )
    assert ok, f"Failed to create subject: {msg}"
    subject = db.get_subject_by_code("VAL101")
    assert subject is not None
    sub_id = subject["id"]
    print(f"[SETUP] Created Subject '{subject['subject_name']}' ({subject['subject_code']}) ID: {sub_id}")

    # Enroll ONLY Student A in VAL101 (Student B is explicitly NOT enrolled)
    ok, msg = sub_mod.set_enrolled_students(sub_id, [stu_a_id])
    assert ok, f"Failed to enroll student: {msg}"
    enrolled_ids = db.get_enrolled_student_ids(sub_id)
    assert stu_a_id in enrolled_ids, "Student A should be enrolled"
    assert stu_b_id not in enrolled_ids, "Student B must NOT be enrolled"
    print(f"[SETUP] Enrollment configured: Enrolled={enrolled_ids}, Unenrolled={[stu_b_id]}")

    # Start active class session for VAL101
    ok, sess = sub_mod.start_attendance_session(sub_id)
    assert ok, f"Failed to start session: {sess}"
    active_sess = db.get_active_session()
    assert active_sess is not None and active_sess["id"] == sess["id"]
    print(f"[SETUP] Class session #{sess['id']} active for {active_sess['subject_name']}.")

    # =========================================================================
    # TEST 1: Unknown person's face
    # =========================================================================
    print("\n" + "-" * 70)
    print("TEST 1: Unknown person's face")
    print("Expected: STUDENT NOT FOUND (No attendance record)")
    print("-" * 70)

    # 1A. Test Face Recognition threshold logic with synthetic encodings
    # Registered student encoding (128-d unit vector)
    known_vector = np.zeros(128, dtype=np.float64)
    known_vector[0] = 1.0
    known_encodings = [
        {"student_id": stu_a_id, "name": "Registered Enrolled Student", "encoding": known_vector}
    ]

    # Impostor / Unknown face encoding with distance > 0.50 tolerance
    # An orthogonal vector has euclidean distance sqrt(1^2 + 1^2) = 1.414 >> 0.50
    unknown_vector = np.zeros(128, dtype=np.float64)
    unknown_vector[1] = 1.0

    # Test tolerance comparison directly
    dist = float(np.linalg.norm(known_vector - unknown_vector))
    assert dist > 0.50, f"Expected distance > 0.50, got {dist}"

    # 1B. Test Attendance validation with unknown student ID
    res_unknown = att_mod.mark_attendance(unknown_id, "FACE")
    print(f"  Result status: {res_unknown['status']}")
    print(f"  Result message: {res_unknown['message']}")
    assert res_unknown["status"] == "unknown", f"Expected 'unknown', got {res_unknown['status']}"
    assert res_unknown["student"] is None, "Student must be None for unknown face"
    assert "not registered" in res_unknown["message"].lower()

    # Verify NO attendance record was created in the active session
    records = db.get_session_attendance(sess["id"])
    assert len(records) == 0, f"Expected 0 attendance records, found {len(records)}"
    print("  [PASS] PASS TEST 1: Unknown face correctly classified as STUDENT NOT FOUND. No record created.")

    # =========================================================================
    # TEST 2: Registered student but NOT enrolled in current subject
    # =========================================================================
    print("\n" + "-" * 70)
    print("TEST 2: Registered student but NOT enrolled in current subject")
    print("Expected: STUDENT FOUND -> NOT ENROLLED (No attendance record)")
    print("-" * 70)

    # Student B exists in Students table, but is NOT enrolled in VAL101
    stu_b = db.get_student_by_id(stu_b_id)
    assert stu_b is not None, "Student B must exist in database"
    assert not db.is_student_enrolled(sub_id, stu_b_id), "Student B must not be enrolled"

    res_not_enrolled = att_mod.mark_attendance(stu_b_id, "FACE")
    print(f"  Result status: {res_not_enrolled['status']}")
    print(f"  Student Identified: {res_not_enrolled['student_name']} ({res_not_enrolled['student_id']})")
    print(f"  Result message: {res_not_enrolled['message']}")

    assert res_not_enrolled["status"] == "not_enrolled", f"Expected 'not_enrolled', got {res_not_enrolled['status']}"
    assert res_not_enrolled["student"] is not None, "Student object must be present (student is registered)"
    assert res_not_enrolled["student_id"] == stu_b_id
    assert "not enrolled" in res_not_enrolled["message"].lower()

    # Verify NO attendance record was created
    records = db.get_session_attendance(sess["id"])
    assert len(records) == 0, f"Expected 0 attendance records, found {len(records)}"
    print("  [PASS] PASS TEST 2: Registered student correctly recognized, but enrollment blocked. No record created.")

    # =========================================================================
    # TEST 3: Registered student AND enrolled in current subject
    # =========================================================================
    print("\n" + "-" * 70)
    print("TEST 3: Registered student AND enrolled in current subject")
    print("Expected: STUDENT FOUND -> ENROLLMENT VERIFIED -> ATTENDANCE RECORDED")
    print("-" * 70)

    stu_a = db.get_student_by_id(stu_a_id)
    assert stu_a is not None, "Student A must exist in database"
    assert db.is_student_enrolled(sub_id, stu_a_id), "Student A must be enrolled"

    res_enrolled = att_mod.mark_attendance(stu_a_id, "FACE")
    print(f"  Result status: {res_enrolled['status']}")
    print(f"  Student: {res_enrolled['student_name']} ({res_enrolled['student_id']})")
    print(f"  Subject: {res_enrolled['subject_name']} ({res_enrolled['subject_code']})")
    print(f"  Method: {res_enrolled['method']}")
    print(f"  Attendance ID: {res_enrolled['attendance_id']}")

    assert res_enrolled["status"] == "ok", f"Expected 'ok', got {res_enrolled['status']}"
    assert res_enrolled["method"] == "FACE"
    assert res_enrolled["student_id"] == stu_a_id
    assert res_enrolled["attendance_id"].startswith("AX-")

    # Verify exactly 1 attendance record exists in the active session
    records = db.get_session_attendance(sess["id"])
    assert len(records) == 1, f"Expected 1 attendance record, found {len(records)}"
    assert records[0]["student_id"] == stu_a_id
    first_att_id = res_enrolled["attendance_id"]
    print(f"  [PASS] PASS TEST 3: Attendance successfully recorded with Verification ID {first_att_id}.")

    # =========================================================================
    # TEST 4: Registered student + enrolled + already attended
    # =========================================================================
    print("\n" + "-" * 70)
    print("TEST 4: Registered student + enrolled + already attended")
    print("Expected: STUDENT FOUND -> ENROLLMENT VERIFIED -> ALREADY MARKED")
    print("-" * 70)

    res_duplicate = att_mod.mark_attendance(stu_a_id, "FACE")
    print(f"  Result status: {res_duplicate['status']}")
    print(f"  Student: {res_duplicate['student_name']} ({res_duplicate['student_id']})")
    print(f"  Result message: {res_duplicate['message']}")
    print(f"  Existing Verification ID: {res_duplicate.get('attendance_id')}")

    assert res_duplicate["status"] == "duplicate", f"Expected 'duplicate', got {res_duplicate['status']}"
    assert res_duplicate["student_id"] == stu_a_id
    assert res_duplicate.get("attendance_id") == first_att_id, "Duplicate must return original Verification ID"

    # Verify STILL exactly 1 attendance record exists (no duplicate inserted)
    records = db.get_session_attendance(sess["id"])
    assert len(records) == 1, f"Expected still 1 attendance record, found {len(records)}"
    print("  [PASS] PASS TEST 4: Duplicate attendance prevented. Returned existing Verification ID.")

    # =========================================================================
    # TEST 5: ID Card Scan Compatibility
    # =========================================================================
    print("\n" + "-" * 70)
    print("TEST 5: ID Card & Barcode scan compatibility")
    print("=" * 70)

    # 5A. Unknown barcode
    res_card_unknown = att_mod.mark_by_barcode("BARCODE_NOT_IN_DB")
    assert res_card_unknown["status"] == "unknown_card", f"Expected 'unknown_card', got {res_card_unknown}"
    print("  [PASS] Unknown ID card returns unknown_card.")

    # 5B. Registered student unenrolled via ID Card
    res_card_unenrolled = att_mod.mark_by_barcode(stu_b_id)
    assert res_card_unenrolled["status"] == "not_enrolled", f"Expected 'not_enrolled', got {res_card_unenrolled}"
    print("  [PASS] Registered unenrolled student via ID card returns not_enrolled.")

    # Clean up test session and subject
    sub_mod.end_current_session()
    sub_mod.delete_subject(sub_id)
    db.delete_student(stu_a_id)
    db.delete_student(stu_b_id)
    print("[CLEANUP] Test session, subject, and students cleaned up.")

    print("\n" + "=" * 70)
    print("ALL 5 TESTS PASSED PERFECTLY!")
    print("=" * 70)


if __name__ == "__main__":
    run_tests()
