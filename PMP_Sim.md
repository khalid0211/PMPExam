# PMP MCQ Exam Simulator - Implementation Plan

## Overview
A Streamlit-based exam simulator with Firebase backend for conducting PMP-style multiple choice question exams.

## Requirements Summary
| Feature | Specification |
|---------|---------------|
| Tech Stack | Streamlit + Firebase (Firestore + Auth) + Pandas |
| Exam Length | All questions from question bank, randomized order |
| Time Limit | 4 hours (230 minutes) with visible countdown timer |
| Pause/Resume | Yes, timer pauses when student exits |
| Scoring | Simple (1 point per correct, no negative marking) |
| Results | Full review with correct answers shown |
| Admin Setup | Hardcoded email in config |
| Deployment | Streamlit Cloud |

## CSV Input Format
```csv
SNo.,Domain,Question,Option A,Option B,Option C,Option D,Correct Answer
1,People,A team member is consistently late...,Reprimand them...,Meet with them privately...,Ignore it...,Ask the Product Owner...,B
2,People,Two senior stakeholders have conflicting...,Choose the requirement...,Escalate to the Sponsor,Facilitate a meeting...,Submit both to CCB,C
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
│   ├── __init__.py
│   ├── login.py              # Login page
│   ├── student_dashboard.py  # Student home with exam history
│   ├── exam_engine.py        # Core exam taking interface
│   ├── review_mode.py        # Post-exam review
│   └── admin_panel.py        # User management, CSV upload
├── components/
│   ├── __init__.py
│   ├── timer.py              # Countdown timer with pause/resume
│   ├── question_card.py      # Question display component
│   └── sidebar_nav.py        # Question navigation grid
├── services/
│   ├── __init__.py
│   ├── user_service.py       # User CRUD
│   ├── question_service.py   # Question bank operations
│   └── exam_service.py       # Exam session management
├── utils/
│   ├── __init__.py
│   ├── csv_parser.py         # CSV upload processing
│   └── scoring.py            # Score calculation
└── data/
    └── sample_questions.csv  # Sample data for testing
```

---

## Implementation Phases

### Phase 1: Setup (Firebase + Project Scaffolding)

#### 1.1 Firebase Console Setup
1. Create Firebase project at https://console.firebase.google.com
2. Enable Authentication > Sign-in method > Google
3. Create Firestore Database (production mode)
4. Generate service account key (Project Settings > Service Accounts > Generate new private key)
5. Configure OAuth in Google Cloud Console (add redirect URIs)

#### 1.2 Project Files

**requirements.txt:**
```
streamlit>=1.28.0
firebase-admin>=6.2.0
google-cloud-firestore>=2.13.0
pandas>=2.0.0
streamlit-autorefresh>=1.0.1
```

**config.py:**
```python
import streamlit as st

# App Constants
EXAM_DURATION_MINUTES = 230  # 4 hours PMP style
EXAM_DURATION_SECONDS = EXAM_DURATION_MINUTES * 60
ADMIN_EMAIL = st.secrets.get("app", {}).get("admin_email", "")

# Session State Keys
class SessionKeys:
    USER = "user"
    EXAM_ID = "exam_id"
    QUESTIONS = "questions"
    ANSWERS = "answers"
    CURRENT_QUESTION_INDEX = "current_question_index"
    MARKED_FOR_REVIEW = "marked_for_review"
    TIMER_START = "timer_start"
    TIME_REMAINING = "time_remaining"

# Status Constants
class ExamStatus:
    IN_PROGRESS = "in-progress"
    COMPLETED = "completed"

class UserRole:
    ADMIN = "admin"
    STUDENT = "student"
```

**.streamlit/secrets.toml (template):**
```toml
[firebase]
type = "service_account"
project_id = "your-project-id"
private_key_id = "..."
private_key = "-----BEGIN PRIVATE KEY-----\n...\n-----END PRIVATE KEY-----\n"
client_email = "firebase-adminsdk-xxx@your-project.iam.gserviceaccount.com"
client_id = "..."
auth_uri = "https://accounts.google.com/o/oauth2/auth"
token_uri = "https://oauth2.googleapis.com/token"
auth_provider_x509_cert_url = "https://www.googleapis.com/oauth2/v1/certs"
client_x509_cert_url = "..."

[app]
admin_email = "your-admin@email.com"
exam_duration_minutes = 230
```

