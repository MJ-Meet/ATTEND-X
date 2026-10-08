"""
ATTEND-X: Subjects & Class Sessions Module
Manages subjects, student enrollments, active class sessions,
and subject-wise attendance analytics.
"""

import logging
from datetime import date, datetime
import database as db

logger = logging.getLogger(__name__)


def _today() -> str:
    return date.today().isoformat()


def _now_time() -> str:
    return datetime.now().strftime("%H:%M:%S")


# ─── Subject Management ───────────────────────────────────────────────────────

def add_subject(subject_code: str, subject_name: str, branch: str = "",
                semester: str = "", faculty: str = "", room: str = "") -> tuple[bool, str]:
    """Validate and insert a new subject."""
    code = subject_code.strip().upper()
    name = subject_name.strip()
    if not code:
        return False, "Subject Code is required."
    if not name:
        return False, "Subject Name is required."

    existing = db.get_subject_by_code(code)
    if existing:
        return False, f"Subject with code '{code}' already exists."

    sub_id = db.insert_subject(code, name, branch, semester, faculty, room)
    if sub_id:
        return True, f"Subject '{name}' ({code}) registered."
    return False, "Failed to register subject."


def edit_subject(subject_id: int, subject_code: str, subject_name: str,
                 branch: str = "", semester: str = "", faculty: str = "", room: str = "") -> tuple[bool, str]:
    """Update an existing subject."""
    code = subject_code.strip().upper()
    name = subject_name.strip()
    if not code or not name:
        return False, "Subject Code and Name are required."

    existing = db.get_subject_by_code(code)
    if existing and existing["id"] != subject_id:
        return False, f"Subject code '{code}' is already used by another subject."

    ok = db.update_subject(subject_id, code, name, branch, semester, faculty, room)
    if ok:
        return True, "Subject updated successfully."
    return False, "Failed to update subject."


def delete_subject(subject_id: int) -> tuple[bool, str]:
    """Delete a subject and its associated enrollments and sessions."""
    ok = db.delete_subject(subject_id)
    if ok:
        return True, "Subject deleted."
    return False, "Failed to delete subject."


def search_subjects(query: str = "") -> list[dict]:
    """Search or list all subjects with enrolled counts and summary metrics."""
    subjects = db.get_all_subjects(query)
    for s in subjects:
        stats = db.get_subject_stats(s["id"])
        s["enrolled_count"] = stats["enrolled"]
        s["total_sessions"] = stats["total_sessions"]
        s["avg_percent"] = stats["avg_percent"]
        s["last_session"] = stats["last_session"]
    return subjects


def get_subject(subject_id: int) -> dict | None:
    return db.get_subject_by_id(subject_id)


# ─── Enrollment Management ───────────────────────────────────────────────────

def get_enrolled_student_ids(subject_id: int) -> list[str]:
    return db.get_enrolled_student_ids(subject_id)


def get_enrolled_students(subject_id: int) -> list[dict]:
    return db.get_enrolled_students(subject_id)


def save_enrollments(subject_id: int, student_ids: list[str]) -> tuple[bool, str]:
    ok = db.set_subject_enrollments(subject_id, student_ids)
    if ok:
        return True, f"Enrolled {len(student_ids)} students successfully."
    return False, "Failed to update enrollment."


set_enrolled_students = save_enrollments


def is_student_enrolled(subject_id: int, student_id: str) -> bool:
    return db.is_student_enrolled(subject_id, student_id)


# ─── Active Session Management ────────────────────────────────────────────────

def start_attendance_session(subject_id: int) -> tuple[bool, dict | str]:
    """
    Start a live class attendance session for a subject.
    Closes any currently active session first.
    Returns (True, session_dict) on success, (False, error_msg) on failure.
    """
    sub = db.get_subject_by_id(subject_id)
    if not sub:
        return False, "Subject not found."

    today = _today()
    now_time = _now_time()

    sess_id = db.create_session(subject_id, today, now_time)
    sess = db.get_session_by_id(sess_id)
    logger.info("Started session %d for subject %s (%s)", sess_id, sub["subject_name"], sub["subject_code"])
    return True, sess


def get_active_session() -> dict | None:
    """Returns currently active session with joined subject data, or None."""
    return db.get_active_session()


def end_current_session() -> tuple[bool, dict | str]:
    """
    Ends the currently active session and calculates summary stats
    (enrolled, present, absent, attendance percentage).
    """
    active = db.get_active_session()
    if not active:
        return False, "No active session to end."

    sess_id = active["id"]
    sub_id = active["subject_id"]
    now_time = _now_time()

    ok = db.end_session(sess_id, now_time)
    if not ok:
        return False, "Failed to end session."

    # Compute final session statistics
    enrolled_students = db.get_enrolled_students(sub_id)
    total_enrolled = len(enrolled_students)

    att_records = db.get_session_attendance(sess_id)
    present_count = len(att_records)
    absent_count = max(0, total_enrolled - present_count)
    rate = round((present_count / total_enrolled * 100) if total_enrolled else 0, 2)
    face_count = sum(1 for r in att_records if r.get("method") == "FACE")
    id_card_count = sum(1 for r in att_records if r.get("method") in ("ID CARD", "ID_CARD"))

    summary = {
        "session_id": sess_id,
        "subject_id": sub_id,
        "subject_code": active["subject_code"],
        "subject_name": active["subject_name"],
        "branch": active["branch"],
        "semester": active["semester"],
        "faculty": active["faculty"],
        "room": active["room"],
        "date": active["date"],
        "start_time": active["start_time"],
        "end_time": now_time,
        "total": total_enrolled,
        "total_enrolled": total_enrolled,
        "present": present_count,
        "present_count": present_count,
        "absent": absent_count,
        "absent_count": absent_count,
        "rate": rate,
        "percent": rate,
        "face_count": face_count,
        "id_card_count": id_card_count,
    }
    logger.info("Ended session %d: %d/%d present (%.2f%%)", sess_id, present_count, total_enrolled, rate)
    return True, summary


# ─── Student Profile Analytics ────────────────────────────────────────────────

def get_student_attendance_profile(student_id: str) -> dict:
    """
    Calculates subject-by-subject attendance stats and overall percentage
    for the student attendance profile dialog.
    """
    student = db.get_student_by_id(student_id)
    if not student:
        return {}

    raw_subjects = db.get_student_subject_attendance(student_id)
    subjects_att = []
    for s in raw_subjects:
        att = s["attended_sessions"]
        tot = s["total_sessions"]
        pct = round((att / tot * 100) if tot else 0, 1)
        sub_entry = dict(s)
        sub_entry["attended"] = att
        sub_entry["percent"] = pct
        subjects_att.append(sub_entry)

    total_classes = sum(s["total_sessions"] for s in subjects_att)
    total_attended = sum(s["attended"] for s in subjects_att)
    overall_pct = round((total_attended / total_classes * 100) if total_classes else 0, 1)

    return {
        "student": student,
        "subjects": subjects_att,
        "total_classes": total_classes,
        "total_sessions": total_classes,
        "total_attended": total_attended,
        "overall_percent": overall_pct,
    }
