import streamlit as st
import time
from services.exam_service import ExamService
from services.question_service import QuestionService
from components.timer import init_timer, render_timer, pause_timer, is_time_expired
from config import SessionKeys, ExamStatus
from utils.scoring import calculate_scores

# Less frequent autosave to prioritize responsive question navigation.
ANSWER_SAVE_INTERVAL_SECONDS = 60
ANSWER_SAVE_NAV_BATCH = 10
LAST_ANSWER_SAVE_TS = "_last_answer_save_ts"
NAV_CHANGES_SINCE_SAVE = "_nav_changes_since_save"
DIRTY_ANSWER_IDS = "_dirty_answer_ids"


def _save_pending_answers(exam_service, exam_id, answers, force=False):
    """Save answers to Firestore only when needed to keep navigation responsive."""
    if not st.session_state.get(SessionKeys.PENDING_SAVE, False):
        return

    now = time.time()
    last_save_ts = st.session_state.get(LAST_ANSWER_SAVE_TS, 0.0)
    nav_changes = st.session_state.get(NAV_CHANGES_SINCE_SAVE, 0)
    dirty_ids = st.session_state.get(DIRTY_ANSWER_IDS, set())
    should_save = force or nav_changes >= ANSWER_SAVE_NAV_BATCH or (now - last_save_ts) >= ANSWER_SAVE_INTERVAL_SECONDS

    if should_save:
        exam_service.save_answer_deltas(exam_id, answers, dirty_ids)
        st.session_state[SessionKeys.PENDING_SAVE] = False
        st.session_state[LAST_ANSWER_SAVE_TS] = now
        st.session_state[NAV_CHANGES_SINCE_SAVE] = 0
        st.session_state[DIRTY_ANSWER_IDS] = set()