---

### Phase 2: Authentication

**firebase_config.py:**
```python
import streamlit as st
import firebase_admin
from firebase_admin import credentials, firestore

@st.cache_resource
def get_db():
    """Initialize Firebase and return Firestore client."""
    if not firebase_admin._apps:
        cred_dict = dict(st.secrets["firebase"])
        cred = credentials.Certificate(cred_dict)
        firebase_admin.initialize_app(cred)
    return firestore.client()
```

**auth.py:**
```python
import streamlit as st
from firebase_config import get_db
from config import ADMIN_EMAIL, SessionKeys, UserRole

def handle_login():
    """Handle Google OAuth login flow."""
    if not st.experimental_user.is_logged_in:
        if st.button("Sign in with Google", type="primary"):
            st.login("google")
        return None

    user_info = st.experimental_user
    user = get_or_create_user(user_info.email, user_info.id)

    if not user.get("is_enabled", False):
        st.error("Your account is disabled. Contact administrator.")
        if st.button("Logout"):
            st.logout()
        return None

    st.session_state[SessionKeys.USER] = user
    return user

def get_or_create_user(email: str, uid: str) -> dict:
    """Get existing user or create new one."""
    db = get_db()
    user_ref = db.collection("users").document(uid)
    user_doc = user_ref.get()

    if user_doc.exists:
        return user_doc.to_dict()

    # Create new user
    is_admin = email == ADMIN_EMAIL
    new_user = {
        "uid": uid,
        "email": email,
        "is_enabled": True,
        "max_tries": 3,
        "current_tries": 0,
        "role": UserRole.ADMIN if is_admin else UserRole.STUDENT
    }
    user_ref.set(new_user)
    return new_user

def logout():
    """Clear session and logout."""
    for key in list(st.session_state.keys()):
        del st.session_state[key]
    st.logout()
```

---

### Phase 3: Services Layer

**services/user_service.py:**
```python
from firebase_config import get_db
from config import UserRole

class UserService:
    def __init__(self):
        self.db = get_db()
        self.collection = self.db.collection("users")

    def get_all_students(self) -> list:
        docs = self.collection.where("role", "==", UserRole.STUDENT).stream()
        return [doc.to_dict() for doc in docs]

    def toggle_user_access(self, uid: str, enabled: bool):
        self.collection.document(uid).update({"is_enabled": enabled})

    def reset_attempts(self, uid: str):
        self.collection.document(uid).update({"current_tries": 0})

    def increment_tries(self, uid: str):
        from google.cloud.firestore_v1 import Increment
        self.collection.document(uid).update({"current_tries": Increment(1)})
```

**services/question_service.py:**
```python
import pandas as pd
import random
from firebase_config import get_db

class QuestionService:
    def __init__(self):
        self.db = get_db()
        self.collection = self.db.collection("question_bank")

    def get_all_questions(self) -> list:
        docs = self.collection.stream()
        return [{"q_id": doc.id, **doc.to_dict()} for doc in docs]

    def get_randomized_questions(self) -> list:
        questions = self.get_all_questions()
        random.shuffle(questions)
        return questions

    def upload_from_csv(self, df: pd.DataFrame) -> tuple[int, int]:
        """Upload questions from user's CSV format."""
        success, errors = 0, 0
        batch = self.db.batch()

        for idx, row in df.iterrows():
            try:
                q_id = f"q_{row['SNo.']}"
                doc_ref = self.collection.document(q_id)

                question_data = {
                    "text": row["Question"],
                    "domain": row["Domain"],
                    "choices": {
                        "a": row["Option A"],
                        "b": row["Option B"],
                        "c": row["Option C"],
                        "d": row["Option D"]
                    },
                    "correct_choice": row["Correct Answer"].lower()
                }
                batch.set(doc_ref, question_data)
                success += 1
            except Exception:
                errors += 1

        batch.commit()
        return success, errors

    def clear_all_questions(self):
        docs = self.collection.stream()
        batch = self.db.batch()
        for doc in docs:
            batch.delete(doc.reference)
        batch.commit()
```

