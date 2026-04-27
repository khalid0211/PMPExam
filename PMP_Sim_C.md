# PMP MCQ Exam Simulator - Implementation Plan

## Overview
A Streamlit-based exam simulator with Firebase backend for conducting PMP-style multiple choice question exams.

## Requirements Summary
- **Tech Stack:** Streamlit + Firebase (Firestore + Auth) + Pandas
- **Exam Length:** All questions from question bank, randomized order
- **Time Limit:** 4 hours (230 minutes) with visible countdown timer
- **Pause/Resume:** Yes, timer pauses when student exits
- **Scoring:** Simple (1 point per correct, no negative marking)
- **Results:** Full review with correct answers shown
- **Admin Setup:** Hardcoded email in config
- **Deployment:** Streamlit Cloud

## CSV Input Format
```
SNo.,Domain,Question,Option A,Option B,Option C,Option D,Correct Answer
1,People,Question text here...,Option A text,Option B text,Option C text,Option D text,B
```

---

## Project Structure

```
F:\Coding\PMPExam\
├── .streamlit/
│   ├── config.toml           # Streamlit theme settings
│   └── secrets.toml          # Firebase credentials, admin email (local only)
├── app.py                    # Main entry point and router
├── requirements.txt          # Python dependencies
├── config.py                 # App constants and session keys
├── firebase_config.py        # Firebase initialization
├── auth.py                   # Google OAuth logic
├── pages/
│   ├── login.py              # Login page
│   ├── student_dashboard.py  # Student home with exam history
│   ├── exam_engine.py        # Core exam taking interface
│   ├── review_mode.py        # Post-exam review
│   └── admin_panel.py        # User management, CSV upload
├── components/
│   ├── timer.py              # Countdown timer with pause/resume
│   ├── question_card.py      # Question display component
│   └── sidebar_nav.py        # Question navigation grid
├── services/
│   ├── user_service.py       # User CRUD
│   ├── question_service.py   # Question bank operations
│   └── exam_service.py       # Exam session management
├── utils/
│   ├── csv_parser.py         # CSV upload processing
│   └── scoring.py            # Score calculation
└── data/
    └── sample_questions.csv  # Sample data for testing
```

---

## Implementation Phases

### Phase 1: Setup (Firebase + Project Scaffolding)

**1.1 Firebase Console Setup**
- Create Firebase project
- Enable Google Authentication
- Create Firestore database (production mode)
- Generate service account key (JSON)
- Configure OAuth in Google Cloud Console

**1.2 Project Files**
- Create `requirements.txt`:
  ```
  streamlit>=1.28.0
  firebase-admin>=6.2.0
  google-cloud-firestore>=2.13.0
  pandas>=2.0.0
  streamlit-autorefresh>=1.0.1
  ```
- Create `.streamlit/secrets.toml` template
- Create `config.py` with constants

**Files to create:** `requirements.txt`, `config.py`, `firebase_config.py`, `.streamlit/secrets.toml`

---

### Phase 2: Authentication

**2.1 Firebase Init (`firebase_config.py`)**
- Initialize Firebase Admin SDK from secrets
- Cache Firestore client with `@st.cache_resource`

**2.2 Auth Module (`auth.py`)**
- Google OAuth using Streamlit's `st.login()`
- Auto-create user in Firestore on first login
- Check `is_enabled` status before granting access
- Auto-promote hardcoded admin email to admin role

**Files to create:** `auth.py`

---

### Phase 3: Services Layer

**3.1 User Service (`services/user_service.py`)**
- Get all students
- Toggle user access (enable/disable)
- Reset attempt counter
- Update max tries
- Increment tries on exam start

