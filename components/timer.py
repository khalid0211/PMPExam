import streamlit as st
from streamlit_autorefresh import st_autorefresh
from datetime import datetime, timezone
from config import SessionKeys, EXAM_DURATION_SECONDS

def init_timer(time_remaining: int = None):
    """Initialize or restore timer state."""
    if SessionKeys.TIME_REMAINING not in st.session_state:
        st.session_state[SessionKeys.TIME_REMAINING] = (
            time_remaining if time_remaining is not None else EXAM_DURATION_SECONDS
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

def render_timer(auto_refresh: bool = True) -> int:
    """Render countdown timer, return remaining seconds."""
    remaining = get_remaining_time()
    if auto_refresh:
        # Adaptive refresh reduces full-page reruns (and CPU/network churn)
        # while preserving second-level precision near the end.
        if remaining > 15 * 60:          # > 15 min
            refresh_interval_ms = 15000
        elif remaining > 5 * 60:         # 5-15 min
            refresh_interval_ms = 5000
        elif remaining > 60:             # 1-5 min
            refresh_interval_ms = 2000
        else:                            # last minute
            refresh_interval_ms = 1000

        st_autorefresh(interval=refresh_interval_ms, limit=None, key="exam_timer_refresh")

    hours = remaining // 3600
    minutes = (remaining % 3600) // 60
    seconds = remaining % 60

    # Color coding
    if remaining <= 300:      # Last 5 minutes
        color = "#FF4B4B"  # Red
    elif remaining <= 900:    # Last 15 minutes
        color = "#FFA500"  # Orange
    else:
        color = "#008000"  # Green

    st.markdown(f"""
        <div style="font-size: 1.5rem; font-weight: bold; color: {color};
                    text-align: center; padding: 10px;
                    border: 2px solid {color}; border-radius: 10px;
                    margin-bottom: 20px;">
            Time Remaining: {hours:02d}:{minutes:02d}:{seconds:02d}
        </div>
    """, unsafe_allow_html=True)

    return remaining

def is_time_expired() -> bool:
    return get_remaining_time() <= 0
