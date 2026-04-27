import streamlit as st

# App Constants
EXAM_DURATION_MINUTES = 230  # 4 hours PMP style
EXAM_DURATION_SECONDS = EXAM_DURATION_MINUTES * 60

# Safe secrets access
def _get_secret(section: str, key: str, default=None):
    try:
        return st.secrets[section][key]
    except (KeyError, FileNotFoundError):
        return default

ADMIN_EMAIL = _get_secret("app", "admin_email", "president@pmilhr.org.pk")
LOCAL_TEST_MODE = _get_secret("app", "is_local", False)

# Session State Keys
class SessionKeys:
    USER = "user"
    EXAM_ID = "exam_id"
    EXAM_DATA = "exam_data"
    QUESTIONS = "questions"
    ANSWERS = "answers"
    CURRENT_QUESTION_INDEX = "current_question_index"
    MARKED_FOR_REVIEW = "marked_for_review"
    TIMER_START = "timer_start"
    TIME_REMAINING = "time_remaining"
    PENDING_SAVE = "pending_save"
    PRACTICE_QUESTIONS = "practice_questions"
    PRACTICE_ANSWERS = "practice_answers"
    PRACTICE_CURRENT_INDEX = "practice_current_index"
    PRACTICE_RESULT = "practice_result"

# Status Constants
class ExamStatus:
    IN_PROGRESS = "in-progress"
    COMPLETED = "completed"

class UserRole:
    ADMIN = "admin"
    STUDENT = "student"
