"""
ATTEND-X: Database Module
Handles SQLite initialization, schema creation, and low-level DB access.
"""

import sqlite3
import os
import logging
from pathlib import Path

DB_PATH = Path("data") / "attendx.db"

logger = logging.getLogger(__name__)


def get_connection() -> sqlite3.Connection:
    """Return a SQLite connection with row_factory for dict-like access."""
    conn = sqlite3.connect(str(DB_PATH), timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def initialize_database():
    """Create all required tables and run migrations if needed."""
    Path("data").mkdir(exist_ok=True)
    Path("faces").mkdir(exist_ok=True)
    Path("generated_cards").mkdir(exist_ok=True)
    Path("exports").mkdir(exist_ok=True)
    (Path("exports") / "receipts").mkdir(exist_ok=True)

    conn = get_connection()
    try:
        cur = conn.cursor()

        # Students table
        cur.execute("""
            CREATE TABLE IF NOT EXISTS students (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id  TEXT    NOT NULL UNIQUE,
                name        TEXT    NOT NULL,
                branch      TEXT    NOT NULL DEFAULT '',
                semester    TEXT    NOT NULL DEFAULT '',
                face_encoding BLOB  DEFAULT NULL,
                photo_path  TEXT    DEFAULT NULL,
                barcode_value TEXT  NOT NULL DEFAULT '',
                created_at  TEXT    NOT NULL DEFAULT (datetime('now','localtime'))
            )
        """)

        # Subjects table
        cur.execute("""
            CREATE TABLE IF NOT EXISTS subjects (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                subject_code TEXT UNIQUE NOT NULL,
                subject_name TEXT NOT NULL,
                branch      TEXT NOT NULL DEFAULT '',
                semester    TEXT NOT NULL DEFAULT '',
                faculty     TEXT NOT NULL DEFAULT '',
                room        TEXT NOT NULL DEFAULT '',
                created_at  TEXT NOT NULL DEFAULT (datetime('now','localtime'))
            )
        """)

        # Subject enrollments table
        cur.execute("""
            CREATE TABLE IF NOT EXISTS subject_enrollments (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                subject_id  INTEGER NOT NULL,
                student_id  TEXT NOT NULL,
                created_at  TEXT NOT NULL DEFAULT (datetime('now','localtime')),
                FOREIGN KEY (subject_id) REFERENCES subjects(id) ON DELETE CASCADE,
                FOREIGN KEY (student_id) REFERENCES students(student_id) ON DELETE CASCADE,
                UNIQUE(subject_id, student_id)
            )
        """)

        # Attendance sessions table
        cur.execute("""
            CREATE TABLE IF NOT EXISTS attendance_sessions (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                subject_id  INTEGER NOT NULL,
                date        TEXT NOT NULL,
                start_time  TEXT NOT NULL,
                end_time    TEXT DEFAULT NULL,
                status      TEXT NOT NULL DEFAULT 'ACTIVE' CHECK(status IN ('ACTIVE', 'COMPLETED')),
                FOREIGN KEY (subject_id) REFERENCES subjects(id) ON DELETE CASCADE
            )
        """)

        # Attendance table
        cur.execute("""
            CREATE TABLE IF NOT EXISTS attendance (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id  INTEGER DEFAULT NULL,
                student_id  TEXT    NOT NULL,
                date        TEXT    NOT NULL,
                time        TEXT    NOT NULL,
                method      TEXT    NOT NULL CHECK(method IN ('FACE', 'ID CARD')),
                status      TEXT    NOT NULL DEFAULT 'PRESENT',
                attendance_id TEXT  DEFAULT NULL,
                FOREIGN KEY (session_id) REFERENCES attendance_sessions(id) ON DELETE CASCADE,
                FOREIGN KEY (student_id) REFERENCES students(student_id) ON DELETE CASCADE
            )
        """)

        # Migration: Check if columns exist in existing attendance table
        cur.execute("PRAGMA table_info(attendance)")
        att_cols = [r["name"] for r in cur.fetchall()]
        if "session_id" not in att_cols:
            cur.execute("ALTER TABLE attendance ADD COLUMN session_id INTEGER DEFAULT NULL REFERENCES attendance_sessions(id) ON DELETE CASCADE")
        if "status" not in att_cols:
            cur.execute("ALTER TABLE attendance ADD COLUMN status TEXT NOT NULL DEFAULT 'PRESENT'")
        if "attendance_id" not in att_cols:
            cur.execute("ALTER TABLE attendance ADD COLUMN attendance_id TEXT DEFAULT NULL")

        # Indexes
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_attendance_student_date
            ON attendance(student_id, date)
        """)
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_attendance_date
            ON attendance(date)
        """)
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_attendance_session
            ON attendance(session_id)
        """)

        # Drop old strict date-level index if present so student can attend multiple sessions on same day
        cur.execute("DROP INDEX IF EXISTS idx_attendance_unique_day")

        # Session-level unique constraint: 1 attendance per student per session
        cur.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS idx_attendance_session_student
            ON attendance(session_id, student_id)
            WHERE session_id IS NOT NULL
        """)
        # Legacy fallback unique index for records without a session
        cur.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS idx_attendance_legacy_day
            ON attendance(student_id, date)
            WHERE session_id IS NULL
        """)

        # Seed default subjects if none exist
        cur.execute("SELECT COUNT(*) as count FROM subjects")
        if cur.fetchone()["count"] == 0:
            default_subjects = [
                ("CS0305", "Data Structures", "CSE", "6", "Prof. Patel", "C-204"),
                ("CS0306", "Database Management System", "CSE", "6", "Prof. Shah", "C-205"),
                ("CS0307", "Computer Networks", "CSE", "6", "Prof. Mehta", "C-206"),
                ("CS0308", "Operating Systems", "CSE", "6", "Prof. Joshi", "C-207"),
            ]
            for s in default_subjects:
                cur.execute(
                    "INSERT INTO subjects (subject_code, subject_name, branch, semester, faculty, room) VALUES (?, ?, ?, ?, ?, ?)",
                    s
                )

        # Auto-enroll all existing students in default subjects if enrollments empty
        cur.execute("SELECT COUNT(*) as count FROM subject_enrollments")
        if cur.fetchone()["count"] == 0:
            cur.execute("SELECT id FROM subjects")
            subject_ids = [r["id"] for r in cur.fetchall()]
            cur.execute("SELECT student_id FROM students")
            student_ids = [r["student_id"] for r in cur.fetchall()]
            for sub_id in subject_ids:
                for stu_id in student_ids:
                    cur.execute(
                        "INSERT OR IGNORE INTO subject_enrollments (subject_id, student_id) VALUES (?, ?)",
                        (sub_id, stu_id)
                    )

        conn.commit()
        logger.info("Database initialized at %s", DB_PATH)
    except Exception as e:
        logger.error("Database initialization error: %s", e)
        raise
    finally:
        conn.close()


def insert_student(student_id: str, name: str, branch: str, semester: str,
                   face_encoding=None, photo_path: str = None,
                   barcode_value: str = "") -> bool:
    """Insert a new student. Returns True on success, False on duplicate."""
    if not barcode_value:
        barcode_value = student_id
    conn = get_connection()
    try:
        conn.execute(
            """INSERT INTO students
               (student_id, name, branch, semester, face_encoding, photo_path, barcode_value)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (student_id, name, branch, semester, face_encoding, photo_path, barcode_value)
        )
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()


