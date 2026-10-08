"""
ATTEND-X: Reports Module
Generates subject-wise and date-range attendance summaries,
calculates attendance percentages, and exports CSV files.
"""

import logging
import csv
from datetime import date, datetime
from pathlib import Path
import database as db

logger = logging.getLogger(__name__)

EXPORTS_DIR = Path("exports")


def generate_report(from_date: str, to_date: str,
                    student_query: str = "",
                    subject_id: int | None = None) -> tuple[str, list]:
    """
    Build a formatted report string and return raw data rows.
    Supports filtering by date range, student, and subject.
    """
    EXPORTS_DIR.mkdir(exist_ok=True)

    # Validate / default dates
    try:
        if from_date:
            datetime.strptime(from_date, "%Y-%m-%d")
        else:
            from_date = date.today().isoformat()
    except (ValueError, TypeError):
        from_date = date.today().isoformat()

    try:
        if to_date:
            datetime.strptime(to_date, "%Y-%m-%d")
        else:
            to_date = date.today().isoformat()
    except (ValueError, TypeError):
        to_date = date.today().isoformat()

    if from_date > to_date:
        from_date, to_date = to_date, from_date

    # Query with subject join
    conn = db.get_connection()
    try:
        sql = """
            SELECT a.date, a.time, a.method, a.status, a.attendance_id, a.session_id,
                   s.student_id, s.name, s.branch as student_branch, s.semester as student_semester,
                   COALESCE(sub.subject_code, 'GENERAL') as subject_code,
                   COALESCE(sub.subject_name, 'General Terminal') as subject_name,
                   COALESCE(sub.faculty, '—') as faculty,
                   COALESCE(sub.room, '—') as room
            FROM attendance a
            JOIN students s ON s.student_id = a.student_id
            LEFT JOIN attendance_sessions sess ON sess.id = a.session_id
            LEFT JOIN subjects sub ON sub.id = sess.subject_id
            WHERE a.date BETWEEN ? AND ?
        """
        params = [from_date, to_date]

        if subject_id is not None:
            sql += " AND (sub.id = ? OR (sess.subject_id = ?))"
            params.extend([subject_id, subject_id])

        sql += " ORDER BY a.date DESC, a.time DESC"
        rows = [dict(r) for r in conn.execute(sql, params).fetchall()]
    finally:
        conn.close()

    # Filter by student query
    q = student_query.strip().lower()
    if q:
        rows = [r for r in rows
                if q in r["student_id"].lower() or q in r["name"].lower()]

    # Fetch subject details if filtered
    subject_info = None
    if subject_id is not None:
        subject_info = db.get_subject_by_id(subject_id)

    lines = []
    lines.append("=" * 68)
    lines.append("  ATTEND-X  ·  CAMPUS ATTENDANCE REPORT")
    lines.append("=" * 68)
    lines.append(f"  Period    :  {from_date}  →  {to_date}")
    if subject_info:
        lines.append(f"  Subject   :  {subject_info['subject_name']} ({subject_info['subject_code']})")
        lines.append(f"  Faculty   :  {subject_info['faculty']}  ·  Room: {subject_info['room']}")
    if q:
        lines.append(f"  Filter    :  {student_query}")
    lines.append(f"  Generated :  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append("")

    if not rows:
        lines.append("  NO ATTENDANCE RECORDS FOUND")
        lines.append("")
        lines.append("  Select another date range or subject.")
        lines.append("=" * 68)
        return "\n".join(lines), rows

    # Summary metrics
    distinct_dates = len({r["date"] for r in rows})
    face_count     = sum(1 for r in rows if r["method"] == "FACE")
    id_count       = sum(1 for r in rows if r["method"] == "ID CARD")
    unique_present = len({r["student_id"] for r in rows})

    total_target = len(db.get_enrolled_students(subject_id)) if subject_id else len(db.get_all_students())
    absent_count = max(0, total_target - unique_present)
    att_rate     = round((unique_present / total_target * 100) if total_target else 0, 2)

    lines.append(f"  Total Records        : {len(rows)}")
    lines.append(f"  Unique Students      : {unique_present}")
    lines.append(f"  Target Enrolled      : {total_target}")
    lines.append(f"  Calculated Absent    : {absent_count}")
    lines.append(f"  Attendance Rate      : {att_rate}%")
    lines.append(f"  Face Identifications : {face_count}")
    lines.append(f"  ID Card Scans        : {id_count}")
    lines.append("")

    # If single subject and single date: list enrolled students with PRESENT / ABSENT status
    if subject_id and from_date == to_date:
        enrolled = db.get_enrolled_students(subject_id)
        present_sids = {r["student_id"] for r in rows}
        lines.append("-" * 68)
        lines.append(f"  {'STUDENT ID':<14} {'STUDENT NAME':<24} {'STATUS':<10} {'METHOD'}")
        lines.append("-" * 68)
        for s in enrolled:
            sid = s["student_id"]
            if sid in present_sids:
                s_rec = next(r for r in rows if r["student_id"] == sid)
                lines.append(f"  {sid:<14} {s['name'][:22]:<24} {'PRESENT':<10} {s_rec['method']}")
            else:
                lines.append(f"  {sid:<14} {s['name'][:22]:<24} {'ABSENT':<10} —")
        lines.append("-" * 68)
        lines.append(f"  Present: {len(present_sids)}   Absent: {len(enrolled) - len(present_sids)}   Total: {len(enrolled)}")
        lines.append(f"  Attendance: {att_rate}%")
        lines.append("")

    # Detailed table of records
    lines.append("=" * 68)
    lines.append(f"  {'DATE':<12} {'TIME':<8} {'CODE':<8} {'STUDENT ID':<12} {'NAME':<18} {'METHOD'}")
    lines.append("-" * 68)
    for r in rows:
        lines.append(
            f"  {r['date']:<12} {r['time'][:5]:<8} {r['subject_code'][:7]:<8} "
            f"{r['student_id']:<12} {r['name'][:16]:<18} {r['method']}"
        )
    lines.append("=" * 68)

    return "\n".join(lines), rows


def export_to_csv(rows: list, output_path: str) -> tuple[bool, str]:
    """
    Write rows to a CSV file including subject and attendance verification ID.
    """
    EXPORTS_DIR.mkdir(exist_ok=True)
    try:
        fieldnames = [
            "date", "time", "subject_code", "subject_name",
            "student_id", "name", "method", "status", "attendance_id"
        ]
        with open(output_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(rows)
        return True, f"Exported {len(rows)} records."
    except Exception as e:
        logger.error("CSV export error: %s", e)
        return False, str(e)


def export_csv(output_path: str = None, subject_id: int | None = None,
               start_date: str = None, end_date: str = None) -> str:
    """Convenience helper to generate rows and export to CSV, returning output path."""
    if not output_path:
        EXPORTS_DIR.mkdir(exist_ok=True)
        fname = f"attendance_{date.today().isoformat()}_{datetime.now().strftime('%H%M%S')}.csv"
        output_path = str(EXPORTS_DIR / fname)
    _, rows = generate_report(from_date=start_date, to_date=end_date,
                              student_query="", subject_id=subject_id)
    ok, _ = export_to_csv(rows, output_path)
    return output_path if ok else ""



def quick_today_summary(subject_id: int | None = None) -> str:
    """Return a single-line summary for today's attendance."""
    today = date.today().isoformat()
    if subject_id:
        enrolled = len(db.get_enrolled_students(subject_id))
        records = db.get_attendance_range(today, today)
        present = len(records)
        pct = round((present / enrolled * 100) if enrolled else 0, 1)
        return f"{present}/{enrolled} present ({pct}%)"
    else:
        records = db.get_attendance_by_date(today)
        total = len(db.get_all_students())
        present = len(records)
        pct = round((present / total * 100) if total else 0, 1)
        return f"{present}/{total} present ({pct}%)"
