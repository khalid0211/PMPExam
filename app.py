import streamlit as st
from auth import handle_login, logout
from config import SessionKeys, UserRole

# Page Configuration
st.set_page_config(
    page_title="PMP Exam Simulator",
    page_icon="🎓",
    layout="wide",
    initial_sidebar_state="expanded"
)

def _get_current_user():
    """Return cached user from session to avoid repeated auth/database calls."""
    cached_user = st.session_state.get(SessionKeys.USER)
    if cached_user:
        return cached_user
    return handle_login()

def main():
    # Authentication (cached user avoids repeated backend lookups on rerun)
    user = _get_current_user()
    if not user:
        return

    # Sidebar Navigation
    with st.sidebar:
        st.title(f"Welcome, {user['email'].split('@')[0]}")
        st.write(f"Role: {user['role'].capitalize()}")
        
        if st.button("Logout", key="logout_btn"):
            logout()
            st.rerun()
            
        st.divider()
        
        # Navigation logic
        if user['role'] == UserRole.ADMIN:
            page = st.radio("Navigation", ["Admin Panel", "Student Dashboard"])
        else:
            page = "Student Dashboard"

    # Routing
    if page == "Admin Panel":
        from pages.admin_panel import render_admin_panel
        render_admin_panel()
    elif page == "Student Dashboard":
        from pages.student_dashboard import render_student_dashboard
        render_student_dashboard()

if __name__ == "__main__":
    main()