**3.2 Question Service (`services/question_service.py`)**
- Get all questions
- Get randomized questions
- Upload from CSV (with column mapping for user's format)
- Clear all questions
- CSV column mapping:
  - `SNo.` -> ignored (auto-generate q_id)
  - `Domain` -> `domain`
  - `Question` -> `text`
  - `Option A/B/C/D` -> `choices.a/b/c/d`
  - `Correct Answer` -> `correct_choice` (normalize to lowercase)

**3.3 Exam Service (`services/exam_service.py`)**
- Create exam (store randomized question order)
- Get exam by ID
- Get user's exams
- Get in-progress exam for resume
- Save individual answer
- Update time remaining (for pause)
- Complete exam with scores

**Files to create:** `services/user_service.py`, `services/question_service.py`, `services/exam_service.py`

---

### Phase 4: Core Exam Engine

**4.1 Timer Component (`components/timer.py`)**
- Use `streamlit-autorefresh` for 1-second updates
- Track `time_remaining` and `timer_start` in session state
- `pause_timer()`: Calculate remaining, clear timer_start
- `resume_timer()`: Set timer_start to now
- Color coding: green (normal), orange (<15 min), red (<5 min)

**4.2 Exam Engine (`pages/exam_engine.py`)**
- Initialize or restore exam state from Firestore
- Display current question with radio buttons for choices
- Previous/Next navigation
- Mark for Review toggle
- Sidebar with question grid (answered/unanswered/marked indicators)
- Progress bar
- Save & Exit button (pause timer, save to Firestore)
- Submit button with confirmation
- Auto-submit when timer expires

**Key State Variables:**
- `exam_id`, `questions`, `answers`, `current_question_index`
- `marked_for_review`, `time_remaining`, `timer_start`

**Files to create:** `components/timer.py`, `pages/exam_engine.py`

---

### Phase 5: Dashboard & Review

**5.1 Student Dashboard (`pages/student_dashboard.py`)**
- Show attempts used/remaining
- Resume button if exam in progress
- Start New Exam button if attempts available
- List of completed exams with scores
- Domain breakdown for each exam
- Review button for each completed exam

**5.2 Review Mode (`pages/review_mode.py`)**
- Navigate through all questions
- Show user's answer vs correct answer
- Green highlight for correct, red for incorrect
- Domain label for each question
- Back to Dashboard button

**Files to create:** `pages/student_dashboard.py`, `pages/review_mode.py`

---

### Phase 6: Admin Panel

**6.1 Admin Panel (`pages/admin_panel.py`)**
- **User Management Tab:**
  - List all students
  - Enable/disable toggle
  - Reset attempts button
  - Update max tries input
- **Question Bank Tab:**
  - Show total question count
  - CSV file uploader
  - Preview uploaded data
  - Append or Replace All options
  - Column validation for expected format

**Files to create:** `pages/admin_panel.py`, `utils/csv_parser.py`

---

### Phase 7: Main App Router

**7.1 Main App (`app.py`)**
- Page config (title, icon, layout)
- Authentication flow
- Route based on user role (admin vs student)
- Route student based on state (dashboard/exam/review)
- Logout handling

**Files to create:** `app.py`

---

### Phase 8: Deployment

**8.1 Streamlit Cloud Setup**
- Push to GitHub
- Connect repository to Streamlit Cloud
- Add secrets in Streamlit Cloud dashboard
- Update Firebase authorized domains
- Update OAuth redirect URIs

---

## Firestore Schema

```
/users/{uid}
  - uid: string
  - email: string
  - is_enabled: boolean (default: true)
  - max_tries: number (default: 3)
  - current_tries: number (default: 0)
  - role: "admin" | "student"

/question_bank/{q_id}
  - text: string
  - domain: string
  - choices: { a, b, c, d }
  - correct_choice: "a" | "b" | "c" | "d"

/exams/{exam_id}
  - exam_id: string
  - user_id: string
  - start_time: timestamp
  - end_time: timestamp | null
  - status: "in-progress" | "completed"
  - total_score: number
  - domain_scores: { domain_name: score }
  - answers: { q_id: selected_choice }
  - time_remaining: number (seconds)
  - question_order: [q_id, ...]
```

---

## Critical Files to Modify/Create

1. **`app.py`** - Main entry point, auth flow, routing
2. **`pages/exam_engine.py`** - Core exam UI, question display, navigation, timer integration
3. **`components/timer.py`** - Countdown timer with pause/resume
4. **`services/exam_service.py`** - Exam CRUD, pause/resume persistence
5. **`services/question_service.py`** - CSV parsing with column mapping for user's format

---

## Verification Plan

1. **Firebase Connection:** Run app, verify connection to Firestore
2. **Authentication:** Test Google login, verify user creation in Firestore
3. **CSV Upload:** Upload sample CSV, verify questions in Firestore
4. **Start Exam:** Create exam, verify randomized questions
5. **Answer Questions:** Select answers, verify saved to Firestore
6. **Pause/Resume:** Exit mid-exam, re-login, verify state restored with correct time
7. **Timer Expiry:** Let timer run out, verify auto-submit
8. **Submit Exam:** Complete exam, verify scores calculated correctly
9. **Review Mode:** Review completed exam, verify correct answers shown
10. **Admin Functions:** Toggle user access, reset attempts, upload new questions
