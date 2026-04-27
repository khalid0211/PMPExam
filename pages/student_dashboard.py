import streamlit as st
from services.exam_service import ExamService
from services.user_service import UserService
from services.question_service import QuestionService
from config import SessionKeys, ExamStatus

def render_student_dashboard():
    exam_service = ExamService()
    user_service = UserService()
    question_service = QuestionService()
    
    user = st.session_state[SessionKeys.USER]
    
    # Internal routing for Student Dashboard
    if "student_view" not in st.session_state:
        st.session_state["student_view"] = "main"

    if st.session_state["student_view"] == "exam":
        from pages.exam_engine import render_exam_engine
        render_exam_engine()
        return

    if st.session_state["student_view"] == "review":
        from pages.review_mode import render_review_mode
        render_review_mode()
        return

    if st.session_state["student_view"] == "practice":
        from pages.practice_mode import render_practice_mode
        render_practice_mode()
        return

    # Main Dashboard UI
    st.title("Student Dashboard")
    
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.subheader("Your Progress")
        exams = exam_service.get_user_exams(user["uid"])
        
        if not exams:
            st.info("You haven't taken any exams yet.")
        else:
            for exam in exams:
                with st.expander(f"Exam {exam['exam_id'][:8]} - {exam['status'].capitalize()} ({exam.get('start_time').strftime('%Y-%m-%d %H:%M')})"):
                    st.write(f"Status: {exam['status']}")
                    if exam['status'] == ExamStatus.COMPLETED:
                        st.write(f"Score: {exam['total_score']} / {len(exam['question_order'])}")
                        if st.button("Review Results", key=f"rev_{exam['exam_id']}"):
                            st.session_state[SessionKeys.EXAM_ID] = exam['exam_id']
                            st.session_state["student_view"] = "review"
                            st.rerun()
                    else:
                        if st.button("Resume Exam", key=f"res_{exam['exam_id']}"):
                            st.session_state[SessionKeys.EXAM_ID] = exam['exam_id']
                            st.session_state["student_view"] = "exam"
                            st.rerun()

    with col2:
        st.subheader("Start New Exam")
        tries_left = user["max_tries"] - user["current_tries"]
        st.metric("Attempts Remaining", tries_left)
        
        # Check if there's an in-progress exam
        in_progress = exam_service.get_in_progress_exam(user["uid"])
        
        if in_progress:
            st.warning("You have an exam in progress.")
            if st.button("Resume Current Exam", type="primary"):
                # Clear old session state to force fresh load from Firestore
                for key in [SessionKeys.TIMER_START, SessionKeys.TIME_REMAINING, SessionKeys.QUESTIONS, SessionKeys.ANSWERS, SessionKeys.CURRENT_QUESTION_INDEX]:
                    if key in st.session_state: del st.session_state[key]
                st.session_state[SessionKeys.EXAM_ID] = in_progress["exam_id"]
                st.session_state["student_view"] = "exam"
                st.rerun()
        elif tries_left > 0:
            if st.button("Start New Exam", type="primary"):
                with st.spinner("Preparing questions..."):
                    # Clear old session state
                    for key in [SessionKeys.TIMER_START, SessionKeys.TIME_REMAINING, SessionKeys.QUESTIONS, SessionKeys.ANSWERS, SessionKeys.CURRENT_QUESTION_INDEX]:
                        if key in st.session_state: del st.session_state[key]
                        
                    questions = question_service.get_randomized_questions()
                    if not questions:
                        st.error("Question bank is empty. Please contact admin.")
                    else:
                        exam_id = exam_service.create_exam(user["uid"], questions)
                        user_service.increment_tries(user["uid"])
                        # Update local user state
                        st.session_state[SessionKeys.USER]["current_tries"] += 1
                        
                        st.session_state[SessionKeys.EXAM_ID] = exam_id
                        st.session_state["student_view"] = "exam"
                        st.rerun()
        else:
            st.error("No attempts remaining.")

        st.divider()
        st.subheader("Practice Mode")
        st.caption("Choose 10 to 30 random questions. Unlimited rounds. Score-only result.")
        practice_count = st.slider("Number of practice questions", min_value=10, max_value=30, value=10, step=1)
        if st.button("Start Practice Round"):
            all_questions = question_service.get_randomized_questions()
            if not all_questions:
                st.error("Question bank is empty. Please contact admin.")
            else:
                selected = all_questions[:min(practice_count, len(all_questions))]
                # Clear stale practice state
                for key in [
                    SessionKeys.PRACTICE_QUESTIONS,
                    SessionKeys.PRACTICE_ANSWERS,
                    SessionKeys.PRACTICE_CURRENT_INDEX,
                    SessionKeys.PRACTICE_RESULT,
                ]:
                    if key in st.session_state:
                        del st.session_state[key]
                st.session_state[SessionKeys.PRACTICE_QUESTIONS] = selected
                st.session_state[SessionKeys.PRACTICE_ANSWERS] = {}
                st.session_state[SessionKeys.PRACTICE_CURRENT_INDEX] = 0
                st.session_state["student_view"] = "practice"
                st.rerun()
