# ATTEND-X — Project Work Distribution & Contribution Split

This document outlines the architectural division of work and individual contributions for the **ATTEND-X (Campus Attendance Terminal)** college project, distributed across 3 team members according to the **60% / 35% / 5%** contribution model.

---

## Executive Summary

| Member | Contribution | Role / Title | Complexity Level | Primary Responsibilities | Total LOC (approx.) |
|---|:---:|---|:---:|---|:---:|
| **Member 1** | **60%** | **Lead Architect & Core Systems / AI Lead** | 🔴 **High (Hardest Core Systems & AI)** | Thread-Safe GUI, Async Camera Engine, SQLite Backend, Biometric Face Recognition, ID Card Engine, Attendance Rules | ~4,300 lines (~60%+) |
| **Member 2** | **35%** | **Optical Scanner, Analytics & Feature Subsystems Developer** | 🟡 **Medium (Scanner & Features)** | PyZbar QR/Barcode Scanner Engine, Course/Subject Catalog, CSV Reports, Receipts & Test Automation | ~1,680 lines (~35%) |
| **Member 3** | **5%** | **Technical Documentation & Setup Assistant** | 🟢 **Basic (Support & QA)** | Technical Documentation (README), Dependencies Management, Windows ZBar DLL Setup, Verification Script | ~250 lines + Docs (~5%) |

---

## 🏆 Why Member 1 Handled the Most Complex / Hardest Engineering Challenges

Member 1 was responsible for the core engineering backbone and artificial intelligence components of the project:

1. **Multi-Threaded Video Pipeline & Concurrency (`camera.py` & `gui.py`):**
   - **The Challenge:** Video capture in OpenCV is synchronous and blocking; running it in the main loop freezes Tkinter immediately.
   - **The Solution:** Built a dedicated `CameraThread` running asynchronously with thread-safe frame queues, rendering at 30 FPS using `root.after()` callbacks without UI lockups or memory leaks.

2. **Biometric Face Recognition Model (`face_recognition_module.py` — 172 lines):**
   - **The Challenge:** Real-time facial localization, 128-dimensional embedding generation, and fast Euclidean distance vector matching.
   - **The Solution:** Built a robust face recognition wrapper with dynamic distance tolerance thresholds to balance false acceptance and false rejection rates.

3. **Dynamic Printable ID Card Generator with QR Embedding (`id_card.py` — 183 lines):**
   - **The Challenge:** Generating high-resolution physical ID cards dynamically with layered student photos, campus branding, and encoded QR metadata.
   - **The Solution:** Engineered an automated image synthesis pipeline using Pillow to render and layout cards on the fly.

4. **Full Dark Terminal GUI State Machine (`gui.py` — 2,646+ lines):**
   - **The Challenge:** Building a responsive terminal-style dashboard entirely from scratch in Tkinter with real-time video overlay, HUD telemetry, and dynamic modal dialogs.
   - **The Solution:** Engineered custom widgets, responsive layout geometry, real-time HUD graphics, and event-driven state transitions.

5. **Relational Database Engine & Transaction Safety (`database.py` — 696 lines):**
   - **The Challenge:** Designing normalized schemas across students, subjects, active class sessions, and logs with zero corruption under rapid scanning.
   - **The Solution:** Implemented SQLite transactions, automated database migrations, indexing, and foreign key integrity constraints.

6. **Attendance Validation State Engine (`attendance.py` — 241 lines):**
   - **The Challenge:** Handling rapid scan events, debouncing multiple detections, checking enrolled vs. unenrolled students, and enforcing single-attendance session rules.
   - **The Solution:** Designed state verification logic that evaluates active class context and prevents duplicate check-ins in real time.

---

## Detailed Distribution by Member

### 👤 Member 1 — 60% (Lead Architect & Core Systems / AI Lead)
> **Core Focus:** The hardest technical engineering tasks — Concurrency, Biometric Face Recognition, Dynamic ID Card Rendering, Thread Safety, Database Architecture, and Core GUI.

#### Assigned Files & Modules:
1. **`gui.py`** (~2,646 lines) — Complete Tkinter dark terminal UI, live camera canvas, session HUD, tab controllers, thread-safe UI updates.
2. **`database.py`** (696 lines) — SQLite schema design, connection pooling, queries, table relationships, automated schema migrations.
3. **`camera.py`** (252 lines) — Asynchronous OpenCV video capture loop (`CameraThread`), frame buffering, and hardware negotiation.
4. **`attendance.py`** (241 lines) — Attendance validation rules, active session binding, debouncing, and duplicate prevention.
5. **`id_card.py`** (183 lines) — Automated student ID card designer using Python `Pillow` (PIL) and QR code embedding.
6. **`face_recognition_module.py`** (172 lines) — Facial landmark detection and 128-d vector embedding extraction using dlib.
7. **`main.py`** (113 lines) — App entry point, bootstrap flow, directory validation, error handlers, and logging pipeline.

#### Key Viva / Presentation Talking Points:
- *"What was the most challenging technical problem you solved?"*  
  **Answer:** *"Decoupling the 30 FPS OpenCV camera capture and biometric face recognition pipeline into asynchronous worker threads so the Tkinter GUI runs smoothly without freezing."*
