"""
ATTEND-X: Attendance Module
High-level attendance operations: marking, querying, subject-session validation,
duplicate prevention, and statistics.
"""

import logging
from datetime import date, datetime
import database as db

logger = logging.getLogger(__name__)


def _today() -> str:
    return date.today().isoformat()          # YYYY-MM-DD


def _now_time() -> str:
    return datetime.now().strftime("%H:%M:%S")


def _gen_attendance_id() -> str:
    return f"AX-{datetime.now().strftime('%y%m%d-%H%M%S')}"


# ─── Core attendance action ────────────────────────────────────────────────────

def mark_attendance(student_id: str, method: str, session_id: int = None) -> dict:
    """
    Attempt to mark attendance for student_id via the given method ('FACE' or 'ID CARD')
    in the currently active class session (or specified session_id).

    Enforces:
      Rule 1: Active session must exist.
      Rule 2: Student must exist.
      Rule 3: Student must be enrolled in the subject.
      Rule 4: Duplicate attendance in the same session is prevented.
      Rule 5: Completed session cannot accept attendance.
    """
    method = "ID CARD" if str(method).upper() in ("ID CARD", "ID_CARD", "CARD", "BARCODE") else "FACE"

    # Step 1: Does the student exist in the database?
    student = db.get_student_by_id(student_id)
    if student is None:
        return {
            "status": "unknown",
            "student": None,
            "student_id": student_id,
            "subject": None,
            "time": _now_time(),
            "method": method,
            "message": "Student not registered in database.",
        }

    # Step 2: Active class session check
    session = None
    if session_id is not None:
        session = db.get_session_by_id(session_id)
    else:
        session = db.get_active_session()

    if not session or session.get("status") != "ACTIVE":
        return {
            "status": "no_session",
            "student": student,
            "student_id": student["student_id"],
            "student_name": student["name"],
            "subject": None,
            "time": _now_time(),
            "method": method,
            "message": "NO ACTIVE CLASS SESSION. Select a subject to start attendance.",
        }

    # Step 3: Subject enrollment check
    if not db.is_student_enrolled(session["subject_id"], student["student_id"]):
        return {
            "status": "not_enrolled",
            "student": student,
            "student_id": student["student_id"],
            "student_name": student["name"],
            "subject": session,
            "subject_code": session["subject_code"],
            "subject_name": session["subject_name"],
            "time": _now_time(),
            "method": method,
            "message": f"{student['name']} is not enrolled in {session['subject_name']}.",
        }

    # Rule 4: Duplicate in same session check
    existing = db.get_session_attendance_record(session["id"], student_id)
    if existing:
        return {
            "status": "duplicate",
            "student": student,
            "student_id": student["student_id"],
            "student_name": student["name"],
            "subject": session,
            "subject_code": session["subject_code"],
            "subject_name": session["subject_name"],
            "time": existing["time"],
            "method": existing["method"],
            "attendance_id": existing.get("attendance_id") or "",
            "message": f"Attendance already recorded at {existing['time']}.",
        }

    today = _today()
    now = _now_time()
    att_id = _gen_attendance_id()

    # Record attendance
    result_code = db.record_session_attendance(session["id"], student_id, today, now, method, att_id)

    if result_code == "ok":
        return {
            "status": "ok",
            "student": student,
            "student_id": student["student_id"],
            "student_name": student["name"],
            "subject": session,
            "subject_code": session["subject_code"],
            "subject_name": session["subject_name"],
            "time": now,
            "method": method,
            "attendance_id": att_id,
            "session_id": session["id"],
            "message": "Attendance recorded successfully.",
        }
    elif result_code == "duplicate":
        existing = db.get_session_attendance_record(session["id"], student_id)
        t = existing["time"] if existing else now
        return {
            "status": "duplicate",
            "student": student,
            "student_id": student["student_id"],
            "student_name": student["name"],
            "subject": session,
            "subject_code": session["subject_code"],
            "subject_name": session["subject_name"],
            "time": t,
            "method": method,
            "attendance_id": existing.get("attendance_id") if existing else "",
            "message": f"Attendance already recorded at {t}.",
        }
    else:
        return {
            "status": "error",
            "student": student,
            "student_id": student["student_id"],
            "student_name": student["name"],
            "subject": session,
            "subject_code": session["subject_code"],
            "subject_name": session["subject_name"],
            "time": now,
            "method": method,
            "message": "Database error while recording attendance.",
        }


