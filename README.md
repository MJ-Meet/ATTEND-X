# ATTEND-X — Campus Attendance Terminal

> **One Camera. Two Ways to Attend.**

ATTEND-X is a desktop attendance application that automatically identifies students by **face recognition** or by **scanning the QR code on their ID card** — no manual mode selection required.

---

## Screenshots / Demo

```
                    ATTEND-X
             CAMPUS ATTENDANCE TERMINAL
                      09:13:24
                    ● READY
        ┌──────────────────────────┐
        │      [ LIVE CAMERA ]     │
        └──────────────────────────┘
      LOOK AT CAMERA OR SCAN YOUR ID CARD
              12 / 50 PRESENT
  ────────────────────────────────────────
  09:01   Rahul Patel       FACE
  09:03   Meet Jethawa      ID CARD
  09:04   Jay Shah          FACE
  ────────────────────────────────────────
```

---

## Features

| Feature | Description |
|---|---|
| Dual-mode detection | Automatically detects face or QR/barcode without mode switching |
| Subject Management | Create, edit, search subjects (code, name, branch, semester, faculty, room) |
| Student Enrollment | Manage enrolled students per subject; unenrolled students are rejected |
| Class Sessions | Start/End attendance session per subject; enforces active class context |
| Session Duplicate Prevention | One check-in per session (student can attend multiple subjects in a day) |
| Digital Attendance Receipt | Generates high-res verification receipt PNG (`AX-YYMMDD-HHMMSS`) |
| Session Summary Modal | Auto-calculates Present, Absent (`Enrolled - Present`), Total, Attendance % |
| Student Attendance Profile | Subject-wise breakdown (`Attended / Total`, `%`, overall attendance rate) |
| Subject-wise Reports | Filter attendance by subject and date range with CSV export |
| Live Terminal Widget | Displays active class details and [ ⏹ END SESSION ] button |
| Demo Mode | Simulate face and ID card attendance against active class sessions |

---

## Project Structure

```
ATTEND-X/
├── main.py                    ← Entry point (run this)
├── database.py                ← SQLite schema, migrations + queries
├── students.py                ← Student CRUD & face encodings
├── subjects.py                ← Subjects, class sessions & enrollments
├── attendance.py              ← Mark attendance & enforce session rules
├── receipt.py                 ← Digital attendance receipt generator (PNG)
├── camera.py                  ← Camera loop + detection dispatch
├── face_recognition_module.py   ← Face detect/identify wrapper
├── barcode_scanner.py         ← pyzbar QR/barcode wrapper
├── id_card.py                 ← ID card PNG generator
├── gui.py                     ← Full Tkinter dark terminal interface
├── reports.py                 ← Subject-aware report text + CSV export
│
├── data/
│   └── attendx.db             ← SQLite database (auto-migrated)
├── faces/                     ← Student face photos
├── generated_cards/           ← Generated ID card PNGs
├── exports/                   ← Exported CSV files
│   └── receipts/              ← Generated digital attendance receipts (PNG)
├── assets/                    ← Custom icons and branding
│
├── requirements.txt
└── README.md
```

---

## Installation (Windows)

### 1. Install Python 3.10+

Download from https://www.python.org/downloads/

Make sure to check **"Add Python to PATH"** during installation.

---

### 2. Create a virtual environment

```cmd
cd "path\to\ATTEND-X"
python -m venv venv
venv\Scripts\activate
```

---

### 3. Install core requirements

```cmd
pip install opencv-python Pillow "qrcode[pil]" pandas
```

---

### 4. Install pyzbar (QR/Barcode scanning)

```cmd
pip install pyzbar
```

> **Windows note:** pyzbar requires the `zbar` DLL.
> If scanning doesn't work, download the Windows binary from:
> https://github.com/NaturalHistoryMuseum/pyzbar#installation
> and place the DLL files in your system PATH or the project folder.

---

### 5. Install face_recognition (Enables Face Identification)

To install face recognition on Windows without needing Visual Studio C++ compilers:

```cmd
pip install dlib-bin
pip install face_recognition_models "setuptools<72"
pip install face_recognition --no-deps
```

> **Note:** The application also works without `face_recognition` installed. ID card QR scanning continues to work automatically.

---

### 6. Run the application

```cmd
python main.py
```

---

## First Run

1. The application creates the SQLite database automatically.
2. Click **STUDENTS** tab → **LOAD DEMO DATA** to add sample students.
3. Go to **STUDENTS** → select a student → **GENERATE ID CARD** to create a printable card.
4. Show the printed/displayed ID card to the camera to test QR scanning.
5. To register a face: **STUDENTS** → select student → **CAPTURE FACE**.

---

## Demo Mode

Click **DEMO MODE** in the navigation bar to simulate attendance
without a physical camera or ID card.

Select a student and click:
- **SIMULATE FACE** — triggers face attendance flow
- **SIMULATE ID CARD** — triggers barcode attendance flow

Results are real database records. The counter and timeline update live.

---

## How Detection Works

```
Camera frame captured
        ↓
  QR/Barcode scan first (fast)
        ↓ found?
  ┌─────┴──────┐
  │ No         │ Yes → Read code → Find student → Mark ID CARD attendance
  ↓            
Face detection (every 8 frames)
        ↓ face found?
  ┌─────┴──────┐
  │ No         │ Yes → Encode face → Match known → Mark FACE attendance
  ↓            
  READY (nothing detected)
```

A cooldown of 3 seconds prevents double-scanning.

---

## Attendance Rules

- One attendance record per student per day.
- If already marked, the system shows **ALREADY MARKED** with the original time.
- No duplicate database records are ever created (enforced by a UNIQUE index).

---

## Privacy

- Face encodings are stored **locally** in SQLite only.
- No camera footage is permanently saved.
- Only the face photo used during registration is stored (in `faces/`).
- No data is sent to any external server.

```
Face data is stored locally for attendance identification only.
No camera footage is permanently recorded.
```

---

## Database Schema

### students
| Field | Type | Notes |
|---|---|---|
| id | INTEGER | PK |
| student_id | TEXT | Unique, e.g. 23CS014 |
| name | TEXT | Full name |
| branch | TEXT | Department |
| semester | TEXT | Semester number |
| face_encoding | BLOB | Pickled numpy array |
| photo_path | TEXT | Path to face photo |
| barcode_value | TEXT | QR code content (default = student_id) |
| created_at | TEXT | ISO datetime |

### attendance
| Field | Type | Notes |
|---|---|---|
| id | INTEGER | PK |
| student_id | TEXT | FK → students |
| date | TEXT | YYYY-MM-DD |
| time | TEXT | HH:MM:SS |
| method | TEXT | FACE or ID CARD |

Unique constraint: `(student_id, date)` — prevents duplicate daily records.

---

## Troubleshooting

| Problem | Solution |
|---|---|
| Camera not opening | Check if another app is using it; try index 1 in `camera.py` |
| pyzbar ImportError | Install zbar DLL (see Installation step 4) |
| dlib build fails | Use pre-built wheel (see Installation step 5) |
| Face not recognized | Re-capture face in better lighting; lower tolerance in `face_recognition_module.py` |
| QR code not scanning | Ensure good lighting; hold card steady; check pyzbar DLL |
| DB locked | Close other connections; restart the app |

---

## License

This project is created for educational purposes as a college mini-project.

---

*Built with Python · Tkinter · OpenCV · SQLite · face_recognition · pyzbar · Pillow*