def update_student(student_id: str, name: str = None, branch: str = None,
                   semester: str = None, face_encoding=None,
                   photo_path: str = None) -> bool:
    """Update student fields. Only non-None values are updated."""
    conn = get_connection()
    try:
        if name is not None:
            conn.execute("UPDATE students SET name=? WHERE student_id=?", (name, student_id))
        if branch is not None:
            conn.execute("UPDATE students SET branch=? WHERE student_id=?", (branch, student_id))
        if semester is not None:
            conn.execute("UPDATE students SET semester=? WHERE student_id=?", (semester, student_id))
        if face_encoding is not None:
            conn.execute("UPDATE students SET face_encoding=? WHERE student_id=?",
                         (face_encoding, student_id))
        if photo_path is not None:
            conn.execute("UPDATE students SET photo_path=? WHERE student_id=?",
                         (photo_path, student_id))
        conn.commit()
        return True
    except Exception as e:
        logger.error("Update student error: %s", e)
        return False
    finally:
        conn.close()


def delete_student(student_id: str) -> bool:
    conn = get_connection()
    try:
        conn.execute("DELETE FROM students WHERE student_id=?", (student_id,))
        conn.commit()
        return True
    except Exception as e:
        logger.error("Delete student error: %s", e)
        return False
    finally:
        conn.close()


