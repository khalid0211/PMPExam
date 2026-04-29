import streamlit as st
import traceback
from auth import handle_login, logout
from config import SessionKeys, UserRole

# Page Configuration
st.set_page_config(
    page_title="PMP Exam Simulator",
    page_icon="🎓",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Hide Streamlit's default multipage list. Navigation is role-based inside this app.
st.markdown(
    """
    <style>
    [data-testid="stSidebarNav"] {
        display: none;
    }
    </style>
    """,
    unsafe_allow_html=True
)

def _get_current_user():
    """Return cached user from session to avoid repeated auth/database calls."""
    cached_user = st.session_state.get(SessionKeys.USER)
    if cached_user:
        return cached_user
    return handle_login()

def main():
    try:
        # Authentication (cached user avoids repeated backend lookups on rerun)
        user = _get_current_user()
        if not user:
            return

        # Sidebar Navigation
        with st.sidebar:
            email = user.get("email", "")
            display_name = user.get("name") or (email.split("@")[0] if email else "User")
            display_role = user.get("role", UserRole.STUDENT).capitalize()
            if user.get("picture"):
                st.image(user["picture"], width=88)
            st.title(display_name)
            if email:
                st.caption(email)
            st.write(f"Role: {display_role}")
            
            if st.button("Logout", key="logout_btn"):
                logout()  # logout() already calls st.rerun()
                
            st.divider()
            
            # Navigation logic
            if user.get("role", UserRole.STUDENT) == UserRole.ADMIN:
                page = st.radio("Navigation", ["Admin Panel", "Student Dashboard"], key="main_nav")
            else:
                st.subheader("Student Dashboard")
                page = "Student Dashboard"

        # Routing
        if page == "Admin Panel":
            from pages.admin_panel import render_admin_panel
            render_admin_panel()
        elif page == "Student Dashboard":
            from pages.student_dashboard import render_student_dashboard
            render_student_dashboard()
    except Exception as e:
        st.error("Application crashed after login.")
        st.caption(f"Error: {e}")
        st.code(traceback.format_exc())

if __name__ == "__main__":
    main()