- *"How does the biometric face recognition matching work?"*  
  **Answer:** *"In `face_recognition_module.py`, I locate facial landmarks, compute a 128-dimensional floating point embedding vector, and calculate the Euclidean distance against stored student facial vectors using calibrated tolerance limits."*

---

### 👤 Member 2 — 35% (Optical Scanner, Analytics & Feature Subsystems Developer)
> **Core Focus:** QR/Barcode optical decoding engine, academic course management, receipt generator, analytics reporting, and automated test suites.

#### Assigned Files & Modules:
1. **`barcode_scanner.py`** (606 lines) — Integrated `pyzbar` for QR/barcode decoding, contrast enhancement filters, and bounding-box coordinates.
2. **`subjects.py`** (172 lines) & **`students.py`** (101 lines) — Subject catalog, student enrollment mapping, and profile CRUD handlers.
3. **`reports.py`** (177 lines) — Attendance data aggregation, summary statistics, and CSV export engine.
4. **`receipt.py`** (109 lines) — Digital attendance verification receipt PNG generator (`AX-YYMMDD-HHMMSS`).
5. **`test_face_validation.py`** (195 lines) — Automated test suite validating face recognition tolerance and edge-cases.
6. **`test_subject_system.py`** (162 lines) — Unit tests covering subject creation, student enrollment constraints, and session transitions.
7. **`test_id_card_fix.py`** (158 lines) — Card layout and DPI rendering test script.

#### Key Viva / Presentation Talking Points:
- *"How does the barcode and QR scanner work under difficult lighting?"*  
  **Answer:** *"In `barcode_scanner.py`, frames pass through adaptive thresholding and contrast normalization filters before PyZbar decodes the QR data and calculates bounding-box coordinates for the HUD."*
- *"How does the system handle subject-wise reporting?"*  
  **Answer:** *"In `reports.py`, queries aggregate attendance records by subject ID and date ranges, calculating attendance percentages and generating structured CSV export files."*

---

### 👤 Member 3 — 5% (Technical Documentation & Setup Assistant)
> **Core Focus:** Project Documentation, Environment Configuration, Windows Dependency Resolution, and Hardware Verification.

#### Assigned Files & Modules:
1. **`README.md`** (257 lines) — Project setup instructions, usage manual, and ASCII architecture diagrams.
2. **`requirements.txt`** — Package dependency curation and virtual environment setup.
3. **`verify_id_scanner_fix.py`** (179 lines) — Hardware verification test script for camera and QR scanner.
4. **Environment Setup & Configuration** — Managing Windows-specific `zbar` DLL linking and dlib installation guide.

#### Key Viva / Presentation Talking Points:
- *"What was your primary role in this project?"*  
  **Answer:** *"I handled technical documentation, environment configuration, cross-platform dependency setup (especially resolving Windows ZBar DLL issues for QR scanning), and conducted hardware verification tests on the camera scanner."*

---

## File-to-Author Attribution Matrix

| File | Primary Author | Share | Complexity | Description |
|---|---|:---:|:---:|---|
| `gui.py` | Member 1 | 60% | 🔴 High | Complete Tkinter dark terminal UI, live canvas, state engine |
| `database.py` | Member 1 | 60% | 🔴 High | SQLite database, schema, migrations & queries |
| `camera.py` | Member 1 | 60% | 🔴 High | Multi-threaded OpenCV video capture & frame dispatch |
| `attendance.py` | Member 1 | 60% | 🔴 High | Session attendance rules, duplicate check logic |
| `id_card.py` | Member 1 | 60% | 🔴 High | Dynamic ID Card synthesis with embedded QR & Pillow graphics |
| `face_recognition_module.py` | Member 1 | 60% | 🔴 High | Biometric face embeddings & Euclidean vector distance matching |
| `main.py` | Member 1 | 60% | 🔴 High | Application entry point & lifecycle |
| `barcode_scanner.py` | Member 2 | 35% | 🟡 Medium | PyZbar QR/Barcode decoding & optical filter pipeline |
| `subjects.py` | Member 2 | 35% | 🟡 Medium | Subject catalog & class session model |
| `students.py` | Member 2 | 35% | 🟡 Medium | Student CRUD & face mapping |
| `reports.py` | Member 2 | 35% | 🟡 Medium | Attendance analytics & CSV exporter |
| `receipt.py` | Member 2 | 35% | 🟡 Medium | Attendance receipt generator |
| `test_face_validation.py` | Member 2 | 35% | 🟡 Medium | Face tolerance & accuracy test suite |
| `test_subject_system.py` | Member 2 | 35% | 🟡 Medium | Subject & session unit testing |
| `test_id_card_fix.py` | Member 2 | 35% | 🟡 Medium | Card rendering & DPI unit testing |
| `verify_id_scanner_fix.py` | Member 3 | 5% | 🟢 Basic | Barcode & hardware verification script |
| `requirements.txt` | Member 3 | 5% | 🟢 Basic | Package dependencies & environment |
| `README.md` | Member 3 | 5% | 🟢 Basic | Complete system documentation |