def get_student_by_id(student_id: str):
    """Return a sqlite3.Row or None."""
    if not student_id:
        return None
    sid = str(student_id).strip()
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT * FROM students WHERE student_id=? COLLATE NOCASE", (sid,)
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def get_student_by_barcode(barcode_value: str):
    if not barcode_value:
        return None
    val = str(barcode_value).strip()
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT * FROM students WHERE barcode_value=? COLLATE NOCASE OR student_id=? COLLATE NOCASE",
            (val, val)
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def get_all_students():
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT * FROM students ORDER BY student_id"
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_all_students_with_encodings():
    """Returns list of dicts containing student_id, name, face_encoding."""
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT student_id, name, face_encoding FROM students "
            "WHERE face_encoding IS NOT NULL"
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def record_attendance(student_id: str, date: str, time: str, method: str) -> str:
    """
    Mark attendance. Returns:
      'ok'        – successfully recorded
      'duplicate' – already marked today
      'error'     – database error
    """
    conn = get_connection()
    try:
        conn.execute(
            "INSERT INTO attendance (student_id, date, time, method) VALUES (?, ?, ?, ?)",
            (student_id, date, time, method)
        )
        conn.commit()
        return "ok"
    except sqlite3.IntegrityError:
        return "duplicate"
    except Exception as e:
        logger.error("Record attendance error: %s", e)
        return "error"
    finally:
        conn.close()


