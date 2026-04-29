import os
import streamlit as st
import requests
from google_auth_oauthlib.flow import Flow
from firebase_config import get_db
from config import ADMIN_EMAIL, SessionKeys, UserRole

SCOPES = [
    "openid",
    "https://www.googleapis.com/auth/userinfo.email",
    "https://www.googleapis.com/auth/userinfo.profile",
]


def _build_flow() -> Flow:
    client_id = st.secrets["google_oauth"]["client_id"]
    client_secret = st.secrets["google_oauth"]["client_secret"]
    redirect_uri = st.secrets["google_oauth"]["redirect_uri"]

    # Allow plain HTTP for local development
    if redirect_uri.startswith("http://"):
        os.environ["OAUTHLIB_INSECURE_TRANSPORT"] = "1"

    client_config = {
        "web": {
            "client_id": client_id,
            "client_secret": client_secret,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": [redirect_uri],
        }
    }

    return Flow.from_client_config(client_config, scopes=SCOPES, redirect_uri=redirect_uri)


def _get_authorization_url() -> str:
    flow = _build_flow()
    auth_url, state = flow.authorization_url(
        access_type="offline",
        include_granted_scopes="true",
        prompt="select_account",
    )
    st.session_state["oauth_state"] = state
    return auth_url


def _handle_oauth_callback() -> dict | None:
    """Exchange the ?code= from Google's redirect into user info. Returns None if no callback."""
    code = st.query_params.get("code")
    if not code:
        return None

    state = st.query_params.get("state")
    saved_state = st.session_state.get("oauth_state")
    if saved_state and state != saved_state:
        st.error("OAuth state mismatch. Please try signing in again.")
        st.query_params.clear()
        return None

    try:
        flow = _build_flow()
        flow.fetch_token(code=code)
        token = flow.credentials.token

        resp = requests.get(
            "https://www.googleapis.com/oauth2/v3/userinfo",
            headers={"Authorization": f"Bearer {token}"},
            timeout=10,
        )
        resp.raise_for_status()
        user_info = resp.json()
    except Exception as e:
        st.error(f"OAuth callback failed: {e}")
        st.query_params.clear()
        return None

    st.query_params.clear()
    return user_info


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
    is_local = st.secrets.get("app", {}).get("is_local", False)

    if is_local:
        st.sidebar.info("Running in Local Dev Mode")
        mock_user = {
            "email": ADMIN_EMAIL,
            "id": "local_dev_user_123",
            "name": ADMIN_EMAIL.split("@")[0],
            "picture": None,
            "is_logged_in": True,
        }
        user = get_or_create_user(mock_user["email"], mock_user["id"])
        user["name"] = mock_user["name"]
        user["picture"] = mock_user["picture"]
        st.session_state[SessionKeys.USER] = user
        return user

    # Handle OAuth callback if Google just redirected back with ?code=
    user_info = _handle_oauth_callback()
    if user_info:
        email = user_info.get("email")
        uid = user_info.get("sub") or email
        name = user_info.get("name")
        picture = user_info.get("picture")

        if not email:
            st.error("Could not retrieve email from Google. Please try again.")
            return None

        try:
            user = get_or_create_user(email, uid)
        except Exception as e:
            st.error(f"Sign-in succeeded, but user profile initialization failed: {e}")
            return None

        if not user:
            st.error("Database connection could not be initialized. Please try again.")
            return None

        user["name"] = name or email.split("@")[0]
        user["picture"] = picture

        if not user.get("is_enabled", False):
            st.error("Your account is disabled. Contact administrator.")
            if st.button("Logout"):
                st.session_state.clear()
                st.rerun()
            return None

        st.session_state[SessionKeys.USER] = user
        st.rerun()
        return user

    # Already logged in from a previous rerun
    if st.session_state.get(SessionKeys.USER):
        return st.session_state[SessionKeys.USER]

    # Not logged in — show login UI
    st.title("PMP Exam Simulator")
    st.image("PMPExamBanner.jpg", width=800)
    st.write("Please sign in to continue.")

    try:
        authorization_url = _get_authorization_url()
        st.link_button("Sign in with Google", authorization_url, type="primary")
    except Exception as e:
        st.error(f"Could not generate login URL: {e}")
        st.caption("Please check your OAuth configuration in secrets.")

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

    new_user = _normalize_user_payload({}, email, uid)
    if new_user["role"] == UserRole.STUDENT:
        new_user["is_enabled"] = False
    user_ref.set(new_user)
    return new_user


def logout():
    """Clear session and return to login screen."""
    for key in list(st.session_state.keys()):
        del st.session_state[key]
    st.rerun()
