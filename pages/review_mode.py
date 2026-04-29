import streamlit as st
from services.exam_service import ExamService
from services.question_service import QuestionService
from services.settings_service import SettingsService
from config import SessionKeys
from utils.scoring import calculate_scores

def render_review_mode():
    exam_service = ExamService()
    question_service = QuestionService()
    settings_service = SettingsService()
    
    exam_id = st.session_state.get(SessionKeys.EXAM_ID)
    if not exam_id:
        st.session_state["student_view"] = "main"
        st.rerun()

    exam_data = exam_service.get_exam(exam_id)
    all_questions = question_service.get_all_questions()
    q_map = {q["q_id"]: q for q in all_questions}
    questions = [q_map[qid] for qid in exam_data["question_order"]]
    answers = exam_data.get("answers", {})
    review_settings = settings_service.get_review_settings()
    detailed_review_enabled = review_settings.get("detailed_review_enabled", False)
    can_view_detailed = detailed_review_enabled

    st.title("Exam Review")
    st.write(f"Score: {exam_data['total_score']} / {len(questions)}")
    
    if st.button("Back to Dashboard"):
        st.session_state["student_view"] = "main"
        st.rerun()

    st.divider()

    if not can_view_detailed:
        total = len(questions)
        correct = exam_data.get("total_score", 0)
        attempted = len(answers)
        incorrect = attempted - correct
        unattempted = total - attempted
        domain_scores = exam_data.get("domain_scores", {})

        # Backward compatibility: rebuild domain scores for older exam docs.
        if not domain_scores:
            _, domain_scores = calculate_scores(questions, answers)

        st.subheader("Domain Breakdown")
        if domain_scores:
            for domain, stats in domain_scores.items():
                domain_correct = stats.get("correct", 0)
                domain_total = stats.get("total", 0)
                st.write(f"- {domain}: {domain_correct} / {domain_total}")
        else:
            st.caption("Domain breakdown not available.")

        st.divider()
        st.subheader("Exam Total")

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Total Questions", total)
        c2.metric("Attempted", attempted)
        c3.metric("Correct", correct)
        c4.metric("Incorrect", max(incorrect, 0))
        st.caption(f"Unattempted: {max(unattempted, 0)}")
        st.info("Detailed review is disabled by administrator. Only summary results are visible.")
        return

    for i, question in enumerate(questions):
        q_id = question["q_id"]
        user_ans = answers.get(q_id)
        correct_ans = question["correct_choice"]
        
        is_correct = user_ans == correct_ans
        
        # Use a simpler header to avoid truncation confusion, show full text inside
        with st.expander(f"Question {i+1}: {'✅ Correct' if is_correct else '❌ Incorrect'}"):
            st.write(f"### Question: {question['text']}")
            st.caption(f"Domain: {question['domain']}")
            
            for key in ["a", "b", "c", "d"]:
                text = question["choices"].get(key, "")
                if key == correct_ans:
                    st.success(f"{key.upper()}: {text} (Correct Answer)")
                elif key == user_ans:
                    st.error(f"{key.upper()}: {text} (Your Answer)")
                else:
                    st.write(f"{key.upper()}: {text}")
            
            if not user_ans:
                st.warning("You did not answer this question.")