def mark_by_barcode(barcode_value: str, session_id: int = None) -> dict:
    """
    Look up student by barcode/QR value then mark attendance via 'ID CARD'.
    Extracts and normalizes student ID (handles prefixes, whitespace, casing).
    """
    import barcode_scanner
    clean_id = barcode_scanner.extract_student_id(barcode_value)
    student = db.get_student_by_barcode(clean_id) or db.get_student_by_id(clean_id)
    if student is None:
        return {
            "status": "unknown_card",
            "student": None,
            "student_id": clean_id or barcode_value,
            "time": _now_time(),
            "method": "ID CARD",
            "message": f"Student ID: {clean_id or barcode_value}",
        }
    return mark_attendance(student["student_id"], "ID CARD", session_id=session_id)


# ─── Stats & Queries ──────────────────────────────────────────────────────────

def get_today_stats(session_id: int = None) -> dict:
    """
    Returns session-specific stats if a session is active/specified,
    or falls back to overall stats if no session is active.
    """
    session = None
    if session_id is not None:
        session = db.get_session_by_id(session_id)
    else:
        session = db.get_active_session()

    if session:
        enrolled_students = db.get_enrolled_students(session["subject_id"])
        total = len(enrolled_students)
        records = db.get_session_attendance(session["id"])
        present = len(records)
        absent = max(0, total - present)
        percent = round((present / total * 100) if total else 0, 1)
        return {
            "present": present,
            "absent": absent,
            "total": total,
            "percent": percent,
            "records": records,
            "session": session,
        }

    # Fallback to general daily stats
    today = _today()
    total_students = len(db.get_all_students())
    records = db.get_attendance_by_date(today)
    present = len(records)
    absent  = max(0, total_students - present)
    percent = round((present / total_students * 100) if total_students else 0, 1)

    return {
        "present": present,
        "absent":  absent,
        "total":   total_students,
        "percent": percent,
        "records": records,
        "session": None,
    }


def get_recent_records(n: int = 14, session_id: int = None) -> list:
    """Return recent attendance records for the active session (or today)."""
    session = None
    if session_id is not None:
        session = db.get_session_by_id(session_id)
    else:
        session = db.get_active_session()

    if session:
        return db.get_session_attendance(session["id"])[:n]

    today = _today()
    records = db.get_attendance_by_date(today)
    return records[:n]


def get_student_stats(student_id: str) -> dict:
    """Returns lifetime stats for a student across all dates and subjects."""
    conn = db.get_connection()
    try:
        rows = conn.execute(
            """SELECT date, time, method FROM attendance
               WHERE student_id=? ORDER BY date DESC, time DESC""",
            (student_id,)
        ).fetchall()
        records = [dict(r) for r in rows]
    finally:
        conn.close()

    conn = db.get_connection()
    try:
        distinct_dates = conn.execute(
            "SELECT COUNT(DISTINCT date) FROM attendance"
        ).fetchone()[0]
    finally:
        conn.close()

    present = len(records)
    absent  = max(0, distinct_dates - present)
    face_count    = sum(1 for r in records if r["method"] == "FACE")
    idcard_count  = sum(1 for r in records if r["method"] == "ID CARD")
    percent = round((present / distinct_dates * 100) if distinct_dates else 0, 1)

    return {
        "student_id":   student_id,
        "present":      present,
        "absent":       absent,
        "total_classes": distinct_dates,
        "percent":      percent,
        "face_count":   face_count,
        "idcard_count": idcard_count,
        "records":      records,
    }
