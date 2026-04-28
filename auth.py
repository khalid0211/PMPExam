import streamlit as st
from firebase_config import get_db
from config import ADMIN_EMAIL, SessionKeys, UserRole

def _read_user_field(user_obj, field, default=None):
    """Read auth fields from both object-style and dict-style user payloads."""
    try:
        if isinstance(user_obj, dict):
            return user_obj.get(field, default)
    except Exception:
        pass
    try:
        return getattr(user_obj, field)
    except Exception:
        pass
    try:
        return user_obj[field]
    except Exception:
        return default


def _get_streamlit_user_info():
    """Support both legacy and current Streamlit auth APIs."""
    # Newer API
    user = getattr(st, "user", None)
    if user is not None:
        is_logged_in = bool(_read_user_field(user, "is_logged_in", False))
        if is_logged_in:
            email = _read_user_field(user, "email")
            # Different runtimes may expose id as "id" or "sub"
            uid = _read_user_field(user, "id") or _read_user_field(user, "sub")
            name = _read_user_field(user, "name") or _read_user_field(user, "given_name")
            picture = (
                _read_user_field(user, "picture")
                or _read_user_field(user, "picture_url")
                or _read_user_field(user, "avatar_url")
            )
            if email:
                return {
                    "is_logged_in": True,
                    "email": email,
                    "id": uid or email,
                    "name": name,
                    "picture": picture
                }

    # Legacy API
    exp_user = getattr(st, "experimental_user", None)
    if exp_user is not None:
        is_logged_in = bool(_read_user_field(exp_user, "is_logged_in", False))
        if is_logged_in:
            email = _read_user_field(exp_user, "email")
            uid = _read_user_field(exp_user, "id") or _read_user_field(exp_user, "sub")
            name = _read_user_field(exp_user, "name") or _read_user_field(exp_user, "given_name")
            picture = (
                _read_user_field(exp_user, "picture")
                or _read_user_field(exp_user, "picture_url")
                or _read_user_field(exp_user, "avatar_url")
            )
            if email:
                return {
                    "is_logged_in": True,
                    "email": email,
                    "id": uid or email,
                    "name": name,
                    "picture": picture
                }

    return {"is_logged_in": False}


def _trigger_streamlit_login():
    """Handle Streamlit login API differences across versions."""
    login_fn = getattr(st, "login", None)
    if login_fn is None:
        raise RuntimeError("Streamlit login API is unavailable in this runtime.")
    try:
        # Newer versions typically use parameterless login().
        login_fn()
    except TypeError:
        # Older experimental auth variant expects provider id.
        login_fn("google")


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
            "name": ADMIN_EMAIL.split("@")[0],
            "picture": None,
            "is_logged_in": True
        }
        user = get_or_create_user(mock_user["email"], mock_user["id"])
        user["name"] = mock_user["name"]
        user["picture"] = mock_user["picture"]
        st.session_state[SessionKeys.USER] = user
        return user

    # Production Streamlit Cloud Auth
    user_info = _get_streamlit_user_info()
    if not user_info.get("is_logged_in", False):
        st.title("PMP Exam Simulator")
        st.image("PMPExamBanner.jpg", use_container_width=True)
        st.write("Please sign in to continue.")
        if st.button("Sign in with Google", type="primary"):
            try:
                _trigger_streamlit_login()
            except Exception as e:
                st.error(
                    "Google login failed. Verify Streamlit Cloud authentication is enabled and app secrets are correct."
                )
                st.caption(f"Auth error details: {e}")
        return None

    user = get_or_create_user(user_info["email"], user_info["id"])
    user["name"] = user_info.get("name") or user["email"].split("@")[0]
    user["picture"] = user_info.get("picture")

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