def get_attendance_by_date(date: str):
    conn = get_connection()
    try:
        rows = conn.execute(
            """SELECT a.student_id, s.name, a.time, a.method
               FROM attendance a
               JOIN students s ON s.student_id = a.student_id
               WHERE a.date=?
               ORDER BY a.time DESC""",
            (date,)
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_attendance_range(from_date: str, to_date: str):
    conn = get_connection()
    try:
        rows = conn.execute(
            """SELECT a.student_id, s.name, a.date, a.time, a.method
               FROM attendance a
               JOIN students s ON s.student_id = a.student_id
               WHERE a.date BETWEEN ? AND ?
               ORDER BY a.date DESC, a.time DESC""",
            (from_date, to_date)
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def student_already_attended_today(student_id: str, date: str) -> bool:
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT time FROM attendance WHERE student_id=? AND date=?",
            (student_id, date)
        ).fetchone()
        return row is not None
    finally:
        conn.close()


def get_today_attendance_record(student_id: str, date: str):
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT * FROM attendance WHERE student_id=? AND date=?",
            (student_id, date)
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


# ═══════════════════════════════════════════════════════════════════════════════
# SUBJECTS & CLASS SESSIONS
# ═══════════════════════════════════════════════════════════════════════════════

# ─── Subjects ─────────────────────────────────────────────────────────────────

def insert_subject(subject_code: str, subject_name: str, branch: str = "",
                   semester: str = "", faculty: str = "", room: str = "") -> int | None:
    conn = get_connection()
    try:
        cur = conn.execute(
            """INSERT INTO subjects (subject_code, subject_name, branch, semester, faculty, room)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (subject_code.strip(), subject_name.strip(), branch.strip(), semester.strip(), faculty.strip(), room.strip())
        )
        conn.commit()
        return cur.lastrowid
    except sqlite3.IntegrityError:
        return None
    except Exception as e:
        logger.error("Insert subject error: %s", e)
        return None
    finally:
        conn.close()


def update_subject(subject_id: int, subject_code: str, subject_name: str,
                   branch: str = "", semester: str = "", faculty: str = "", room: str = "") -> bool:
    conn = get_connection()
    try:
        conn.execute(
            """UPDATE subjects
               SET subject_code=?, subject_name=?, branch=?, semester=?, faculty=?, room=?
               WHERE id=?""",
            (subject_code.strip(), subject_name.strip(), branch.strip(), semester.strip(), faculty.strip(), room.strip(), subject_id)
        )
        conn.commit()
        return True
    except Exception as e:
        logger.error("Update subject error: %s", e)
        return False
    finally:
        conn.close()


def delete_subject(subject_id: int) -> bool:
    conn = get_connection()
    try:
        conn.execute("DELETE FROM subjects WHERE id=?", (subject_id,))
        conn.commit()
        return True
    except Exception as e:
        logger.error("Delete subject error: %s", e)
        return False
    finally:
        conn.close()


def get_subject_by_id(subject_id: int) -> dict | None:
    conn = get_connection()
    try:
        row = conn.execute("SELECT * FROM subjects WHERE id=?", (subject_id,)).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def get_subject_by_code(subject_code: str) -> dict | None:
    conn = get_connection()
    try:
        row = conn.execute("SELECT * FROM subjects WHERE subject_code=?", (subject_code.strip(),)).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def get_all_subjects(search_query: str = "") -> list[dict]:
    conn = get_connection()
    try:
        q = search_query.strip()
        if q:
            rows = conn.execute(
                """SELECT s.*, 
                          (SELECT COUNT(*) FROM subject_enrollments WHERE subject_id = s.id) as enrolled_count
                   FROM subjects s
                   WHERE s.subject_code LIKE ? OR s.subject_name LIKE ? OR s.faculty LIKE ? OR s.branch LIKE ?
                   ORDER BY s.subject_code ASC""",
                (f"%{q}%", f"%{q}%", f"%{q}%", f"%{q}%")
            ).fetchall()
        else:
            rows = conn.execute(
                """SELECT s.*, 
                          (SELECT COUNT(*) FROM subject_enrollments WHERE subject_id = s.id) as enrolled_count
                   FROM subjects s
                   ORDER BY s.subject_code ASC"""
            ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


# ─── Enrollments ──────────────────────────────────────────────────────────────

def enroll_student(subject_id: int, student_id: str) -> bool:
    conn = get_connection()
    try:
        conn.execute(
            "INSERT OR IGNORE INTO subject_enrollments (subject_id, student_id) VALUES (?, ?)",
            (subject_id, student_id.strip())
        )
        conn.commit()
        return True
    except Exception as e:
        logger.error("Enroll student error: %s", e)
        return False
    finally:
        conn.close()


def unenroll_student(subject_id: int, student_id: str) -> bool:
    conn = get_connection()
    try:
        conn.execute(
            "DELETE FROM subject_enrollments WHERE subject_id=? AND student_id=?",
            (subject_id, student_id.strip())
        )
        conn.commit()
        return True
    except Exception as e:
        logger.error("Unenroll student error: %s", e)
        return False
    finally:
        conn.close()


def set_subject_enrollments(subject_id: int, student_ids: list[str]) -> bool:
    conn = get_connection()
    try:
        conn.execute("DELETE FROM subject_enrollments WHERE subject_id=?", (subject_id,))
        for sid in student_ids:
            conn.execute(
                "INSERT INTO subject_enrollments (subject_id, student_id) VALUES (?, ?)",
                (subject_id, sid.strip())
            )
        conn.commit()
        return True
    except Exception as e:
        logger.error("Set subject enrollments error: %s", e)
        return False
    finally:
        conn.close()


def get_enrolled_student_ids(subject_id: int) -> list[str]:
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT student_id FROM subject_enrollments WHERE subject_id=? ORDER BY student_id",
            (subject_id,)
        ).fetchall()
        return [r["student_id"] for r in rows]
    finally:
        conn.close()


def get_enrolled_students(subject_id: int) -> list[dict]:
    conn = get_connection()
    try:
        rows = conn.execute(
            """SELECT s.* FROM students s
               JOIN subject_enrollments se ON se.student_id = s.student_id
               WHERE se.subject_id=?
               ORDER BY s.student_id""",
            (subject_id,)
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def is_student_enrolled(subject_id: int, student_id: str) -> bool:
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT id FROM subject_enrollments WHERE subject_id=? AND student_id=?",
            (subject_id, student_id.strip())
        ).fetchone()
        return row is not None
    finally:
        conn.close()


# ─── Sessions ─────────────────────────────────────────────────────────────────

def create_session(subject_id: int, date: str, start_time: str) -> int:
    conn = get_connection()
    try:
        # Mark any other currently active sessions as COMPLETED
        conn.execute("UPDATE attendance_sessions SET status='COMPLETED' WHERE status='ACTIVE'")
        cur = conn.execute(
            """INSERT INTO attendance_sessions (subject_id, date, start_time, status)
               VALUES (?, ?, ?, 'ACTIVE')""",
            (subject_id, date, start_time)
        )
        conn.commit()
        return cur.lastrowid
    except Exception as e:
        logger.error("Create session error: %s", e)
        raise
    finally:
        conn.close()


def get_active_session() -> dict | None:
    conn = get_connection()
    try:
        row = conn.execute(
            """SELECT sess.*, sub.subject_code, sub.subject_name, sub.branch, sub.semester, sub.faculty, sub.room
               FROM attendance_sessions sess
               JOIN subjects sub ON sub.id = sess.subject_id
               WHERE sess.status = 'ACTIVE'
               ORDER BY sess.id DESC
               LIMIT 1"""
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def get_session_by_id(session_id: int) -> dict | None:
    conn = get_connection()
    try:
        row = conn.execute(
            """SELECT sess.*, sub.subject_code, sub.subject_name, sub.branch, sub.semester, sub.faculty, sub.room
               FROM attendance_sessions sess
               JOIN subjects sub ON sub.id = sess.subject_id
               WHERE sess.id = ?""",
            (session_id,)
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def end_session(session_id: int, end_time: str) -> bool:
    conn = get_connection()
    try:
        conn.execute(
            "UPDATE attendance_sessions SET status='COMPLETED', end_time=? WHERE id=?",
            (end_time, session_id)
        )
        conn.commit()
        return True
    except Exception as e:
        logger.error("End session error: %s", e)
        return False
    finally:
        conn.close()


def get_sessions_by_subject(subject_id: int) -> list[dict]:
    conn = get_connection()
    try:
        rows = conn.execute(
            """SELECT sess.*,
                      (SELECT COUNT(*) FROM attendance WHERE session_id = sess.id) as present_count
               FROM attendance_sessions sess
               WHERE sess.subject_id = ?
               ORDER BY sess.date DESC, sess.start_time DESC""",
            (subject_id,)
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


# ─── Session Attendance & Queries ─────────────────────────────────────────────

def record_session_attendance(session_id: int, student_id: str, date: str, time: str,
                              method: str, attendance_id: str = None) -> str:
    conn = get_connection()
    try:
        norm_method = "ID CARD" if method.upper() in ("ID CARD", "ID_CARD", "CARD", "BARCODE") else "FACE"
        conn.execute(
            """INSERT INTO attendance (session_id, student_id, date, time, method, status, attendance_id)
               VALUES (?, ?, ?, ?, ?, 'PRESENT', ?)""",
            (session_id, student_id, date, time, norm_method, attendance_id)
        )
        conn.commit()
        return "ok"
    except sqlite3.IntegrityError:
        return "duplicate"
    except Exception as e:
        logger.error("Record session attendance error: %s", e)
        return "error"
    finally:
        conn.close()


def get_session_attendance(session_id: int) -> list[dict]:
    conn = get_connection()
    try:
        rows = conn.execute(
            """SELECT a.*, s.name, s.branch, s.semester
               FROM attendance a
               JOIN students s ON s.student_id = a.student_id
               WHERE a.session_id = ?
               ORDER BY a.time DESC""",
            (session_id,)
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_session_attendance_record(session_id: int, student_id: str) -> dict | None:
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT * FROM attendance WHERE session_id=? AND student_id=?",
            (session_id, student_id)
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def get_student_subject_attendance(student_id: str) -> list[dict]:
    """
    Returns breakdown of student's attendance across all enrolled subjects:
    subject_code, subject_name, attended_sessions, total_sessions, percent
    """
    conn = get_connection()
    try:
        rows = conn.execute(
            """SELECT sub.id as subject_id, sub.subject_code, sub.subject_name,
                      (SELECT COUNT(*) FROM attendance_sessions WHERE subject_id = sub.id) as total_sessions,
                      (SELECT COUNT(DISTINCT a.session_id) 
                       FROM attendance a 
                       JOIN attendance_sessions sess ON sess.id = a.session_id
                       WHERE sess.subject_id = sub.id AND a.student_id = ?) as attended_sessions
               FROM subjects sub
               JOIN subject_enrollments se ON se.subject_id = sub.id
               WHERE se.student_id = ?
               ORDER BY sub.subject_code ASC""",
            (student_id, student_id)
        ).fetchall()
        result = []
        for r in rows:
            tot = r["total_sessions"]
            att = r["attended_sessions"]
            pct = round((att / tot * 100) if tot else 0, 1)
            result.append({
                "subject_id": r["subject_id"],
                "subject_code": r["subject_code"],
                "subject_name": r["subject_name"],
                "total_sessions": tot,
                "attended_sessions": att,
                "percent": pct
            })
        return result
    finally:
        conn.close()


def get_subject_stats(subject_id: int) -> dict:
    conn = get_connection()
    try:
        # Total enrolled
        cur = conn.execute("SELECT COUNT(*) as count FROM subject_enrollments WHERE subject_id=?", (subject_id,))
        enrolled = cur.fetchone()["count"]

        # Total sessions
        cur = conn.execute("SELECT COUNT(*) as count FROM attendance_sessions WHERE subject_id=?", (subject_id,))
        total_sessions = cur.fetchone()["count"]

        # Last session
        last_sess = conn.execute(
            """SELECT * FROM attendance_sessions WHERE subject_id=? ORDER BY date DESC, start_time DESC LIMIT 1""",
            (subject_id,)
        ).fetchone()

        last_sess_dict = dict(last_sess) if last_sess else None
        last_present = 0
        last_absent = 0
        if last_sess_dict:
            cur = conn.execute("SELECT COUNT(*) as count FROM attendance WHERE session_id=?", (last_sess_dict["id"],))
            last_present = cur.fetchone()["count"]
            last_absent = max(0, enrolled - last_present)

        # Average attendance percentage across all sessions
        avg_pct = 0.0
        if total_sessions > 0 and enrolled > 0:
            cur = conn.execute(
                """SELECT COUNT(*) as total_attendance
                   FROM attendance a
                   JOIN attendance_sessions s ON s.id = a.session_id
                   WHERE s.subject_id = ?""",
                (subject_id,)
            )
            total_att = cur.fetchone()["total_attendance"]
            avg_pct = round((total_att / (total_sessions * enrolled)) * 100, 1)

        return {
            "enrolled": enrolled,
            "total_sessions": total_sessions,
            "avg_percent": avg_pct,
            "last_session": last_sess_dict,
            "last_present": last_present,
            "last_absent": last_absent,
        }
    finally:
        conn.close()
