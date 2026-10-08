"""
ATTEND-X: Student Management Module
High-level operations for adding, editing, deleting and searching students.
"""

import logging
import os
from pathlib import Path
import database as db

logger = logging.getLogger(__name__)

FACES_DIR = Path("faces")


def add_student(student_id: str, name: str, branch: str, semester: str) -> tuple[bool, str]:
    """
    Add a student with no face encoding yet.
    Returns (success: bool, message: str).
    """
    student_id = student_id.strip().upper()
    name = name.strip()
    branch = branch.strip()
    semester = semester.strip()

    if not student_id:
        return False, "Student ID cannot be empty."
    if not name:
        return False, "Name cannot be empty."

    ok = db.insert_student(student_id, name, branch, semester, barcode_value=student_id)
    if ok:
        return True, f"Student {student_id} registered successfully."
    else:
        return False, f"Student ID '{student_id}' already exists."


def edit_student(student_id: str, name: str = None, branch: str = None,
                 semester: str = None) -> tuple[bool, str]:
    ok = db.update_student(student_id, name=name, branch=branch, semester=semester)
    if ok:
        return True, "Student updated."
    return False, "Failed to update student."


def remove_student(student_id: str) -> tuple[bool, str]:
    # Remove face file if exists
    face_file = FACES_DIR / f"{student_id}.jpg"
    if face_file.exists():
        try:
            face_file.unlink()
        except OSError:
            pass

    ok = db.delete_student(student_id)
    if ok:
        return True, f"Student {student_id} removed."
    return False, "Failed to remove student."


def search_students(query: str) -> list:
    """Return students whose ID or name contains the query string."""
    query = query.strip().lower()
    all_students = db.get_all_students()
    if not query:
        return all_students
    return [s for s in all_students
            if query in s["student_id"].lower() or query in s["name"].lower()]


def get_student(student_id: str) -> dict | None:
    return db.get_student_by_id(student_id)


def load_demo_students() -> list[str]:
    """Insert demo students. Returns list of messages."""
    demo = [
        ("23CS001", "Rahul Patel",   "Computer Science", "6"),
        ("23CS002", "Priya Shah",    "Computer Science", "6"),
        ("23CS003", "Jay Patel",     "Computer Science", "6"),
        ("23CS004", "Meet Jethawa",  "Computer Science", "6"),
        ("23CS005", "Riya Shah",     "Computer Science", "6"),
        ("23CS006", "Dev Patel",     "Computer Science", "6"),
        ("23ME001", "Aryan Mehta",   "Mechanical Engg",  "4"),
        ("23ME002", "Pooja Desai",   "Mechanical Engg",  "4"),
        ("23EC001", "Nikhil Trivedi","Electronics",      "5"),
        ("23EC002", "Simran Kaur",   "Electronics",      "5"),
    ]
    results = []
    for sid, name, branch, sem in demo:
        ok, msg = add_student(sid, name, branch, sem)
        results.append(msg)
    return results


def save_face_encoding(student_id: str, encoding, photo_path: str = None) -> tuple[bool, str]:
    """
    Persist a face encoding (numpy array) as bytes in the database.
    """
    import pickle
    try:
        encoding_bytes = pickle.dumps(encoding)
        db.update_student(student_id, face_encoding=encoding_bytes, photo_path=photo_path)
        return True, "Face encoding saved."
    except Exception as e:
        logger.error("Save face encoding error: %s", e)
        return False, str(e)


def load_all_face_encodings() -> list[dict]:
    """
    Returns list of {student_id, name, encoding (numpy array)}.
    """
    import pickle
    rows = db.get_all_students_with_encodings()
    result = []
    for r in rows:
        try:
            enc = pickle.loads(r["face_encoding"])
            result.append({"student_id": r["student_id"], "name": r["name"], "encoding": enc})
        except Exception as e:
            logger.warning("Could not load encoding for %s: %s", r["student_id"], e)
    return result
