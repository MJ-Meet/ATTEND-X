"""
Comprehensive verification test for ATTEND-X Subject & Session System.
Tests all requirements from section 33 of the specification.
"""
import sys
import os
from pathlib import Path

# Ensure project root is in path
sys.path.insert(0, os.path.abspath("."))

import database as db
import students as stu_mod
import subjects as sub_mod
import attendance as att_mod
import reports as rep_mod
import receipt as rec_mod

def run_tests():
    print("=" * 60)
    print("RUNNING ATTEND-X SUBJECT SYSTEM VERIFICATION TESTS")
    print("=" * 60)

    # Clean any dangling active session for test isolation
    active = db.get_active_session()
    if active:
        sub_mod.end_current_session()
        print(f"Ended previous active session #{active['id']}")

    for code in ("TEST101", "TEST102"):
        s = db.get_subject_by_code(code)
        if s:
            sub_mod.delete_subject(s["id"])

    # Setup demo students if needed
    students = db.get_all_students()
    if len(students) < 3:
        stu_mod.add_student("TEST001", "Jethawa Meet", "CSE", "6")
        stu_mod.add_student("TEST002", "Riya Shah", "CSE", "6")
        stu_mod.add_student("TEST003", "Rahul Patel", "CSE", "6")
        stu_mod.add_student("TEST004", "Jay Patel", "CSE", "6")
        students = db.get_all_students()

    s1_id = students[0]["student_id"]
    s2_id = students[1]["student_id"]
    s3_id = students[2]["student_id"]
    unenrolled_id = "UNENROLLED999"
    stu_mod.add_student(unenrolled_id, "Unenrolled Student", "MECH", "4")

    # 1. Test 1: Create a subject
    print("\n[TEST 1] Create a Subject...")
    ok, msg = sub_mod.add_subject(
        subject_code="TEST101",
        subject_name="Test Algorithms",
        branch="CSE",
        semester="6",
        faculty="Prof. Alan Turing",
        room="LAB-3"
    )
    assert ok, f"Subject creation failed: {msg}"
    subject = db.get_subject_by_code("TEST101")
    assert subject is not None and subject["subject_code"] == "TEST101"
    sub_id = subject["id"]
    print(f"  PASS: Subject '{subject['subject_name']}' ({subject['subject_code']}) created with ID {sub_id}.")

    # 2. Test 2: Enroll students
    print("\n[TEST 2] Enroll Students...")
    enrolled_list = [s1_id, s2_id, s3_id]
    ok, msg = sub_mod.set_enrolled_students(sub_id, enrolled_list)
    assert ok, f"Enrollment failed: {msg}"
    current_enrolled = db.get_enrolled_student_ids(sub_id)
    assert set(current_enrolled) == set(enrolled_list), f"Enrolled mismatch: {current_enrolled}"
    print(f"  PASS: {len(current_enrolled)} students enrolled: {current_enrolled}")

    # Test Rule 1: Attempt marking attendance without active session
    print("\n[RULE 1 CHECK] Attempt marking attendance without active session...")
    res_nosess = att_mod.mark_attendance(s1_id, "FACE")
    assert res_nosess["status"] == "no_session", f"Expected 'no_session', got: {res_nosess}"
    print("  PASS: Blocked marking attendance without an active session.")

    # 3. Test 3: Start attendance session
    print("\n[TEST 3] Start Attendance Session...")
    ok, sess = sub_mod.start_attendance_session(sub_id)
    assert ok, f"Failed to start session: {sess}"
    active_sess = sub_mod.get_active_session()
    assert active_sess is not None and active_sess["id"] == sess["id"]
    print(f"  PASS: Session #{sess['id']} active for {active_sess['subject_name']}.")

    # 4. Test 4: Mark student using face
    print("\n[TEST 4] Mark student using FACE...")
    res_face = att_mod.mark_attendance(s1_id, "FACE")
    assert res_face["status"] == "ok", f"Face attendance failed: {res_face}"
    assert res_face["method"] == "FACE"
    assert res_face["subject_code"] == "TEST101"
    assert "AX-" in res_face["attendance_id"]
    print(f"  PASS: {res_face['student_name']} marked PRESENT via FACE. Attendance ID: {res_face['attendance_id']}")

    # 5. Test 5: Mark another student using ID Card
    print("\n[TEST 5] Mark another student using ID CARD...")
    res_card = att_mod.mark_attendance(s2_id, "ID_CARD")
    assert res_card["status"] == "ok", f"ID card attendance failed: {res_card}"
    assert res_card["method"] in ("ID CARD", "ID_CARD")
    print(f"  PASS: {res_card['student_name']} marked PRESENT via {res_card['method']}. Attendance ID: {res_card['attendance_id']}")

    # 6. Test 6: Try scanning the same student again in this session
    print("\n[TEST 6] Scan same student again (Duplicate check)...")
    res_dup = att_mod.mark_attendance(s1_id, "FACE")
    assert res_dup["status"] == "duplicate", f"Expected 'duplicate', got: {res_dup}"
    print(f"  PASS: Correctly rejected duplicate attendance for {s1_id}.")

    # 7. Test 7: Try an unregistered student
    print("\n[TEST 7] Scan unregistered student...")
    res_unreg = att_mod.mark_attendance("GHOST_STUDENT_999", "FACE")
    assert res_unreg["status"] == "unknown", f"Expected 'unknown', got: {res_unreg}"
    print("  PASS: Correctly rejected unregistered student.")

    # 8. Test 8: Try a student NOT enrolled in this subject
    print("\n[TEST 8] Scan student not enrolled in this subject...")
    res_notenrolled = att_mod.mark_attendance(unenrolled_id, "FACE")
    assert res_notenrolled["status"] == "not_enrolled", f"Expected 'not_enrolled', got: {res_notenrolled}"
    print(f"  PASS: Correctly rejected unenrolled student: {res_notenrolled['message']}")

    # Test Receipt Generation
    print("\n[RECEIPT TEST] Generate digital receipt PNG...")
    r_path = rec_mod.generate_receipt_image(res_face)
    assert r_path and Path(r_path).exists(), f"Receipt generation failed: {r_path}"
    print(f"  PASS: Receipt PNG successfully created at: {r_path}")

    # 9. Test 9: End session and verify statistics (Present, Absent, Total, %)
    print("\n[TEST 9] End session and verify calculation...")
    ok, summary = sub_mod.end_current_session()
    assert ok, f"Failed to end session: {summary}"
    assert summary["total_enrolled"] == 3
    assert summary["present_count"] == 2
    assert summary["absent_count"] == 1  # s3_id was absent
    assert abs(summary["percent"] - 66.67) < 0.1
    print(f"  PASS: Session ended. Total: {summary['total_enrolled']}, Present: {summary['present_count']}, Absent: {summary['absent_count']}, Rate: {summary['percent']}%")

    # Verify session is no longer active
    assert sub_mod.get_active_session() is None
    print("  PASS: Active session is now None.")

    # 10. Test 10: Start another subject and check same student can attend
    print("\n[TEST 10] Start different subject and verify student can attend...")
    ok, msg2 = sub_mod.add_subject("TEST102", "Test Database", "CSE", "6", "Prof. Codd", "LAB-4")
    assert ok, f"Subject TEST102 creation failed: {msg2}"
    sub2_id = db.get_subject_by_code("TEST102")["id"]
    sub_mod.set_enrolled_students(sub2_id, [s1_id])
    ok, sess2 = sub_mod.start_attendance_session(sub2_id)
    assert ok

    res_sub2 = att_mod.mark_attendance(s1_id, "FACE")
    assert res_sub2["status"] == "ok", f"Expected ok in second subject, got: {res_sub2}"
    print(f"  PASS: {s1_id} successfully marked in separate subject TEST102!")
    sub_mod.end_current_session()

    # 11. Test 11: Student attendance profile
    print("\n[TEST 11] Verify student attendance profile...")
    profile = sub_mod.get_student_attendance_profile(s1_id)
    assert profile is not None
    assert len(profile["subjects"]) >= 2
    print(f"  PASS: Student profile loaded for {profile['student']['name']}:")
    for s_info in profile["subjects"]:
        print(f"    - {s_info['subject_name']}: {s_info['attended']}/{s_info['total_sessions']} ({s_info['percent']}%)")
    print(f"    OVERALL: {profile['total_attended']}/{profile['total_sessions']} ({profile['overall_percent']}%)")

    # 12. Test 12: Export CSV with subject information
    print("\n[TEST 12] Export CSV with subject filter...")
    csv_path = rep_mod.export_csv(subject_id=sub_id)
    assert csv_path and Path(csv_path).exists(), f"CSV export failed: {csv_path}"
    with open(csv_path, "r", encoding="utf-8") as f:
        content = f.read()
        assert "TEST101" in content.upper() or "ALGORITHMS" in content.upper()
        assert "ATTENDANCE_ID" in content.upper()
    print(f"  PASS: CSV exported with subject and attendance ID at: {csv_path}")

    # Cleanup test subjects
    sub_mod.delete_subject(sub_id)
    sub_mod.delete_subject(sub2_id)
    stu_mod.remove_student(unenrolled_id)
    print("\n[CLEANUP] Test subjects and temporary student cleaned up.")

    print("\n" + "=" * 60)
    print("ALL 12 VERIFICATION TESTS PASSED SUCCESSFULLY!")
    print("=" * 60)

if __name__ == "__main__":
    run_tests()
