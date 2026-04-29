import streamlit as st
from streamlit_google_auth import Authenticate
from firebase_config import get_db
from config import ADMIN_EMAIL, SessionKeys, UserRole


def _get_authenticator():
    """Create and return the Google authenticator instance."""
    # Get credentials from secrets
    client_id = st.secrets["auth"]["client_id"]
    client_secret = st.secrets["auth"]["client_secret"]
    redirect_uri = st.secrets["auth"]["redirect_uri"].replace("/oauth2callback", "")
    cookie_secret = st.secrets["auth"]["cookie_secret"]

    # Build credentials dict for streamlit-google-auth
    credentials = {
        "web": {
            "client_id": client_id,
            "client_secret": client_secret,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": [redirect_uri]
        }
    }

    return Authenticate(
        secret_credentials_path=credentials,
        cookie_name="pmp_exam_auth",
        cookie_key=cookie_secret,
        redirect_uri=redirect_uri,
    )


def _normalize_user_payload(user: dict, email: str, uid: str) -> dict:
    """Backfill required fields for older/incomplete user records."""
    is_admin = email.lower() == ADMIN_EMAIL.lower()
    normalized = dict(user or {})
    normalized["uid"] = normalized.get("uid") or uid
    normalized["email"] = normalized.get("email") or email
    normalized["is_enabled"] = normalized.get("is_enabled", is_admin)
    normalized["max_tries"] = normalized.get("max_tries", 3)
    normalized["current_tries"] = normalized.get("current_tries", 0)
    normalized["role"] = normalized.get("role") or (UserRole.ADMIN if is_admin else UserRole.STUDENT)
    return normalized


def handle_login():
    """Handle Google OAuth login flow with local development support."""
    # Check if running locally
    is_local = st.secrets.get("app", {}).get("is_local", False)

    if is_local:
        st.sidebar.info("Running in Local Dev Mode")
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

    # Production: Use streamlit-google-auth
    try:
        authenticator = _get_authenticator()
        authenticator.check_authentification()
    except Exception as e:
        st.error(f"Authentication initialization failed: {e}")
        return None

    # Check if user is connected
    if st.session_state.get("connected", False):
        user_info = st.session_state.get("user_info", {})
        email = user_info.get("email")
        uid = user_info.get("id") or user_info.get("sub") or email
        name = user_info.get("name")
        picture = user_info.get("picture")

        if not email:
            st.error("Could not retrieve email from Google. Please try again.")
            if st.button("Retry Login"):
                authenticator.logout()
                st.rerun()
            return None

        try:
            user = get_or_create_user(email, uid)
        except Exception as e:
            st.error(f"Sign-in succeeded, but user profile initialization failed: {e}")
            return None

        if not user:
            st.error("Database connection could not be initialized. Please try again.")
            return None

        user["name"] = name or user.get("email", email).split("@")[0]
        user["picture"] = picture

        if not user.get("is_enabled", False):
            st.error("Your account is disabled. Contact administrator.")
            if st.button("Logout"):
                authenticator.logout()
                st.rerun()
            return None

        st.session_state[SessionKeys.USER] = user
        return user

    # Not logged in - show login UI
    st.title("PMP Exam Simulator")
    st.image("PMPExamBanner.jpg", width=800)
    st.write("Please sign in to continue.")

    try:
        authorization_url = authenticator.get_authorization_url()
        st.link_button("Sign in with Google", authorization_url, type="primary")
    except Exception as e:
        st.error(f"Could not generate login URL: {e}")
        st.caption("Please check your OAuth configuration in Streamlit Cloud secrets.")

    return None


def get_or_create_user(email: str, uid: str) -> dict:
    """Get existing user or create new one in Firestore."""
    db = get_db()
    if not db:
        return {}

    user_ref = db.collection("users").document(uid)
    user_doc = user_ref.get()

    if user_doc.exists:
        existing_user = user_doc.to_dict() or {}
        normalized = _normalize_user_payload(existing_user, email, uid)
        if normalized != existing_user:
            user_ref.set(normalized, merge=True)
        return normalized

    # Create new user
    new_user = _normalize_user_payload({}, email, uid)
    if new_user["role"] == UserRole.STUDENT:
        new_user["is_enabled"] = False
    user_ref.set(new_user)
    return new_user


def logout():
    """Clear session and logout."""
    try:
        authenticator = _get_authenticator()
        authenticator.logout()
    except Exception:
        pass

    for key in list(st.session_state.keys()):
        del st.session_state[key]
    st.rerun()
