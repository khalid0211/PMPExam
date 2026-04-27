import streamlit as st
from firebase_config import get_db
from config import ADMIN_EMAIL, SessionKeys, UserRole

def _get_streamlit_user_info():
    """Support both legacy and current Streamlit auth APIs."""
    # Newer API
    user = getattr(st, "user", None)
    if user is not None:
        try:
            if user.is_logged_in:
                return {"is_logged_in": True, "email": user.email, "id": user.id}
        except AttributeError:
            pass

    # Legacy API
    exp_user = getattr(st, "experimental_user", None)
    if exp_user is not None:
        try:
            if exp_user.get("is_logged_in", False):
                return {"is_logged_in": True, "email": exp_user.email, "id": exp_user.id}
        except Exception:
            try:
                if getattr(exp_user, "is_logged_in", False):
                    return {"is_logged_in": True, "email": exp_user.email, "id": exp_user.id}
            except Exception:
                pass

    return {"is_logged_in": False}


def handle_login():
    """Handle Google OAuth login flow with local development support."""
    # check if running locally or on Streamlit Cloud
    is_local = st.secrets.get("app", {}).get("is_local", False)

    if is_local:
        st.sidebar.info("Running in Local Dev Mode")
        # Mock user for local testing
        mock_user = {
            "email": ADMIN_EMAIL,
            "id": "local_dev_user_123",
            "is_logged_in": True
        }
        user = get_or_create_user(mock_user["email"], mock_user["id"])
        st.session_state[SessionKeys.USER] = user
        return user

    # Production Streamlit Cloud Auth
    user_info = _get_streamlit_user_info()
    if not user_info.get("is_logged_in", False):
        st.title("PMP Exam Simulator")
        st.write("Please sign in to continue.")
        if st.button("Sign in with Google", type="primary"):
            try:
                st.login("google")
            except Exception as e:
                st.error("Login is only available on Streamlit Cloud. To test locally, set is_local = true in secrets.toml")
        return None

    user = get_or_create_user(user_info["email"], user_info["id"])

    if not user.get("is_enabled", False):
        st.error("Your account is disabled. Contact administrator.")
        if st.button("Logout"):
            st.logout()
        return None

    st.session_state[SessionKeys.USER] = user
    return user

def get_or_create_user(email: str, uid: str) -> dict:
    """Get existing user or create new one in Firestore."""
    db = get_db()
    if not db:
        return {}
        
    user_ref = db.collection("users").document(uid)
    user_doc = user_ref.get()

    if user_doc.exists:
        return user_doc.to_dict()

    # Create new user
    is_admin = email.lower() == ADMIN_EMAIL.lower()
    new_user = {
        "uid": uid,
        "email": email,
        # New students require admin approval before they can access exams.
        "is_enabled": is_admin,
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