**services/exam_service.py:**
```python
from datetime import datetime, timezone
from firebase_config import get_db
from config import ExamStatus, EXAM_DURATION_SECONDS
import uuid

class ExamService:
    def __init__(self):
        self.db = get_db()
        self.collection = self.db.collection("exams")

    def create_exam(self, user_id: str, questions: list) -> str:
        exam_id = str(uuid.uuid4())
        question_ids = [q["q_id"] for q in questions]

        exam_data = {
            "exam_id": exam_id,
            "user_id": user_id,
            "start_time": datetime.now(timezone.utc),
            "end_time": None,
            "status": ExamStatus.IN_PROGRESS,
            "total_score": 0,
            "domain_scores": {},
            "answers": {},
            "time_remaining": EXAM_DURATION_SECONDS,
            "question_order": question_ids
        }

        self.collection.document(exam_id).set(exam_data)
        return exam_id

    def get_in_progress_exam(self, user_id: str) -> dict:
        docs = (self.collection
                .where("user_id", "==", user_id)
                .where("status", "==", ExamStatus.IN_PROGRESS)
                .limit(1)
                .stream())
        for doc in docs:
            return doc.to_dict()
        return None

    def save_answer(self, exam_id: str, question_id: str, answer: str):
        self.collection.document(exam_id).update({
            f"answers.{question_id}": answer
        })

    def update_time_remaining(self, exam_id: str, time_remaining: int):
        self.collection.document(exam_id).update({
            "time_remaining": time_remaining
        })

    def complete_exam(self, exam_id: str, total_score: int,
                      domain_scores: dict, answers: dict):
        self.collection.document(exam_id).update({
            "status": ExamStatus.COMPLETED,
            "end_time": datetime.now(timezone.utc),
            "total_score": total_score,
            "domain_scores": domain_scores,
            "answers": answers
        })

    def get_user_exams(self, user_id: str) -> list:
        docs = self.collection.where("user_id", "==", user_id).stream()
        exams = [doc.to_dict() for doc in docs]
        return sorted(exams, key=lambda x: x.get("start_time", 0), reverse=True)
```

---

### Phase 4: Timer Component

**components/timer.py:**
```python
import streamlit as st
from streamlit_autorefresh import st_autorefresh
from datetime import datetime, timezone
from config import SessionKeys, EXAM_DURATION_SECONDS

def init_timer(time_remaining: int = None):
    """Initialize or restore timer state."""
    if SessionKeys.TIME_REMAINING not in st.session_state:
        st.session_state[SessionKeys.TIME_REMAINING] = (
            time_remaining if time_remaining else EXAM_DURATION_SECONDS
        )
    if SessionKeys.TIMER_START not in st.session_state:
        st.session_state[SessionKeys.TIMER_START] = datetime.now(timezone.utc)

def get_remaining_time() -> int:
    """Calculate current remaining time in seconds."""
    if SessionKeys.TIMER_START not in st.session_state:
        return st.session_state.get(SessionKeys.TIME_REMAINING, EXAM_DURATION_SECONDS)

    initial_remaining = st.session_state[SessionKeys.TIME_REMAINING]
    start_time = st.session_state[SessionKeys.TIMER_START]
    elapsed = (datetime.now(timezone.utc) - start_time).total_seconds()

    return max(0, int(initial_remaining - elapsed))

def pause_timer() -> int:
    """Pause timer and return remaining time for storage."""
    remaining = get_remaining_time()
    st.session_state[SessionKeys.TIME_REMAINING] = remaining
    if SessionKeys.TIMER_START in st.session_state:
        del st.session_state[SessionKeys.TIMER_START]
    return remaining

def resume_timer(stored_time: int):
    """Resume timer from stored remaining time."""
    st.session_state[SessionKeys.TIME_REMAINING] = stored_time
    st.session_state[SessionKeys.TIMER_START] = datetime.now(timezone.utc)

def render_timer() -> int:
    """Render countdown timer, return remaining seconds."""
    st_autorefresh(interval=1000, limit=None, key="exam_timer_refresh")

    remaining = get_remaining_time()
    hours = remaining // 3600
    minutes = (remaining % 3600) // 60
    seconds = remaining % 60

    # Color coding
    if remaining <= 300:      # Last 5 minutes
        color = "red"
    elif remaining <= 900:    # Last 15 minutes
        color = "orange"
    else:
        color = "green"

    st.markdown(f"""
        <div style="font-size: 2rem; font-weight: bold; color: {color};
                    text-align: center; padding: 10px;
                    border: 2px solid {color}; border-radius: 10px;">
            {hours:02d}:{minutes:02d}:{seconds:02d}
        </div>
    """, unsafe_allow_html=True)

    return remaining

def is_time_expired() -> bool:
    return get_remaining_time() <= 0
```