def render_exam_engine():
    exam_service = ExamService()
    question_service = QuestionService()

    exam_id = st.session_state.get(SessionKeys.EXAM_ID)
    if not exam_id:
        st.error("No active exam found.")
        if st.button("Back to Dashboard"):
            st.session_state["student_view"] = "main"
            st.rerun()
        return

    # Load Exam Data - cache in session state to avoid repeated Firestore calls
    if SessionKeys.EXAM_DATA not in st.session_state:
        exam_data = exam_service.get_exam(exam_id)
        if not exam_data or exam_data["status"] == ExamStatus.COMPLETED:
            st.session_state["student_view"] = "main"
            st.rerun()
            return
        st.session_state[SessionKeys.EXAM_DATA] = exam_data

    exam_data = st.session_state[SessionKeys.EXAM_DATA]

    # Load Questions (if not in session) - fetch only needed questions
    if SessionKeys.QUESTIONS not in st.session_state:
        question_ids = exam_data["question_order"]
        questions = question_service.get_questions_by_ids(question_ids)
        # Order by question_order
        q_map = {q["q_id"]: q for q in questions}
        st.session_state[SessionKeys.QUESTIONS] = [q_map[qid] for qid in question_ids if qid in q_map]
        st.session_state[SessionKeys.ANSWERS] = exam_data.get("answers", {})
        st.session_state[SessionKeys.CURRENT_QUESTION_INDEX] = 0
        st.session_state[SessionKeys.MARKED_FOR_REVIEW] = set()
        st.session_state[SessionKeys.PENDING_SAVE] = False  # Track if answers need saving
        st.session_state[LAST_ANSWER_SAVE_TS] = time.time()
        st.session_state[NAV_CHANGES_SINCE_SAVE] = 0
        st.session_state[DIRTY_ANSWER_IDS] = set()
        # Clean up stale per-question widget keys from prior exam sessions.
        for key in list(st.session_state.keys()):
            if key.startswith("q_"):
                del st.session_state[key]

    questions = st.session_state[SessionKeys.QUESTIONS]
    answers = st.session_state[SessionKeys.ANSWERS]
    curr_idx = st.session_state[SessionKeys.CURRENT_QUESTION_INDEX]
    
    # Initialize Timer
    init_timer(exam_data.get("time_remaining"))

    # Header with Timer
    col1, col2 = st.columns([3, 1])
    with col1:
        st.title(f"PMP Exam")
        st.write(f"Question {curr_idx + 1} of {len(questions)}")
    with col2:
        remaining = render_timer()
        if is_time_expired():
            st.warning("Time expired! Submitting exam...")
            submit_exam(exam_service, exam_id, questions, answers)
            st.rerun()

    # Sidebar - Simple Info
    with st.sidebar:
        st.subheader("Exam Status")
        st.write(f"Answered: {len(answers)} / {len(questions)}")
        st.write(f"Marked for Review: {len(st.session_state[SessionKeys.MARKED_FOR_REVIEW])}")
        
        st.divider()
        if st.button("Save & Exit", use_container_width=True):
            _save_pending_answers(exam_service, exam_id, answers, force=True)
            remaining = pause_timer()
            exam_service.update_time_remaining(exam_id, remaining)
            # Clear local exam state
            for key in [SessionKeys.QUESTIONS, SessionKeys.ANSWERS, SessionKeys.CURRENT_QUESTION_INDEX,
                        SessionKeys.TIMER_START, SessionKeys.TIME_REMAINING, SessionKeys.EXAM_DATA, SessionKeys.PENDING_SAVE,
                        LAST_ANSWER_SAVE_TS, NAV_CHANGES_SINCE_SAVE, DIRTY_ANSWER_IDS]:
                if key in st.session_state: del st.session_state[key]
            st.session_state["student_view"] = "main"
            st.rerun()

    # Main Question UI (stable fallback: native Streamlit widgets)
    question = questions[curr_idx]
    q_id = question["q_id"]

    st.markdown(
        """
        <style>
        .question-text {
            font-size: 1.0rem;
            line-height: 1.45;
            white-space: pre-wrap;
            overflow-wrap: anywhere;
        }
        div[data-testid="stRadio"] label p {
            font-size: 0.93rem;
            line-height: 1.4;
            white-space: normal;
            overflow-wrap: anywhere;
        }
        </style>
        """,
        unsafe_allow_html=True
    )
    st.markdown(f"<div class='question-text'><strong>Question:</strong> {question['text']}</div>", unsafe_allow_html=True)
    st.caption(f"Domain: {question['domain']}")

    options = question["choices"]
    option_labels = {
        "a": f"A) {options['a']}",
        "b": f"B) {options['b']}",
        "c": f"C) {options['c']}",
        "d": f"D) {options['d']}"
    }

    current_ans = answers.get(q_id, None)
    index = list(option_labels.keys()).index(current_ans) if current_ans else None

    choice = st.radio(
        "Select your answer:",
        options=list(option_labels.keys()),
        format_func=lambda x: option_labels[x],
        index=index
    )

    if choice != current_ans:
        answers[q_id] = choice
        st.session_state[SessionKeys.PENDING_SAVE] = True
        st.session_state[DIRTY_ANSWER_IDS] = st.session_state.get(DIRTY_ANSWER_IDS, set())
        st.session_state[DIRTY_ANSWER_IDS].add(q_id)

    st.divider()
    b_col1, b_col2, b_col3, b_col4 = st.columns([1, 1, 1, 1])

    with b_col1:
        if st.button("⬅️ Previous", disabled=curr_idx == 0):
            st.session_state[NAV_CHANGES_SINCE_SAVE] = st.session_state.get(NAV_CHANGES_SINCE_SAVE, 0) + 1
            _save_pending_answers(exam_service, exam_id, answers)
            st.session_state[SessionKeys.CURRENT_QUESTION_INDEX] -= 1
            st.rerun()

    with b_col2:
        is_marked = q_id in st.session_state[SessionKeys.MARKED_FOR_REVIEW]
        if st.button("🚩 Unmark" if is_marked else "🚩 Mark for Review"):
            if is_marked:
                st.session_state[SessionKeys.MARKED_FOR_REVIEW].remove(q_id)
            else:
                st.session_state[SessionKeys.MARKED_FOR_REVIEW].add(q_id)
            st.rerun()

    with b_col3:
        if st.button("Next ➡️", disabled=curr_idx == len(questions) - 1):
            st.session_state[NAV_CHANGES_SINCE_SAVE] = st.session_state.get(NAV_CHANGES_SINCE_SAVE, 0) + 1
            _save_pending_answers(exam_service, exam_id, answers)
            st.session_state[SessionKeys.CURRENT_QUESTION_INDEX] += 1
            st.rerun()

    with b_col4:
        if st.button("Finish & Submit", type="primary"):
            st.session_state["show_submit_confirm"] = True

    if st.session_state.get("show_submit_confirm"):
        st.warning("Are you sure you want to submit? You cannot change your answers after this.")
        c1, c2 = st.columns(2)
        if c1.button("Yes, Submit Exam"):
            submit_exam(exam_service, exam_id, questions, answers)
            st.rerun()
        if c2.button("Cancel"):
            del st.session_state["show_submit_confirm"]
            st.rerun()

def submit_exam(exam_service, exam_id, questions, answers):
    _save_pending_answers(exam_service, exam_id, answers, force=True)
    total_score, domain_scores = calculate_scores(questions, answers)
    exam_service.complete_exam(exam_id, total_score, domain_scores, answers)
    # Clear local exam state
    for key in [SessionKeys.QUESTIONS, SessionKeys.ANSWERS, SessionKeys.CURRENT_QUESTION_INDEX,
                SessionKeys.TIMER_START, SessionKeys.TIME_REMAINING, SessionKeys.EXAM_DATA, SessionKeys.PENDING_SAVE,
                LAST_ANSWER_SAVE_TS, NAV_CHANGES_SINCE_SAVE, DIRTY_ANSWER_IDS]:
        if key in st.session_state: del st.session_state[key]
    st.session_state["student_view"] = "main"
    st.success("Exam submitted successfully!")
