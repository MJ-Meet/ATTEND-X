<div align="center">

# ⚡ ATTEND-X
### **Next-Gen Campus Attendance Terminal**
*One Camera. Zero Queues. Dual-Mode Biometric & Optical Check-In.*

[![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/)
[![OpenCV](https://img.shields.io/badge/OpenCV-Computer%20Vision-5C3EE8?style=for-the-badge&logo=opencv&logoColor=white)](https://opencv.org/)
[![Tkinter](https://img.shields.io/badge/GUI-Tkinter%20Dark%20Terminal-222222?style=for-the-badge&logo=gnometerminal&logoColor=white)](https://docs.python.org/3/library/tkinter.html)
[![SQLite](https://img.shields.io/badge/Database-SQLite3%20(WAL)-003B57?style=for-the-badge&logo=sqlite&logoColor=white)](https://sqlite.org/)
[![Dlib / Face Rec](https://img.shields.io/badge/Biometrics-128D%20Embeddings-FF6F00?style=for-the-badge&logo=scikitlearn&logoColor=white)](https://github.com/ageitgey/face_recognition)
[![PyZbar](https://img.shields.io/badge/Scanner-PyZbar%20QR%20Engine-009688?style=for-the-badge&logo=qr-code&logoColor=white)](https://github.com/NaturalHistoryMuseum/pyzbar)
[![License](https://img.shields.io/badge/License-Academic%20%2F%20MIT-blue?style=for-the-badge)](#license)

<br/>

```
  █████╗ ████████╗████████╗███████╗███╗   ██╗██████╗     ██╗  ██╗
 ██╔══██╗╚══██╔══╝╚══██╔══╝██╔════╝████╗  ██║██╔══██╗    ╚██╗██╔╝
 ███████║   ██║      ██║   █████╗  ██╔██╗ ██║██║  ██║     ╚███╔╝ 
 ██╔══██║   ██║      ██║   ██╔══╝  ██║╚██╗██║██║  ██║     ██╔██╗ 
 ██║  ██║   ██║      ██║   ███████╗██║ ╚████║██████╔╝    ██╔╝ ██╗
 ╚═╝  ╚═╝   ╚═╝      ╚═╝   ╚══════╝╚═╝  ╚═══╝╚═════╝     ╚═╝  ╚═╝
```

> **ATTEND-X** replaces slow, paper-based roll calls and proxy attendance with a unified, high-speed campus terminal.  
> Using **OpenCV multi-threading**, **dlib biometric landmark embeddings**, and **optical QR decoding**, students attend classes in **< 1 second** — simply by looking at the camera or presenting their student ID card.

---

</div>

## 📌 At A Glance

| Metric / Capability | Specification |
|---|---|
| **Recognition Speed** | `< 0.8s` (Sub-second dual-mode detection) |
| **Detection Methods** | **Facial Biometrics** (128-d Euclidean) + **Optical QR/Barcode** (`pyzbar`) |
| **Concurrency Engine** | Multi-threaded background capture (`CameraThread`) decoupled from UI |
| **Camera FPS** | 30 FPS steady non-blocking Tkinter video feed |
| **Anti-Proxy Protection** | One check-in per session with active class & enrollment verification |
| **Digital Verification** | Auto-generates high-resolution verification receipt image (`AX-YYMMDD-HHMMSS`) |
| **Reporting** | Subject-wise analytics with instant CSV export for College ERP |
| **Deployment** | 100% offline, privacy-first, zero cloud latency, local SQLite WAL engine |

---

## 🖥️ Live Terminal HUD Demo

```text
 ┌────────────────────────────────────────────────────────────────────────┐
 │  ATTEND-X : CAMPUS ATTENDANCE TERMINAL                     [ 09:14:02 ] │
 │  ACTIVE CLASS: CS-501 (Data Structures) | PROF. S. SHARMA  [ ● RUNNING] │
 ├────────────────────────────────────────┬───────────────────────────────┤
 │                                        │  STUDENT VERIFICATION HUD    │
 │       ┌────────────────────────┐       │  Name:     Rahul Patel        │
 │       │     [ LIVE 30 FPS ]    │       │  Roll No:  23CS014            │
 │       │                        │       │  Branch:   CSE (Sem 5)        │
 │       │    ● FACE DETECTED     │       │  Method:   BIOMETRIC_FACE     │
 │       │   [0.42 MATCH SCORE]   │       │  Status:   ✓ PRESENT          │
 │       └────────────────────────┘       │  Receipt:  AX-261013-091402   │
 │                                        ├───────────────────────────────┤
 │    LOOK AT CAMERA OR SCAN ID CARD      │  SESSION ATTENDANCE TIMELINE  │
 │          [ 42 / 60 PRESENT ]           │  09:13:58  Jay S.    ID CARD  │
 │     [=====================>    ] 70%   │  09:14:02  Rahul P.  FACE     │
 └────────────────────────────────────────┴───────────────────────────────┘
```

---

## 🚀 Key Features

### 👁️ Dual-Mode Biometric & Optical Recognition
* **Zero Mode Switching:** No buttons to press. The unified vision pipeline automatically identifies whether a face is in frame or a student is holding up an ID card QR code.
* **128-Dimensional Facial Vectors:** Extracts biometric landmark embeddings using deep neural networks to match faces across varied lighting and angles.
* **High-Speed QR Engine:** Preprocesses camera frames with adaptive thresholding and contrast normalization to scan ID cards instantly.

### 🛡️ Active Class Sessions & Anti-Proxy Engine
* **Subject Context:** Attendance is tied to scheduled course sessions (e.g., *CS-501, Operating Systems*).
* **Strict Enrollment Verification:** Students not enrolled in the active subject are rejected (`UNENROLLED`).
* **Anti-Duplicate Lock:** Students cannot be scanned twice within the same class session (`DUPLICATE REJECTED`).

### 🪪 Automated ID Card & Digital Receipt Synthesis
* **Printable ID Card Generator:** Built-in Pillow rendering engine that generates customized, campus-branded ID card PNGs with embedded QR codes and student portraits.
* **Digital Attendance Receipts:** Instant high-resolution cryptographic verification token (`AX-YYMMDD-HHMMSS.png`) generated for students as proof of attendance.

### 📊 Real-Time Analytics & CSV Reports
* **Subject-Wise Breakdown:** Filter attendance records by subject code, date range, branch, or semester.
* **ERP-Ready Export:** Generates clean CSV spreadsheets with attendance percentage calculations for university management systems.

### 🎮 Standalone Demo Simulation Mode
* Built-in simulation tool allowing faculty or viva examiners to test facial and barcode recognition without needing an external webcam.

---

## 🔄 System Architecture & Data Flow

```mermaid
flowchart TD
    A[Webcam Feed] --> B[CameraThread - OpenCV 30 FPS]
    B --> C{Frame Dispatcher}
    
    C -->|Stage 1: Scan Optical| D[pyzbar Engine]
    D -->|QR Decoded| E[Parse Student ID]
    
    C -->|Stage 2: If No QR| F[Face Recognition Module]
    F -->|Face Located| G[Extract 128-d Embedding Vector]
    G -->|Euclidean Matching <= 0.5| E
    
    E --> H{Attendance Engine}
    H -->|Not Enrolled| I[Show Status: UNENROLLED]
    H -->|Already Checked-in| J[Show Status: DUPLICATE]
    H -->|Valid Entry| K[Log Attendance to SQLite]
    
    K --> L[Generate Receipt PNG]
    K --> M[Update Live GUI Canvas & Audio HUD]
    K --> N[Update Real-time Attendance Counter]
```

---

## 🛠️ Technology Stack

| Layer | Technologies Used | Description |
|---|---|---|
| **Core Language** | ![Python](https://img.shields.io/badge/Python-3776AB?style=flat&logo=python&logoColor=white) **Python 3.10+** | Modern typed Python with dataclasses & logging |
| **Computer Vision** | ![OpenCV](https://img.shields.io/badge/OpenCV-5C3EE8?style=flat&logo=opencv&logoColor=white) **OpenCV (`cv2`)** | Video capture, frame preprocessing & bounding-box tracking |
| **Biometrics** | ![dlib](https://img.shields.io/badge/dlib-FF6F00?style=flat&logo=scikitlearn&logoColor=white) **`face_recognition`** | HOG/CNN face detection & 128-d embedding extraction |
| **Optical Scanner** | ![QR](https://img.shields.io/badge/PyZbar-009688?style=flat&logo=qr-code&logoColor=white) **`pyzbar`** | C-based optical barcode & QR code decoding |
| **User Interface** | ![Tkinter](https://img.shields.io/badge/Tkinter-222222?style=flat&logo=gnometerminal&logoColor=white) **Tkinter / ttk** | Responsive dark-mode terminal UI with custom HUD |
| **Concurrency** | ![Threading](https://img.shields.io/badge/threading-4B8BBE?style=flat) **Python `threading`** | Decoupled background capture to prevent UI lag |
| **Image Synthesis** | ![Pillow](https://img.shields.io/badge/Pillow-3776AB?style=flat) **Pillow & `qrcode`** | ID card and digital receipt layout generation |
| **Database** | ![SQLite](https://img.shields.io/badge/SQLite-003B57?style=flat&logo=sqlite&logoColor=white) **SQLite3** | Relational storage with WAL mode & atomic transactions |
| **Data Analytics** | ![Pandas](https://img.shields.io/badge/Pandas-150458?style=flat&logo=pandas&logoColor=white) **Pandas** | Tabular data analysis and CSV report exports |

---

## 📂 Project Structure

```
ATTEND-X/
├── main.py                     # Application entry point & bootstrapping
├── gui.py                      # Full Tkinter dark terminal UI & HUD (2,600+ LOC)
├── camera.py                   # Multi-threaded OpenCV video capture pipeline
├── database.py                 # SQLite relational schema, queries & WAL mode
├── attendance.py               # Attendance validation, duplicate checks & session rules
├── face_recognition_module.py  # Biometric facial landmark & vector matching
├── barcode_scanner.py          # PyZbar optical decoding & contrast filter engine
├── id_card.py                  # Automated printable student ID card generator
├── receipt.py                  # Digital attendance verification receipt synthesis
├── subjects.py                 # Academic courses & class session management
├── students.py                 # Student catalog & photo mapping
├── reports.py                  # Subject attendance analytics & CSV export
│
├── test_face_validation.py     # Face tolerance & accuracy test suite
├── test_subject_system.py      # Session & enrollment unit tests
├── test_id_card_fix.py         # ID card layout & DPI rendering tests
├── verify_id_scanner_fix.py    # Scanner hardware verification test harness
│
├── data/                       # Local SQLite database (attendx.db)
├── faces/                      # Student face biometric registration photos
├── generated_cards/            # Generated student ID card PNGs
├── exports/                    # Exported attendance CSV spreadsheets
│   └── receipts/               # Generated digital verification receipts
│
├── requirements.txt            # Project dependencies
└── README.md                   # Technical documentation
```

## ⚡ Quick Installation & Setup

### 1. Clone the Repository
```bash
git clone https://github.com/MJ-Meet/ATTEND-X.git
cd ATTEND-X
```

### 2. Set Up Virtual Environment
```bash
# Windows
python -m venv venv
venv\Scripts\activate
```

### 3. Install Core Dependencies
```bash
pip install opencv-python Pillow "qrcode[pil]" pandas pyzbar
```

### 4. Install Biometric Face Recognition *(Optional but Recommended)*
To install `face_recognition` on Windows without needing Visual Studio C++ compilers:
```bash
pip install dlib-bin
pip install face_recognition_models "setuptools<72"
pip install face_recognition --no-deps
```

> **Note:** ATTEND-X features graceful degradation. If `face_recognition` is not installed, the terminal runs seamlessly using **ID Card QR scanning**.

### 5. Launch the Application
```bash
python main.py
```

---

## 🎯 Quick Start Guide

1. **Launch Terminal:** Run `python main.py`. The database initializes automatically.
2. **Load Sample Data:** Click **STUDENTS** → **LOAD DEMO DATA** to populate sample students.
3. **Generate ID Card:** Go to **STUDENTS** → select a student → **GENERATE ID CARD** to create a printable card with an embedded QR code.
4. **Register Faces:** Go to **STUDENTS** → select student → **CAPTURE FACE** to train biometric embeddings.
5. **Start Class Session:** Go to **TERMINAL** → pick your subject → Click **[ START SESSION ]**.
6. **Mark Attendance:** Hold an ID card to the webcam or look directly at the lens.
7. **End & Export:** Click **[ ⏹ END SESSION ]** to view the session summary, then export reports under **REPORTS** → **EXPORT CSV**.

---

## 🔒 Privacy & Local-First Philosophy

* 🛡️ **Zero Cloud Transmission:** Biometric embeddings and student data never leave the local machine.
* 💾 **No Video Recording:** Video frames are processed in-memory and discarded immediately; no surveillance video is saved.
* 🔐 **Isolated Embeddings:** Facial data is stored as 128-dimensional floating point vectors inside local SQLite storage.

---

## 📄 License

Developed for academic engineering purposes under the **MIT License**.

---

<div align="center">
  <b>Built with ❤️ by the ATTEND-X Team</b><br/>
  <i>Python · OpenCV · Tkinter · SQLite · face_recognition · pyzbar · Pillow</i>
</div>