---

### Phase 5: Scoring Utility

**utils/scoring.py:**
```python
def calculate_scores(questions: list, answers: dict) -> tuple[int, dict]:
    """Calculate total and domain-wise scores."""
    total_score = 0
    domain_scores = {}

    for question in questions:
        q_id = question["q_id"]
        domain = question["domain"]
        correct = question["correct_choice"]
        user_answer = answers.get(q_id)

        if domain not in domain_scores:
            domain_scores[domain] = 0

        if user_answer and user_answer.lower() == correct.lower():
            total_score += 1
            domain_scores[domain] += 1

    return total_score, domain_scores
```

---

## Firestore Schema

### Users Collection (`/users/{uid}`)
| Field | Type | Description |
|-------|------|-------------|
| uid | string | Unique ID from Google Auth |
| email | string | User's email |
| is_enabled | boolean | Admin-controlled access toggle |
| max_tries | number | Maximum allowed exam attempts (default: 3) |
| current_tries | number | Attempts used |
| role | string | "admin" or "student" |

### Question Bank Collection (`/question_bank/{q_id}`)
| Field | Type | Description |
|-------|------|-------------|
| text | string | Question text |
| domain | string | Category (People, Process, Business Environment) |
| choices | map | {a, b, c, d} with option text |
| correct_choice | string | "a", "b", "c", or "d" |

### Exams Collection (`/exams/{exam_id}`)
| Field | Type | Description |
|-------|------|-------------|
| exam_id | string | Unique exam ID |
| user_id | string | Reference to user |
| start_time | timestamp | When exam started |
| end_time | timestamp/null | When exam completed |
| status | string | "in-progress" or "completed" |
| total_score | number | Final score |
| domain_scores | map | {domain_name: score} |
| answers | map | {q_id: selected_choice} |
| time_remaining | number | Seconds remaining (for pause/resume) |
| question_order | array | [q_id, ...] preserving randomized order |

---

## Critical Files Summary

| File | Purpose |
|------|---------|
| `app.py` | Main entry point, auth flow, routing |
| `pages/exam_engine.py` | Core exam UI, question display, navigation, timer |
| `components/timer.py` | Countdown timer with pause/resume |
| `services/exam_service.py` | Exam CRUD, pause/resume persistence |
| `services/question_service.py` | CSV parsing with column mapping |

---

## Verification Checklist

- [ ] Firebase Connection: Run app, verify Firestore connection
- [ ] Authentication: Test Google login, verify user in Firestore
- [ ] CSV Upload: Upload questions, verify in Firestore
- [ ] Start Exam: Create exam, verify randomized questions
- [ ] Answer Questions: Select answers, verify saved
- [ ] Pause/Resume: Exit mid-exam, re-login, verify state + time restored
- [ ] Timer Expiry: Let timer run out, verify auto-submit
- [ ] Submit Exam: Complete exam, verify scores
- [ ] Review Mode: Review completed exam, verify answers shown
- [ ] Admin Functions: Toggle access, reset attempts, upload questions

---

## Deployment Checklist (Streamlit Cloud)

1. Push code to GitHub repository
2. Connect repo to Streamlit Cloud
3. Add secrets in Streamlit Cloud dashboard
4. Update Firebase authorized domains with Streamlit URL
5. Update Google OAuth redirect URIs
6. Test end-to-end in production
