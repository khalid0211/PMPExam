import streamlit as st
from config import SessionKeys
from utils.scoring import calculate_scores


def _reset_practice_state():
    for key in [
        SessionKeys.PRACTICE_QUESTIONS,
        SessionKeys.PRACTICE_ANSWERS,
        SessionKeys.PRACTICE_CURRENT_INDEX,
        SessionKeys.PRACTICE_RESULT,
    ]:
        if key in st.session_state:
            del st.session_state[key]


def render_practice_mode():
    questions = st.session_state.get(SessionKeys.PRACTICE_QUESTIONS, [])
    if not questions:
        st.warning("No practice session found.")
        if st.button("Back to Dashboard"):
            st.session_state["student_view"] = "main"
            st.rerun()
        return

    if SessionKeys.PRACTICE_ANSWERS not in st.session_state:
        st.session_state[SessionKeys.PRACTICE_ANSWERS] = {}
    if SessionKeys.PRACTICE_CURRENT_INDEX not in st.session_state:
        st.session_state[SessionKeys.PRACTICE_CURRENT_INDEX] = 0

    answers = st.session_state[SessionKeys.PRACTICE_ANSWERS]
    curr_idx = st.session_state[SessionKeys.PRACTICE_CURRENT_INDEX]

    st.title("Practice Mode")
    st.caption("Unlimited practice rounds. Final result shows score only.")
    st.write(f"Question {curr_idx + 1} of {len(questions)}")

    if SessionKeys.PRACTICE_RESULT in st.session_state:
        result = st.session_state[SessionKeys.PRACTICE_RESULT]
        st.success(f"Practice Score: {result['score']} / {result['total']}")
        if st.button("Start New Practice Round", type="primary"):
            _reset_practice_state()
            st.session_state["student_view"] = "main"
            st.rerun()
        if st.button("Back to Dashboard"):
            st.session_state["student_view"] = "main"
            st.rerun()
        return

    question = questions[curr_idx]
    q_id = question["q_id"]

    st.markdown(
        """
        <style>
        .practice-question-text {
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
    st.markdown(
        f"<div class='practice-question-text'><strong>Question:</strong> {question['text']}</div>",
        unsafe_allow_html=True
    )
    st.caption(f"Domain: {question['domain']}")

    options = question["choices"]
    labels = {
        "a": f"A) {options['a']}",
        "b": f"B) {options['b']}",
        "c": f"C) {options['c']}",
        "d": f"D) {options['d']}",
    }
    current_ans = answers.get(q_id)
    index = list(labels.keys()).index(current_ans) if current_ans else None
    choice = st.radio(
        "Select your answer:",
        options=list(labels.keys()),
        format_func=lambda x: labels[x],
        index=index,
        key=f"practice_q_{q_id}",
    )
    answers[q_id] = choice

    st.divider()
    c1, c2, c3 = st.columns([1, 1, 1])
    with c1:
        if st.button("⬅️ Previous", disabled=curr_idx == 0):
            st.session_state[SessionKeys.PRACTICE_CURRENT_INDEX] -= 1
            st.rerun()
    with c2:
        if st.button("Next ➡️", disabled=curr_idx == len(questions) - 1):
            st.session_state[SessionKeys.PRACTICE_CURRENT_INDEX] += 1
            st.rerun()
    with c3:
        if st.button("Finish Practice", type="primary"):
            total_score, _ = calculate_scores(questions, answers)
            st.session_state[SessionKeys.PRACTICE_RESULT] = {
                "score": total_score,
                "total": len(questions),
            }
            st.rerun()
