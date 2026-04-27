import os
import streamlit.components.v1 as components


_FRONTEND_DIR = os.path.join(os.path.dirname(__file__), "question_navigator_frontend")
_question_navigator = components.declare_component("question_navigator", path=_FRONTEND_DIR)


def render_question_navigator(questions, answers, current_index, remaining_seconds, sync_every=10, key="question_nav"):
    """Render browser-side question navigation component."""
    return _question_navigator(
        questions=questions,
        answers=answers,
        current_index=current_index,
        remaining_seconds=remaining_seconds,
        sync_every=sync_every,
        key=key,
        default=None,
    )
